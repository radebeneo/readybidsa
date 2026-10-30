# Skills and Commands on {{PROJECT_NAME}}

This is the quick reference for every skill, Copilot command and terminal command that the context kit adds to {{PROJECT_NAME}}. For each one it covers what it does, when to use it and when not to, and where to run it.

For how the build works from start to finish, and who decides what, read `context/HOW-TO-USE.md`.

## How to start a skill

Each workflow is a **skill**. You can start the same skill from OpenCode or from GitHub Copilot. Both follow the same playbook in `context/playbooks/`, so the result is the same whichever tool you use.

| Where | How | Example |
| --- | --- | --- |
| OpenCode | Describe the task in plain words. OpenCode picks the matching skill from `.agents/skills/`. You can also name the skill. | "Implement unit 03", or "Use the implement-unit skill for unit 03" |
| Copilot Chat | Type `/` and the command name. The prompt file in `.github/prompts/` asks for anything else it needs. | `/implement-unit`, then answer "03" |

Tips:

- **One skill per conversation.** Start a new conversation for each unit or workflow.
- **Not sure which skill fits?** Describe the task. The agent will suggest the right skill, or tell you the change needs a spec.
- **Approvals still apply.** Whichever skill you use, the agent stops and asks before anything that needs approval, and it never approves, merges, deploys to Production or signs off a release.

## At a glance

| Skill | Copilot command | What it does | Use it when | Usually started by |
| --- | --- | --- | --- | --- |
| `setup-context` | `/setup-context` | Fills in the context files from your documents and the code | The kit has just been added, or a new brand or module needs a file | Technical lead |
| `plan-build` | `/plan-build` | Breaks the project into ordered units and milestones | The context is set up, or the scope has changed significantly | Technical lead, with the delivery lead |
| `write-unit-spec` | `/write-unit-spec` | Writes the spec for one unit | A unit is next in the build plan | Developer |
| `implement-unit` | `/implement-unit` | Builds an approved unit and prepares the pull request | The unit's spec is `Ready` | Developer |
| `fix-small` | `/fix-small` | Makes a small, low-risk change without a spec | A bug fix with a known cause, a text change or similar | Developer |
| `review-unit` | `/review-unit` | Prepares a review report of a pull request for a person | A pull request is waiting for review | Reviewer |
| `prepare-release` | `/prepare-release` | Prepares the release checklist for Staging or Production | A release or go-live is planned | Technical lead or release manager |
| `record-decision` | `/record-decision` | Writes an architecture decision record (ADR) | A significant decision has been made, or needs to change | Technical lead |
| `refresh-context` | `/refresh-context` | Brings the context files up to date | Reviews are overdue, after a release, or after a large change | Technical lead or file owners |

The usual order on a build is:

1. `setup-context`, once
2. `plan-build`, once, then again when scope changes
3. For each unit: `write-unit-spec`, then `implement-unit`, then `review-unit`
4. `prepare-release` before each release to Staging or Production
5. `refresh-context` after each release

Use `fix-small` and `record-decision` whenever they are needed.

## Which one do I need?

| If you want to | Use |
| --- | --- |
| Start using the kit on this project | `setup-context` |
| Add a file for a new brand, or fill in a module that was skipped | `setup-context` |
| Turn the scope into a list of units | `plan-build` |
| Re-plan after the scope changed | `plan-build` |
| Build something new, however small | `write-unit-spec`, then `implement-unit` |
| Fix a typo, a label or a bug whose cause you know | `fix-small`, if it meets every criterion |
| Check a pull request before you approve it | `review-unit` |
| Get ready to deploy to Staging or Production, or to go live | `prepare-release` |
| Fix something found after merge, in Staging or at go-live | Record it in the snag log, then `fix-small` or a new unit spec |
| Choose between technical options, or change an earlier decision | `record-decision` |
| Bring the files up to date after a release or a large change | `refresh-context` |
| Check that the context files are complete and safe | `node context/check-context.mjs` |
| Add the kit to another repository, or update to a newer kit | The `enterprise-context-kit` skill, or the `init` kit command below |

## The skills

### `setup-context`

**What it does:** Drafts each context file, one at a time, from the documents you give it and from the existing code. It asks the right person to confirm each draft before moving on. Anything nobody can answer yet goes in the Open questions list in `context/progress-tracker.md`. Significant choices already made, such as the hosting platform, are recorded as ADRs.

**Use it when:**

- the kit has just been added to the repository
- a new brand needs a file in `context/brands/`
- a module that was skipped now applies to the project

**Do not use it when:** the files are already set up and only need bringing up to date. Use `refresh-context` instead.

**Start it:**

- OpenCode: "Set up the context files"
- Copilot: `/setup-context`, which asks for the source material

**Give it:** the brief, statement of work or proposal, designs, the design system and design token source, brand guidelines, kickoff notes, and the client's security and hosting requirements. Never give it secrets, credentials or production data.

**You decide:** each file's owner confirms its content. When a file has no `FILL` comments left and is confirmed, its Status is set to `Active`, or `Not applicable` for a module that does not apply.

**Finished when:** the context check reports no errors, every core file is `Active`, every module is `Active` or `Not applicable`, and every brand has an `Active` file.

**Playbook:** `context/playbooks/setup-context.md`

### `plan-build`

**What it does:** Breaks the project into small, ordered units of work and writes `context/specs/00-build-plan.md`. Unit 01 is always a minimal solution deployed through the pipeline to every environment. The plan includes milestones for regular releases to Staging, client acceptance, a go-live rehearsal and hypercare. Every unit is added to `context/progress-tracker.md` as `Not started`.

**Use it when:**

- the core context files are `Active`
- the scope changes significantly

**Do not use it when:**

- you want to write a spec. Specs are written one at a time with `write-unit-spec`, just before each unit is built.
- you want to add a small fix. Small fixes go through `fix-small` and are not units.

**Start it:**

- OpenCode: "Plan the build"
- Copilot: `/plan-build`

**You decide:** the order, the scope of each unit, the release milestones and anything missing. The plan becomes `Active` once you approve it.

**Playbook:** `context/playbooks/plan-build.md`

### `write-unit-spec`

**What it does:** Writes the spec for one unit in `context/specs/`, from the unit spec template. The spec covers the goal, scope, brands affected, approach, files likely to change, approval gates, release impact, acceptance criteria and tests. The agent checks the snag log for problems in the same area and adds acceptance criteria that would catch them again.

**Use it when:** a unit is next in the build plan and the units it depends on are `Done`.

**Do not use it when:**

- there is no build plan yet. Run `plan-build` first.
- the change is small enough for `fix-small`. The agent will suggest it.

**Start it:**

- OpenCode: "Write the spec for unit 03"
- Copilot: `/write-unit-spec`, which asks for the unit number. Leave it blank for the next unit.

**You decide:** whether to approve the spec. Check that every acceptance criterion can be tested and that the Release impact section is complete. Once approved, the unit is `Ready`.

**Playbook:** `context/playbooks/write-unit-spec.md`

### `implement-unit`

**What it does:** Builds one unit from its approved spec. The agent:

- checks that the spec is `Ready` and its dependencies are `Done`
- tells you its plan before it changes code
- writes the tests alongside the code
- keeps the Release impact section current as it builds
- runs the definition of done, the Before staging checks and the context check
- updates the context files and progress tracker
- writes the pull request description

After merge, it helps recheck the unit in the first shared environment. Only then is the unit `Done`.

**Use it when:** the unit's spec is `Ready`.

**Do not use it when:** there is no spec, or the spec is not `Ready`. Use `write-unit-spec` first.

**Start it:**

- OpenCode: "Implement unit 03"
- Copilot: `/implement-unit`, which asks for the unit number

**You decide:** whether to agree to the plan and to any approval gates. A person reviews and merges the pull request, applies or approves any actions in shared environments, and confirms the recheck.

**Playbook:** `context/playbooks/implement-unit.md`

### `fix-small`

**What it does:** Checks that a change qualifies as small and asks you to confirm it. For a bug fix, it writes a test that fails because of the bug. It then makes the smallest change that works, runs every check and writes the pull request description.

**Use it when** the change is one of these, and meets every criterion in the playbook:

- a bug fix whose cause and expected behaviour are clear
- a change to text, labels or translations
- a visual fix that uses existing design tokens and components
- a documentation or code comment change
- a test-only change that adds coverage

**Do not use it when** the change:

- adds anything new: a page, component, block, document type, endpoint, integration, setting or dependency
- needs anything in any environment beyond the code, such as a setting, secret, schema change, content or manual step
- touches an approval gate or a protected path, including brand tokens, logos and approved brand copy
- changes security, personal data handling or behaviour other units rely on

If you are unsure, write a spec instead.

**Start it:**

- OpenCode: "Small fix: the footer link to the privacy page is broken"
- Copilot: `/fix-small`, which asks what needs fixing

**You decide:** whether the change qualifies. A person reviews and merges the pull request.

**Playbook:** `context/playbooks/fix-small.md`

### `review-unit`

**What it does:** Prepares a review of a pull request or branch for a person to act on. It checks the scope, the approval gates, the evidence for each acceptance criterion and the release impact against the diff. It runs the checks and reads the code, then writes a report with findings by severity and a recommendation. It never approves, declines or merges a pull request, and never posts comments unless the reviewer asks.

**Use it when:** a pull request is waiting for review. This applies whether an agent or a developer wrote it, and includes small changes and release fixes.

**Do not use it when:** you want the code changed. Fixes the reviewer asks for are a separate change.

**Start it:**

- OpenCode: "Review branch feature/03-search against develop"
- Copilot: `/review-unit`, which asks for the branch, pull request or unit

**Give it:** the branch and the branch it merges into, and the pull request description if you have it.

**You decide:** the outcome. The recommendation is advice. The reviewer is responsible for what they approve. A missing or incomplete Release impact section is a blocking finding.

**Playbook:** `context/playbooks/review-unit.md`

### `prepare-release`

**What it does:** Prepares a release checklist for Staging or Production, including the first go-live. The agent:

- lists every unit and change in the release, and flags any that are not `Done`
- collects every unit's release impact, grouped into before, during and after deployment
- checks the diff for anything no spec lists
- checks the target environment against the Environment parity table
- for Production, checks the readiness criteria and the rehearsal
- prepares the smoke tests and the rollback

It then walks through every gap with you. After the release, it records the release in the progress tracker and every snag in the snag log.

**Use it when:**

- before every release to Staging
- before every release to Production, including the first go-live
- before the go-live rehearsal

**Do not use it when:** you want something deployed. Agents never deploy to Production or change Production configuration, secrets or data, and they ask before changing any shared environment.

**Start it:**

- OpenCode: "Prepare the release to Staging for units 03 to 06"
- Copilot: `/prepare-release`, which asks for the target environment and what is in the release

**Give it:** the target environment, what is in the release, and the planned date and time with the time zone.

**You decide:** whether each gap blocks the release, and go or no-go. People run the production steps and sign off.

**Playbook:** `context/playbooks/prepare-release.md`

### `record-decision`

**What it does:** Checks the existing decisions in `context/decisions/`, then drafts an ADR that describes the problem, the options, including their disadvantages, and the decision. The ADR starts as `Proposed`. Once a person accepts it, the agent adds it to the index and updates the context files it affects. If it replaces an earlier decision, the old ADR is marked as superseded.

**Use it when:**

- a significant decision has been made that later work depends on, for example the hosting platform, the front-end approach or a caching strategy
- an accepted decision needs to change

**Do not use it when:** the choice is easy to reverse and affects only one unit. Record it in that unit's spec instead.

**Start it:**

- OpenCode: "Record a decision about how we cache search results"
- Copilot: `/record-decision`, which asks for the decision to record

**You decide:** only a person sets an ADR to `Accepted` or `Rejected`.

**Playbook:** `context/playbooks/record-decision.md`

### `refresh-context`

**What it does:** Finds files that are overdue for review, still in `Draft`, missing an owner or reporting errors. It reads the snag log and proposes a rule, check or acceptance criterion for every repeated cause. It then compares each file in scope with the project as it is today and proposes edits. Edits are applied, and review dates changed, only after the owner confirms. The refresh goes in one pull request.

**Use it when:**

- the context check reports overdue reviews
- after each release
- before a new phase of work
- after a large change
- when people join or leave the team

**Do not use it when:** the project is being set up for the first time. Use `setup-context` instead.

**Start it:**

- OpenCode: "Refresh the context files"
- Copilot: `/refresh-context`, which asks which files to refresh. Leave it blank for everything the context check reports.

**You decide:** each file's owner confirms the edits, or confirms the file is still accurate.

**Playbook:** `context/playbooks/refresh-context.md`

## The kit skill: `enterprise-context-kit`

This skill lives in the kit repository, not in this one. It is available in OpenCode once the kit's `skills` folder has been added to your OpenCode configuration. The kit's `GUIDE.md` explains how.

**What it does:** Adds the kit to a repository, updates a repository to a newer kit version, or runs the context check. It asks for the project name, client, context owner and profile, shows a dry run, and waits for your agreement before it writes anything.

**Use it when:**

- adding the kit to a new or existing repository
- updating a repository to a newer kit version

**Do not use it for** day-to-day work on this project. Use the workflow skills above.

**Start it** in OpenCode: "Add the context kit to this repository" or "Run the context check".

In Copilot there is no equivalent. Run the kit commands below instead.

## Terminal commands

### The context check

Run this from the root of this repository. It needs Node.js 20 or later and nothing else.

```bash
node context/check-context.mjs
```

| Option | What it does |
| --- | --- |
| `--strict` | Fails on warnings as well as errors |
| `--json` | Prints the result as JSON |
| `--root <folder>` | Checks another folder instead of this repository |

It exits with `0` when the check passes, `1` when it fails and `2` when it could not run.

**Use it:**

- during setup, to see which files still need content
- before you open a pull request that changes any context file
- after fixing anything it reported

It also runs on every pull request in Bitbucket Pipelines. What each message means, and what to do about it, is in `context/HOW-TO-USE.md`.

Do not edit `context/check-context.mjs`. It is updated from the kit.

### Kit commands

These commands belong to the kit, not to this repository. Only the person adding the kit to a repository, or updating one to a newer kit, needs them. Run them in one of these ways:

- from a clone of the kit, as shown below
- straight from the kit's Bitbucket repository, by replacing `node tools/eck.mjs` with `npx --yes "git+https://bitbucket.org/<workspace>/enterprise-context-kit.git#<tag>"`
- as `eck`, if the kit has been installed with `npm install --global` or `npm link`

`GUIDE.md` in the kit explains each way.

| Command | What it does | Use it when |
| --- | --- | --- |
| `node tools/eck.mjs init <folder>` | Adds the kit to a repository. Existing files are kept, and the kit's version is written beside them as `.kit-new` | Adding the kit to a repository, or updating one to a newer kit version |
| `node tools/eck.mjs check <folder>` | Checks a repository's context files, like the context check | The repository has no copy of `context/check-context.mjs` |
| `node tools/eck.mjs list` | Lists the stack profiles | Choosing a profile before `init` |
| `node tools/eck.mjs help` | Shows every command and option. `--help` and `-h` do the same. | You need a reminder |
| `node tools/eck.mjs --version` | Prints the kit version. `-v` does the same. | Checking which version you have |

Options for `init`:

| Option | What it does |
| --- | --- |
| `--name <text>` | Project name. Defaults to the folder name. |
| `--client <text>` | Client name. Defaults to `TBC`. |
| `--owner <text>` | Person or role that owns the context files. Defaults to `TBC`. |
| `--profile <id>` | Stack profile: `generic` (default) or any profile your team has added |
| `--review-days <n>` | Days between context reviews. Defaults to 90. |
| `--yes`, `-y` | Asks no questions and uses the options given, with defaults for the rest |
| `--dry-run` | Shows what would change without writing anything. Run this first. |
| `--force` | Overwrites existing files instead of writing `.kit-new` copies. Use only when you are sure. |

`check` also accepts `--strict` and `--json`.

## Where things live

| What | Where |
| --- | --- |
| Skills, used by OpenCode and Copilot | `.agents/skills/<skill name>/SKILL.md` |
| Copilot commands | `.github/prompts/<skill name>.prompt.md` |
| Playbooks: the steps every skill follows | `context/playbooks/<skill name>.md` |
| The context check | `context/check-context.mjs` |
| The kit skill and the kit commands | The kit repository |

The skills and Copilot commands only point to the playbooks. To change how a workflow works, change its playbook, and every tool follows the change.
