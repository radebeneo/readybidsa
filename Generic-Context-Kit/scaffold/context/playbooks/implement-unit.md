# Playbook: Implement a Unit

Use this playbook to build one unit from an approved spec. The goal is a small, reviewable pull request that meets every acceptance criterion, deploys cleanly to every environment and leaves the context files accurate.

## Before you start

1. **Check the spec.** Open the unit's spec in `context/specs/`. Its Status must be `Ready`. If there is no spec, or it is not `Ready`, stop and use `context/playbooks/write-unit-spec.md` first.
2. **Check dependencies.** Every unit this one depends on must be `Done` in `context/progress-tracker.md`.
3. **Read the context.** Read the files listed in `AGENTS.md`, everything in the spec's Context to read section, and `context/ai-workflow-rules.md`. Read the Configuration by environment and Environment parity sections of `context/modules/environments-delivery.md`, and the Before staging checks in `context/modules/quality-testing.md`.
4. **Study the code.** Find similar features in the codebase and follow their patterns.
5. **State your plan.** Tell the person which files you will change, the approach, any approval gates, anything the unit will need in each environment beyond its code, and how you will verify each acceptance criterion. Wait for agreement if the spec lists approval gates.
6. **Update the tracker.** Set the unit to `In progress` in `context/progress-tracker.md` and in the spec.

## Build

- Work in small steps and check each one before moving on.
- Change only what the spec covers. Record anything else you notice under Notes for the next session in `context/progress-tracker.md`.
- Write the tests listed in the spec alongside the code, not afterwards.
- Stop and ask for approval before anything listed under approval gates in `context/ai-workflow-rules.md`, even if it was not in the spec.
- If the spec turns out to be wrong or incomplete, stop and say so. Do not quietly change the scope.
- **Keep the Release impact section current.** Each time you add or rename a setting, need a secret, change schema, depend on content or media, call a new service, add a feature flag or need a manual step, add it to the Release impact section of the spec straight away. Do not leave it until the end.
- **Do not depend on your machine.** No hard-coded local paths, hostnames, ports, certificates or data. Every value that differs by environment comes from configuration, as described in `context/modules/environments-delivery.md`.

## Verify

1. Run every command in the definition of done in `AGENTS.md` and fix any failures. Never skip or weaken a check to make it pass.
2. Go through the acceptance criteria one by one and confirm each is met. Note how you checked it: a test, a command, or a manual check with steps.
3. Run the Before staging checks in `context/modules/quality-testing.md` for the pages and components the unit changes.
4. Compare your diff with the Release impact section of the spec. Every new or changed setting, secret, schema file, migration, scheduled job, package and manual step must be listed, with what each environment needs. Every row must have content or "None".
5. Run `node context/check-context.mjs`.
6. Review your own diff as a reviewer would, using the checklist in `context/modules/quality-testing.md`.

## Finish

1. Update any context file your change made out of date, for example a new component in `context/ui-context.md`, or a new setting in `context/modules/environments-delivery.md`.
2. Record any significant decision as an ADR in `context/decisions/`.
3. Set the unit to `In review` in the spec and in `context/progress-tracker.md`, and update Next up and Notes for the next session.
4. Write the pull request description:
   - **What:** a summary of the change.
   - **Why:** the unit and its goal, with a link to the spec.
   - **How to test:** steps a reviewer can follow.
   - **Acceptance criteria:** each one, with how it was verified.
   - **Release impact:** a short summary of what each environment needs beyond the code, or "None", with a link to the spec's section.
   - **Look closely at:** anything risky, uncertain or needing a second opinion.
   - **Context updated:** the context files changed.

A person reviews and merges the pull request.

## After merge

The unit is not `Done` when it is merged. Once the pipeline has deployed it to Development, or the first shared environment named in `context/modules/environments-delivery.md`:

1. Apply, or ask the person to apply, the Development actions from the Release impact section. Agents do not change shared environments without approval.
2. Recheck the acceptance criteria there, or ask the person to.
3. If anything fails that worked locally, record it in the Snag log in `context/modules/go-live.md` with its cause, then fix it as a small change or a new unit.
4. Only when the criteria pass in that environment, set the unit to `Done` in the spec and in `context/progress-tracker.md`.

## Done when

- Every check in the definition of done passes.
- Every acceptance criterion is met and its verification is recorded.
- The Release impact section matches the change.
- The context files and progress tracker are up to date.
- The pull request description is ready for review.
