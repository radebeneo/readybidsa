# Unit NN: Unit name

| Owner | Status | Build plan |
| --- | --- | --- |
| Name or role | Spec in review | [00-build-plan.md](00-build-plan.md) |

Status is one of: Spec in review, Ready, In progress, In review, Done, Blocked.

Copy this file to `NN-short-name.md`, fill in every section and delete the guidance comments. A unit is ready to build only when a person has approved its spec and set Status to `Ready`.

## Goal

<!-- FILL: One or two sentences: what this unit delivers and why it matters to users or the project. -->

## Scope

### In scope

<!-- FILL: Exactly what this unit builds or changes. -->

### Out of scope

<!-- FILL: Related work that this unit does not include, and which later unit covers it, if any. -->

## Context to read

<!-- FILL: The context files, modules, ADRs and design references the implementer must read for this unit. Be specific, for example "context/ui-context.md, Components section" or a Figma frame link. -->

## Brands affected

<!-- FILL: The brands whose pages, components or copy this unit changes, each linked to its file in context/brands/, or "None" for a unit with no interface or copy changes. Say whether the change must look the same for every brand or differs per brand. -->

## Approach

<!-- FILL: How the unit will be built: the main components, where new code goes, which existing patterns to follow, and any data, content or schema changes. Keep it short. The implementer can fill in detail. -->

## Files likely to change

<!-- FILL: The files or folders you expect to add or change. This helps reviewers spot scope creep. -->

## Approval gates

<!-- FILL: Anything in this unit that needs human approval under context/ai-workflow-rules.md, for example a new dependency or a migration, or "None". -->

## Release impact

Everything this unit needs, beyond deploying its code, to work in each environment. `context/playbooks/prepare-release.md` collects this section from every unit into the release checklist, so anything missing here tends to surface as a snag at staging or go-live. The implementer keeps it up to date as the unit is built.

| Area | What changes | What each environment needs |
| --- | --- | --- |
| Configuration | | |
| Secrets | | |
| Schema and migrations | | |
| Content and media | | |
| Integrations and external services | | |
| Feature flags | | |
| Infrastructure, DNS and certificates | | |
| Manual steps | | |
| Rollback | | |

<!-- FILL: Complete every row, or write "None" in it. For each action, say which environments it applies to (Development, Staging, Production), who does it, and whether it happens before, during or after deployment. Name secrets and where they are stored; never write their values. In the Rollback row, note anything that redeploying the previous version would not undo. Example: "Secrets | New payment service credential | Add to the Staging and Production secret stores before deployment; owner: technical lead". -->

## Acceptance criteria

<!-- FILL: A numbered list of checks that prove the unit is done. Each one must be specific and testable. Example: "1. An editor can add a Hero block to any content page and set a heading, image and link." -->

## Tests

<!-- FILL: The tests this unit adds or changes, by type, as described in context/modules/quality-testing.md. -->

## Open questions

<!-- FILL: Questions that must be answered before or during the build, or "None". -->
