# Playbook: Refresh the Context

Use this playbook to keep the context files accurate: when the context check reports overdue reviews, before a new phase of work, after a release, after a large change, or when people join or leave the team. The goal is files that describe the project as it is today, each confirmed by its owner, and rules that stop the same snags happening again.

## Steps

1. **Find what needs attention.** Run `node context/check-context.mjs` and list the files that are overdue for review, still in `Draft`, without an owner, or reporting errors. Ask the person whether anything has changed recently that the files may not reflect, for example a new integration, environment, brand or team member.
2. **Learn from the snag log.** Read the Snag log in `context/modules/go-live.md` for entries added since the last refresh.
   - Group them by cause. A cause that appears more than once, or a single snag that delayed a release, needs a change that would have prevented it.
   - Propose that change in the right place: a rule in `context/ai-workflow-rules.md` or `context/code-standards.md`, a check in the Before staging section of `context/modules/quality-testing.md`, a row in the Environment parity table, a readiness criterion or pre-launch check in `context/modules/go-live.md`, or guidance in the unit spec template.
   - Fill in the Prevented next time by column for each snag the change covers.
3. **Agree the scope.** Agree with the person which files to refresh this time, including any changes proposed from the snag log. Work through them one at a time, ideally with each file's owner.
4. **For each file:**
   1. Read it, then compare it with the project as it is now. Inspect the code, configuration, package manifests and pipelines, and read the ADRs and specs completed since its Last reviewed date.
   2. List the differences: facts that are out of date, missing, no longer true, or that contradict another context file or an ADR.
   3. Propose the edits. Keep each fact in one file and link to it from others.
   4. Ask the owner to confirm the edits, or to confirm that the file is still accurate.
   5. Only after the owner confirms, apply the edits and set Last reviewed to today's date.
   6. Add anything nobody can answer yet to Open questions in `context/progress-tracker.md`.
5. **Respect decisions.** If the project now contradicts an Accepted ADR, do not edit the ADR. Propose a new ADR that supersedes it.
6. **Check again.** Run `node context/check-context.mjs` and fix what it reports.
7. **Update the tracker.** Add a row to the History table in `context/progress-tracker.md` listing the files refreshed and the snags addressed.
8. **Prepare one pull request** for the refresh. Describe it as a context refresh and list each file with a summary of what changed.

## Rules

- The Last reviewed date records a review by a person. Never change it unless a person has confirmed the file's content.
- Describe what is true now, not what is planned. Planned work belongs in the build plan.
- Do not delete a section because it is hard to fill. Leave the `FILL` comment and add an open question. A module that no longer applies is marked `Not applicable`.
- Do not delete snag log entries. They are the project's record of what went wrong and why.
- Never add secrets, personal contact details or production data.

## Done when

- Every file in scope has been confirmed by its owner, with a current Last reviewed date.
- Every repeated cause in the snag log has a proposed or agreed change.
- `node context/check-context.mjs` reports no errors.
- The tracker lists the refresh and any open questions.
