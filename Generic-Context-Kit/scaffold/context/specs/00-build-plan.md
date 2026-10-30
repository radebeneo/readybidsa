# Build Plan

| Owner | Last reviewed | Status |
| --- | --- | --- |
| {{OWNER}} | {{TODAY}} | Draft |

The project broken into units of work, in the order they will be built. Each unit is small enough to build, test and review in one pull request, and gets its own spec in this folder before work starts.

Write this plan with `context/playbooks/plan-build.md` once the core context files are `Active`. When no `FILL` comments remain, set Status to `Active`.

## Approach

<!-- FILL: A short description of how the build is sequenced and why, for example "a production-like deployment first, then foundations, then the page templates editors need most, then integrations". Note any milestones or release dates from context/project-overview.md. -->

## Units

| # | Unit | Goal | Depends on | Spec |
| --- | --- | --- | --- | --- |
<!-- FILL: One row per unit, in build order. Number units 01, 02, 03 and so on. Unit 01 takes a minimal solution through the pipeline to every environment, including Staging, using the hosting, configuration, secret store and schema promotion that Production will use. The spec column links to the unit's spec file once it is written. Example: "| 01 | Production-like deployment | A minimal solution builds, deploys through the pipeline to Development and Staging, and reads its settings and secrets the way Production will | None | 01-production-like-deployment.md |" -->

## Milestones

<!-- FILL: Group the units into milestones, each released to Staging, with target dates if known. Before the first go-live, include a go-live rehearsal in Staging at least a week before launch, time for client acceptance testing and fixes, the go-live itself and a hypercare period. See context/modules/go-live.md. -->

## Risks and unknowns

<!-- FILL: Anything that could change the plan, for example integrations without test environments, differences between Staging and Production, designs not yet signed off or decisions still needed. Say which units each one affects. -->
