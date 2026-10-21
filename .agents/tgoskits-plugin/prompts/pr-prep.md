---
description: Full PR workflow - clean branch, code, CI loop, review loop, create PR
argument-hint: "<pr title>"
---

# Complete PR preparation workflow

PR title: `${1:?provide a Conventional Commits title, e.g. feat(axbuild): ...}`

Plugin root: `.agents/tgoskits-plugin` (override with `TGOSKITS_PLUGIN_ROOT`).
Before Phase 1 and again before Phase 5, confirm the completion evidence for
every claim you are about to report: clean tree, passing checks, submitted PR.

## Phase 1: Branch setup

Create a clean feature branch from `upstream/dev`:

```bash
git fetch upstream dev
UPSTREAM_REF=$(git rev-parse upstream/dev)
BRANCH_NAME=$(printf '%s' "${1:-}" | tr ' ' '-' | tr -cd 'a-zA-Z0-9/-' | tr '[:upper:]' '[:lower:]')
git checkout -b "$BRANCH_NAME" "$UPSTREAM_REF"
```

If `upstream/dev` is unreachable, stop and tell the user:

> Cannot find upstream/dev. Configure it with:
> `git remote add upstream https://github.com/rcore-os/tgoskits.git`

Mark the task active so the journal tools have a target:

```bash
mkdir -p .agents/tgoskits-plugin/cache
printf '%s\n' "$BRANCH_NAME" > .agents/tgoskits-plugin/cache/task-active.flag
date -u +%Y-%m-%dT%H:%M:%SZ > .agents/tgoskits-plugin/cache/task-started-at.txt
```

Report the branch name and that it is based on `upstream/dev`.

## Phase 2: Coding

Write the change. Append a change trail to `log.md` after meaningful edits,
either through the `activity_log` flow (`scripts/post-tool-use-log.py`) or by
summarizing the changed files yourself. When coding is done, move to Phase 3.

## Phase 3: CI loop

```bash
bash .agents/tgoskits-plugin/scripts/local-ci.sh full
```

- Pass: continue to Phase 4.
- Fail: show the failing commands with output, fix the code, re-run. At most
  five iterations, reporting `CI iteration <N>/5: fixed <what>, <list> still failing`.
  Do not proceed until CI passes. Never make a check pass by weakening it.

## Phase 4: Independent review loop

Do not read the reviewer agent inline: that carries implementation bias.
Delegate to a fresh context instead, using the bundled persona
`.agents/tgoskits-plugin/agents/pr-review.md` (or the `review-single-pr` skill
for a single named PR). Give the reviewer only the diff and the base ref:

```
Review the PR on branch <BRANCH>.
Base: upstream/dev.
Modified files: <git diff --name-only upstream/dev...HEAD>
Diff: <git diff upstream/dev...HEAD>
This is a third-party review; you have no prior knowledge of this code.
Apply the Fresh Eyes Protocol and emit REVIEW.md with BLOCK/WARN/INFO findings.
```

At most three iterations:

1. Collect `REVIEW.md`.
2. Fix every BLOCK item.
3. Commit: `git commit -am "fix(review): address BLOCK findings from review round N"`.
4. Re-run `bash .agents/tgoskits-plugin/scripts/local-ci.sh quick`.
5. Repeat with a fresh review context.

Report `Review iteration <N>/3: <X> BLOCK, <Y> WARN remaining`. At three
iterations with BLOCK items left, list them and ask the user before proceeding.

## Phase 5: PR creation

Write the body with the project template:

```markdown
## Summary
<One-line summary of what this PR does>

### 1. <Issue Title>

**Root Cause**: <logic-bug | memory-bug | validation-bug | resource-bug | data-race | atomicity-violation | order-violation | deadlock | lock-hierarchy-violation | missing-barrier | starvation | livelock>
**Manifestation**: <wrong-result | wrong-output | crash | hang | silent-corruption | leak>

**Analysis**: <root cause, which function/line, why the defect exists, which invariant was violated>

**Solution**: <files changed, the specific fix, and why it is correct>

**Repro**: `<path to test case>` - <one-line description of the minimal repro>
```

Then:

```bash
git push -u origin HEAD
gh pr create --base dev --title "<title>" --body "$PR_BODY"
python3 .agents/tgoskits-plugin/scripts/journal-generator.py "$BRANCH_NAME"
```

Report the PR URL and the journal path.

## Error handling

- `gh` missing: install from https://cli.github.com/
- Not authenticated: run `gh auth login`
- Push rejected for permissions: fork the repository first
