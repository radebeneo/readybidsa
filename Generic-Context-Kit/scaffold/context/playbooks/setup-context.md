# Playbook: Set Up the Context Files

Use this playbook to fill in the context files for a new project, or for an existing codebase that has just had the kit added. The goal is a set of short, accurate files that any agent or new team member can rely on.

## Who provides what

The agent drafts. People supply the facts and confirm them. The agent never invents a fact to fill a gap.

| Information | Who provides it | How |
| --- | --- | --- |
| Project name, client, context owner, stack profile | The developer running `eck init` | Prompts or flags at init |
| Goals, audience, scope, out of scope, success measures | Delivery lead or client lead | Brief, statement of work, proposal or kickoff notes |
| Stack, hosting, environments, pipelines | Technical lead | Conversation, or the agent reads the existing codebase |
| Code conventions | Technical lead | The agent infers them from existing code; the lead confirms |
| Brands, themes, voice and the design token source | Design lead and brand owner | Design system, brand guidelines or the token repository |
| Security, compliance and data rules | Client security contact or technical lead | Client security requirements |
| Integrations and operations | Technical lead | Integration list, runbooks or support model |
| Owner and review date for each file | The agent proposes; the owner confirms | During setup |

For an existing codebase, the agent can draft most of the architecture, code standards, environments and integrations by reading the code. A person must still confirm each draft. For a new project, most facts come from people and documents.

## Inputs

Ask the person running this playbook for whatever they have, for example:

- the brief, statement of work or proposal
- designs, a design system or brand guidelines
- an existing codebase, if there is one
- notes from kickoff or discovery workshops
- the client's security, brand or hosting requirements

Anything nobody can answer yet goes in the Open questions list in `context/progress-tracker.md`, with the person or role who should answer it.

Never ask for, or accept, secrets, credentials or production data. If someone pastes them, tell them to remove the material and rotate any secret involved.

## Steps

1. **Check what exists.** Run `node context/check-context.mjs` to see which files still need content. Read `context/kit.json` to see which profile was used.
2. **Read the source material** the person provides. For an existing codebase, also inspect it: solution and project files, package manifests, configuration files, pipeline YAML, folder structure and a few representative source files.
3. **Fill in one file at a time**, in this order:
   1. `context/project-overview.md`
   2. `context/architecture.md`
   3. `context/code-standards.md`
   4. `context/ui-context.md`, including the Brands table and the design token source
   5. one file per brand in `context/brands/`, copied from `_brand-template.md` and confirmed by the brand owner
   6. `context/ai-workflow-rules.md` (add project rules only; keep the defaults)
   7. the files in `context/modules/`
   8. any extra context files the profile added, listed in `AGENTS.md`
4. **For each file:**
   - Replace every `FILL` comment with real content, then delete the comment.
   - Keep the header block. Set Owner to a person or role, and Last reviewed to today's date.
   - Write only what you know. Where the source material does not answer a question, add it to the Open questions list in `context/progress-tracker.md` and leave the `FILL` comment in place.
   - Describe what the codebase actually does, not what it should ideally do. Note gaps as open questions.
   - Keep it short. Bullet points and tables are better than paragraphs.
   - Show the person the draft and ask them to confirm or correct it before you move on.
5. **Set Status.** When a file has no `FILL` comments left and the person has confirmed it, set Status to `Active`. If a module does not apply to this project, set its Status to `Not applicable` and delete its sections.
6. **Record decisions.** If a choice already made is significant (for example the CMS, hosting platform or front-end approach), write an ADR with `context/playbooks/record-decision.md` so it is not reopened later.
7. **Check again.** Run `node context/check-context.mjs` and fix what it reports. Warnings for files still in `Draft` are acceptable only while their open questions are being answered.
8. **Update the tracker.** In `context/progress-tracker.md`, record what was set up, the open questions and the next step, which is usually `context/playbooks/plan-build.md`.

## Rules

- Do not invent facts. A blank section with an open question is better than a confident guess.
- Do not copy large blocks from the source material. Summarise it and link to the original.
- Never put secrets, personal contact details or production data in a context file.
- Keep each fact in one file. Link to it from others rather than repeating it.
- Never copy design token values such as hex codes into a context or brand file. Name the theme and link to the token source.

## Done when

- `node context/check-context.mjs` reports no errors.
- Every core file is `Active`, and every module is `Active` or `Not applicable`.
- Every brand the project presents has an `Active` file in `context/brands/`.
- The person has confirmed each file.
- Remaining open questions are listed in `context/progress-tracker.md`.
