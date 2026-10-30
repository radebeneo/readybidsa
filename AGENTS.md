# ReadyBid SA: rules for coding agents

These rules apply to the whole repository. `apps/web/AGENTS.md` adds Next.js-specific rules.

## Product limits

- ReadyBid assists tender **preparation** only. Never present output as legal certification,
  an eligibility guarantee or an award prediction.
- English, text-readable PDFs only. Pages without extractable text must be **flagged and kept**,
  never dropped silently.
- Out of scope: OCR, vector databases, autonomous agents, tender scraping, billing, automatic
  submission and government-portal integrations.

## No fabricated results

- Mocks are allowed only in automated tests or in clearly labelled dev fixtures
  (`dev-fixture-` prefix, see `tests/fixtures/README.md`).
- When credentials are missing, show "Integration not configured". Never show placeholder data
  as if it were real.
- Every extracted requirement and evidence match must keep its source page and passage.

## Architecture

- Shared Python logic lives in `packages/readybid_core`. The API and worker import it; do not
  duplicate processing code between them.
- Background jobs are defined in `readybid_core.jobs` so the enqueuer and worker share them.
- Secrets (Supabase service role key, Groq key) are server-only. Never expose them through
  `NEXT_PUBLIC_*` variables or API responses.
- CORS uses an explicit origin allow-list (`CORS_ORIGINS`). No wildcards.
- Do not assume a Groq SDK feature works on every model. Check it against
  `openai/gpt-oss-120b` (the configured default) before relying on it.

## Dependencies

- Pin versions and keep lockfiles (`pnpm-lock.yaml`, `uv.lock`) committed and in sync.
- Verify a package is legitimate and compatible before adding it.

## Safety

- Ask the user before any purchase, public deployment or destructive operation (deleting data,
  dropping tables, force-removing files).
- Leave `Generic-Context-Kit/` untouched. It is an unrelated template kit.
- Never commit `.env` files, credentials or uploaded documents.

## Working practices

- Inspect before changing. Preserve unrelated work.
- Build small vertical slices. Update `docs/implementation-status.md` after each one.
- Run the checks in `README.md` and report real results, separating implemented, incomplete
  and untested work.
