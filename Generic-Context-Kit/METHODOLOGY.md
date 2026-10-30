# The Methodology

AI coding agents are only as good as what they know about the project. Without context, an agent guesses at structure, invents patterns and makes changes that need human approval without asking. This kit replaces guessing with a small set of written files that agents read before every task, plus a disciplined way of working through the build.

## Principles

1. **Write it down once.** Every fact about the project lives in one context file. Other files link to it rather than repeating it. Rules live in `AGENTS.md` and `context/`, and workflows live in `context/playbooks/`. Tool-specific files only point to them.
2. **Small units, approved specs.** Work is broken into units that fit in one pull request. Each unit gets a written spec with testable acceptance criteria, and a person approves it before any code is written.
3. **People stay in control.** Agents stop at approval gates: authentication, migrations, dependencies, pipelines, deletions, design tokens, logos, approved brand copy and anything else listed in `context/ai-workflow-rules.md`. Agents can prepare a review, but a person reviews and merges every change.
4. **Safe by default.** No secrets, no production data and no real personal data, anywhere in the repository or in prompts. The context check looks for likely secrets on every pull request.
5. **Context is code.** Context files are reviewed, versioned and kept accurate in the same pull request as the change that affects them. Each file has an owner and a review date, and the check flags files that are overdue.
6. **Facts, not guesses.** A section left blank with an open question is better than a confident invention. Agents leave `FILL` comments in place and raise questions instead of making things up.

## The six core files

| File | Answers |
| --- | --- |
| `project-overview.md` | What are we building, for whom, and what is out of scope? |
| `architecture.md` | What is the stack, where does code go, and what may depend on what? |
| `code-standards.md` | How is code written, named, tested and committed here? |
| `ui-context.md` | What does it look like, and how must it behave for users? |
| `ai-workflow-rules.md` | What may agents do alone, what needs approval, and what must they never do? |
| `progress-tracker.md` | Where are we now, what is next, and what is blocked? |

The first five change slowly. The progress tracker changes with every unit, which is how one session hands over to the next, whether the next session is a person or an agent.

## Enterprise modules

Enterprise projects need more than the core six. The modules cover what a client, auditor or support team will ask about:

- **Security and compliance:** data classification, regulations, secrets, authentication and incident contacts.
- **Integrations:** every external system, how it is called and what happens when it fails.
- **Environments and delivery:** environments, branching, Bitbucket pipelines, deployment, configuration by environment, the parity between Staging and Production, schema promotion and rollback.
- **Quality and testing:** test types, commands, the checks every unit passes before staging, accessibility and performance testing, and the review checklist.
- **Operations:** hosting, monitoring, backups, support and runbooks.
- **Go-live:** readiness criteria, pre-launch checks, the cutover plan, smoke tests, rollback, hypercare, the rehearsal and the snag log.

A module that does not apply is kept and marked `Not applicable`, so its absence is a recorded decision rather than an oversight.

## Decisions and specs

- **Decision records** (`context/decisions/`) capture why significant choices were made. They stop agents, and new team members, from reopening settled questions. Accepted decisions are never edited; a new record supersedes them.
- **The build plan** (`context/specs/00-build-plan.md`) orders the units: a production-like deployment first, then foundations, then the highest-priority features, with risky work early. It plans regular releases to Staging and, before the first go-live, a rehearsal.
- **Unit specs** are written just before each unit is built, so they reflect what earlier units taught the team. Each one has a Release impact section listing what every environment needs beyond the code.

## The cycle

```text
Set up context ──> Plan the build ──> Write unit spec ──> Implement unit ──┐
                                            ^                             │
                                            └────────── next unit ────────┘
```

1. **Set up context.** The agent drafts each file from the brief, designs and existing code. A person confirms each one.
2. **Plan the build.** The agent proposes the units and their order. A person approves the plan.
3. **Write the unit spec.** The agent writes scope, approach, approval gates and acceptance criteria. A person approves it and marks it `Ready`.
4. **Implement the unit.** The agent builds it, runs every check in the definition of done, verifies each acceptance criterion, keeps the release impact current and updates the context. A person reviews and merges the pull request. The unit is `Done` only once it has been deployed to the first shared environment and its criteria rechecked there.

Five workflows support the cycle:

- **Small changes.** Not every change deserves a spec. A bug fix with a known cause, a text change, a visual fix using existing tokens, a documentation change or a test-only change can go through `fix-small.md` instead. The lane is narrow on purpose: the change must add nothing new, touch no approval gate or protected path, and a person must confirm that it qualifies. When in doubt, it is a unit.
- **Reviews.** `review-unit.md` has the agent check a pull request against its spec, the rules and the brand files, and write a report with severities and a recommendation. The agent never approves, merges or posts the review; a person decides.
- **Releases.** `prepare-release.md` collects the release impact of every unit in a release into one checklist, checks it against the diff and the target environment, and lists the gaps. For Production it also checks the go-live readiness criteria. The agent never deploys to Production or signs off; people do.
- **Decisions.** `record-decision.md` turns a significant choice into an ADR, and supersedes an old one rather than editing it.
- **Refreshing the context.** Context drifts. `refresh-context.md` compares the context files with the code and the decisions, proposes corrections, and changes a review date only once the owner has confirmed the file. It also reads the snag log and turns repeated causes into rules or checks.

## Staging and go-live

The point of the kit is fewer snags at staging and go-live. Snags cannot be eliminated, but most come from a small set of causes, and each cause has a place where the kit catches it earlier:

- **Something nobody wrote down,** such as a new setting, secret, licence or manual step. Every unit spec records its release impact as it is built, reviews block on anything missing, and the release checklist is assembled from those sections rather than from memory.
- **Something that worked only locally.** A unit is not done until it has run in a shared environment, and the first unit proves the whole deployment path before any features exist.
- **Something different in Production.** The parity table makes every Staging and Production difference a recorded, accepted risk instead of a surprise.
- **Something checked too late.** Accessibility, performance, security and deployability checks run on every unit, not in a crunch before launch.
- **Something done only once.** The go-live plan is rehearsed end to end in Staging, including rollback, before it is run in Production.
- **The same snag twice.** The snag log records each snag's cause, and refreshing the context turns repeated causes into rules, checks and acceptance criteria for the next release.

## Brands and design tokens

Enterprise clients often run several brands or markets on one platform. Each brand gets its own file in `context/brands/` with its personality, voice, theme, logos, imagery and approved copy, so an agent writing a headline or styling a block knows which brand it is working for. What every brand shares, such as components, layout, accessibility and the token structure, stays in `context/ui-context.md`.

Design token values live in one place: the token source named in `ui-context.md`. Context files and brand files name themes and link to the source; they never copy values such as hex codes, because copies drift. Changing a token value, a theme, a logo or approved brand copy is an approval gate, so these changes never go through the small-change lane.

## Placeholders

Templates use two kinds of placeholder:

- `{{TOKEN}}` values are filled in by `eck init` from your answers and the chosen profile. Any left in a file are errors.
- `<!-- FILL: ... -->` comments are guidance for the person or agent filling in the file. Each one is replaced with real content and deleted. A file can be marked `Active` only when none remain.

## Profiles

The scaffold is stack-neutral. A profile adds what is specific to a stack: verify commands, extra approval gates, protected paths, schema promotion rules and extra context files. The kit ships with the `generic` profile, which suits any stack and is the default. New profiles extend it, for example one for a particular CMS or framework, or for multi-site solutions where each site has its own brand, hostnames and theme.
