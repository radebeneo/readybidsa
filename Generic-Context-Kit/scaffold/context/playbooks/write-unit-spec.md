# Playbook: Write a Unit Spec

Use this playbook to write the spec for one unit from `context/specs/00-build-plan.md`. A spec tells the implementer exactly what to build and how to prove it is done. Write it just before the unit is built.

## Steps

1. **Pick the unit.** Use the unit the person names. If they do not name one, take the next unit in the build plan whose dependencies are `Done`, and confirm it with them.
2. **Read the context.** Read the files listed in `AGENTS.md`, the modules that apply to this unit, any related ADRs, and the specs of the units it depends on. Check the Snag log in `context/modules/go-live.md` for snags in the same area, and add an acceptance criterion that would catch each one again.
3. **Look at the code.** If code already exists, find where this unit's work will go and the patterns it should follow.
4. **Copy the template.** Copy `context/specs/_unit-spec-template.md` to `context/specs/NN-short-name.md`, using the unit's number from the build plan.
5. **Fill it in.** Complete every section:
   - **Goal:** one or two sentences.
   - **Scope:** what is in, and what is explicitly out.
   - **Context to read:** specific files, sections and design frames, not whole folders.
   - **Brands affected:** each brand whose pages, components or copy change, linked to its file in `context/brands/`. Read those files before you write the acceptance criteria.
   - **Approach:** enough direction to keep the work consistent with the architecture, without writing the code in advance.
   - **Files likely to change:** so reviewers can spot scope creep.
   - **Approval gates:** anything that needs a person's approval under `context/ai-workflow-rules.md`.
   - **Release impact:** everything the unit will need in each environment beyond its code: settings, secrets, schema, content, integrations, feature flags, infrastructure and manual steps, and anything a rollback would not undo. Check the Configuration by environment and Environment parity sections of `context/modules/environments-delivery.md`. Fill in what you know now and write "None" where nothing applies; the implementer adds to it as the unit is built.
   - **Acceptance criteria:** numbered, specific and testable. Include error, empty and edge cases, accessibility and any content editor experience.
   - **Tests:** the tests the unit adds, by type.
   - **Open questions:** anything still unknown.
6. **Review it.** Show the spec to the person. Resolve open questions with them, or record them as blockers. Revise until they approve it.
7. **Mark it ready.** Once approved, set the spec's Status to `Ready`, link it from the build plan, and set the unit to `Ready` in `context/progress-tracker.md`.

## Rules

- One spec covers one unit. If the spec grows beyond one pull request, split the unit and update the build plan.
- Acceptance criteria describe behaviour, not implementation. "Editors can reorder blocks" is better than "add a sortable list".
- Do not start implementing until the spec is `Ready`.
- If the work is small enough for `context/playbooks/fix-small.md`, say so and suggest that playbook instead of writing a spec.
- If the unit needs a decision that later work depends on, record it with `context/playbooks/record-decision.md` before the spec is approved.

## Done when

- The spec has no guidance comments left and its Status is `Ready`.
- The build plan and progress tracker both show the unit as `Ready`.
