# How to Use the Context Kit

This guide takes a team from "we have heard of the kit" to a project where every agent works from the same facts, rules and workflows. It is written for the whole team, with a section for each role.

- **This guide** covers adopting the kit: installing it, adding it to a project, the first week, and keeping projects up to date.
- **`context/HOW-TO-USE.md`**, which `eck init` copies into every project, covers day-to-day use: which workflow to ask for, what each status means, what to check and who decides what. Point the project team to that file once the kit is in place.
- **`context/SKILLS-AND-COMMANDS.md`**, also copied into every project, is the quick reference to every skill, Copilot command and terminal command: what each one does, and where and when to use it.
- **[README.md](README.md)** is the reference for commands and files. **[METHODOLOGY.md](METHODOLOGY.md)** explains why the kit works the way it does.

## What the kit does

AI agents are only as good as the facts they are given. On an enterprise build, most expensive mistakes are not bad code. They are a missing requirement, a setting nobody wrote down, a difference between Staging and Production, or a go-live step that was never rehearsed. These are the snags that turn up at staging and go-live.

The kit gives every project:

- **Context files** in `context/` that hold the project's facts: goals, architecture, standards, design, brands, security, integrations, environments, testing, operations and go-live.
- **One entry point**, `AGENTS.md`, that OpenCode reads directly and Copilot is pointed to, so both tools follow the same rules.
- **Nine workflows**, written once as playbooks in `context/playbooks/`, and started from OpenCode or Copilot.
- **Approval gates** that make agents stop and ask before risky changes, and rules that stop them approving, merging, deploying to Production or signing off.
- **A release discipline** that records each unit's release impact as it is built, rehearses go-live and learns from every snag.
- **A context check** that runs on every pull request and fails the build when the context is missing, incomplete or contains a secret.

The kit cannot remove every snag. It moves the causes of most snags earlier in the build, where they are cheaper to fix.

### The key idea: the kit is a copier

`eck init` copies the kit's files into the project repository. Once they are committed there, the project no longer depends on the kit.

```text
Kit repo (Bitbucket)                 Project repo (Bitbucket)
enterprise-context-kit/              client-site/
  scaffold/   ──┐                      AGENTS.md
  profiles/   ──┼── eck init ──►       .agents/skills/        (9 skills)
  tools/      ──┘   (one time)         .github/copilot-instructions.md
                                       .github/prompts/       (9 prompts)
                                       context/               (facts, playbooks, checker)
                                       bitbucket-pipelines.yml (+ context check step)
```

The copy is complete:

- `AGENTS.md` and `.agents/skills/` are read by OpenCode straight from the project.
- `.github/` is read by Copilot straight from the project.
- `context/check-context.mjs` is a copy of the checker, so the pipeline runs it from the project.
- `context/kit.json` records which kit version was used.

The one file `eck init` does not change is `bitbucket-pipelines.yml`. You add the context check step to it yourself, as described in "Add the context check to the pipeline" below.

### Who does what with the kit

| Person | Needs the kit? | What they do |
| --- | --- | --- |
| The technical lead, or whoever adopts the kit | Yes, once per project | Runs `eck init` against their local clone of the project, then commits on a branch and opens a pull request |
| Every other developer | No | Pulls the project after the pull request is merged. They get `AGENTS.md`, the skills, the prompts and `context/` automatically. |
| Bitbucket Pipelines | No | Runs `node context/check-context.mjs` from the project on every pull request |
| Reviewers, QA and project managers | No | Read `context/HOW-TO-USE.md` and `context/SKILLS-AND-COMMANDS.md` in the project |

### Step by step

**The technical lead, once per project:**

1. Gets the kit at a release tag, for example `v1.1.0`. Either clone the kit and check out the tag, or use the `npx` command in "Running the kit" below.
2. Clones the project and creates a branch.
3. Runs `eck init "<path-to-project>"`. From a clone, that is `node tools/eck.mjs init "<path-to-project>"` from the kit folder.
4. Merges any `.kit-new` files, adds the pipeline step, then commits, pushes and opens a pull request.

**Everyone else, after the pull request is merged:**

1. Runs `git pull` on the project.
2. Opens the project in OpenCode, or in VS Code with Copilot. The skills and prompts work straight away.

### When the kit is updated

The project does not update itself. The copied files stay at the version recorded in `context/kit.json` until someone updates them on purpose:

1. Someone gets the new kit tag.
2. They run `eck init` again on a branch in the project.
3. They merge the `.kit-new` files and open a pull request.

This keeps projects stable: a kit change can never break a project in the middle of a build. The cost is that each project is updated by hand, as described in "Updating a project to a newer kit" below.

## Before you start

You need:

- **Node.js 20 or later** on the machine that runs `eck init`, and in the pipeline for the context check. Nothing else is installed: the tools use Node built-ins only and run on Windows and macOS.
- **The kit**, run straight from its Bitbucket repository with `npx`, or cloned once. Either way, use a tagged release, not an unreleased branch. See "Running the kit" below.
- **Git**, if you run the kit straight from Bitbucket.
- **OpenCode, Copilot or both.** No extra setup is needed for Copilot Enterprise. For OpenCode, see "Optional: make the kit skill available in OpenCode" below.
- **The project repository**, new or existing, cloned locally on a branch you can open a pull request from.
- **A context owner**: the person or role who will own the context files. This is usually the technical lead.
- **The stack profile.** The kit ships with `generic`, the default, which suits any stack. Run `eck list` to see the profiles, including any your team has added.

Gather the source material the agent will need during setup. It does not have to be complete:

- the brief, statement of work or proposal
- kickoff or discovery notes
- designs, the design system, the design token source and brand guidelines
- the client's security, hosting and compliance requirements
- the list of integrations and environments

Never give the agent secrets, credentials or production data.

## Who needs the kit

Only the person who adds the kit to a project, or updates a project to a newer kit, needs the kit itself. This is usually the technical lead.

`eck init` is a one-time copier. It copies the context files, skills, prompts and the context check into the project repository. From then on the project owns those files, and they are committed like any other file.

| Who | Needs the kit? | What they need |
| --- | --- | --- |
| The person adding or updating the kit | Yes, to run `eck init` | Node.js 20 or later, and Git if they run the kit from Bitbucket |
| Developers, reviewers, QA and everyone else on the project | No | The project repository, OpenCode or Copilot, and Node.js 20 or later to run `node context/check-context.mjs` locally |
| The Bitbucket pipeline | No | Nothing extra. The context check step uses its own Node.js image and runs the copy in `context/` |

A project stays on the kit version it was created with, which is recorded in `context/kit.json`. It does not change when a new kit is released. Someone updates it on purpose, as described in "Updating a project to a newer kit" below.

## Running the kit

There are three ways to run the kit's `eck` command. They all run the same code, so pick whichever suits you.

### From Bitbucket with npx (nothing to clone)

`npx` comes with Node.js. It downloads the tagged kit version from Bitbucket into npm's cache and runs it:

```bash
npx --yes "git+https://bitbucket.org/<workspace>/enterprise-context-kit.git#v1.1.0" init <path-to-your-repo> --dry-run
```

- Replace `<workspace>` with the Bitbucket workspace that holds the kit.
- `#v1.1.0` is the release tag. Always give a tag. Everyone then runs the same version, and `npx` downloads a new version only when you change the tag.
- The kit repository is private, so Git needs access to it. Over HTTPS, Git asks you to sign in to Bitbucket the first time. If you use SSH keys with Bitbucket, use `git+ssh://git@bitbucket.org/<workspace>/enterprise-context-kit.git#v1.1.0` instead.
- On Bitbucket Data Center, use your server's clone URL, for example `git+https://bitbucket.example.com/scm/<project>/enterprise-context-kit.git#v1.1.0`.

### Installed from Bitbucket (a permanent `eck` command)

To type `eck` instead of the full `npx` command, install the tagged version once:

```bash
npm install --global "git+https://bitbucket.org/<workspace>/enterprise-context-kit.git#v1.1.0"
eck --version
```

To move to a newer version, run the same install command with the new tag.

### From a clone

Clone the kit, check out a release tag and run `node tools/eck.mjs` from the kit folder:

```bash
git clone https://bitbucket.org/<workspace>/enterprise-context-kit.git
cd enterprise-context-kit
git checkout v1.1.0
node tools/eck.mjs --version
```

You need a clone if you want the kit skill in OpenCode, or if you are changing the kit itself.

In the rest of this guide, `eck` stands for whichever of these you use.

## Add the kit to a project

Usually done by the technical lead or a senior developer. It takes a few minutes. The steps are the same for a new project and an existing repository. Where they differ, each step says so.

Start on a branch in the project repository. For a new project, create the repository in Bitbucket first, clone it and create a branch. The kit can go in before there is any code, and it should: the first unit of the build plan sets up the solution and the pipeline, and the agent needs the context to plan it.

### 1. Preview the changes

```bash
eck init <path-to-your-repo> --dry-run
```

`init` asks for the project name, client, context owner and profile, then lists every file it would create. Nothing is written in a dry run.

To skip the questions, pass everything as flags:

```bash
eck init <path-to-your-repo> --yes --profile generic --name "Client Site" --client "Client name" --owner "Technical lead"
```

### 2. Run it

Run the same command without `--dry-run`. `init` then runs the context check. Warnings for files still in `Draft` are expected at this point.

`init` never overwrites an existing file. If a file already exists and differs, the kit's version is written beside it as `<file>.kit-new`.

- **New project:** there is nothing to conflict with, so every file is listed as `create`.
- **Existing repository:** expect a `.kit-new` file for an `AGENTS.md` or `.github/copilot-instructions.md` the repository already has. Merge what you want to keep from the existing file into the kit's version, or the other way round, then delete the `.kit-new` file. Keep the kit's sections, such as "Before any task" and the Playbooks table, because the skills and prompts rely on them. Never commit `.kit-new` files.

### 3. Add the context check to the pipeline

The step is in [`ci/bitbucket-pipelines.context-check.yml`](ci/bitbucket-pipelines.context-check.yml), and a copy is under Pipelines in the project's `context/modules/environments-delivery.md`. It uses its own Node.js image, so it works in .NET pipelines without changes.

**If the project has no `bitbucket-pipelines.yml` yet,** which is usual for a new project, copy `ci/bitbucket-pipelines.context-check.yml` to the repository root and rename it `bitbucket-pipelines.yml`. Add the build, test and deployment steps to it when the build plan's first unit sets them up.

**If the project already has a `bitbucket-pipelines.yml`,** add the step to it. Do not replace the file.

1. Add the `context-check` step under `definitions:` and `steps:`. If the file already has a `definitions:` section, add the step to that section. A second `definitions:` key breaks the file.
2. Run the step on pull requests. If the file already has a `pull-requests:` section, add `- step: *context-check` to each pull request pipeline. If it has none, add the `pull-requests:` section from the snippet.
3. Leave the existing steps, images and deployments as they are.

For example, an existing .NET pipeline with the context check running beside the build:

```yaml
image: mcr.microsoft.com/dotnet/sdk:8.0

definitions:
  steps:
    - step: &build
        name: Build and test
        script:
          - dotnet build
          - dotnet test
    - step: &context-check
        name: Context check
        image: node:lts-slim
        script:
          - node context/check-context.mjs

pipelines:
  pull-requests:
    '**':
      - parallel:
          - step: *build
          - step: *context-check
```

Bitbucket reports mistakes in the file when the pipeline runs. To check it before you push, paste it into Atlassian's Bitbucket Pipelines validator. If your Bitbucket plan supports merge checks, require a passing build before a pull request can be merged, so the context check cannot be skipped.

### 4. Commit on a branch

Commit the new files, including `bitbucket-pipelines.yml`, on the branch and open a pull request, like any other change. A person reviews and merges it.

### Optional: make the kit skill available in OpenCode

The kit includes a OpenCode skill that runs these steps for you when asked. The skill needs a clone of the kit on your machine. Add the kit's `skills` folder to the `skills` array in your OpenCode config:

```jsonc
{ "skills": ["C:/path/to/enterprise-context-kit/skills"] }
```

Then, in the project, ask OpenCode to "add the context kit to this repository". It asks for the project name, client, owner and profile, shows a dry run and waits for your agreement before it writes anything.

## The first week

The aim of the first week is accurate context files and a build plan whose first unit proves the project can be deployed.

### Day 1: set up the context

Open the project in OpenCode and say "Set up the context files", or run `/setup-context` in Copilot Chat. Give the agent the source material you gathered.

The agent fills in one file at a time and asks the right person to confirm each one:

| Information | Who provides it |
| --- | --- |
| Goals, audience, scope, out of scope, success measures | Delivery lead or client lead |
| Stack, hosting, environments, pipelines | Technical lead |
| Code conventions | Technical lead confirms what the agent infers from the code |
| Brands, themes, voice and the design token source | Design lead and brand owner |
| Security, compliance and data rules | Client security contact or technical lead |
| Integrations and operations | Technical lead |

Anything nobody can answer yet goes in the Open questions list in `context/progress-tracker.md`, with the person who should answer it. A blank section with an open question is better than a confident guess, and the agent will not guess.

For an existing codebase, the agent drafts most of the architecture, standards, environments and integrations by reading the code. Someone still confirms each draft.

### Days 2 to 3: answer the open questions

Work through the open questions with the people named against them. When a file has no `FILL` comments left and its owner has confirmed it, set its Status to `Active`. If a module does not apply, for example there are no integrations, set its Status to `Not applicable`.

Pay particular attention to these sections. They prevent the most staging and go-live snags:

- **Configuration by environment** and **Environment parity** in `context/modules/environments-delivery.md`
- **Before staging** checks in `context/modules/quality-testing.md`
- **Launch scope and date**, **Roles** and **Readiness criteria** in `context/modules/go-live.md`

Setup is finished when `node context/check-context.mjs` reports no errors, every core file is `Active`, every module is `Active` or `Not applicable`, and every brand has an `Active` file in `context/brands/`.

### Days 3 to 5: plan the build

Say "Plan the build", or run `/plan-build`. The agent writes `context/specs/00-build-plan.md`, which breaks the project into units that can each be built, tested and reviewed in one pull request.

Check that:

- **Unit 01 is a production-like deployment**: a minimal solution deployed through the pipeline to every environment. This finds hosting, pipeline and configuration problems in week one rather than at go-live.
- **The milestones** include regular releases to Staging, client acceptance, a go-live rehearsal and hypercare.
- **Each unit** delivers something that can be seen, run or tested, and depends only on units before it.

Then start the first unit: "Write the spec for unit 01".

## Day to day

Once the context is set up, the team works in a simple loop. The details are in `context/HOW-TO-USE.md` in each project.

1. The agent writes a unit's spec. A person approves it.
2. The agent builds the unit and keeps its Release impact section current. A person reviews and merges the pull request.
3. The unit is deployed to the first shared environment and its acceptance criteria are rechecked there. Only then is it `Done`.
4. Repeat for the next unit.

Small, low-risk changes, such as a bug fix with a known cause or a text change, can use the small-change lane instead of a spec, but only if they meet every criterion and a person confirms it.

| To | In OpenCode, say | In Copilot Chat, run |
| --- | --- | --- |
| Fill in the context files | "Set up the context files" | `/setup-context` |
| Break the project into units | "Plan the build" | `/plan-build` |
| Write the spec for a unit | "Write the spec for unit 03" | `/write-unit-spec` |
| Build an approved unit | "Implement unit 03" | `/implement-unit` |
| Make a small, low-risk change | "Small fix: ..." | `/fix-small` |
| Prepare a review of a pull request | "Review branch ... against ..." | `/review-unit` |
| Prepare a release checklist | "Prepare the release to Staging for ..." | `/prepare-release` |
| Record an architecture decision | "Record a decision about ..." | `/record-decision` |
| Bring the context files up to date | "Refresh the context files" | `/refresh-context` |

## Who does what

The rule throughout: **people supply the facts and make the decisions; agents draft, build and check.** Agents never approve, merge or post a review, deploy to Production, change Production configuration, secrets or data, or sign off a release.

| Role | Adopting the kit | During the build | At release and go-live |
| --- | --- | --- | --- |
| Technical lead | Runs `eck init`, adds the pipeline step, owns most context files | Approves specs or names who does, answers approval gates, keeps Environment parity honest | Owns deployment and configuration checks, runs the context refresh after each release |
| Developers | Help confirm the code conventions and architecture | Ask for specs and builds, check the agent's plan and evidence, keep Release impact current, recheck units after deployment | Supply missing release impact, fix snags |
| Reviewers | None | Ask the agent to prepare reviews, decide the outcome, block on missing Release impact | Review release fixes the same way |
| QA and testers | Help write the Before staging checks | Check acceptance criteria are testable, run Before staging checks, record snags | Write and run smoke tests, take part in the rehearsal |
| Delivery and project managers | Supply goals, scope and success measures | Check the build plan and milestones, follow the progress tracker | Own the go-live plan with the release manager, run go or no-go |
| Design and brand leads | Supply the design system, token source and brand guidelines | Approve changes to tokens, themes, logos and approved copy | Confirm brand content is ready |

`context/HOW-TO-USE.md` has a fuller section for each role.

## Releases and go-live

Before every release to Staging or Production, say "Prepare the release to Staging for units 03 to 06", or run `/prepare-release`. The agent:

- collects the Release impact of every unit in the release into one checklist, environment by environment
- checks it against the code changes and the environment, and lists the gaps
- checks the readiness criteria in `context/modules/go-live.md`, for the first go-live and other major releases

People then run the production steps, make the go or no-go decision and sign off.

Before the first go-live, rehearse it in Staging: run the cutover plan, the smoke tests and the rollback end to end, with the same steps you will use in Production. The rehearsal is a milestone in the build plan.

After each release, record every snag in the Snag log in `context/modules/go-live.md` with its cause, then refresh the context. Refreshing turns repeated causes into rules, checks or acceptance criteria, so the same snag does not come back.

## Updating a project to a newer kit

When a new kit version is released, check `CHANGELOG.md` for what changed, then:

1. Use the new kit version: change the tag in your `npx` command, reinstall with the new tag, or pull your clone and check out the new tag.
2. On a branch in the project, run `eck init` again with the same answers. `--dry-run` shows what will change first.
3. Files the kit has not changed are left alone. Files that differ, including the context files you have filled in, get a `.kit-new` copy. Merge only the new template sections into your filled-in files; do not replace your content.
4. `context/check-context.mjs` can usually be replaced outright with its `.kit-new` copy.
5. Update `kitVersion` in `context/kit.json` once you have merged everything.
6. Delete every `.kit-new` file, run `node context/check-context.mjs` and open a pull request.

## Troubleshooting

**`node` is not recognised.** Install Node.js 20 or later and open a new terminal.

**`npx` says the repository was not found, or asks for a password it will not accept.** Git cannot reach the kit repository. Check that you can open it in Bitbucket, then try `git ls-remote` with the same URL, without `git+` and the tag. Over HTTPS, sign in with your Bitbucket account or an API token. Over SSH, check that your SSH key is added to Bitbucket.

**`npx` says `git` is not found.** Install Git and open a new terminal, or run the kit from a clone instead.

**`eck` runs an older version than expected.** Check the tag at the end of the URL. With `npm install --global`, run the install command again with the new tag. `eck --version` prints the version you are running.

**`eck init` lists files as `conflict`.** They already exist and differ from the kit's version. Your files were kept; the kit's versions are beside them as `.kit-new`. Merge and delete them, or rerun with `--force` only if you are sure you want the kit's versions instead.

**The context check fails in the pipeline but passes locally.** Make sure the files the check reports are committed, and that the step runs from the repository root. The check reads `context/kit.json` to find the files to check.

**The context check reports a possible secret.** Remove it, rotate the secret, and store it as described in `context/modules/security-compliance.md`. Removing it from the latest commit is not enough once it has been pushed.

**Copilot does not show the prompts such as `/setup-context`.** Prompt files are in `.github/prompts/`. Check that they are committed and that prompt files are enabled for your Copilot organisation.

**OpenCode does not use the workflows.** Check that `AGENTS.md` is at the repository root and the skills are in `.agents/skills/`. Start a new conversation after adding the kit.

**The agent keeps asking questions instead of filling in a file.** That is by design: it will not invent facts. Give it the source document, or answer the question and it will continue.

**An agent did something the rules forbid.** Stop it, point it to the rule and ask it to undo the change. If the rule is unclear, reword it in `context/ai-workflow-rules.md`. If the mistake reached a shared environment, record it in the snag log.
