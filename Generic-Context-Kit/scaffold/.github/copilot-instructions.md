# {{PROJECT_NAME}}: Copilot Instructions

The instructions for this repository live in [`AGENTS.md`](../AGENTS.md) and the files in [`context/`](../context/). Read `AGENTS.md` first and follow it. Read the context files it lists before you suggest or change code.

If anything below differs from `AGENTS.md`, `AGENTS.md` is correct.

## Always

- Treat `context/` as the source of truth for this project's goals, architecture, standards and UI.
- Follow the patterns in `context/code-standards.md` and the boundaries in `context/architecture.md`.
- Work on one unit at a time, from an approved spec in `context/specs/`. Only small changes that meet every criterion in `context/playbooks/fix-small.md` may skip the spec.
- For interface or copy changes, follow `context/ui-context.md` and the brand file in `context/brands/` for each brand affected.
- Record everything a unit needs in each environment beyond its code in the Release impact section of its spec.
- Update `context/progress-tracker.md` when you finish a piece of work.

## Never

- Commit secrets, credentials, connection strings or API keys.
- Use production data or real personal data in code, tests or fixtures.
- Change authentication, migrations, dependencies, brand tokens or approved copy without human approval.
- Weaken or skip tests, linting or the context check.
- Approve or merge a pull request.
- Deploy to Production, change Production configuration, secrets or data, or sign off a release.

## Workflows

Run these prompt files from Copilot Chat:

| Prompt | Use it to |
| --- | --- |
| `/setup-context` | Fill in the context files for a new or existing project |
| `/plan-build` | Break the project into buildable units |
| `/write-unit-spec` | Write a spec for one unit |
| `/implement-unit` | Implement an approved unit |
| `/fix-small` | Make a small, low-risk change without a spec |
| `/review-unit` | Prepare a review of a pull request or branch |
| `/prepare-release` | Prepare a release checklist for Staging or Production, including go-live |
| `/record-decision` | Record an architecture decision |
| `/refresh-context` | Bring the context files up to date |
