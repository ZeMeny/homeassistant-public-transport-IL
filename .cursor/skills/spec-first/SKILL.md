---
name: spec-first
description: Write or update a SPEC.md before writing code for any new feature or non-trivial change. Use when a task has unclear scope, multiple possible designs, or more than one file to change.
---
# Spec first

1. If `SPEC.md` (or `specs/<feature>.md`) exists for the task, read it and work against it.
2. Otherwise draft one from `templates/SPEC.md`: goal, constraints, testable acceptance criteria, out of scope, open questions.
3. Ask the human to confirm open questions before coding. Do not guess on scope.
4. Break the spec into a `PLAN.md` of small steps, each verifiable by a test or a command.
5. While coding, update PLAN.md checkboxes and record decisions. If the spec turns out wrong, update it first, then the code.
6. Done = every acceptance criterion is checked and demonstrated (test, log, or screenshot) in the PR.
