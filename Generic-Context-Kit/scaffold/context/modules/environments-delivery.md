# Environments and Delivery

| Owner | Last reviewed | Status |
| --- | --- | --- |
| {{OWNER}} | {{TODAY}} | Draft |

Where the project runs, how code gets there, and how releases are made. Agents read this file before changing configuration, pipelines or anything that behaves differently between environments.

Changes to pipelines, deployment scripts and infrastructure always need human approval. See `context/ai-workflow-rules.md`.

Replace each `FILL` comment with real content, then delete the comment. When no `FILL` comments remain, set Status to `Active`.

## Environments

| Environment | Purpose | URL | Deployed from | Data |
| --- | --- | --- | --- | --- |
<!-- FILL: One row per environment. Example: "| Development | Integration testing by the team | https://dev.example.com | develop branch, automatically | Synthetic only |". Typical environments are Local, Development, Staging or UAT, and Production. -->

## Local setup

<!-- FILL: What a developer needs installed (with versions), how to get the code running locally, how to get local configuration values, and how to get a local database or content. Keep this short and link to the repository README for detail. -->

## Branching and pull requests

<!-- FILL: The branching model (for example trunk-based with short-lived feature branches, or Gitflow), branch naming, which branches are protected in Bitbucket, required approvals and checks before merge, and the merge strategy. -->

## Pipelines

The project uses Bitbucket Pipelines. Every pull request runs the context check:

```yaml
- step:
    name: Context check
    image: node:lts-slim
    script:
      - node context/check-context.mjs
```

<!-- FILL: The other steps in bitbucket-pipelines.yml and what each does, for example build, unit tests, linting, front-end build, security scan, packaging and deployment. Note which steps run on pull requests, which run on merge, and which need a manual trigger. -->

## Deployment

<!-- FILL: How each environment is deployed (for example a Bitbucket deployment step to an Azure App Service), who can trigger a deployment, what approval production needs, and any deployment windows or change-freeze periods. -->

## Configuration by environment

Every setting a unit adds needs a value in every environment, or a recorded reason for having none, before it is released. The unit spec's Release impact section lists them.

<!-- FILL: How settings differ between environments and where each environment's values come from, for example appsettings.{Environment}.json for non-secret values and Key Vault for secrets. Say who can change each environment's values. List any feature flags. -->

## Environment parity

Staging is where a release is proved, so it should match Production in everything that can change how the release behaves. Each difference below is a known risk that someone has accepted. A difference that is not listed is an unknown risk, and a likely go-live snag.

| Area | Staging | Production | Why it is accepted | How the risk is covered |
| --- | --- | --- | --- | --- |
<!-- FILL: One row per difference between Staging and Production. Check at least: hosting plan and instance count, load balancing, runtime and framework versions, database engine and size, CDN, caching and firewall rules, authentication provider, integration endpoints (sandbox or live), email delivery, licences, hostnames and certificates, scheduled jobs, and data volume. Example: "| Instances | 1 | 2, load balanced | Cost | Load-balanced setup tested in the go-live rehearsal |". If nothing differs, replace this comment with a sentence saying so and the date it was checked. -->

## Schema and content promotion

{{SCHEMA_PROMOTION}}

## Releases

Every release to Staging or Production has a checklist prepared with `context/playbooks/prepare-release.md`, built from the Release impact section of each unit it contains. The first go-live, and every later major release, also follows `context/modules/go-live.md`.

<!-- FILL: How a release is prepared and approved, versioning, release notes, where release checklists are kept, who signs off with the client, and how the client is told. -->

## Rollback

<!-- FILL: How to roll back a failed deployment, including code, schema and content. Say what cannot be rolled back automatically, and the point of no return for a release, for example once a migration has run or editors have created content on a new content type. -->
