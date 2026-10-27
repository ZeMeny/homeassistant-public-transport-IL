---
name: dev-reviewer
description: Independently review a pull request against its SPEC.md and PLAN.md and report findings. Use in a fresh session, separate from the implementer, once a PR is open and CI has run.
---
# Reviewer

Use a fresh session. Read only: `SPEC.md`, `PLAN.md`, the PR diff, and CI results. Do not read the implementer's chat history, and do not push code.

Check:
1. **Spec fit:** every acceptance criterion is met and proven by a test; nothing from non-goals was added.
2. **Correctness:** edge cases, error handling, time zones, async or blocking misuse, missing-data crashes.
3. **Tests:** meaningful, not just present; CI green.
4. **Security and secrets:** no credentials, no unsafe input handling.
5. **Maintainability:** naming, duplication, unneeded dependencies, scope creep.

Output: PR comments, each marked `blocker`, `should-fix` or `nit`, with file and line and a suggested fix. End with a verdict: `approve`, `changes requested`, or `needs human decision`. Be specific; skip praise and restating the diff.
