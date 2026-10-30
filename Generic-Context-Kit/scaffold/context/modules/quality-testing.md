# Quality and Testing

| Owner | Last reviewed | Status |
| --- | --- | --- |
| {{OWNER}} | {{TODAY}} | Draft |

How this project proves that its code works. Agents read this file before writing or changing tests, and use it to decide what tests a unit needs.

Replace each `FILL` comment with real content, then delete the comment. When no `FILL` comments remain, set Status to `Active`.

## Rules

- Every unit includes tests for the behaviour it adds or changes.
- A bug fix includes a test that fails without the fix.
- Tests are deterministic. They do not depend on the clock, test order, network access or live external systems.
- Test data is synthetic. Never use production or real personal data.
- Never delete, skip or loosen a failing test to make a build pass. Fix the code or ask.

## Before staging

These checks run on every unit before it is merged, not only before a release. A problem found at the end of the build is harder to fix, and is a common cause of a delayed go-live.

- **Accessibility:** automated checks pass on every page and component the unit changes, and they can be used with a keyboard alone.
- **Performance:** pages the unit changes stay within the budgets under Performance testing.
- **Security:** dependency and code scanning report no new findings of high severity or above.
- **Deployable:** the unit works when deployed, not only locally. It depends on no local-only file, path, setting, certificate or data, and the Release impact section of its spec is complete.
<!-- FILL: The tool and threshold for each check, and which ones run automatically in the pipeline. Add project-specific checks, for example visual regression, SEO metadata or analytics events. -->

## Test types

| Type | What it covers | Tool | Where tests live | When it runs |
| --- | --- | --- | --- | --- |
<!-- FILL: One row per type you use, for example unit, integration, component, end-to-end, accessibility, visual regression and performance. Example: "| Unit | Services and helpers in isolation | xUnit | tests/Project.Tests.Unit | Every pull request |" -->

## Running tests

<!-- FILL: The exact commands to run each type of test locally, and any setup they need (for example a local database or a running site). -->

## Coverage

<!-- FILL: Coverage targets, if any, and which code is excluded. Say which areas must always have tests, for example pricing, permissions and form handling. -->

## Test data

<!-- FILL: How test data and content are created (for example builders, fixtures or a seed script), and where they live. -->

## Accessibility testing

<!-- FILL: Automated tools (for example axe or Pa11y), manual checks with keyboard and screen readers, and which pages are tested before each release. The accessibility target is in context/ui-context.md. -->

## Performance testing

<!-- FILL: Performance budgets, tools (for example Lighthouse CI or k6) and when performance is tested. Targets are in context/architecture.md. -->

## Browser and device testing

<!-- FILL: How supported browsers and devices are tested, and by whom. The supported list is in context/ui-context.md. -->

## Code review checklist

Reviewers check every pull request for:

- The change matches the unit spec, and nothing outside it has changed.
- Tests cover the new behaviour and pass in the pipeline.
- The Before staging checks above pass.
- The Release impact section of the spec matches the change, and nothing works only locally.
- No secrets, personal data or production data have been added.
- The code follows `context/code-standards.md`.
- Context files are updated where the change affects them.
<!-- FILL: Any project-specific review checks. -->

## Acceptance and sign-off

Snags found once a change is merged, whether in Development, Staging, at go-live or in hypercare, are recorded in the Snag log in `context/modules/go-live.md` with their cause.

<!-- FILL: How the client tests and accepts work (for example UAT on staging), who signs off, and how defects are reported and prioritised. -->
