# tgoskits-plugin

Agent-agnostic workflow plugin for the TGOSKits monorepo: local CI, PR
preparation, independent review, feature implementation, bug hunting, driver
auditing, and syscall comparison for OS/kernel work.

This plugin deliberately avoids harness-specific packaging. It ships portable
pieces that most agent runtimes can consume:

| Piece | Location | Consumed as |
|---|---|---|
| Subagent personas | `agents/*.md` | agent definitions / subagent prompts |
| Prompt templates | `prompts/*.md` | `/test`, `/pr-prep` commands |
| Workflow gates | `mcp/server.py` | MCP tools |
| Gate and CI scripts | `scripts/` | direct invocation |
| CI image config | `config/docker-ci.toml` | read by `scripts/local-ci.sh` |

Repository skills live in `.agents/skills/` and are shared with the whole
repository; this plugin references them instead of duplicating them.

## Agents

| Agent | Purpose |
|---|---|
| `pr-review` | POSIX/Linux semantic review with the Fresh Eyes Protocol (CPI-06) |
| `self-evolve` | Cyclic self-audit of this plugin with fresh-context rounds (CPI-07) |
| `bug-hunt` | Find bugs, write repro tests, fix, verify |
| `impl` | Implement missing StarryOS features end to end |
| `test-gen` | Generate tests from reference Linux behavior |
| `driver-audit` | Audit drivers against the four-layer architecture |

Each agent declares only `name`, `description`, and the repository skills it
depends on, so any harness can load it.

## MCP tools

Run `python3 .agents/tgoskits-plugin/mcp/server.py` as a stdio MCP server. It
exposes:

| Tool | Effect |
|---|---|
| `validate_deps` | Verify required repository skills and bundled files exist |
| `docker_check` | Refuse docker commands when the daemon is unreachable |
| `pre_pr_gate` | Block `gh pr create` / `git push` until the branch is ready |
| `review_gate` | Warn when a session looks like self-review |
| `local_ci` | Run quick, full, or single os/arch Docker CI |
| `syscall_diff` | Compare a Linux strace trace with target OS output |
| `generate_journal` | Build a task journal from `log.md` and CI results |

Example registration (pi):

```json
{
  "mcpServers": {
    "tgoskits": {
      "command": "python3",
      "args": [".agents/tgoskits-plugin/mcp/server.py"]
    }
  }
}
```

Any MCP client can register the same command instead.

## Prompt templates

Copy or reference `prompts/` from your agent's prompt directory:

- `/test [quick|full|fmt|clippy|starry|arceos|axvisor] [arch]`
- `/pr-prep <title>`

## Path resolution

Gate scripts resolve their locations through `scripts/plugin_env.py`:

| Variable | Meaning | Fallback |
|---|---|---|
| `TGOSKITS_PLUGIN_ROOT` | this plugin directory | derived from the script path |
| `TGOSKITS_PROJECT_DIR` | workspace the gates inspect | current directory |
| `TGOSKITS_TOOL_INPUT` | command text a pre-tool gate inspects | argument or stdin JSON |

The historical `CLAUDE_PLUGIN_ROOT`, `CLAUDE_PROJECT_DIR`, and
`CLAUDE_TOOL_INPUT` names are still honored, so existing hook wiring keeps
working without this plugin depending on it.

## Validation

```bash
python3 .agents/tgoskits-plugin/scripts/validate-deps.py
bash .agents/tgoskits-plugin/scripts/test-plugin.sh
```

`test-plugin.sh` checks Python and Bash syntax, agent and prompt frontmatter,
required bundled files, and that the MCP server answers `tools/list`.

## Requirements

- `python3` (no third-party packages)
- Docker for `local_ci`
- `gh` CLI for the PR phase of `/pr-prep`

See `docs/lifecycle-gates.md` for how the gates replace harness lifecycle hooks.
