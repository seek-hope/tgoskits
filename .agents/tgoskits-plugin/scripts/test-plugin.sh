#!/usr/bin/env bash
# Deterministic self-check for the tgoskits-plugin.
#
# Verifies syntax, agent/prompt frontmatter, bundled files, gate wiring, and
# that the MCP server answers `tools/list`. Exits non-zero on the first failure.
set -euo pipefail

PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_ROOT="$(cd "$PLUGIN_ROOT/../.." && pwd)"
cd "$PLUGIN_ROOT"

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

pass() {
    echo "ok: $*"
}

# 1. Python syntax
for f in scripts/*.py mcp/server.py; do
    python3 -m py_compile "$f" || fail "python syntax: $f"
done
pass "python syntax"

# 2. Bash syntax
for f in scripts/*.sh; do
    bash -n "$f" || fail "bash syntax: $f"
done
pass "bash syntax"

# 3. Bundled files and dependency wiring
TGOSKITS_PROJECT_DIR="$PROJECT_ROOT" python3 scripts/validate-deps.py \
    || fail "validate-deps"
pass "dependencies"

# 4. Agent frontmatter: name/description present, no harness-specific fields
for f in agents/*.md; do
    head -1 "$f" | grep -qx -- '---' || fail "missing frontmatter: $f"
    grep -q '^name: ' "$f" || fail "missing name: $f"
    grep -q '^description: ' "$f" || fail "missing description: $f"
    if grep -qE '^(model|color|tools):' "$f"; then
        fail "harness-specific frontmatter field: $f"
    fi
done
pass "agent frontmatter"

# 5. Prompt frontmatter
for f in prompts/*.md; do
    head -1 "$f" | grep -qx -- '---' || fail "missing frontmatter: $f"
    grep -q '^description: ' "$f" || fail "missing description: $f"
done
pass "prompt frontmatter"

# 6. MCP server answers tools/list
response=$(printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' \
    | python3 mcp/server.py)
python3 - "$response" <<'PY' || fail "mcp tools/list"
import json
import sys

payload = json.loads(sys.argv[1])
tools = {tool["name"] for tool in payload["result"]["tools"]}
expected = {
    "validate_deps",
    "docker_check",
    "pre_pr_gate",
    "review_gate",
    "local_ci",
    "syscall_diff",
    "generate_journal",
}
missing = expected - tools
if missing:
    raise SystemExit(f"missing MCP tools: {sorted(missing)}")
PY
pass "mcp tools/list"

# 7. Every MCP tool maps to a bundled script
python3 - <<'PY' || fail "mcp tool wiring"
import json
import os
import re

source = open("mcp/server.py").read()
scripts = set(os.listdir("scripts"))
for script in re.findall(r'run_script\("([^"]+)"', source):
    if script not in scripts:
        raise SystemExit(f"MCP server references missing script: {script}")
PY
pass "mcp tool wiring"

echo "all plugin checks passed"
