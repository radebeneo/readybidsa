# Playbook: Make a Small Change

Use this playbook for small, low-risk changes that do not need a unit spec, such as a bug fix with a known cause or a text change. The goal is a quick change that is still tested, checked and reviewed by a person.

## Does it qualify?

A change qualifies only if **all** of these are true:

- **It is one of these kinds:**
  - a bug fix where the cause and the expected behaviour are clear
  - a change to text, labels or translations
  - a visual fix that uses existing design tokens and components
  - a documentation or code comment change
  - a test-only change that adds coverage
- **It is small.** It changes a few files at most, and a reviewer can understand the whole diff in a few minutes.
- **It adds nothing new.** It adds no page, component, block, document type, endpoint, integration, setting or dependency.
- **It has no release impact.** It needs no new or changed setting, secret, schema, content, feature flag or manual step in any environment. It deploys like any other code change.
- **It touches no approval gate and no protected path** listed in `context/ai-workflow-rules.md`. This includes brand tokens, logos and approved brand copy such as claims and disclaimers.
- **Nothing else depends on it.** It does not change security, personal data handling or behaviour that other units rely on.

If any of these is false, or you are unsure, it is not a small change. Use `context/playbooks/write-unit-spec.md` instead.

## Steps

1. **Describe the change** in one or two sentences: what is wrong or needs changing, and what the result should be.
2. **Check that it qualifies.** Go through the criteria above and tell the person which kind of change it is. Ask them to confirm it qualifies. If it does not, say why and stop.
3. **Read the context.** Read `AGENTS.md` and the context files for the area you are changing. For a visual or copy change, also read `context/ui-context.md` and the brand file in `context/brands/` for each brand affected.
4. **For a bug fix, prove the bug.** Reproduce it, then write a test that fails because of it, wherever the project has tests for that area.
5. **Make the smallest change** that achieves the result. Do not tidy up nearby code. Record anything else you notice under Notes for the next session in `context/progress-tracker.md`.
6. **Watch the size.** If the change grows beyond the criteria while you work, stop and say so. It then needs a unit spec.
7. **Verify.** Run every command in the definition of done in `AGENTS.md` and fix any failures. Run `node context/check-context.mjs`. Review your own diff using the checklist in `context/modules/quality-testing.md`.
8. **Update the context** if the change made any context file out of date.
9. **Write the pull request description:**
   - **What and why:** the change and the reason for it.
   - **Small change:** the kind of change, and a statement that it touches no approval gate or protected path.
   - **How to test:** steps a reviewer can follow.
   - **Verified by:** the tests and checks you ran.

A person reviews and merges the pull request. Small changes are not added to the build plan or the progress tracker, unless they change something the next session needs to know.

## Done when

- The person has confirmed that the change qualifies.
- For a bug fix, a test fails without the fix and passes with it.
- Every check in the definition of done passes.
- The pull request description is ready for review.
