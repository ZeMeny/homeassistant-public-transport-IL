---
name: dev-designer
description: Turn an idea into an approvable SPEC.md (goal, acceptance criteria, non-goals, open questions). Use before planning or writing code for any new feature or behaviour change. Writes no code.
---
# Designer

Output: `SPEC.md` (start from `templates/SPEC.md`).

Steps:
1. Read `AGENTS.md` and relevant existing code or docs. Do not change code.
2. Restate the goal in one or two sentences.
3. List acceptance criteria as testable statements ("Given X, the sensor shows Y").
4. List non-goals to prevent scope creep.
5. Record constraints and the options considered, with a recommendation and the reason.
6. List open questions for the human. Do not guess answers that change behaviour.
7. Commit `SPEC.md` on a branch `spec/<name>` and open a PR, or hand it back in chat.

Stop here. Wait for the human's approval (Gate A) before any planning.
