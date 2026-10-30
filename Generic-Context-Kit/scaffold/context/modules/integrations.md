# Integrations

| Owner | Last reviewed | Status |
| --- | --- | --- |
| {{OWNER}} | {{TODAY}} | Draft |

The external systems this project connects to and how each connection works. Agents read this file before writing code that calls, or is called by, another system.

If the project has no integrations, set Status to `Not applicable` and delete the sections below.

Replace each `FILL` comment with real content, then delete the comment. When no `FILL` comments remain, set Status to `Active`.

## Summary

| System | Purpose | Direction | Owner | Environments available |
| --- | --- | --- | --- | --- |
<!-- FILL: One row per external system. Direction is Outbound (we call it), Inbound (it calls us) or Both. Example: "| Salesforce Marketing Cloud | Newsletter sign-ups | Outbound | Client CRM team | Sandbox, Production |" -->

## General rules

- All calls to external systems go through the integration layer described in `context/architecture.md`. Pages, views and controllers never call external APIs directly.
- Every outbound call has a timeout, and failures are logged without personal data.
- A failure in an external system should degrade the feature, not take down the page.
- Credentials for each system are stored as described in `context/modules/security-compliance.md`.
- Tests use fakes or recorded responses. They never call a live external system.

## Systems

Copy this section once for each system in the summary table.

### System name

<!-- FILL: For each system:
- What it is used for, and which features depend on it.
- API type and version (for example REST, GraphQL, SOAP or webhook), and a link to its documentation.
- Base URL for each environment. Never include credentials.
- How requests are authenticated (for example OAuth client credentials or an API key in a header).
- Rate limits and quotas.
- Data sent and received, noting any personal data.
- Timeout, retry and caching behaviour.
- What users see when the system is unavailable.
- Who to contact when it fails.
-->

## Inbound endpoints and webhooks

<!-- FILL: Endpoints this project exposes to other systems: the path, who calls it, how calls are authenticated or signed, and the payload format. -->

## Scheduled jobs and imports

<!-- FILL: Any scheduled sync, import or export jobs: what they do, how often they run, where they run, and what happens when one fails. -->
