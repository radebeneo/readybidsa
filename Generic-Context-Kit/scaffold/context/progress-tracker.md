# Progress Tracker

| Owner | Last reviewed | Status |
| --- | --- | --- |
| {{OWNER}} | {{TODAY}} | Active |

The current state of the build. Agents read this file before starting work and update it when they finish. Keep it short: move old entries to the history at the bottom once a phase is complete.

## Current phase

Context setup. Fill in the context files with `context/playbooks/setup-context.md`, then plan the build with `context/playbooks/plan-build.md`.

## Units

The full list of units is in `context/specs/00-build-plan.md`. This table shows their status.

| Unit | Status | Owner | Notes |
| --- | --- | --- | --- |
| Context setup | In progress | {{OWNER}} | Kit {{KIT_VERSION}} added on {{TODAY}} |

Status is one of: Not started, Spec in review, Ready, In progress, In review, Done, Blocked.

## Next up

- Fill in the context files and set each one to `Active`.
- Run `node context/check-context.mjs` and fix what it reports.
- Write the build plan.

## Open questions

Questions that need an answer from a person. Remove each one once it is answered, and record the answer in the right context file or ADR.

- None yet.

## Blockers

- None.

## Notes for the next session

Anything the next person or agent needs to know to pick up the work.

- None yet.

## History

| Date | Change |
| --- | --- |
| {{TODAY}} | Context Kit {{KIT_VERSION}} added with the {{PROFILE_NAME}} profile. |
