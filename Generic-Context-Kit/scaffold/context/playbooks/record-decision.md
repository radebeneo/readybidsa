# Playbook: Record a Decision

Use this playbook to write an architecture decision record (ADR) for one significant decision, or to replace an existing one. The goal is a short record of what was decided and why, so the question is not reopened without a reason.

## Does it need an ADR?

Use the criteria in `context/decisions/README.md`. If the choice is easy to reverse and affects only one unit, record it in that unit's spec instead.

## Steps

1. **Check existing decisions.** Read the index in `context/decisions/README.md` and any ADR on the same topic. If an Accepted ADR already covers the question, say so and stop. If the new decision changes an Accepted ADR, the new ADR supersedes it.
2. **Gather the facts.** Ask the person for the problem, the constraints, the options considered and who decides. Read the context files and specs that the decision affects. Do not invent options or reasons to fill the record.
3. **Copy the template.** Copy `context/decisions/ADR-0000-template.md` to `context/decisions/ADR-NNNN-short-title.md`. Use the next free four-digit number and a short lowercase title with hyphens, for example `ADR-0003-hosting-platform.md`.
4. **Fill it in.** Complete every section and delete the guidance comments. Set Status to `Proposed`, Date to today's date and Deciders to the people or roles who will decide. Describe each option fairly, including its disadvantages.
5. **Ask for the decision.** Show the person the draft. Only a person sets Status to `Accepted` or `Rejected`.
6. **Once it is Accepted:**
   - Add it to the index in `context/decisions/README.md`.
   - Update every file listed under Context files to update, in the same pull request.
   - If it supersedes an ADR, set the old ADR's Status to `Superseded by ADR-NNNN` and update its row in the index. Change nothing else in the old ADR.
7. **Check.** Run `node context/check-context.mjs` and fix what it reports.

## Rules

- One decision per ADR.
- Never change the decision in an Accepted ADR. Write a new ADR that supersedes it.
- Keep Rejected ADRs. They record that an option was considered and why it was turned down.
- Never put secrets, personal data or confidential commercial terms in an ADR.

## Done when

- The ADR has no `FILL` comments, and a person has set its Status.
- An Accepted ADR is in the index, and the context files it affects are updated.
- `node context/check-context.mjs` reports no errors.
