# Lifecycle gates without harness hooks

Claude Code style plugins react to lifecycle events (`SessionStart`,
`PreToolUse`, `PostToolUse`, `Stop`). Those events do not exist in every agent
runtime, so this plugin keeps the *behaviour* and drops the *event plumbing*.
Each former hook is now a callable gate that any harness, MCP client, or prompt
template can call at the equivalent moment.

## Mapping

| Former event | Gate | Script | When to call |
|---|---|---|---|
| SessionStart | `validate_deps` | `scripts/validate-deps.py` | session start, before long work |
| SessionStart | `review_gate` | `scripts/review-gate.py` | before starting a review |
| PreToolUse (Bash, docker) | `docker_check` | `scripts/docker-check.py` | before a docker command |
| PreToolUse (Bash, PR/push) | `pre_pr_gate` | `scripts/pre-pr-gate.py` | before `gh pr create` / `git push` |
| PostToolUse (Edit/Write) | activity log | `scripts/post-tool-use-log.py` | after meaningful edits |
| Stop | `generate_journal` | `scripts/journal-generator.py` | when the task ends |

## Policy per gate

- **`validate_deps`** — blocking. A missing skill or bundled file means a later
  gate would fail unpredictably, so fail loudly and early.
- **`review_gate`** — warning only. It never blocks; it reports that the current
  session has implementation activity and that review should run in a fresh
  context.
- **`docker_check`** — blocking for docker commands only. Never fall back to
  running tests on the host.
- **`pre_pr_gate`** — blocking. Requires `upstream/dev` to be reachable, the
  branch to be based on its HEAD, a passing `cache/last-ci-result.json`, and no
  direct push to `main`/`dev`.
- **activity log + `generate_journal`** — advisory. They build the change trail
  and the journal; they never block delivery.

## State

Gate state lives in `.agents/tgoskits-plugin/cache/`:

| File | Written by | Read by |
|---|---|---|
| `last-ci-result.json` | `scripts/local-ci.sh` | `pre_pr_gate`, `generate_journal` |
| `task-active.flag` | PR preparation phase | `review_gate`, session-end journal |
| `task-started-at.txt` | PR preparation phase | `generate_journal` |

The cache is local runtime state and is not tracked.

## Invoking the gates

Three equivalent paths:

1. **MCP tools** — `mcp/server.py` exposes every gate as a tool, so an agent can
   call them without shelling out.
2. **Scripts** — run them directly with `TGOSKITS_PROJECT_DIR` set:
   `python3 scripts/pre-pr-gate.py "git push"`.
3. **Prompt templates** — `prompts/pr-prep.md` calls the gates in the correct
   order for the full PR workflow.

All three share `scripts/plugin_env.py` for path resolution, so behaviour cannot
drift between them.
