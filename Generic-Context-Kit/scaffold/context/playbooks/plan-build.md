# Playbook: Plan the Build

Use this playbook to break the project into units of work and write `context/specs/00-build-plan.md`. Run it once the core context files are `Active`, and again whenever scope changes significantly.

## What makes a good unit

- It delivers something that can be seen, run or tested, not just a layer of code.
- It can be built, tested and reviewed in one pull request, usually in a day or two of work.
- Its acceptance criteria can be checked without waiting for later units.
- It depends only on units that come before it.

Split a unit if it touches many unrelated areas, needs several approval gates, or cannot be described in one sentence.

## Steps

1. **Read the context.** Read the files listed in `AGENTS.md`, the modules that apply, including `context/modules/environments-delivery.md` and `context/modules/go-live.md`, and the existing decisions in `context/decisions/`.
2. **List the work.** Start from the Key features table in `context/project-overview.md`. Add the foundation work that features depend on, for example solution setup, pipelines, environments, authentication, shared layout, design tokens and a theme for each brand in `context/brands/`, and integrations.
3. **Start with a production-like deployment.** Unit 01 should take a minimal version of the solution all the way through the pipeline to every environment, including Staging, using the same hosting, configuration approach, secret store and schema promotion that Production will use. If Production is not available yet, use the environment closest to it, and add the gap to the Environment parity table. Deployment problems found in the first week are cheap. Found at go-live, they delay the launch.
4. **Order it.** Put foundations first, then the features with the highest priority, then the rest. Within that, build what unblocks other work first, and tackle risky or uncertain work early so problems surface while there is still time. Integrations that need credentials, network access or client-side setup are usually risky: start them early.
5. **Size it.** Split or merge items until each one meets the description of a good unit above.
6. **Plan the releases.** Group the units into milestones that are released to Staging regularly, not all at the end. Before the first go-live, add:
   - a **go-live rehearsal** milestone, at least a week before launch, in which the cutover plan, smoke tests and rollback in `context/modules/go-live.md` are run end to end in Staging
   - time for client acceptance testing and fixing what it finds
   - time for hypercare after launch
7. **Write the plan.** Fill in `context/specs/00-build-plan.md`: the approach, one row per unit, milestones, and risks and unknowns. Number units 01, 02, 03 and so on.
8. **Review it.** Show the plan to the person and ask them to confirm the order, the scope of each unit, the release milestones and anything missing. Revise until they approve it, then set Status to `Active`.
9. **Update the tracker.** Add every unit to the Units table in `context/progress-tracker.md` with Status `Not started`, and set the next step: write the spec for unit 01 with `context/playbooks/write-unit-spec.md`.

## Rules

- Plan only what is in scope in `context/project-overview.md`. Raise anything else as an open question.
- Do not write unit specs in this playbook. Each spec is written just before its unit is built, so it reflects what has been learned.
- If the plan depends on a decision that has not been made, list it under risks and unknowns and add it to the open questions. Once it is made, record it with `context/playbooks/record-decision.md`.
- Do not add small fixes as units. They go through `context/playbooks/fix-small.md`.
- Do not plan a single release at the end of the build. Regular releases to Staging surface snags while they are still small.

## Done when

- `context/specs/00-build-plan.md` is `Active` and approved.
- The plan starts with a production-like deployment and, before the first go-live, includes a rehearsal milestone.
- Every unit appears in the Units table in `context/progress-tracker.md`.
