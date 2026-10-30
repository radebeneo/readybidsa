-- ReadyBid SA initial schema: organisation-based tenancy.
--
-- Access model
-- * Every tenant-owned row carries organisation_id. Composite foreign keys that include
--   organisation_id stop a child row from pointing at another organisation's parent.
-- * Authenticated users may only READ rows of organisations they belong to (RLS below).
--   There are no insert/update/delete policies for `authenticated`, so direct client
--   writes are denied.
-- * All writes go through the FastAPI backend with the service role key. The service
--   role BYPASSES RLS, so the backend authorises every request itself
--   (readybid_core.authz). RLS is the second line of defence, not the only one.
-- * Citations are tied to source segments by foreign keys that include the document,
--   organisation and page number, so a stored citation cannot point at another
--   document, organisation or page.

create extension if not exists pgcrypto;

-- Organisations and membership ----------------------------------------------------
create table public.organisations (
  id uuid primary key default gen_random_uuid(),
  name text not null check (char_length(name) between 1 and 200),
  created_at timestamptz not null default now()
);

create table public.organisation_members (
  organisation_id uuid not null references public.organisations (id) on delete cascade,
  user_id uuid not null references auth.users (id) on delete cascade,
  role text not null default 'member' check (role in ('owner', 'admin', 'member')),
  created_at timestamptz not null default now(),
  primary key (organisation_id, user_id)
);

create index organisation_members_user_idx on public.organisation_members (user_id);

-- Membership checks used by RLS. SECURITY DEFINER avoids recursive RLS evaluation on
-- organisation_members; search_path is pinned so the function cannot be hijacked.
create or replace function public.is_org_member(org uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.organisation_members m
    where m.organisation_id = org
      and m.user_id = (select auth.uid())
  );
$$;

-- Same check for storage object paths, whose first folder is the organisation id.
-- Compares as text so a malformed path never raises a cast error.
create or replace function public.is_org_member_folder(folder text)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.organisation_members m
    where m.organisation_id::text = folder
      and m.user_id = (select auth.uid())
  );
$$;

revoke all on function public.is_org_member(uuid) from public;
revoke all on function public.is_org_member_folder(text) from public;
grant execute on function public.is_org_member(uuid) to authenticated;
grant execute on function public.is_org_member_folder(text) to authenticated;

-- Tenders ----------------------------------------------------------------------------
create table public.tenders (
  id uuid primary key default gen_random_uuid(),
  organisation_id uuid not null references public.organisations (id) on delete cascade,
  title text not null check (char_length(title) between 1 and 300),
  reference text check (char_length(reference) <= 200),
  created_by uuid references auth.users (id) on delete set null,
  created_at timestamptz not null default now(),
  unique (id, organisation_id)
);

create index tenders_org_idx on public.tenders (organisation_id, created_at desc);

-- Uploaded documents (immutable versions) --------------------------------------------
-- A re-upload creates a new row with the next version number. The row's id plus sha256
-- is the immutable version identity used by segments, analysis runs and citations.
create table public.documents (
  id uuid primary key default gen_random_uuid(),
  organisation_id uuid not null,
  tender_id uuid not null,
  document_type text not null default 'tender' check (document_type in ('tender')),
  original_filename text not null check (char_length(original_filename) between 1 and 255),
  storage_path text not null unique,
  sha256 text not null check (sha256 ~ '^[0-9a-f]{64}$'),
  size_bytes bigint not null check (size_bytes > 0),
  page_count integer not null check (page_count >= 1),
  version integer not null check (version >= 1),
  created_by uuid references auth.users (id) on delete set null,
  created_at timestamptz not null default now(),
  foreign key (tender_id, organisation_id)
    references public.tenders (id, organisation_id) on delete cascade,
  unique (tender_id, version),
  unique (id, organisation_id, sha256),
  unique (id, organisation_id, tender_id, sha256)
);

create index documents_tender_idx on public.documents (tender_id, version desc);

create or replace function public.prevent_document_identity_change()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.id is distinct from old.id
    or new.organisation_id is distinct from old.organisation_id
    or new.tender_id is distinct from old.tender_id
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

create trigger documents_immutable
  before update on public.documents
  for each row execute function public.prevent_document_identity_change();

-- One source segment per physical PDF page --------------------------------------------
-- id is deterministic (readybid_core.pdf.segment_id) so re-running extraction is idempotent.
create table public.source_segments (
  id text primary key check (id ~ '^seg_[0-9a-f]{32}$'),
  organisation_id uuid not null,
  document_id uuid not null,
  document_sha256 text not null,
  page_number integer not null check (page_number >= 1),
  text text not null,
  char_count integer not null check (char_count >= 0),
  extraction_status text not null
    check (extraction_status in ('ok', 'suspicious', 'empty', 'error')),
  extraction_note text,
  created_at timestamptz not null default now(),
  foreign key (document_id, organisation_id, document_sha256)
    references public.documents (id, organisation_id, sha256) on delete cascade,
  unique (document_id, page_number),
  unique (id, organisation_id, document_id, page_number)
);

-- Analysis runs ----------------------------------------------------------------------
create table public.analysis_runs (
  id uuid primary key default gen_random_uuid(),
  organisation_id uuid not null,
  tender_id uuid not null,
  document_id uuid not null,
  document_sha256 text not null,
  status text not null default 'queued'
    check (status in ('queued', 'running', 'completed', 'partial', 'failed')),
  model text not null,
  pages_total integer check (pages_total >= 0),
  -- Pages that are empty, suspicious or failed extraction. Kept and flagged, never dropped.
  flagged_pages integer[] not null default '{}',
  -- Pages whose text was longer than one model call allows and was cut off.
  truncated_pages integer[] not null default '{}',
  -- Model citations that failed validation, and requirements dropped for lack of one.
  rejected_citations integer not null default 0 check (rejected_citations >= 0),
  dropped_requirements integer not null default 0 check (dropped_requirements >= 0),
  groups_total integer not null default 0 check (groups_total >= 0),
  groups_completed integer not null default 0 check (groups_completed >= 0),
  groups_failed integer not null default 0 check (groups_failed >= 0),
  coverage_complete boolean,
  error text,
  created_by uuid references auth.users (id) on delete set null,
  created_at timestamptz not null default now(),
  started_at timestamptz,
  finished_at timestamptz,
  foreign key (tender_id, organisation_id)
    references public.tenders (id, organisation_id) on delete cascade,
  -- The analysed document must belong to the same tender and organisation, at this version.
  foreign key (document_id, organisation_id, tender_id, document_sha256)
    references public.documents (id, organisation_id, tender_id, sha256) on delete cascade,
  unique (id, organisation_id),
  unique (id, organisation_id, document_id)
);

create index analysis_runs_tender_idx on public.analysis_runs (tender_id, created_at desc);

-- Background processing jobs (RQ) ------------------------------------------------------
create table public.processing_jobs (
  id uuid primary key default gen_random_uuid(),
  organisation_id uuid not null,
  analysis_run_id uuid not null,
  kind text not null default 'analyse_document' check (kind in ('analyse_document')),
  status text not null default 'queued'
    check (status in ('queued', 'running', 'completed', 'partial', 'failed')),
  stage text not null default 'queued' check (char_length(stage) <= 200),
  progress integer not null default 0 check (progress between 0 and 100),
  attempts integer not null default 0 check (attempts >= 0),
  rq_job_id text unique,
  error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  foreign key (analysis_run_id, organisation_id)
    references public.analysis_runs (id, organisation_id) on delete cascade,
  unique (analysis_run_id, kind)
);

-- Extracted requirements -------------------------------------------------------------
create table public.requirements (
  id uuid primary key default gen_random_uuid(),
  organisation_id uuid not null,
  analysis_run_id uuid not null,
  document_id uuid not null,
  -- Normalised text key used for conservative, idempotent de-duplication within a run.
  dedupe_key text not null check (dedupe_key ~ '^[0-9a-f]{64}$'),
  position integer not null check (position >= 0),
  title text not null check (char_length(title) between 1 and 200),
  requirement_text text not null check (char_length(requirement_text) between 1 and 4000),
  category text not null check (
    category in ('eligibility', 'returnable', 'scoring', 'contractual', 'informational', 'unclear')
  ),
  evidence_needed text check (char_length(evidence_needed) <= 2000),
  stage text not null check (
    stage in ('submission', 'evaluation', 'award', 'contract_start', 'unclear')
  ),
  -- Only a consequence stated in the document. Null when not explicit.
  consequence text check (char_length(consequence) <= 2000),
  ambiguity_notes text check (char_length(ambiguity_notes) <= 2000),
  created_at timestamptz not null default now(),
  foreign key (analysis_run_id, organisation_id, document_id)
    references public.analysis_runs (id, organisation_id, document_id) on delete cascade,
  unique (analysis_run_id, dedupe_key),
  unique (id, organisation_id, document_id)
);

create index requirements_run_idx on public.requirements (analysis_run_id, position);

-- Validated citations ----------------------------------------------------------------
create table public.requirement_sources (
  id uuid primary key default gen_random_uuid(),
  organisation_id uuid not null,
  requirement_id uuid not null,
  document_id uuid not null,
  segment_id text not null,
  page_number integer not null check (page_number >= 1),
  quote text not null check (char_length(quote) between 1 and 2000),
  quote_sha256 text not null check (quote_sha256 ~ '^[0-9a-f]{64}$'),
  created_at timestamptz not null default now(),
  foreign key (requirement_id, organisation_id, document_id)
    references public.requirements (id, organisation_id, document_id) on delete cascade,
  -- Page number comes from segment metadata, enforced here, never from the model.
  foreign key (segment_id, organisation_id, document_id, page_number)
    references public.source_segments (id, organisation_id, document_id, page_number)
    on delete cascade,
  unique (requirement_id, segment_id, quote_sha256)
);

create index requirement_sources_requirement_idx on public.requirement_sources (requirement_id);

-- Row level security: members may read their organisation's rows ---------------------
alter table public.organisations enable row level security;
alter table public.organisation_members enable row level security;
alter table public.tenders enable row level security;
alter table public.documents enable row level security;
alter table public.source_segments enable row level security;
alter table public.analysis_runs enable row level security;
alter table public.processing_jobs enable row level security;
alter table public.requirements enable row level security;
alter table public.requirement_sources enable row level security;

create policy "Members read their organisations" on public.organisations
  for select to authenticated using (public.is_org_member(id));

create policy "Members read memberships of their organisations" on public.organisation_members
  for select to authenticated
  using (user_id = (select auth.uid()) or public.is_org_member(organisation_id));

create policy "Members read tenders" on public.tenders
  for select to authenticated using (public.is_org_member(organisation_id));

create policy "Members read documents" on public.documents
  for select to authenticated using (public.is_org_member(organisation_id));

create policy "Members read source segments" on public.source_segments
  for select to authenticated using (public.is_org_member(organisation_id));

create policy "Members read analysis runs" on public.analysis_runs
  for select to authenticated using (public.is_org_member(organisation_id));

create policy "Members read processing jobs" on public.processing_jobs
  for select to authenticated using (public.is_org_member(organisation_id));

create policy "Members read requirements" on public.requirements
  for select to authenticated using (public.is_org_member(organisation_id));

create policy "Members read requirement sources" on public.requirement_sources
  for select to authenticated using (public.is_org_member(organisation_id));

-- Private storage bucket ---------------------------------------------------------------
-- Objects live at "<organisation id>/<tender id>/<document id>.pdf", generated by the
-- server. The bucket limit is a hard cap; keep it >= MAX_UPLOAD_BYTES in the API settings.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('documents', 'documents', false, 15728640, array['application/pdf'])
on conflict (id) do update
  set public = false,
      file_size_limit = excluded.file_size_limit,
      allowed_mime_types = excluded.allowed_mime_types;

-- Read-only for members. Uploads and deletes go through the API (service role), and
-- the browser only ever receives short-lived signed URLs issued after a permission check.
create policy "Members read organisation documents" on storage.objects
  for select to authenticated
  using (
    bucket_id = 'documents'
    and public.is_org_member_folder((storage.foldername(name))[1])
  );
