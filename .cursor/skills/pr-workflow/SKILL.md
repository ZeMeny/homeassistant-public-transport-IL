---
name: pr-workflow
description: Git and pull-request workflow for agent-made changes. Use whenever changing code in a repository - branching, committing, testing, and opening a PR. Never push directly to main.
---
# PR workflow

1. Sync: `git fetch && git switch main && git pull`.
2. Branch per task: `git switch -c <type>/<short-name>` (feat, fix, chore, docs).
3. Small commits, each with one logical change and an imperative message ("Add config flow").
4. Run tests and linters locally before every push; fix failures, don't skip them.
5. Push the branch and open a PR to `main` with: what changed, why, how it was tested, link to SPEC/issue.
6. CI is the gate: a PR is not done until checks pass. Never merge your own PR unless the human asks.
7. Never push to `main`, force-push shared branches, or rewrite published history.
8. Address review comments with new commits; keep the PR focused - open a new one for unrelated work.
