# Context

This folder is the project's shared memory for people and AI agents. Agents read it before every task; people keep it accurate.

It was created with the Context Kit {{KIT_VERSION}} using the {{PROFILE_NAME}} profile. The details are in `kit.json`.

## What is here

| Path | Purpose |
| --- | --- |
| `HOW-TO-USE.md` | How the team works with the agents and these files: workflows, statuses, roles and checks. Start here. |
| `SKILLS-AND-COMMANDS.md` | Quick reference: every skill, Copilot command and terminal command, what it does, and where and when to use it |
| `project-overview.md` | What is being built, for whom and why |
| `architecture.md` | The stack, structure and boundaries |
| `code-standards.md` | How code is written |
| `ui-context.md` | How the product looks and behaves |
| `ai-workflow-rules.md` | What agents may do, what needs approval, and what they must never do |
| `progress-tracker.md` | The current state of the build |
| `brands/` | One file per brand: personality, voice, theme, logo, imagery and approved copy |
| `modules/` | Enterprise topics: security and compliance, integrations, environments and delivery, quality and testing, operations, go-live |
| `decisions/` | Architecture decision records |
| `specs/` | The build plan and one spec per unit of work |
| `playbooks/` | Step-by-step workflows that agents follow: set up, plan, specify, implement, small changes, review, releases, decisions and refreshing the context |
| `check-context.mjs` | Checks that the files are complete and safe |

## Keeping it accurate

- Update a context file in the same pull request as the change that makes it out of date.
- Each file has an Owner and a Last reviewed date. Owners review their files at least every {{REVIEW_DAYS}} days, and the check warns when a review is overdue. Brand files in `brands/` follow the same rule.
- To bring the files up to date in one pass, use `playbooks/refresh-context.md`.
- Never put secrets, personal data or production data in these files.

## Checking

Run this from the repository root:

```bash
node context/check-context.mjs
```

It needs Node.js 20 or later and nothing else. It runs on every pull request in Bitbucket Pipelines.
