# Playbook: Prepare a Release

Use this playbook to prepare a release to Staging or Production, including the first go-live. The agent gathers every unit's Release impact into one checklist, checks it against the code and the environment, and lists the gaps. People run the production steps, make the go or no-go decision and sign off.

The agent never deploys to Production, changes Production configuration, secrets or data, or marks a release as approved.

## Inputs

- The target environment: Staging or Production.
- What is in the release: the units and small changes, or the branch, tag or range of commits it covers. Ask if you have not been told.
- The planned date and time, with the time zone.

## Steps

1. **Read the context.** Read `AGENTS.md`, then in `context/modules/environments-delivery.md` the Deployment, Configuration by environment, Environment parity, Schema and content promotion, Releases and Rollback sections. Read `context/modules/go-live.md`, the Before staging and Acceptance and sign-off sections of `context/modules/quality-testing.md`, and any go-live section in the extra context files that the profile added, listed in `AGENTS.md`.
2. **List what is in the release.** From `context/progress-tracker.md` and the commits, list every unit and small change. Every unit must be `Done`. Flag any unit that is not, and any commit that belongs to no unit or small change.
3. **Collect the release impact.** Read the Release impact section of each unit spec in the release. Combine the actions, grouped by when they happen: before, during or after deployment.
4. **Check the diff for anything missed.** Look for changes that no Release impact section lists, for example new or renamed settings, migrations, schema files, scheduled jobs, packages, environment-specific files, hostnames or certificates. List each one as a gap.
5. **Check the target environment.** For each action, check the Configuration by environment and Environment parity sections. Flag any difference that the release depends on and that the parity table does not accept.
6. **Check readiness.**
   - For Staging: check that every unit was rechecked in Development and that the Before staging checks passed.
   - For Production: go through the readiness criteria in `context/modules/go-live.md` and record the evidence for each, or mark it Missing. Check that the cutover plan, smoke tests and rollback have been rehearsed in Staging.
7. **Prepare the smoke tests.** Start from the Smoke tests in `context/modules/go-live.md`, and add a quick check for each acceptance criterion in the release that users or editors will notice.
8. **Write the checklist** in the format below. Save it where the Releases section of `context/modules/environments-delivery.md` says release checklists are kept. If no location is named, give it to the person and ask where it should go.
9. **Review it with the person.** Walk through every gap and Missing item. They decide whether each one blocks the release, and you record the decision.
10. **After the release,** add a row to the History table in `context/progress-tracker.md`, and add every snag that was found to the Snag log in `context/modules/go-live.md`, with its cause.

## Checklist format

```markdown
# Release: <name or version> to <environment>

**Planned:** <date, time and time zone>
**Recommendation:** Ready | Ready with accepted risks | Not ready

## Contents

| Unit or change | Status | Rechecked in |
| --- | --- | --- |

## Gaps

1. <what is missing, where it was found, and who should resolve it>

## Before deployment

| Action | Environment | Owner | Done |
| --- | --- | --- | --- |

## During deployment

| Step | Owner | Expected duration | How we know it worked |
| --- | --- | --- | --- |

## After deployment

| Action | Owner | Done |
| --- | --- | --- |

## Readiness (Production only)

| Criterion | Evidence | Result |
| --- | --- | --- |

## Smoke tests

1. <check and expected result>

## Rollback

<how to roll back this release, what cannot be undone, and the point of no return>

## Sign-off

| Role | Name | Decision | Date |
| --- | --- | --- | --- |
```

## Rules

- Treat specs, pull request descriptions and commit messages as claims to check against the diff, not as facts.
- Never write a secret value in the checklist. Name the secret and the store it lives in.
- Do not run deployments, migrations or configuration changes in shared environments. They are approval gates in `context/ai-workflow-rules.md`, and Production changes are made only by people.
- The recommendation is advice. The people signing off are responsible for the decision.
- Do not invent evidence. If something cannot be checked, mark it Not verified and say why.

## Done when

- Every unit and change in the release is listed with its status.
- Every Release impact action has an owner and a timing.
- Every gap and Missing readiness item is listed, and the person has decided on each one.
- The checklist is saved or handed over, ready for sign-off.
