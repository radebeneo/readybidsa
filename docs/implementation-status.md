# Implementation status

Last updated: 2026-10-29. Covers two vertical slices:

1. Sign in, create a tender workspace, upload a tender PDF, process it in the background and show
   source-linked requirements.
2. Company evidence library, explicit evidence selection per analysis, requirement-to-evidence
   matching, human review decisions, the review checklist and CSV/JSON export.

Each item below is in one of three groups:

- **Tested with mocks:** automated tests pass using fake Supabase, storage, queue and model
  providers (`tests/readybid_testing/fakes.py`). These tests show the logic is correct. They do
  not show that it works against real services.
- **Live-verified:** checked against real running services.
- **Not verified:** written but not run end to end.

## Check results (2026-10-29)

| Check | Result |
| --- | --- |
| `uv run pytest --ignore=packages/readybid_core/tests/test_live_groq.py` (mocked only) | 177 passed, 1 warning (Starlette `httpx` deprecation), after the worker reconnect fix (12 new tests in `services/worker/tests/test_worker.py`; 23 worker tests in total) and the checklist HTTP/1.1 client fix (adds `test_supabase_clients_use_http1_with_separate_timeouts`). Includes 47 matching tests (`test_matching.py`) and the evidence, checklist, decision and export tests in `test_endpoints.py` |
| `uv run pytest` (default) | Not rerun after this slice. The live Groq test runs automatically whenever `GROQ_API_KEY` is set, so a default run makes a real model call. It last passed on 2026-10-29 before the matching slice |
| `uv run ruff check .` / `uv run ruff format --check .` | Pass (39 files formatted), rerun after the HTTP/1.1 client fix |
| `uv lock --check` | Pass (60 packages resolved, no drift), rerun after pinning `httpx==0.28.1` |
| `pnpm lint:web` / `pnpm typecheck:web` | Pass, rerun after the reference-count note in `checklist-view.tsx` |
| `pnpm build:web` | Pass after this slice (8 pages, including the new `/documents` page). One earlier run, before this slice, crashed during "Running TypeScript" with a V8 out-of-memory error (`Zone Allocation failed`). The rerun passed with no changes, so it looks like a transient local environment issue |

## Tested with mocks

| Area | Detail | Evidence |
| --- | --- | --- |
| Auth | Supabase access tokens verified in the API: JWKS (RS256/ES256) by default, HS256 only when `SUPABASE_JWT_SECRET` is set. Requires audience `authenticated`, issuer `<SUPABASE_URL>/auth/v1`, role `authenticated` and a UUID `sub`. An unreachable JWKS returns 503, not 401 | `services/api/tests/test_auth.py` |
| Organisations | First sign-in creates one organisation owned by the caller. A second create returns 409. Membership is resolved on the server, so client-supplied IDs are never trusted alone | `test_endpoints.py` |
| Tenant isolation (API) | User B gets 404 for every User A organisation, tender, document, analysis, job and source. A document from another tender cannot be analysed under a different tender | `test_user_b_cannot_reach_anything_in_user_a_organisation`, `test_a_document_from_another_tender_in_the_same_org_cannot_be_analysed_there` |
| Uploads | PDF only, checked by content. Encrypted, malformed and non-PDF files are rejected. Size (15 MB) and page (100) limits are configurable. Server-generated private storage path; SHA-256 and an immutable version per upload. Version conflicts are retried, and the orphaned file is removed on persistent conflict | `test_upload_*`, `test_invalid_uploads_are_rejected_by_content`, `test_*version_conflict*` |
| Text extraction | One segment per page with deterministic IDs. Image-only and empty pages are kept and flagged, never dropped | `test_core.py`, `test_image_only_page_is_kept_and_flagged_as_incomplete_coverage` |
| Background processing | RQ job with queued, running, completed, partial and failed states. Bounded timeout and retries. Transient storage errors retry and converge. Reruns do not duplicate rows. A failure callback never overwrites a finished run | `packages/readybid_core/tests/test_jobs.py` |
| Requirement extraction | Model output is parsed as JSON and validated with Pydantic, with at most 2 repair attempts. Persistently invalid output fails the run without inventing results. A failed page group gives a partial result. A fatal provider error stops further model calls | `test_jobs.py` |
| Citations | Page comes from segment metadata only. The segment must belong to the analysed document version. The quote must match exactly after whitespace normalisation. Invalid citations are rejected, and requirements left without a valid citation are dropped and counted | `test_invalid_citations_are_rejected_and_uncited_requirements_dropped`, `test_citation_to_another_document_cannot_be_persisted` |
| Analysis start | Starting twice returns the active run. A stuck run is failed and replaced. A queue outage fails the run visibly (503). Missing model or queue configuration returns 503 | `test_endpoints.py` |
| Full API flow | Create tender, upload, analyse, poll the job, list requirements and open a source, using fakes | `test_full_flow_returns_source_linked_requirements_and_coverage_warnings` |
| Missing configuration | Returns 503 "Integration not configured", never placeholder data | `test_missing_supabase_configuration_returns_503_not_placeholder_data` |
| Health, status and CORS | Unchanged from the scaffolding slice | `test_api.py`, `test_core.py` |
| Worker setup | Requires `REDIS_URL`, listens on the `readybid` queue and uses timer timeouts on Windows. The scheduler polls every `RQ_SCHEDULER_INTERVAL_SECONDS` (default 10, range 1–60) instead of RQ's 1 s default, which would exhaust Upstash's free command quota | `services/worker/tests/test_worker.py` |
| Evidence library | Org-scoped upload through the same PDF checks, extraction and source tracking as tenders. A known label is required (`reference_letter`, `company_profile`, `staff_certificate`, `declaration`, `tax_status`, `other`). Flagged pages are kept, and storage paths are never returned | `test_evidence_upload_keeps_flagged_pages_and_hides_storage_paths`, `test_evidence_upload_needs_a_known_label` |
| Explicit evidence selection | Only the selected evidence documents are used, each pinned by SHA-256. No selection means no matching calls. A different selection starts a new analysis instead of reusing the active one | `test_only_explicitly_selected_evidence_is_used`, `test_analysis_without_selected_evidence_makes_no_matching_calls`, `test_a_different_evidence_selection_starts_a_new_analysis` |
| Matching rules | Missing reference letters produce an evidence-gap finding, not a blocker. Scoring and preference gaps are never potential blockers; only eligibility or stated disqualification can be. Counts come from deterministic code using numbers written in the requirement, and model counts that are not confirmed are dropped. Two files are not assumed to be two projects. Overclaiming wording ("verified", "genuine", "compliant") is withheld | `test_matching.py` (47 tests), e.g. `test_missing_reference_produces_an_evidence_gap`, `test_scoring_issue_is_not_classified_as_disqualification`, `test_two_files_are_not_assumed_to_be_two_projects`, `test_overclaiming_model_wording_is_withheld` |
| Unreadable evidence | Only passages from `ok` segments count as candidate support. Each requirement is classified on the readable text, as if unreadable or missing pages were absent, so potential blockers and evidence gaps stay visible. A bounded extraction warning (at most 450 characters, stored text at most 1000) names each affected file with its unreadable and cut page ranges, in both the count summary and the next action. Only when no selected document has readable text does a requirement without a stated blocker become `extraction_incomplete` | `test_unreadable_evidence_cannot_count_as_support`, `test_image_only_evidence_keeps_blocker_and_marks_the_rest_incomplete`, `test_missing_pages_add_a_warning_without_hiding_the_gap`, `test_one_unreadable_document_does_not_hide_other_results`, `test_extraction_warning_*`, `test_unreadable_evidence_never_counts_as_candidate_support` |
| Matching citations and failures | Evidence quotes must match the cited segment, and invalid citations are rejected and not counted. Invalid output is repaired once, then left unassessed. A fatal provider error stops later batches; one failed batch gives a partial result. Evidence text cannot close the prompt delimiters | `test_invalid_citations_are_rejected_and_not_counted`, `test_output_that_stays_invalid_leaves_requirements_unassessed`, `test_fatal_provider_error_stops_later_batches`, `test_evidence_text_cannot_close_the_delimiters` |
| Human review decisions | Append-only per run, with reviewer identity and timestamp. `not_applicable` requires notes. Decisions survive a refresh. A new analysis starts unresolved and only shows earlier decisions as a hint, never overwriting them | `test_review_decisions_are_recorded_and_survive_a_refresh`, `test_a_new_analysis_does_not_overwrite_earlier_decisions` |
| Tenant isolation (evidence and review) | User B gets 404 for User A's evidence list and upload, checklist, decisions, export and evidence sources | `test_user_b_cannot_reach_user_a_evidence_checklist_or_decisions` |
| Export | CSV (BOM, all fields quoted, CRLF) and JSON contain tender identity, analysis time, document versions, findings, source refs, unresolved warnings and human decisions. Leading `= + - @ \t \r \n \|` (including full-width forms and after whitespace) are neutralised. Unknown formats return 422. `Cache-Control: no-store` | `test_csv_export_is_complete_and_formula_safe`, `test_spreadsheet_safe_neutralises_formula_triggers`, `test_json_export_carries_the_checklist_and_decisions`, `test_export_rejects_unknown_formats` |

## Live-verified

| Area | Detail | Date |
| --- | --- | --- |
| Live model call | `test_live_groq.py` passes against Groq with `openai/gpt-oss-120b` (strict `json_schema` plus Pydantic). The previous default, `llama-3.3-70b-versatile`, was retired by Groq on 2026-08-16 | 2026-10-29 |
| Supabase keys | `service_role` (API) and `anon` (web) keys belong to the same project as `SUPABASE_URL` | 2026-10-28 |
| Schema applied | Migration run in the SQL Editor. All nine tables answer the REST API (HTTP 200). Bucket `documents` exists: private, 15728640-byte limit, `application/pdf` only. This proves the objects exist, not that RLS isolates tenants (see below) | 2026-10-29 |
| Upstash Redis | `REDIS_URL` uses `rediss://` (TLS). PING, SET/GET and `INFO` work (Redis 8.4.0, about 300 ms per round trip from South Africa to the EU region). `GET /integrations/status` reports Redis `reachable: true` | 2026-10-29 |
| Worker on Windows plus Upstash | `uv run readybid-worker` starts, listens on `readybid` and acquires the scheduler lock. RQ spawns the scheduler as a child process (no `fork` needed), and it heartbeats into Upstash. Its key TTL was observed at 62 s, above RQ's 1 s-default maximum of 61 s, so `RQ_SCHEDULER_INTERVAL_SECONDS=10` is in effect | 2026-10-29 |
| End-to-end API flow (live) | Two confirmed `dev-fixture-` users signed in with Supabase password auth and each created an organisation through `POST /organisations` (a second create returned 409). User A created a tender and uploaded a synthetic 5-page PDF whose page 4 is image-only (201, version 1). A non-PDF was rejected (422 `not_pdf`). The signed URL returned the PDF. The analysis ran through Upstash, the Windows worker and Groq and completed in 17.5 s on the first attempt (2/2 page groups, 0 failed). It produced 4 requirements, each cited on a text page (1, 2, 3, 5). Every source resolved with the matching document version. Page 4 was flagged and coverage marked incomplete. Rejected citations and dropped requirements were both 0, and the preparation notice was present | 2026-10-29 |
| Tenant isolation (API, live) | User B got 404 for User A's tender list, tender create, tender, document file, analysis start, job, analysis, requirements, source and upload. User A got 404 for User B's tenders. No token returned 401 | 2026-10-29 |
| Worker long idle on Upstash | After the live job (09:32), the worker sat idle on Upstash until 12:19 and kept cycling normally: it logged registry cleaning about every 13.5 minutes, so the blocking dequeue (405 s) survived Upstash's idle handling repeatedly. At 12:19 Upstash reset the connection (`WinError 10054`). The scheduler child crashed on its heartbeat, reconnects timed out or were reset during the TLS handshake, and the worker logged "Redis connection timeout, quitting..." and exited. It did not restart. See Known issues | 2026-10-29 |
| RLS and storage (live sessions) | Using each user's own JWT against Supabase REST, all nine tables returned only that user's organisation rows. B saw none of A's tenders, documents, segments, runs, requirements, sources or jobs, and the anon key saw nothing. Direct INSERT returned 403. Direct UPDATE and DELETE by A and by B changed 0 rows (checked with `Prefer: return=representation` and a service-role read-back). Storage: A could download its own object with its JWT. B could not download or sign A's object, there is no public access, and direct uploads are refused | 2026-10-29 |
| Evidence migration applied | `20261029000000_evidence_and_review.sql` is applied on the live project. All 9 REST probes returned HTTP 200, and an OpenAPI comparison found every expected table and column. When and how it was applied is not recorded | 2026-10-29 |
| RLS on evidence and review tables (live sessions) | With each `dev-fixture-` user's JWT, A and B each saw 0 rows from the other organisation in the new tables, and the anon key saw none. A direct INSERT into `review_decisions` by A returned 403 (`42501`). UPDATE and DELETE on the new tables were not probed | 2026-10-29 |
| Live matching runs | 4 analysis runs completed matching between 11:18 and 12:28 against Groq `openai/gpt-oss-120b`, with 5 requirements each, 0 failed and 0 rejected citations. Together they wrote 20 `evidence_matches`, 4 `evidence_match_sources` (all on `ok` pages), 9 `review_decisions` (satisfied 2, not_satisfied 2, not_applicable 3, unresolved 2) and 20 `action_items` (all open). Who started them, and through which path, is not recorded. Matching quality has not been reviewed. 3 of the 4 runs show the `extraction_incomplete` behaviour that has since been fixed (see Known issues); their stored rows keep the old statuses until re-run | 2026-10-29 |
| Checklist 500 fix (live) | `GET` checklist intermittently returned 500 with `httpx.ReadError: [WinError 10035]`, caused by one shared HTTP/2 client used across FastAPI's sync thread pool. Each Supabase client now gets its own HTTP/1.1 `httpx.Client` (30 s repository, 60 s storage). Concurrent checklist GETs against the running API now return 200 | 2026-10-29 |
| Live matching run #5 (fixed code) | Run `1b0cbacd`, started with `analyse_document_job` after the unreadable-evidence fix, with 2 of 10 evidence documents selected. It finished in about 18 s with `missing_evidence` 4 and `potential_blocker_review_required` 1 (position 1, `eligibility`, page 2), and no `extraction_incomplete`. The checklist rows and the "Coverage incomplete" banner (page 5) match the stored rows | 2026-10-29 |
| Run #5 provenance (read-only DB probe) | 5 matches map 1:1 to the 5 requirements. The single `evidence_match_sources` row is from a selected document, on page ≥1, with a `segment_id` and a matching `quote_sha256`. Every requirement has a `requirement_sources` citation on the tender document with page ≥1, a `segment_id` and a matching quote hash. Checked by probe because the source drawer could not be reached in CM Browser | 2026-10-29 |
| Blocker change between runs #4 and #5 | Requirement key `6e9a948c37` (position 3, `returnable`) was a potential blocker in run #4 (`4d60d1cd`) and `missing_evidence` in run #5. Its extracted fields are identical in all 3 runs: preference wording, a negated disqualifying term, `states_disqualification=False`, `blocker_allowed=False`. Under the current `blocker_allowed` rule it cannot become a blocker. The most likely cause is that run #4 was processed by older worker code; this is not confirmed, because there is no git history to compare. Covered by existing regression tests in `test_matching.py` ("will not disqualify") | 2026-10-29 |
| Browser flow, fixture A | Signed in as `dev-fixture-a`: `/tenders` lists 5 Org A workspaces. The evidence selector disables the scanned certificate ("No readable text"). The run `4d60d1cd` checklist renders, with the new reference-count note on row 3. `/documents` shows the scanned certificate as unreadable and the tax status and reference letter as "Text readable", plus the 10-document note, the disclaimer and the upload form. The middle of the document list was not seen (CM Browser could not scroll) | 2026-10-29 |
| Browser isolation, fixture B | Signed in as `dev-fixture-b`: `/tenders` shows only Org B's two "dev-fixture B intrusion tender" (DF-B-002) workspaces. Opening Org A's tender URL shows "Something went wrong Not found." with no data. `/documents` shows "dev-fixture Org B" with "No company documents yet" | 2026-10-29 |

## Implemented, compiles, not verified end to end

The web app passes lint, type checks and a production build. The API, queue, worker, model,
RLS and storage behind it are live-verified (see above). On 2026-10-29 parts of the pages were
driven in CM Browser with both fixture accounts (see "Browser flow, fixture A" and "Browser
isolation, fixture B"). CM Browser could not scroll, take screenshots or open the source drawer
reliably, so the items below that are not named in those rows are still unverified in a browser.

- **Sign-in** (`/login`) with Supabase Auth in the browser. All data goes through the API with
  the user's bearer token.
- **Tenders workspace** (`/tenders`): create the organisation, then list and create tenders.
- **Tender detail** (`/tenders/[id]`): PDF upload with a progress bar and cancel, start
  analysis, job progress polling with back-off, and resume from the latest job.
- **Requirements view**: requirements table, coverage warnings (flagged or truncated pages,
  failed page groups, rejected citations, dropped requirements), and a source drawer showing
  the cited passage with a link to the PDF page through a short-lived signed URL.
- **`documents_immutable` trigger.** RLS and storage policies are live-verified with real
  sessions, but the trigger has not been exercised against the real database. It only matters
  for service-role writes, because members cannot update rows at all.
- **RQ retries and recovery.** One analysis job ran end to end on the real queue, and long idle
  was observed (see Live-verified). The worker now rebuilds itself after a Redis connection
  loss (see Known issues), but this is tested with mocks only. Still unverified: a real job
  retry after a transient failure, a real reconnect after an Upstash reset, the scheduler lock
  being re-acquired after a restart, and real Upstash command usage per day.
- **Extraction quality.** The live model test checks one fixture only; quality on real tender
  documents has not been reviewed.

### Evidence and review slice (2026-10-29)

The migration, RLS on the new tables and real matching runs are now live-verified (see
Live-verified). The items below are still open.

- **Migration contents.** `supabase/migrations/20261029000000_evidence_and_review.sql` adds
  `analysis_evidence_documents`, `evidence_matches`, `evidence_match_sources`,
  `review_decisions` and `action_items`. It also adds the evidence columns on `documents` (with a
  nullable `tender_id`), matching progress columns on `analysis_runs` (`matching_status`,
  requirement counts, rejected citations, truncated segments, `matching_error`) and a composite
  unique key on `requirements`. It is applied live. UPDATE and DELETE isolation on the new
  tables has not been probed.
- **Matching quality.** Groq (`openai/gpt-oss-120b`) matching calls have run live on synthetic
  `dev-fixture-` evidence, but the quality of the results has not been reviewed, and nothing has
  run on real reference letters, company profiles or certificates.
- **Worker matching step.** `_match_evidence_step` (progress 91–98%) has run on the real queue
  (4 completed runs) but still has no dedicated job-level test in `test_jobs.py`.
- **Web pages.** These pass lint, type checks and the production build. Partly driven in CM
  Browser on 2026-10-29 (the `/documents` list top and bottom, the disabled unreadable document
  in the selector, the checklist rows, the count note and the coverage banner; see Live-verified).
  Not yet driven: evidence upload, selecting evidence and starting an analysis from the page,
  filters, row detail, recording a review decision, CSV/JSON export and the source drawer:
  - `/documents` ("Company documents"): evidence upload with a required label, shown as
    "Your label: …", never as verified fact.
  - Evidence selector on the tender page: nothing selected by default, capped at the per-analysis
    limit, unreadable documents disabled, locked while an analysis runs.
  - Review checklist (replaces the requirements table): requirement, category, current
    assessment, matched documents, proposed next action, source link and review control; filters
    for missing evidence, potential blockers and unresolved; review indicators (unresolved items,
    extraction warnings); row detail with tender quote, candidate evidence quote, AI explanation
    and decision history; CSV/JSON export download.
  - Source drawer in evidence mode: shows the user's label, the AI relationship as "Suggested
    relationship (AI, review required)" and a warning that flagged pages cannot count as support.
- **`RequirementsView`** in `apps/web/src/components/requirements-view.tsx` is no longer rendered.
  It is kept for now (the file still exports `CoverageSummary`, which the checklist uses).

To verify the web pages, set up Supabase (`docs/supabase-setup.md`), fill in `.env` (with an
Upstash `REDIS_URL`) and `apps/web/.env.local`, start the API, the worker and the web app, then
run the flow above in a browser with two separate user accounts.

Live test data (counted 2026-10-29): two `dev-fixture-` users (`dev-fixture-a@example.com`,
`dev-fixture-b@example.com`) and their 2 organisations, plus 16 documents (tender PDFs and
1-page synthetic evidence labelled `reference_letter`, `tax_status` and `staff_certificate`),
8 analysis runs (4 with completed matching), 20 evidence matches, 9 review decisions and 20 open
action items. Their passwords are in the gitignored `.env.dev-fixtures`. Delete them in Supabase
Auth when testing is finished; this is destructive, so confirm first.

## Not started

- Action item management: `save_evidence_matches` writes `action_items` rows during matching, and
  the checklist shows the open ones as the "proposed next action". No API route or UI updates,
  assigns or closes them yet
- Full browser verification of the evidence and review pages (partly done; see "Evidence and
  review slice" for what is still open), and a quality review of live matching results
- PDF viewer with in-page source highlighting (the source drawer currently links to the page)
- Deployment to Vercel and Render

## Known issues

- Starlette warns that using `httpx` with its test client is deprecated (suggests `httpx2`).
  Tests still pass; revisit when updating test dependencies.
- `eslint@9` is flagged as deprecated by pnpm. It is the version `eslint-config-next` 16.4
  expects; upgrade together with it.
- **Fixed (mocked tests only): the worker exited after a Redis connection loss.** On 2026-10-29
  an Upstash connection reset ended both the worker and its scheduler, and nothing restarted
  them. RQ 2.12 quits its work loop on a Redis timeout, and on a connection error anywhere
  outside the blocking dequeue (such as a heartbeat). Now, in
  `services/worker/src/readybid_worker/main.py`:
  - `build_connection` adds a 30 s health check, socket keepalive, a 10 s connect timeout and 3
    jittered command retries on connection and timeout errors. `Redis.from_url` applies no
    retries and no health check by default. The settings survive RQ's rebuild of the
    connection in the scheduler child (tested).
  - `run_forever` rebuilds the worker whenever it exits without a stop request, waiting 5 s,
    then doubling up to 60 s; the delay resets after a run of at least 5 minutes. A Redis error
    raised from RQ's teardown also triggers a restart.
  - Ctrl+C or a stop signal ends the loop with exit code 0 and no restart.
  - A wrong or unreachable `REDIS_URL` still fails fast: the first attempt PINGs Redis and exits
    with code 1 instead of retrying forever.
  - RQ re-acquires the scheduler lock during maintenance once the previous holder's lock expires,
    so no extra scheduler code was added.
  
  12 tests in `services/worker/tests/test_worker.py`. Not yet verified against a real Upstash
  reset. The worker still running locally was started before this change and uses the old code.
  For production, a platform restart policy (Render restarts crashed services) is still useful
  as a second layer.
- **No "Acquired scheduler lock" log after a forced kill.** The worker currently running was
  started after the previous one was force-killed, and it has not logged that it acquired the
  scheduler lock. The likely cause is that the killed worker's lock had not yet expired; RQ
  retries during maintenance (about every 10 minutes). Not confirmed; check the log or the
  `rq:scheduler-lock:readybid` key before relying on scheduled retries.
- **Duplicate fixture data.** Fixture A's document library lists each synthetic evidence file
  more than once, and Org B has two identical "dev-fixture B intrusion tender" (DF-B-002)
  workspaces. These are `dev-fixture-` rows from repeated test setup. Removing them is
  destructive, so it waits for confirmation.
- **Checklist Source and Review columns sit off-screen.** The checklist table uses
  `min-w-[64rem]` inside `overflow-x-auto`, so on a narrow window the Source and Review columns
  need horizontal scrolling. Not changed yet.
- **Fixed (mocked tests only): one unreadable evidence file turned unrelated requirements into
  `extraction_incomplete`.** Previously a single run-wide `incomplete` flag in
  `build_evidence_context` was checked before the potential-blocker and missing-evidence rules,
  so one image-only `staff_certificate` gave 5 `extraction_incomplete` in each of 3 live runs and
  hid blockers and gaps. Now (product decision: keep the status, add a warning) `classify`
  checks blockers first and returns `extraction_incomplete` only when no selected document has
  readable text. Otherwise the status reflects the readable evidence, and `count_summary` and
  `next_action` carry an extraction warning naming the files and pages (no schema change).
  Text cut to fit the evidence budget is named too; the warning says it was not shown to the
  model, because a quote from a cut page still validates against the stored text. Not yet
  re-run live: the 20 existing `evidence_matches` keep their old statuses until their analyses
  are re-run.
- `pnpm build:web` once ran out of memory during type checking (see check results). If it
  happens again, retry with `$env:NODE_OPTIONS="--max-old-space-size=4096"`.
