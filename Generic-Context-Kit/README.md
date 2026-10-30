# Context Kit

A plug-and-play scaffold that gives AI coding agents the context they need to work safely on enterprise solution projects. Add it to a new or existing repository with one command. OpenCode and GitHub Copilot then both follow the same project rules, workflows and approval gates.

The kit is stack-neutral. It ships with a `generic` profile, and you can add profiles for the stacks your team uses. Its tools need only Node.js 20 or later and run on Windows and macOS.

- **New to the kit?** Start with [GUIDE.md](GUIDE.md). It walks the whole team through adopting the kit, the first week on a project, who does what and how releases work.
- **Working on a project that already has the kit?** Read `context/HOW-TO-USE.md` in that project. `context/SKILLS-AND-COMMANDS.md` lists every skill and command, and when to use each one.
- **Why the kit is structured this way** is explained in [METHODOLOGY.md](METHODOLOGY.md).

## Quick start

Run the kit straight from its Bitbucket repository. Replace `<workspace>` with the workspace that holds the kit, and `v1.1.0` with the release you want:

```bash
npx --yes "git+https://bitbucket.org/<workspace>/enterprise-context-kit.git#v1.1.0" init <path-to-your-repo>
```

Or, from a clone of the kit:

```bash
node tools/eck.mjs init <path-to-your-repo>
```

`init` asks for the project name, client, context owner and profile. To skip the questions:

```bash
node tools/eck.mjs init <path-to-your-repo> --yes --profile generic --name "Client Site" --client "Client name" --owner "Technical lead"
```

Then:

1. Open the repository in OpenCode or Copilot and ask the agent to set up the context. In Copilot Chat you can run `/setup-context`.
2. Add the step from [`ci/bitbucket-pipelines.context-check.yml`](ci/bitbucket-pipelines.context-check.yml) to the project's `bitbucket-pipelines.yml`. [GUIDE.md](GUIDE.md) explains how to merge it into an existing file.
3. Run `node context/check-context.mjs`, then commit the new files.

`init` never overwrites an existing file. If a file already exists and differs, the kit's version is written beside it as `<file>.kit-new` for you to merge. Use `--force` to overwrite instead, or `--dry-run` to see what would change.

## Commands

| Command | What it does |
| --- | --- |
| `eck init [folder]` | Adds the scaffold to a repository. Options: `--name`, `--client`, `--owner`, `--profile`, `--review-days`, `--yes`, `--force`, `--dry-run` |
| `eck check [folder]` | Checks the context files. Options: `--strict` (warnings also fail), `--json` |
| `eck list` | Lists the stack profiles |

Run `node <kit folder>/tools/eck.mjs <command>` from a clone, or `npx --yes "<kit git URL>#<tag>" <command>` straight from Bitbucket. To get a permanent `eck` command, run `npm install --global "<kit git URL>#<tag>"`, or `npm link` in a clone.

## What gets added

```text
AGENTS.md                         Main instructions for every agent
.agents/skills/                   Workflow skills (OpenCode and Copilot)
.github/
  copilot-instructions.md         Copilot entry point; points to AGENTS.md
  instructions/                   Copilot instructions scoped to file types
  prompts/                        Copilot prompt files for the workflows
context/
  HOW-TO-USE.md                   Team guide: workflows, statuses, roles and checks
  SKILLS-AND-COMMANDS.md          Quick reference: every skill and command, and when to use it
  project-overview.md             What is being built, for whom and why
  architecture.md                 Stack, structure and boundaries
  code-standards.md               How code is written
  ui-context.md                   How the product looks and behaves
  ai-workflow-rules.md            Scope, approval gates and things agents must never do
  progress-tracker.md             Current state of the build
  brands/                         One file per brand: personality, voice, theme,
                                  logo, imagery and approved copy
  modules/                        Security and compliance, integrations, environments
                                  and delivery, quality and testing, operations,
                                  go-live (with the snag log)
  decisions/                      Architecture decision records (ADRs)
  specs/                          Build plan and one spec per unit of work
  playbooks/                      The nine workflows, step by step
  check-context.mjs               The context check (Node built-ins only)
  kit.json                        Kit version, profile and the files to check
```

Profiles can add files, for example a stack-specific context file in `context/` and matching Copilot instructions in `.github/instructions/`.

## How each tool finds the context

| Tool | Reads | Workflows |
| --- | --- | --- |
| OpenCode | `AGENTS.md` | Skills in `.agents/skills/` |
| GitHub Copilot | `.github/copilot-instructions.md` and `.github/instructions/` | Prompt files in `.github/prompts/` and skills in `.agents/skills/` |

The skills folder is `.agents/skills/`, a tool-neutral location that both OpenCode and Copilot search. No other tool is needed.

The rules live once, in `AGENTS.md` and `context/`. The workflows live once, in `context/playbooks/`. The skills and prompt files are thin wrappers that point to the playbooks, so updating a playbook updates every tool.

## The workflow

| Step | Playbook | Skill or prompt |
| --- | --- | --- |
| 1. Fill in the context files | `context/playbooks/setup-context.md` | `setup-context` |
| 2. Break the project into units | `context/playbooks/plan-build.md` | `plan-build` |
| 3. Write a spec for the next unit | `context/playbooks/write-unit-spec.md` | `write-unit-spec` |
| 4. Implement the approved unit | `context/playbooks/implement-unit.md` | `implement-unit` |

Repeat steps 3 and 4 for each unit. A person approves every spec and reviews every pull request.

These workflows support the cycle:

| Task | Playbook | Skill or prompt |
| --- | --- | --- |
| Make a small, low-risk change without a spec | `context/playbooks/fix-small.md` | `fix-small` |
| Prepare a review of a pull request for a person | `context/playbooks/review-unit.md` | `review-unit` |
| Prepare a release to Staging or Production, including go-live | `context/playbooks/prepare-release.md` | `prepare-release` |
| Record an architecture decision | `context/playbooks/record-decision.md` | `record-decision` |
| Bring the context files up to date | `context/playbooks/refresh-context.md` | `refresh-context` |

The small-change lane is for bug fixes with a known cause, text changes, visual fixes that use existing tokens, documentation and test-only changes. A change qualifies only if it meets every criterion in `fix-small.md`, has no release impact, touches no approval gate or protected path, and a person confirms that it qualifies. Agents prepare reviews but never approve, merge or post them.

## Fewer snags at staging and go-live

Snags cannot be eliminated, but most of them have the same few causes: a setting, secret or manual step nobody wrote down, a difference between Staging and Production nobody accepted, a one-off go-live step that was never rehearsed, or a check left until the end. The kit moves each of these earlier in the build:

| What | Where | How it helps |
| --- | --- | --- |
| Release impact | Every unit spec | Settings, secrets, schema, content, integrations, flags, infrastructure, manual steps and rollback limits are recorded per environment as the unit is built. Reviews treat a missing item as blocking. |
| Done means deployed | `AGENTS.md`, `implement-unit.md` | A unit is `Done` only once it has been deployed to the first shared environment and its acceptance criteria rechecked there. |
| Environment parity | `context/modules/environments-delivery.md` | Every difference between Staging and Production is listed, with why it is accepted and how the risk is covered. |
| Before staging checks | `context/modules/quality-testing.md` | Accessibility, performance, security and deployability checks run on every unit, not only before a release. |
| Production-like first unit | `plan-build.md`, `00-build-plan.md` | Unit 01 deploys a minimal solution through the pipeline to every environment, and the plan includes a go-live rehearsal milestone. |
| Release checklist | `prepare-release.md` | The agent collects every unit's release impact, checks it against the diff and the environment, and lists the gaps. People run production steps and sign off. |
| Go-live plan | `context/modules/go-live.md` | Readiness criteria, pre-launch checks, cutover plan, smoke tests, rollback, hypercare and the rehearsal. |
| Snag log | `context/modules/go-live.md` | Every snag found after merge is recorded with its cause. `refresh-context.md` turns repeated causes into rules, checks or acceptance criteria. |

## Brands and design tokens

Each brand the project presents has a file in `context/brands/`, copied from `_brand-template.md`. It records the brand's personality, voice, words to use and avoid, theme, logos, imagery and approved copy such as claims and disclaimers. The design system that every brand shares is in `context/ui-context.md`, which also names the design token source.

Context files never contain token values such as hex codes. They name the theme and link to the token source, so there is only one place to change a colour. Changing token values, themes, logos or approved brand copy is an approval gate.

## The context check

`node context/check-context.mjs` runs on every pull request. It fails on:

- missing context files or entry points
- unresolved `{{TOKEN}}` placeholders
- files marked `Active` that still contain `FILL` comments
- unknown statuses or invalid review dates
- likely secrets, such as private keys, cloud access keys, tokens and passwords in connection strings

It warns about files still in `Draft`, missing owners and reviews older than the review period (90 days by default). Use `--strict` to fail on warnings too.

Brand files in `context/brands/` are checked like the other context files. The template (`_brand-template.md`) and `README.md` are skipped.

## Profiles

| Profile | Use for |
| --- | --- |
| `generic` (default) | Any stack |

A profile supplies verify commands, extra approval gates, protected paths and schema promotion rules, and can add or replace files. To add one, see [profiles/README.md](profiles/README.md).

## Distributing the kit

- **Bitbucket:** keep the kit in its own repository, and tag a release for each version in `CHANGELOG.md`. The person adding the kit to a project runs it straight from Bitbucket with `npx`, or from a clone. Nobody else on the project needs it. "Who needs the kit" and "Running the kit" in [GUIDE.md](GUIDE.md) explain both.
- **OpenCode skill:** the kit includes a skill in [`skills/enterprise-context-kit/`](skills/enterprise-context-kit/SKILL.md) that adds the kit to a repository when asked. Add the kit's `skills` folder to the `skills` array in your OpenCode config:

  ```jsonc
  { "skills": ["C:/path/to/enterprise-context-kit/skills"] }
  ```

  Then ask OpenCode to "add the context kit to this repository".
- **Copilot Enterprise:** no extra setup. Copilot picks up `.github/copilot-instructions.md`, `.github/instructions/` and `.github/prompts/` from each repository.

## Updating a project to a newer kit

Run `eck init` again on the project. Files the kit has not changed are left alone. Files that differ, including any you have filled in, get a `.kit-new` copy to compare and merge. `context/check-context.mjs` can usually be replaced outright. Update `kitVersion` in `context/kit.json` once you have merged.

## Working on the kit

- Read [AGENTS.md](AGENTS.md) for the maintenance rules.
- Run `npm test` after every change.
- Record changes in [CHANGELOG.md](CHANGELOG.md) and bump `version` in `package.json` when releasing.
