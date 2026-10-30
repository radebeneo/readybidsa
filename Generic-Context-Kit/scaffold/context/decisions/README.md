# Decision Records

An architecture decision record (ADR) captures one significant decision, why it was made and what it rules out. Agents check these records before proposing a change to the architecture, libraries or patterns, so the same question is not reopened without reason.

## When to write one

Write an ADR when a decision:

- is hard or expensive to reverse, for example choosing a framework, hosting platform or data store
- sets a pattern that later work must follow
- rejects an obvious alternative that someone is likely to suggest again
- trades one requirement against another, for example speed of delivery against flexibility

## How to write one

Agents follow `context/playbooks/record-decision.md`, which covers these steps in more detail. People can follow the same playbook or the short version below.

1. Copy `ADR-0000-template.md` to `ADR-NNNN-short-title.md`, using the next free number.
2. Fill in every section, then delete the guidance comments.
3. Set Status to `Proposed` and raise it in a pull request for review.
4. Once agreed, set Status to `Accepted` and add it to the index below.

Never edit an accepted ADR to change the decision. Write a new ADR that supersedes it, and set the old one's Status to `Superseded by ADR-NNNN`.

## Index

| ADR | Title | Status | Date |
| --- | --- | --- | --- |
| None yet | | | |
