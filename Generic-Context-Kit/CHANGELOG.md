# Changelog

All notable changes to the Context Kit are recorded here.

The kit uses semantic versioning:

- **Major:** breaking changes to the file structure, `kit.json` or the context check rules.
- **Minor:** new profiles, modules, playbooks or sections.
- **Patch:** wording changes and fixes.

Each project records the kit version it was created with in `context/kit.json`.

## 1.1.0 (2026-10-27)

### Added

- A small-change lane: `context/playbooks/fix-small.md`, with the `fix-small` skill and prompt. Bug fixes with a known cause, text changes, visual fixes using existing tokens, documentation and test-only changes can skip the unit spec if they meet every criterion and a person confirms it.
- `context/playbooks/review-unit.md`, with the `review-unit` skill and prompt. The agent prepares a review report for a person, with severities and a recommendation, and never approves, merges or posts it.
- `context/playbooks/refresh-context.md`, with the `refresh-context` skill and prompt, to bring the context files up to date in one pass. Review dates change only after the owner confirms.
- `context/playbooks/record-decision.md`, with the `record-decision` skill and prompt, to write and supersede ADRs.
- `context/brands/`, with a README and `_brand-template.md`: one file per brand for personality, voice, theme, logos, imagery and approved copy. The context check discovers and checks brand files automatically.
- A Brands affected section in the unit spec template.
- `.github/instructions/ui-brand.instructions.md` for Copilot.
- `context/modules/go-live.md`: launch scope, roles, readiness criteria, pre-launch checks, cutover plan, smoke tests, go or no-go and rollback, hypercare, rehearsal and a snag log that records each snag's cause.
- `context/playbooks/prepare-release.md`, with the `prepare-release` skill and prompt. The agent collects every unit's release impact into a checklist for Staging or Production, checks it against the diff and the environment, and lists the gaps. People run production steps and sign off.
- A Release impact section in the unit spec template, covering configuration, secrets, schema, content, integrations, feature flags, infrastructure, manual steps and rollback for each environment.
- An Environment parity table in `context/modules/environments-delivery.md`, listing each difference between Staging and Production with why it is accepted and how the risk is covered.
- A Before staging section in `context/modules/quality-testing.md`: accessibility, performance, security and deployability checks on every unit.
- A Milestones section in the build plan, including a go-live rehearsal before the first launch.
- `GUIDE.md`: a how-to guide for adopting the kit, covering prerequisites, adding the kit to a project, the first week, day-to-day use, who does what by role, releases and go-live, updating a project and troubleshooting.
- `context/HOW-TO-USE.md`, copied into every project: the team's guide to the workflows and how to start them in OpenCode and Copilot, unit statuses, what to check in a spec, the small-change lane, what agents will not do, a section for each role, the context check messages, recording snags and common questions. `AGENTS.md` points agents to it when people ask how to work, and `eck init` suggests sharing it with the team.
- `context/SKILLS-AND-COMMANDS.md`, copied into every project: a quick reference to every skill and its Copilot command, the kit skill, the context check and the `eck` commands, with what each one does, when to use it and when not to, how to start it, what to give it and what people decide. `AGENTS.md`, `context/README.md`, both guides, the kit skill and `eck init` point to it.
- The kit can be run straight from its Bitbucket repository with `npx`, or installed with `npm install --global`, without cloning it. `package.json` lists the files to install, and `.gitattributes` keeps LF line endings in the scripts so `eck` also runs on macOS.
- `GUIDE.md` explains that the kit is a one-time copier, with a diagram, who does what and how updates reach a project. It also explains who needs the kit, the three ways to run it, the differences between a new project and an existing repository, and how to merge the context check into an existing `bitbucket-pipelines.yml`. `context/HOW-TO-USE.md` answers whether developers need the kit and which kit version a project uses.
- Tests for brand files, the brand gates, the staging and go-live files, the team guides, the skill and command reference, and the wiring of every workflow (skill, playbook, prompt and entry points).

### Changed

- `context/ui-context.md` now has a Brands table and a Design tokens section that names the token source, its structure, theming and breakpoints. Context files link to the token source instead of copying values.
- `context/ai-workflow-rules.md` adds approval gates for design token values, themes, logos, approved brand copy and brand files, and forbids copying token values and approving or merging pull requests.
- `AGENTS.md` and `.github/copilot-instructions.md` list all nine workflows, the small-change lane and the brand files.
- The definition of done in `AGENTS.md` now requires a complete Release impact section, and a unit becomes `Done` only after it has been deployed to the first shared environment and rechecked there. Agents never deploy to Production or sign off a release.
- `implement-unit.md` keeps the release impact current during the build and adds an After merge step. `review-unit.md` treats missing release impact as a blocking finding. `write-unit-spec.md` fills in the release impact and checks the snag log. `refresh-context.md` turns repeated snag causes into rules and checks.
- `plan-build.md` starts every build with a production-like deployment unit and plans regular releases to Staging, client acceptance, a go-live rehearsal and hypercare.
- The small-change lane now requires that a change has no release impact.
- `context/ai-workflow-rules.md` adds approval gates for deploying to, or changing, shared environments, and forbids deploying to Production or signing off a release.
- The context check's default file list includes `context/modules/go-live.md`.
- The context check now says "1 FILL comment remains" rather than "1 FILL comment remain".
- The next steps printed by `eck init` point to the pipeline step in `context/modules/environments-delivery.md`, not to a file inside the kit, which may be in npm's cache.
- The setup playbook now has a Who provides what table showing which facts come from people, which the agent drafts from the codebase, and who confirms each one.

## 1.0.0 (2026-10-27)

### Added

- `eck init` to add the scaffold to new or existing repositories, either interactively or with flags. Existing files are never overwritten unless `--force` is used; the kit's version is written alongside as a `.kit-new` copy.
- `eck check` and the standalone `context/check-context.mjs`, which report missing files, unfilled sections, unresolved placeholders, likely secrets, overdue reviews and draft files.
- Core context files: project overview, architecture, code standards, UI context, AI workflow rules and progress tracker.
- Enterprise modules: security and compliance, environments and delivery (Bitbucket), integrations, quality and testing, and operations.
- Decision records (ADRs), a build plan and a unit spec template.
- Playbooks for context setup, build planning, writing unit specs and implementing units.
- Agent entry points: `AGENTS.md` (OpenCode) and `.github/copilot-instructions.md` (GitHub Copilot).
- Copilot instructions scoped to file types in `.github/instructions/`.
- Workflow wrappers: skills in `.agents/skills/` (OpenCode and Copilot) and prompt files in `.github/prompts/` (Copilot).
- Profiles: `generic`, the stack-neutral default. New profiles extend it.
- A Bitbucket Pipelines step for the context check.
- A kit-level OpenCode skill in `skills/enterprise-context-kit/` that adds the kit to a repository when asked.
- `README.md` and `METHODOLOGY.md`.
- A test suite for the CLI, the token rules and the context check (`npm test`).
