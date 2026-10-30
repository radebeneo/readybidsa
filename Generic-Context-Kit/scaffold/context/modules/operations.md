# Operations

| Owner | Last reviewed | Status |
| --- | --- | --- |
| {{OWNER}} | {{TODAY}} | Draft |

How the system is run and supported once it is live. Agents read this file before changing logging, health checks, caching, scheduled jobs or anything that affects how the system behaves in production.

Replace each `FILL` comment with real content, then delete the comment. When no `FILL` comments remain, set Status to `Active`.

## Hosting

<!-- FILL: Where each environment is hosted (for example Azure App Service, a managed platform service or the client's own data centre), who owns the hosting account, and the main resources such as web apps, databases, storage, CDN and search. -->

## Monitoring and alerts

<!-- FILL: The monitoring tools (for example Application Insights or Datadog), what is monitored (uptime, errors, response times, resource use), alert thresholds, and who receives each alert. -->

## Logging

<!-- FILL: Where logs go, how long they are kept, and how to search them. Logging rules for code are in context/code-standards.md, and what must never be logged is in context/modules/security-compliance.md. -->

## Health checks

<!-- FILL: The health check endpoints, what each one checks, and what uses them (for example the load balancer or uptime monitor). -->

## Backups and recovery

<!-- FILL: What is backed up (database, media, configuration), how often, how long backups are kept, where they are stored, and how to restore. Include the recovery point and recovery time objectives agreed with the client. -->

## Support

The extra support in the days straight after a go-live is described under Hypercare in `context/modules/go-live.md`. This section covers normal support once hypercare ends.

<!-- FILL: The support model after launch: support hours, how issues are reported, priority levels and response times, and who is on call. Use team or role names, not personal phone numbers. -->

## Runbooks

<!-- FILL: Links to, or short steps for, common operational tasks, for example clearing caches, rebuilding search indexes, restarting the site, rotating a secret and handling a traffic spike. -->

## Maintenance and upgrades

<!-- FILL: How and when the platform, framework and dependencies are upgraded, including end-of-support dates for the versions in use, and how upgrades are tested. -->
