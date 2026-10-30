# How to Use the Context Files on {{PROJECT_NAME}}

This guide is for everyone on the {{PROJECT_NAME}} team: technical leads, developers, reviewers, testers, delivery leads and design leads. It explains how to work with the AI agents and the files in `context/`, from the first day of the build to go-live and after.

You do not need to read the playbooks to use them. The agent follows them for you. This guide tells you what to ask for, what you will be asked to decide, and what to check.

For a quick reference to every skill and command, what each one does and when to use it, see `context/SKILLS-AND-COMMANDS.md`.

## The idea in one minute

- `context/` holds the facts about this project: its goals, architecture, standards, design, brands, environments and plan. Agents read these files before every task, so they work from the same facts as the team.
- `AGENTS.md` is the entry point. OpenCode reads it directly, and Copilot is pointed to it by `.github/copilot-instructions.md`.
- Every workflow is written down once, as a playbook in `context/playbooks/`. You start a workflow by asking the agent for it.
- **People supply the facts and make the decisions.** They approve specs, review and merge pull requests, run production changes and sign off releases.
- **Agents draft, build and check.** They write specs and code, prepare reviews and release checklists, and keep the context files up to date. They never invent a fact to fill a gap, and they stop and ask when something needs approval.

## Starting a workflow

| To | In OpenCode, say something like | In Copilot Chat, run |
| --- | --- | --- |
| Fill in the context files | "Set up the context files" | `/setup-context` |
| Break the project into units | "Plan the build" | `/plan-build` |
| Write the spec for a unit | "Write the spec for unit 03" | `/write-unit-spec` |
| Build an approved unit | "Implement unit 03" | `/implement-unit` |
| Make a small, low-risk change | "Small fix: the footer link to the privacy page is broken" | `/fix-small` |
| Prepare a review of a pull request | "Review branch feature/03-search against develop" | `/review-unit` |
| Prepare a release checklist | "Prepare the release to Staging for units 03 to 06" | `/prepare-release` |
| Record an architecture decision | "Record a decision about how we cache search results" | `/record-decision` |
| Bring the context files up to date | "Refresh the context files" | `/refresh-context` |

Tips:

- **Be specific.** Name the unit, branch, environment or release. If you leave something out, the agent will ask.
- **Give it the source.** Point the agent to the brief, ticket, design file or meeting notes that hold the facts. It will not make them up.
- **One task per conversation.** Start a new conversation for each unit or workflow. It keeps the agent focused and the history short.
- **Read the plan before you say yes.** Before it changes code, the agent says which files it will change and how it will check the result.

## The build, step by step

1. **Set up the context (once).** Ask the agent to set up the context. It drafts each file from the documents you give it and from the existing code, then asks the right person to confirm. Each file's owner checks it and sets its Status to `Active`.
2. **Plan the build (once, then whenever scope changes).** The agent breaks the work into units in `context/specs/00-build-plan.md`. Unit 01 is always a minimal solution deployed through the pipeline to every environment, so deployment problems show up in week one, not at go-live. The plan also sets milestones, including regular releases to Staging and a go-live rehearsal.
3. **Build one unit at a time.** For each unit: the agent writes the spec, a person approves it, the agent builds it, a person reviews and merges it, and it is deployed to the first shared environment and rechecked there.
4. **Release.** Before each release to Staging or Production, the agent prepares a release checklist from every unit's Release impact. People run the production steps and sign off.
5. **Learn.** Record every snag found after merge in the snag log. Refreshing the context turns repeated causes into rules and checks.

## The life of a unit

The status of every unit is in `context/progress-tracker.md`.

| Status | What it means |
| --- | --- |
| Not started | The unit is in the build plan but has no spec yet. |
| Spec in review | The agent has drafted the spec, and a person is reviewing it. |
| Ready | A person has approved the spec. Building can start. |
| In progress | The unit is being built. |
| In review | The pull request is open and waiting for a person to review it. |
| Done | It has been merged, deployed through the pipeline to Development or the first shared environment, and its acceptance criteria have been rechecked there. |
| Blocked | Work cannot continue. The reason is under Blockers in the progress tracker. |

**Working on a laptop is not Done.** A unit is `Done` only when it works in a shared environment.

### What a good spec contains

Read every spec before you approve it. Check in particular:

- **Acceptance criteria.** Each one can be checked, and you would accept the unit if all of them pass.
- **Release impact.** Everything the unit needs in each environment beyond its code: settings, secrets, schema, content, integrations, feature flags, infrastructure, manual steps and anything that cannot be rolled back. Most go-live snags start as a line that was missing here.
- **Brands affected.** Which brands the change touches, if any.
- **Out of scope.** What the unit deliberately does not do.

## Small changes

A small change can skip the spec. It qualifies only if **all** of the following are true, and a person confirms it:

- It is a bug fix with a clear cause, a text or translation change, a visual fix that uses existing design tokens and components, a documentation change or a test-only change.
- It is small enough that a reviewer can understand the whole diff in a few minutes.
- It adds nothing new: no page, component, block, document type, endpoint, integration, setting or dependency.
- It has no release impact. It needs nothing in any environment beyond the code itself.
- It touches no approval gate or protected path.

The full criteria are in `context/playbooks/fix-small.md`. If in doubt, write a spec.

## What agents will not do

Agents never:

- approve, merge or post a review to a pull request
- deploy to Production, or change Production configuration, secrets or data
- sign off a release
- commit secrets, or use production or real personal data
- skip or weaken tests, linting or the context check to make a build pass

Agents stop and ask a person before they change authentication or permissions, add or run migrations, add or upgrade dependencies, change pipelines or infrastructure, deploy to or change a shared environment, change design tokens, logos or approved brand copy, or do anything else listed under Approval gates in `context/ai-workflow-rules.md`.

**When an agent asks for approval,** read what it plans to do and answer clearly, yes or no. An approval covers only what the agent described. If the plan changes, it must ask again.

## Your role

### Technical lead

- Owns most context files, and confirms the stack, environments, pipelines and conventions during setup.
- Approves specs, or names who does, and answers approval gate requests.
- Records significant decisions as ADRs, or asks the agent to draft them.
- Keeps the Environment parity table in `context/modules/environments-delivery.md` honest: every difference between Staging and Production, why it is accepted and how the risk is covered.
- Runs a context refresh after each release and when the check reports overdue reviews.

### Developers

- Ask the agent to write the spec for the next unit, then to implement it once it is `Ready`.
- Check the agent's plan before it changes code, and check its evidence for each acceptance criterion.
- Keep the Release impact section of the spec current while building. If you add a setting, it goes in the spec in the same change.
- After merge, check the unit in the first shared environment before it is marked `Done`.
- Use the small-change lane only when every criterion is met.

### Reviewers

- Ask the agent to prepare a review of the pull request. It lists findings by severity and recommends an outcome. You decide.
- Treat a missing or incomplete Release impact section as blocking.
- Check that context files changed in the same pull request when the change made them out of date.
- You are responsible for the change you approve, not the agent.

### QA and testers

- Read the acceptance criteria while the spec is in review, and say when one cannot be tested.
- Use the Before staging checks in `context/modules/quality-testing.md` on every unit, not only before a release.
- Record each snag you find after merge in the snag log, with its cause.
- Help write the smoke tests in `context/modules/go-live.md`, and run them at the rehearsal and at go-live.

### Delivery and project managers

- Supply the goals, audience, scope, out of scope and success measures for `context/project-overview.md` during setup.
- Check the build plan and milestones, including the go-live rehearsal and hypercare.
- Follow progress in `context/progress-tracker.md`, including Open questions and Blockers.
- Own the go-live plan in `context/modules/go-live.md` with the release manager: roles, readiness criteria, cutover plan, go or no-go and hypercare.

### Design and brand leads

- Supply the design system, the design token source and the brand guidelines for `context/ui-context.md` and the files in `context/brands/`.
- Approve changes to design token values, themes, logos, approved brand copy and brand files. These are approval gates.
- Context files name the token source rather than copying values such as hex codes, so there is only one place to change a colour.

## Keeping the context accurate

- Update a context file in the same pull request as the change that makes it out of date. The agent does this as part of its work, and reviewers check it.
- Each file has an Owner and a Last reviewed date. Owners review their files at least every {{REVIEW_DAYS}} days.
- To bring everything up to date in one pass, ask the agent to refresh the context. It changes review dates only after each owner confirms.
- Never put secrets, personal data or production data in these files.

## The context check

Run this from the repository root. It needs Node.js 20 or later and nothing else:

```bash
node context/check-context.mjs
```

It also runs on every pull request in Bitbucket Pipelines. Errors fail the build. Warnings do not, unless you add `--strict`.

| Message | What to do |
| --- | --- |
| Missing | Restore the file. If it does not apply to this project, keep it and set its Status to `Not applicable`. |
| Status is Active but FILL comments remain | Finish the sections the `FILL` comments ask for, or set the Status back to `Draft`. |
| Unresolved placeholder | Replace the placeholder with the real value. |
| Possible secret | Remove it, rotate the secret and store it as described in `context/modules/security-compliance.md`. |
| Status is not one of the allowed values | Use one of the statuses the message lists. |
| Draft | Expected during setup. Finish the file, have the owner confirm it, then set it to `Active`. |
| No owner is set | Put a person or role in the Owner column. |
| Last reviewed too long ago | Ask the owner to review the file, or refresh the context. |

## Recording snags

A snag is anything found after a change was merged that needed fixing: in Development, in Staging, at go-live or in hypercare. Record each one in the Snag log at the bottom of `context/modules/go-live.md`, with:

- the date and environment
- what went wrong
- its cause: Missing requirement, Environment difference, Configuration, Content or data, Integration, Missed release step, Code defect or Other
- what would have prevented it

Write it down even when the fix is quick. The log is how the team stops the same snag from coming back on the next release.

## Common questions

**The code and the context files disagree. Which is right?** The agent stops and asks. Decide which is correct, then fix the other one in the same change.

**The agent did not follow a rule.** Point it to the rule and ask it to try again. If it keeps happening, the rule is probably unclear: reword it in the context file. If the mistake reached a shared environment, record it in the snag log.

**There are `.kit-new` files in the repository.** They are newer kit versions of files that already existed here. Compare each one with the existing file, merge what you want to keep, then delete the `.kit-new` file. Never commit them.

**Do I need the kit on my machine?** No. The kit only adds these files to the repository and updates them to newer kit versions. Day to day you need this repository, OpenCode or Copilot, and Node.js 20 or later for the context check. Only the person who updates the project to a newer kit runs the kit.

**Which kit version does this project use?** The one in `kitVersion` in `context/kit.json`. It changes only when someone updates the project to a newer kit.

**Someone new has joined.** Ask them to read this guide, `context/project-overview.md` and `AGENTS.md`, in that order. Then they can ask the agent anything about the project.

**Where do I find a specific workflow's steps?** In `context/playbooks/`. The table in `AGENTS.md` lists them all.
