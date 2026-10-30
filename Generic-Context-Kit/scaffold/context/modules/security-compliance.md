# Security and Compliance

| Owner | Last reviewed | Status |
| --- | --- | --- |
| {{OWNER}} | {{TODAY}} | Draft |

How this project protects data, handles secrets and meets the client's legal and policy requirements. Agents read this file before touching authentication, personal data, configuration, logging or anything that crosses a trust boundary.

Replace each `FILL` comment with real content, then delete the comment. When no `FILL` comments remain, set Status to `Active`.

## Data classification

| Data | Classification | Where it is stored | Retention |
| --- | --- | --- | --- |
<!-- FILL: One row per kind of data the system holds or passes through, for example form submissions, member accounts, analytics events and editor accounts. Classification is Public, Internal, Confidential or Personal. Example: "| Contact form submissions | Personal | CMS database, forwarded to CRM | 12 months |" -->

## Regulations and policies

<!-- FILL: The laws, standards and client policies that apply, and what each one requires of this project. Examples: GDPR, POPIA, CCPA, PCI DSS, the client's information security policy, cookie consent rules. Note the person responsible for compliance sign-off. -->

## Personal data

- Collect only the personal data a feature needs, and say why in the unit spec.
- Never log personal data. Mask or omit it in error messages and telemetry.
- Never copy production personal data into development, test or staging environments.
<!-- FILL: Consent capture, cookie banner and tag management rules, subject access and deletion requests, and data processing agreements with third parties. -->

## Secrets and configuration

- Secrets never go in the repository, including in example files, tests and pipeline YAML.
- Each environment has its own secrets. A secret from one environment is never reused in another.
<!-- FILL: Where secrets are stored (for example Azure Key Vault or Bitbucket secured repository variables), how developers get local values (for example user secrets or a local .env file listed in .gitignore), who can read production secrets, and how secrets are rotated. -->

## Authentication and authorisation

Changes in this area always need human approval. See `context/ai-workflow-rules.md`.

<!-- FILL: How each kind of user signs in (for example CMS editors through Microsoft Entra ID, site members through a customer identity provider), roles and permissions, session lifetime, and multi-factor requirements. -->

## Application security

- Follow the OWASP Top 10 and the OWASP Application Security Verification Standard at the level agreed with the client.
- Validate all input on the server. Encode all output for the context it is rendered in.
- Use parameterised queries or the ORM. Never build SQL from strings.
- Protect state-changing requests against cross-site request forgery.
<!-- FILL: Required security headers and content security policy, CORS rules, file upload rules, rate limiting and bot protection (for example on forms). -->

## Dependencies and scanning

<!-- FILL: The tools used to scan dependencies and code (for example Snyk, Dependabot, SonarQube or Mend), when they run, and the rule for fixing findings, for example "critical and high findings block the release". -->

## Security testing

<!-- FILL: Penetration test schedule, who performs it, and how findings are tracked. -->

## Incidents

<!-- FILL: Who to contact if a security issue or data breach is suspected, the client's notification requirements and time limits, and where the incident process is documented. Use team or role names, not personal phone numbers. -->
