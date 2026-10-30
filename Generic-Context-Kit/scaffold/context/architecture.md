# Architecture

| Owner | Last reviewed | Status |
| --- | --- | --- |
| {{OWNER}} | {{TODAY}} | Draft |

How the system is put together: the stack, the structure, and the boundaries that code must respect. Agents use this file to decide where new code belongs and what it may depend on.

Replace each `FILL` comment with real content, then delete the comment. When no `FILL` comments remain, set Status to `Active`.

## System overview

<!-- FILL: A short description of the main parts of the system and how they talk to each other. A simple text diagram helps, for example:

    Browser -> CDN -> Web app -> Database
                         |
                         +-> Search service
                         +-> CRM API
-->

## Stack

| Layer | Choice | Version | Notes |
| --- | --- | --- | --- |
<!-- FILL: One row per layer: language and runtime, framework, CMS, front-end build, styling, database, search, hosting, CI/CD, monitoring. Pin major versions. Example: "| Runtime | .NET | 8 (LTS) | Upgrade only through an ADR |" -->

## Solution structure

<!-- FILL: The top-level folders or projects and what belongs in each. Show the tree, then one line per folder. Agents put new code where this section says it goes. -->

## Components and responsibilities

<!-- FILL: The main components or modules, what each one owns, and what each one must not do. Example: "Web: renders pages and handles requests. It must not call external APIs directly; it goes through the Integrations project." -->

## Dependency rules

<!-- FILL: Which parts may depend on which. Example: "Core has no dependencies on other projects. Web depends on Core and Integrations. Nothing depends on Web." -->

## Data and content model

<!-- FILL: The main entities or content types, where each is stored, and who owns it. Note any data that is personal or sensitive, and link to context/modules/security-compliance.md for how it is handled. -->

## Request and data flow

<!-- FILL: How a typical request moves through the system, and how data gets in and out (editors, imports, APIs, scheduled jobs). Include caching layers. -->

## Non-functional requirements

<!-- FILL: Targets for performance, availability, scale, accessibility, browser support and data retention. Use numbers where possible. Example: "Largest Contentful Paint under 2.5 s on 4G for the 75th percentile." -->

## Related context

- Integrations with other systems: `context/modules/integrations.md`
- Hosting and environments: `context/modules/environments-delivery.md`
- Security and compliance: `context/modules/security-compliance.md`
- Decisions behind this architecture: `context/decisions/`
