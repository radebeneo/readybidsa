# Test fixtures

Fixtures here are for automated tests and labelled local development only. They must never be
shown in the app as real results.

Rules:

- Use synthetic documents only. Never add real tender packs or real company documents (tax,
  registration, B-BBEE, banking or ID documents).
- Name dev fixtures with a `dev-fixture-` prefix so they are obviously not real data.
- Prefer generating small PDFs in test code (see `build_pdf`, `IMAGE_ONLY`,
  `build_encrypted_pdf` and `build_malformed_pdf` in `tests/readybid_testing/pdfs.py`) over
  committing binary files.

There are no committed fixture files yet.

`tests/readybid_testing/` holds shared test-only helpers: synthetic PDFs, in-memory fakes for
the repository, storage and queue, and `ScriptedProvider`, a mocked model. Tests that use
`ScriptedProvider` prove pipeline logic, not real model behaviour. The live model test
(`packages/readybid_core/tests/test_live_groq.py`) is skipped unless `GROQ_API_KEY` is set.
