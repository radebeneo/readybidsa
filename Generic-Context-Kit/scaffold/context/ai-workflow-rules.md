# AI Workflow Rules

| Owner | Last reviewed | Status |
| --- | --- | --- |
| {{OWNER}} | {{TODAY}} | Draft |

How AI agents work in this repository: what they may do on their own, what needs a person's approval, and what they must never do. These rules apply to every agent and every task.

The rules below are the enterprise defaults. Add project-specific rules where the `FILL` comments ask. Do not remove a default rule without the technical lead's approval. When no `FILL` comments remain, set Status to `Active`.

## Scope

- Work on one unit at a time, from an approved spec in `context/specs/`.
- A small, low-risk change may skip the spec only if it meets every criterion in `context/playbooks/fix-small.md` and a person confirms that it qualifies. Anything that touches an approval gate or a protected path below never qualifies.
- Change only what the unit needs. Note unrelated problems in `context/progress-tracker.md` instead of fixing them.
- If the spec is unclear or seems wrong, stop and ask. Do not fill gaps with assumptions.
- If a task would take the work outside the unit's scope, stop and say so before continuing.

## Before you change code

1. Read the context files listed in `AGENTS.md`.
2. Read the unit spec and any ADRs it references.
3. Look at how similar features are already built, and follow that pattern.
4. State your plan briefly: the files you will change and how you will check the result.

## Approval gates

Stop and get explicit approval from a person before you:

- Change authentication, authorisation, sessions, roles or permissions.
- Create, change or run database migrations, or change a schema.
- Add, remove or upgrade any dependency, package or tool.
- Change CI/CD pipelines, deployment scripts or infrastructure configuration.
- Deploy to, or change the configuration, secrets or data of, any shared environment such as Development or Staging.
- Change security headers, CORS, content security policy or cookie settings.
- Delete files or data that you did not create in the current task.
- Call an external service that has side effects, such as sending email or writing to a shared system.
- Change design token values, add or remove a theme, or change how a theme is chosen. The token source is named in `context/ui-context.md`.
- Change a logo, or approved brand copy such as claims, legal lines and disclaimers listed in a file in `context/brands/`.
- Add a brand, or change a brand file's personality, voice or rules.
{{APPROVAL_GATES}}
<!-- FILL: Add any project-specific approval gates, or delete this comment if there are none. -->

## Never

- Commit secrets, credentials, connection strings, certificates or API keys, even in examples or tests.
- Use production data, client data or real personal data in code, tests, fixtures, seed content, logs or prompts. Use synthetic data.
- Paste client-confidential material into tools or services that are not approved for it.
- Disable, skip or weaken tests, linting, type checks or the context check to make a build pass.
- Edit generated files by hand. Change the source and regenerate.
- Copy token values such as hex codes into components or context files. Use the tokens, and link to the token source.
- Approve, merge or post a review to a pull request. Prepare reviews with `context/playbooks/review-unit.md` for a person to use.
- Deploy to Production, change Production configuration, secrets or data, or sign off a release. Prepare the release checklist with `context/playbooks/prepare-release.md`; people run the production steps and sign off.
- Change files in these protected paths:
{{PROTECTED_PATHS}}

## Data handling

- Treat everything in this repository as client-confidential unless `context/modules/security-compliance.md` says otherwise.
- When you need example data, make it obviously fake, for example `jane.doe@example.com`.
- Never log personal data, tokens or full request bodies.

## When you are stuck

- If a command fails twice for the same reason, stop and report the error rather than trying variations.
- If you are unsure whether something needs approval, treat it as if it does.
- Say what you tried, what happened and what you need to continue.

## Finishing a unit

1. Meet the definition of done in `AGENTS.md`.
2. Check each acceptance criterion in the spec and say how you verified it.
3. Make sure the Release impact section of the spec lists everything the change needs in each environment beyond its code.
4. Update `context/progress-tracker.md`.
5. Update any context file that your change made out of date.
6. Summarise the change for the pull request: what changed, why, how to test it, and anything the reviewer should look at closely.

## Human review

Every change made by an agent is reviewed by a person in a Bitbucket pull request before it is merged. The reviewer is responsible for the change, not the agent.
<!-- FILL: Required reviewers, and any areas that need a second reviewer (for example security-sensitive code). -->
