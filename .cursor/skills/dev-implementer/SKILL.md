---
name: dev-implementer
description: Implement an approved PLAN.md on one branch with tests, tracking progress in the plan, and open one PR. Use only after the plan has been approved by the human.
---
# Implementer

Precondition: `SPEC.md` and `PLAN.md` are approved. If not, stop and say so.

Steps:
1. Follow the `pr-workflow` skill for branching, commits and PR rules.
2. Work through `PLAN.md` step by step. Write the test first where practical, then the code.
3. After each step: run tests and linters, tick the step in `PLAN.md`, commit.
4. Do not change `SPEC.md` or the plan's scope. If something does not fit, stop and report it with the options.
5. Open one PR linking the spec and plan, with what changed, how it was tested, and anything deferred.
6. When the reviewer's findings arrive, fix them in new commits and reply to each. Maximum two fix rounds, then ask the human.
7. Never merge your own PR.
