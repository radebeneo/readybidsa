# Code Standards

| Owner | Last reviewed | Status |
| --- | --- | --- |
| {{OWNER}} | {{TODAY}} | Draft |

How code is written in this project. Agents follow these rules for every change. Where a rule here conflicts with a tool's default, this file wins.

Replace each `FILL` comment with real content, then delete the comment. When no `FILL` comments remain, set Status to `Active`.

## Principles

These apply to every language in the project. Change them only by agreement with the technical lead.

- Prefer clear code over clever code. The next reader may be a new team member or an agent.
- Follow the existing pattern in the file or folder you are working in, even if you would do it differently.
- Keep changes small and focused on the unit being built. Do not refactor unrelated code.
- Handle errors where you can do something useful about them. Never swallow an exception silently.
- No dead code, commented-out code or unexplained `TODO` comments. Record follow-up work in `context/progress-tracker.md`.

## Languages

| Language | Style guide | Formatter and linter |
| --- | --- | --- |
<!-- FILL: One row per language used, for example C#, TypeScript, SCSS, Razor. Example: "| C# | Microsoft C# coding conventions, nullable enabled | dotnet format, .editorconfig |" -->

## Naming

<!-- FILL: Naming rules for files, folders, classes, methods, variables, CSS classes, database objects and CMS aliases. Give one example of each. -->

## Project organisation

<!-- FILL: Where each kind of code goes, for example controllers, services, view models, views, components, styles and tests, and how files are named. Point to context/architecture.md for the overall structure. -->

## Error handling and logging

<!-- FILL: How errors are raised, caught and shown to users. Which logger to use, what log levels mean, and what must never be logged (for example personal data, tokens or full request bodies). -->

## Configuration

<!-- FILL: How settings are read (for example the options pattern or environment variables), how they are named, and which file or store holds each kind of setting. Secrets never go in the repository. -->

## Data access

<!-- FILL: How code reads and writes data: which libraries, where queries live, how transactions and caching are handled, and how migrations are created. -->

## Comments and documentation

<!-- FILL: When comments are expected (for example public APIs and non-obvious decisions), the format for doc comments, and which READMEs must be kept up to date. -->

## Dependencies

- Every new or upgraded dependency needs human approval. See `context/ai-workflow-rules.md`.
- Prefer the platform's built-in features and the libraries already in use.
<!-- FILL: Approved package sources (for example the company NuGet or npm feed), licence rules and any banned libraries. -->

## Source control

<!-- FILL: Branch naming (for example feature/PROJ-123-short-description), commit message format, pull request size and description rules, required reviewers in Bitbucket, and merge strategy. -->

## Examples

<!-- FILL: Two or three short examples of code that follows these standards, taken from this project once it has some. Short "do" and "don't" pairs are the most useful kind. -->
