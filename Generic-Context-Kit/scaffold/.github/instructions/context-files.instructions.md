---
applyTo: "context/**/*.md"
---

# Editing context files

These files are the project's shared memory for people and agents. When you edit one:

- Keep the header table (Owner, Last reviewed, Status) at the top. Set Last reviewed to today's date when you review or substantially change a file.
- Replace `FILL` comments with real content and delete each comment once its section is complete. Never invent facts to fill a section; leave the comment and add an open question to `context/progress-tracker.md`.
- Keep each fact in one file and link to it from others.
- Keep it short. Prefer bullet points and tables to paragraphs.
- Never add secrets, personal contact details, client personal data or production data.
- Run `node context/check-context.mjs` after editing.

The full workflow is in `context/playbooks/setup-context.md`.
