---
name: dev-loop
description: The overall design, plan, build, review loop for agent-made changes, with the human approval gates. Use at the start of any non-trivial feature to know which role to take and when to stop for approval.
---
# Development loop

Roles, each run in its own fresh session so context stays clean:

1. **Designer** (`dev-designer`) writes `SPEC.md`. **Gate A: human approves the spec.**
2. **Planner** (`dev-planner`) writes `PLAN.md` from the approved spec. **Gate B: human approves the plan. No code before this.**
3. **Implementer** (`dev-implementer`) builds the plan on one branch and opens one PR.
4. **Reviewer** (`dev-reviewer`) reviews the PR in a separate session with no access to the implementer's history. Findings go in as PR comments.
5. Implementer fixes findings. Maximum two fix rounds, then hand to the human.
6. **Gate C: human merges.** Agents never merge.

Rules:
- State lives in files in the repo (`SPEC.md`, `PLAN.md`) and in the PR, never only in chat.
- If a later role finds a problem with an earlier artifact, stop and report it; do not silently change it.
- Use a different model or tool for the reviewer than for the implementer when possible.
- Small tasks (typo, one-line fix) may skip Designer and Planner but still use a branch and PR.
