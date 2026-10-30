# Go-Live

| Owner | Last reviewed | Status |
| --- | --- | --- |
| {{OWNER}} | {{TODAY}} | Draft |

How the project goes live for the first time, and how each later major release is cut over. Agents read this file before preparing a release with `context/playbooks/prepare-release.md`.

Most go-live snags come from something that worked in Staging but differs in Production, or from a step that happens only once and was never rehearsed. This file records those steps so they can be rehearsed and checked. The known differences between Staging and Production are in the Environment parity table in `context/modules/environments-delivery.md`.

An agent prepares checklists and checks evidence. People make every go or no-go decision, run every production change and sign off.

Keep this module after the first launch. Later major releases use the same plan, and the snag log carries on.

Replace each `FILL` comment with real content, then delete the comment. When no `FILL` comments remain, set Status to `Active`.

## Launch scope and date

<!-- FILL: What goes live (sites, brands, markets and features), the target date and time with the time zone, and any fixed dependencies, for example a campaign launch or the end of the contract for the old system. -->

## Roles

| Role | Responsibility | Who |
| --- | --- | --- |
| Release manager | Runs the cutover plan and calls go or no-go | |
| Technical lead | Deployment, configuration and technical checks | |
| Client sign-off | Accepts the release on the client's behalf | |
| Hosting and DNS | Infrastructure, scaling, DNS and certificates | |
| Support | Hypercare after go-live | |
<!-- FILL: The role or team for each row. Add roles such as the client's IT team or third-party vendors. Use role or team names, not personal phone numbers. -->

## Readiness criteria

Go-live goes ahead only when every item below is true. The release checklist records the evidence for each one.

- Every unit in the release is `Done`, and the release has been deployed to Staging and checked there.
- Client acceptance testing is complete and signed off, with no open defects of a blocking severity.
- The go-live rehearsal has been run end to end in Staging, including rollback, and the issues it found are resolved.
- Every Production action from the units' Release impact sections has an owner and a place in the cutover plan.
- Production configuration, secrets, licences, certificates and DNS changes are prepared and checked.
- The Before staging checks in `context/modules/quality-testing.md` pass in Staging.
- Monitoring and alerts are in place for Production, and the support team knows the release is coming.
- Where Production already holds data, a recent backup exists and a restore has been tested.
<!-- FILL: Any project-specific criteria, for example a penetration test, legal approval of content, SEO redirects signed off or a content freeze agreed. -->

## Pre-launch checks

Checks made in Production, or in Staging where Production is not yet reachable, in the days before go-live.

| Check | How it is verified | Owner |
| --- | --- | --- |
<!-- FILL: One row per check. For example: DNS time-to-live lowered ahead of the switch; certificates valid for every hostname; redirects from old URLs mapped and tested; search engine indexing allowed in Production and blocked elsewhere; analytics and tag manager pointing at Production; email sending domain verified; error and maintenance pages ready; cookie consent configured. -->

## Cutover plan

The ordered steps on the day, rehearsed in Staging first.

| Step | Action | Owner | Expected duration | How we know it worked |
| --- | --- | --- | --- | --- |
<!-- FILL: One row per step, in order. For example: content freeze starts; deploy the release to Production; run migrations or import schema; switch DNS; warm caches; run the smoke tests; go or no-go decision; content freeze ends. -->

## Smoke tests

Short checks run in Production straight after deployment, to confirm the release works. They should take minutes, not hours.

<!-- FILL: A numbered list. For example: the home page and one page per template load for each brand; sign-in works; a form submits and the submission arrives; search returns results; each integration responds; the health check is green; no new errors appear in the logs. Use test accounts and synthetic data, never real personal data. -->

## Go or no-go and rollback

<!-- FILL: When the go or no-go decision is made, who makes it, and the criteria for rolling back. Name the point of no return, after which rolling back is no longer possible (for example once DNS has switched and editors have created content), and what happens instead. The rollback steps are in context/modules/environments-delivery.md. -->

## Hypercare

<!-- FILL: The period of extra support after go-live: how long it lasts, who is on hand and when, how issues are reported and triaged, how often monitoring is checked, and when normal support in context/modules/operations.md takes over. -->

## Rehearsal

<!-- FILL: When the go-live rehearsal is held in Staging, who runs it, and where its notes are kept. The rehearsal runs the cutover plan, the smoke tests and the rollback end to end, using the same steps that will be used in Production. -->

## Snag log

Record every snag found after a change was merged: in Development, in Staging, at go-live or in hypercare. Give each one a cause from the list below. `context/playbooks/refresh-context.md` reviews this log and turns repeated causes into rules, checks or acceptance criteria, so the same snag does not happen on the next release.

| Date | Environment | Snag | Cause | Prevented next time by |
| --- | --- | --- | --- | --- |

Cause is one of: Missing requirement, Environment difference, Configuration, Content or data, Integration, Missed release step, Code defect, Other.
