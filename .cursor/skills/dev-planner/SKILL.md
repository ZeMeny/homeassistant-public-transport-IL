---
name: dev-planner
description: Turn an approved SPEC.md into a step-by-step PLAN.md with small verifiable steps, test strategy and risks, then wait for human approval. Use after the spec is approved and before any code is written.
---
# Planner

Input: approved `SPEC.md`. Output: `PLAN.md` (start from `templates/PLAN.md`).

Steps:
1. Read `SPEC.md`, `AGENTS.md` and the code the change touches.
2. Break the work into small steps, each verifiable (a test passes, a command output matches). One PR-sized scope total; split into several plans if larger.
3. For each acceptance criterion in the spec, name the test that proves it.
4. List files to be created or changed, new dependencies, and risks or unknowns.
5. Note a rollback path if the change is risky.
6. Commit `PLAN.md` on the task branch. Do not write production code.

Stop here. Present the plan to the human and wait for approval (Gate B). Incorporate feedback in `PLAN.md`; do not start implementing until approved.
