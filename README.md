# ReadyBid SA

A tender-readiness assistant for South African small businesses. It helps you prepare a
tender submission: upload a tender PDF and your company documents, extract the requirements,
match evidence, flag gaps, show the source passages and record your review decisions.

ReadyBid SA **assists with preparation only**. It does not provide legal certification,
guarantee eligibility or predict awards.

> **Status:** two vertical slices built, not deployed.
>
> - **Built and live-verified** against real Supabase, Upstash Redis and Groq: sign-in, tender
>   workspaces, tender PDF upload, background requirement extraction with source citations,
>   the company evidence library, evidence matching and the review checklist, plus tenant
>   isolation through the API and row level security.
> - **Partly verified:** the web pages were driven in a browser with two test accounts, but
>   evidence upload, review decisions, export and the source drawer have not been. Matching
>   quality has only been checked on synthetic test documents. The worker's Redis reconnect
>   is tested with mocks only.
> - **Not built:** action item management, in-page source highlighting and deployment.
>
> Details, test results and known issues are in
> [`docs/implementation-status.md`](docs/implementation-status.md).

## Layout

| Path                     | What it is                                                            |
| ------------------------ | --------------------------------------------------------------------- |
| `apps/web`               | Next.js 16 App Router frontend (TypeScript, Tailwind 4, shadcn/ui)    |
| `services/api`           | FastAPI service (`readybid_api`)                                      |
| `services/worker`        | RQ background worker (`readybid_worker`)                              |
| `packages/readybid_core` | Shared Python code used by both the API and the worker                |
| `supabase/migrations`    | Database schema, row level security and the private storage bucket    |
| `tests/fixtures`         | Synthetic test fixtures only                                          |
| `docs`                   | Setup guides and implementation status                                |

## Prerequisites

- Node.js 22 or later and pnpm 12 (`corepack enable`)
- Python 3.14 and [uv](https://docs.astral.sh/uv/) 0.12
- An [Upstash](https://upstash.com/) Redis database (the free tier is enough). Required to
  analyse tenders: analysis runs as a background job on the queue

## First-time setup

Run these from the repository root.

```powershell
pnpm install
uv sync --all-packages
Copy-Item .env.example .env
Copy-Item apps/web/.env.example apps/web/.env.local
```

Leave values empty until you have credentials. Missing values show as
"Integration not configured" in the dashboard instead of failing.

To connect Supabase, follow [`docs/supabase-setup.md`](docs/supabase-setup.md).

## Run locally

Use one terminal per process, each from the repository root.

```powershell
# 1. Redis: no local process. Create a free Upstash Redis database (eviction off, closest
#    region), copy its TCP connection string and set REDIS_URL=rediss://... in .env.
#    Use the rediss:// (TLS) URL, not the REST URL or token.

# 2. API on http://localhost:8000 (docs at /docs)
uv run uvicorn readybid_api.main:app --reload --port 8000

# 3. Worker (needs REDIS_URL). Restart the API too if you set REDIS_URL after starting it.
uv run readybid-worker

# 4. Web on http://localhost:3000
pnpm dev:web
```

The API reads `.env` from the current directory, so start it from the repository root.

## Checks

```powershell
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv lock --check
pnpm lint:web
pnpm typecheck:web
pnpm build:web
```

All Python tests use fake Supabase, storage, queue and model providers except
`packages/readybid_core/tests/test_live_groq.py`, which calls the real model. It is skipped
unless `GROQ_API_KEY` is set. Report its result separately from the mocked tests.

## Configuration

API and worker settings go in the root `.env` (see `.env.example` for every option and its
default). Web settings go in `apps/web/.env.local` (see `apps/web/.env.example`).

| Variable | Used by | Purpose |
| --- | --- | --- |
| `CORS_ORIGINS` | API | Comma-separated browser origins allowed to call it. Must include the web app's origin |
| `SUPABASE_URL` | API, worker | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | API, worker | Server-only key. Never put it in the web app |
| `SUPABASE_JWT_SECRET` | API | Optional. Only for projects on the legacy HS256 secret; otherwise tokens are checked against JWKS |
| `SUPABASE_STORAGE_BUCKET` | API, worker | Private bucket for PDFs. Defaults to `documents` |
| `GROQ_API_KEY` | API, worker | Groq key for requirement extraction. The API refuses to start an analysis without it |
| `GROQ_MODEL` | API, worker | Defaults to `openai/gpt-oss-120b` (`llama-3.3-70b-versatile` was retired by Groq in August 2026) |
| `REDIS_URL` | API, worker | Job queue connection |
| `MAX_UPLOAD_BYTES`, `MAX_PDF_PAGES` | API | Upload limits. Defaults 15 MB and 100 pages. Keep the size at or below the bucket limit |
| `SIGNED_URL_TTL_SECONDS` | API | Lifetime of signed PDF links. Defaults to 120 |
| `LLM_*` | Worker | Model timeout, output size, repair attempts (max 2) and requirements per page group |
| `ANALYSIS_*` | Worker | Page group size and character limits |
| `JOB_TIMEOUT_SECONDS`, `JOB_MAX_RETRIES` | API, worker | Background job bounds. Defaults 900 s and 2 retries |
| `RQ_SCHEDULER_INTERVAL_SECONDS` | worker | How often the scheduler re-queues due retries (1–60 s, default 10). RQ's own default of 1 s would exhaust Upstash's free command quota |
| `API_URL` | Web (server) | API base URL for the dashboard status panel, read at request time |
| `NEXT_PUBLIC_API_URL` | Web (browser) | **Required.** API base URL the browser calls with the user's token. Inlined at build time |
| `NEXT_PUBLIC_SUPABASE_URL` | Web (browser) | Supabase project URL, for sign-in |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Web (browser) | Public anon key, for sign-in. Never the service role key |

`NEXT_PUBLIC_*` values are built into the browser bundle, so restart `pnpm dev:web` or rebuild
after changing them, and never put secrets in them.

## Deployment

Planned targets are Vercel (web) and Render (API and worker). Nothing is deployed, and
nothing should be deployed publicly without explicit approval.
