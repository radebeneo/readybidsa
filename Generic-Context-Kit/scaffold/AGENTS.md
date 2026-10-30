# {{PROJECT_NAME}}: Agent Instructions

These instructions apply to every AI coding agent working in this repository, including OpenCode and GitHub Copilot. OpenCode reads this file directly, and `.github/copilot-instructions.md` points here, so the rules live in one place.

{{PROJECT_NAME}} is built for {{CLIENT_NAME}}. The full picture is in `context/project-overview.md`.

## Before any task

Read these files in order. They are the source of truth for this project. If the code and the context files disagree, stop and ask which one is right. Do not guess.

{{CONTEXT_READING_LIST}}

Read these when they are relevant to the task:

- `context/brands/`: one file per brand, covering its personality, voice, theme, logo, imagery and approved copy. Read the file for every brand that an interface or copy change affects.
- `context/modules/`: security and compliance, integrations, environments and delivery, quality and testing, operations, and go-live. Read the module that covers the area you are changing. Skip any module whose Status is `Not applicable`.
- `context/decisions/`: architecture decision records (ADRs). Check for an existing decision before you propose a change to the architecture, libraries or patterns.
- `context/specs/`: the build plan and unit specs. Work only on the unit you have been given.
- `context/HOW-TO-USE.md`: the team's guide to working with agents and these files. When a person asks how to use the workflows, what a status means or who decides something, answer from this guide and point them to it.
- `context/SKILLS-AND-COMMANDS.md`: the quick reference to every skill, Copilot command and terminal command. When a person asks which skill or command to use, answer from it and point them to it.

## How work is done

1. Work on one unit at a time, from an approved spec in `context/specs/`. If there is no spec, write one first with `context/playbooks/write-unit-spec.md` and ask for approval.
2. A small, low-risk change, such as a bug fix with a known cause or a text change, may skip the spec only if it meets every criterion in `context/playbooks/fix-small.md` and a person confirms that it qualifies. A change that touches an approval gate or a protected path never qualifies.
3. Follow `context/ai-workflow-rules.md` for scope, approval gates and things you must never do.
4. Meet the definition of done below before you report work as finished.
5. Update `context/progress-tracker.md` with what changed, what is next and any open questions.
6. If you made a decision that later work depends on, record it as an ADR with `context/playbooks/record-decision.md`.
7. Before a release to Staging or Production, prepare the release checklist with `context/playbooks/prepare-release.md`. People run the production steps and sign off.
8. Never approve or merge a pull request, deploy to Production or sign off a release. A person reviews and merges every change.

## Definition of done

A unit or small change is done only when all of the following pass:

{{VERIFY_COMMANDS}}

Also confirm that every acceptance criterion in the unit spec has been met, and say how you checked each one. For a small change, confirm that it still meets every criterion in `context/playbooks/fix-small.md`.

For a unit, confirm that the Release impact section of its spec lists everything the change needs in each environment beyond its code, such as settings, secrets, schema, content and manual steps, and that nothing in it works only on your machine.

A unit becomes `Done` only after a person has merged it, it has been deployed through the pipeline to Development or the first shared environment, and its acceptance criteria have been rechecked there. Working locally is not enough.

## Playbooks

| Task | Playbook |
| --- | --- |
| Fill in the context files for a new or existing project | `context/playbooks/setup-context.md` |
| Break the project into buildable units | `context/playbooks/plan-build.md` |
| Write a spec for one unit | `context/playbooks/write-unit-spec.md` |
| Implement an approved unit | `context/playbooks/implement-unit.md` |
| Make a small, low-risk change without a spec | `context/playbooks/fix-small.md` |
| Prepare a review of a pull request for a person | `context/playbooks/review-unit.md` |
| Prepare a release to Staging or Production, including go-live | `context/playbooks/prepare-release.md` |
| Record an architecture decision | `context/playbooks/record-decision.md` |
| Bring the context files up to date | `context/playbooks/refresh-context.md` |

## Non-negotiables

- Never commit secrets, credentials, connection strings or API keys. Use the secret store described in `context/modules/security-compliance.md`.
- Never use production data or real personal data in code, tests, fixtures, seed content or prompts. Use synthetic data.
- Get human approval before you change authentication or authorisation, add or run migrations, add or upgrade dependencies, or do anything else listed under approval gates in `context/ai-workflow-rules.md`.
- Never deploy to Production, or change Production configuration, secrets or data. People do this, following the release checklist.
- Never weaken or skip tests, linting or the context check to make a build pass.
- Keep the context files accurate. When you change something they describe, update them in the same change.
