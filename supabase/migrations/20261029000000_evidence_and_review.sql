-- ReadyBid SA: company evidence library, evidence matching and human review.
--
-- Apply after 20261028000000_initial_schema.sql.
--
-- Design
-- * Evidence documents are organisation-owned `documents` rows with document_type 'evidence'
--   and no tender. They use the same validation, private storage, per-page extraction and
--   immutable-version rules as tender documents. Each evidence upload is its own document
--   (version 1).
-- * An analysis run only uses the evidence documents explicitly selected for it
--   (analysis_evidence_documents, pinned to the document's sha256). Evidence citations have
--   a foreign key to that selection, so a stored citation cannot point at an unselected
--   document, another organisation's document, another version or another page.
-- * AI assessments (evidence_matches.ai_status) and human decisions (review_decisions) are
--   stored separately. "human_reviewed" is shown by the API when a decision exists; it is
--   never written into ai_status, so the AI assessment is preserved.
-- * Review decisions are append-only and belong to one run's requirements. Requirement ids
--   are deterministic per run, so a new analysis creates new requirements with no decisions
--   and never overwrites earlier ones.
-- * As before, members may only READ. All writes go through the API with the service role.

-- Documents: allow organisation-level evidence ---------------------------------------
alter table public.documents drop constraint documents_document_type_check;
alter table public.documents
  add constraint documents_document_type_check check (document_type in ('tender', 'evidence'));

alter table public.documents alter column tender_id drop not null;

-- The uploader's own label for an evidence document. A label, not a verified fact.
alter table public.documents
  add column evidence_label text check (
    evidence_label in (
      'reference_letter',
      'company_profile',
      'staff_certificate',
      'declaration',
      'tax_status',
      'other'
    )
  );

alter table public.documents
  add constraint documents_type_shape_check check (
    (document_type = 'tender' and tender_id is not null and evidence_label is null)
    or (
      document_type = 'evidence'
      and tender_id is null
      and evidence_label is not null
      and version = 1
    )
  );

alter table public.documents
  add constraint documents_id_org_sha_type_key unique (id, organisation_id, sha256, document_type);

create index documents_evidence_idx on public.documents (organisation_id, created_at desc)
  where document_type = 'evidence';

create or replace function public.prevent_document_identity_change()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.id is distinct from old.id
    or new.organisation_id is distinct from old.organisation_id
    or new.tender_id is distinct from old.tender_id
    or new.document_type is distinct from old.document_type
    or new.evidence_label is distinct from old.evidence_label
    or new.storage_path is distinct from old.storage_path
    or new.sha256 is distinct from old.sha256
    or new.version is distinct from old.version
    or new.size_bytes is distinct from old.size_bytes
    or new.page_count is distinct from old.page_count then
    raise exception 'document versions are immutable';
  end if;
  return new;
end;
$$;

-- Analysis runs: evidence matching progress, tracked separately from extraction ------
alter table public.analysis_runs
  add column matching_status text not null default 'not_requested'
    check (matching_status in ('not_requested', 'pending', 'completed', 'partial', 'failed')),
  add column matching_requirements_total integer not null default 0
    check (matching_requirements_total >= 0),
  add column matching_requirements_failed integer not null default 0
    check (matching_requirements_failed >= 0),
  add column matching_rejected_citations integer not null default 0
    check (matching_rejected_citations >= 0),
  -- Evidence segments whose text was cut to fit the bounded matching prompt.
  add column matching_truncated_segments text[] not null default '{}',
  add column matching_error text check (char_length(matching_error) <= 2000);

-- Lets child rows pin a requirement to its run as well as its organisation.
alter table public.requirements
  add constraint requirements_id_org_run_key unique (id, organisation_id, analysis_run_id);

-- Explicit evidence selection per run ----------------------------------------------
create table public.analysis_evidence_documents (
  analysis_run_id uuid not null,
  organisation_id uuid not null,
  document_id uuid not null,
  document_sha256 text not null,
  -- Constant column so the foreign key below only accepts evidence documents.
  document_type text not null default 'evidence' check (document_type = 'evidence'),
  created_at timestamptz not null default now(),
  primary key (analysis_run_id, document_id),
  foreign key (analysis_run_id, organisation_id)
    references public.analysis_runs (id, organisation_id) on delete cascade,
  foreign key (document_id, organisation_id, document_sha256, document_type)
    references public.documents (id, organisation_id, sha256, document_type) on delete cascade,
  unique (analysis_run_id, organisation_id, document_id)
);

-- AI assessment per requirement -------------------------------------------------------
create table public.evidence_matches (
  id uuid primary key,
  organisation_id uuid not null,
  analysis_run_id uuid not null,
  requirement_id uuid not null,
  ai_status text not null check (
    ai_status in (
      'evidence_found_review_required',
      'missing_evidence',
      'ambiguous_requirement',
      'potential_blocker_review_required',
      'extraction_incomplete'
    )
  ),
  explanation text not null check (char_length(explanation) between 1 and 4000),
  uncertainty_notes text check (char_length(uncertainty_notes) <= 4000),
  -- Written by deterministic code, never by the model.
  count_summary text not null check (char_length(count_summary) between 1 and 1000),
  required_count integer check (required_count between 1 and 1000),
  candidate_document_count integer not null default 0 check (candidate_document_count >= 0),
  model text not null,
  created_at timestamptz not null default now(),
  foreign key (requirement_id, organisation_id, analysis_run_id)
    references public.requirements (id, organisation_id, analysis_run_id) on delete cascade,
  unique (requirement_id),
  unique (id, organisation_id, analysis_run_id)
);

create index evidence_matches_run_idx on public.evidence_matches (analysis_run_id);

-- Candidate evidence passages ----------------------------------------------------------
create table public.evidence_match_sources (
  id uuid primary key,
  organisation_id uuid not null,
  evidence_match_id uuid not null,
  analysis_run_id uuid not null,
  document_id uuid not null,
  segment_id text not null,
  page_number integer not null check (page_number >= 1),
  quote text not null check (char_length(quote) between 1 and 2000),
  quote_sha256 text not null check (quote_sha256 ~ '^[0-9a-f]{64}$'),
  relationship text check (char_length(relationship) <= 2000),
  -- Copied from the segment when saved. Only 'ok' passages count as candidate support.
  extraction_status text not null
    check (extraction_status in ('ok', 'suspicious', 'empty', 'error')),
  created_at timestamptz not null default now(),
  foreign key (evidence_match_id, organisation_id, analysis_run_id)
    references public.evidence_matches (id, organisation_id, analysis_run_id) on delete cascade,
  -- The cited document must have been selected for this run.
  foreign key (analysis_run_id, organisation_id, document_id)
    references public.analysis_evidence_documents (analysis_run_id, organisation_id, document_id)
    on delete cascade,
  -- Page number comes from segment metadata, enforced here, never from the model.
  foreign key (segment_id, organisation_id, document_id, page_number)
    references public.source_segments (id, organisation_id, document_id, page_number)
    on delete cascade,
  unique (evidence_match_id, segment_id, quote_sha256)
);

create index evidence_match_sources_match_idx on public.evidence_match_sources (evidence_match_id);

-- Human review decisions (append-only) ------------------------------------------------
create table public.review_decisions (
  id uuid primary key default gen_random_uuid(),
  organisation_id uuid not null,
  analysis_run_id uuid not null,
  requirement_id uuid not null,
  decision text not null check (
    decision in (
      'unresolved',
      'satisfied_for_submission_review',
      'not_satisfied',
      'not_applicable'
    )
  ),
  notes text check (char_length(notes) <= 2000),
  -- No foreign key to auth.users, so the audit trail survives deletion of the user.
  reviewer_id uuid not null,
  created_at timestamptz not null default now(),
  check (decision <> 'not_applicable' or char_length(btrim(coalesce(notes, ''))) > 0),
  foreign key (requirement_id, organisation_id, analysis_run_id)
    references public.requirements (id, organisation_id, analysis_run_id) on delete cascade
);

create index review_decisions_run_idx
  on public.review_decisions (analysis_run_id, requirement_id, created_at desc);

create or replace function public.prevent_review_decision_update()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  raise exception 'review decisions are append-only; record a new decision instead';
end;
$$;

create trigger review_decisions_append_only
  before update on public.review_decisions
  for each row execute function public.prevent_review_decision_update();

-- Proposed next actions ---------------------------------------------------------------
create table public.action_items (
  id uuid primary key,
  organisation_id uuid not null,
  analysis_run_id uuid not null,
  requirement_id uuid not null,
  evidence_match_id uuid not null,
  origin text not null default 'matching' check (origin in ('matching')),
  description text not null check (char_length(description) between 1 and 1000),
  status text not null default 'open' check (status in ('open', 'done')),
  created_at timestamptz not null default now(),
  foreign key (requirement_id, organisation_id, analysis_run_id)
    references public.requirements (id, organisation_id, analysis_run_id) on delete cascade,
  foreign key (evidence_match_id, organisation_id, analysis_run_id)
    references public.evidence_matches (id, organisation_id, analysis_run_id) on delete cascade,
  unique (requirement_id, origin)
);

create index action_items_run_idx on public.action_items (analysis_run_id);

-- Row level security: members may read their organisation's rows ---------------------
alter table public.analysis_evidence_documents enable row level security;
alter table public.evidence_matches enable row level security;
alter table public.evidence_match_sources enable row level security;
alter table public.review_decisions enable row level security;
alter table public.action_items enable row level security;

create policy "Members read analysis evidence selections" on public.analysis_evidence_documents
  for select to authenticated using (public.is_org_member(organisation_id));

create policy "Members read evidence matches" on public.evidence_matches
  for select to authenticated using (public.is_org_member(organisation_id));

create policy "Members read evidence match sources" on public.evidence_match_sources
  for select to authenticated using (public.is_org_member(organisation_id));

create policy "Members read review decisions" on public.review_decisions
  for select to authenticated using (public.is_org_member(organisation_id));

create policy "Members read action items" on public.action_items
  for select to authenticated using (public.is_org_member(organisation_id));

-- Storage: evidence objects live at "<organisation id>/evidence/<document id>.pdf". The
-- existing read policy already keys on the first folder (the organisation id).
