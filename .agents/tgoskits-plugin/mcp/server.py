#!/usr/bin/env python3
"""Stdio MCP server exposing the TGOSKits workflow gates as tools.

Any MCP-capable agent can call these tools instead of depending on a specific
harness's lifecycle hooks. The server is intentionally dependency free: it
speaks newline-delimited JSON-RPC 2.0 on stdin/stdout and shells out to the
scripts in ``../scripts``.

Tools:
  validate_deps   check that required repository skills and bundled files exist
  docker_check    verify the Docker daemon can run a docker command
  pre_pr_gate     block PR creation or direct push unless the branch is ready
  review_gate     warn when a session looks like self-review
  local_ci        run the Docker local CI (quick, full, or one os/arch test)
  syscall_diff    compare a Linux strace trace with target OS output
  generate_journal  build a task journal from log.md and CI results
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(PLUGIN_ROOT, "scripts")
PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "tgoskits-plugin", "version": "1.0.0"}

TOOLS = [
    {
        "name": "validate_deps",
        "description": (
            "Validate that the repository skills and bundled plugin files this "
            "workflow depends on are present. Run before a long review or "
            "implementation cycle."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_dir": {
                    "type": "string",
                    "description": "Repository root (default: current directory).",
                }
            },
        },
    },
    {
        "name": "docker_check",
        "description": (
            "Verify the Docker daemon is reachable before a docker command. "
            "Exits non-zero with recovery instructions when Docker is unusable."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The command about to run; only commands containing 'docker' are gated.",
                }
            },
            "required": ["command"],
        },
    },
    {
        "name": "pre_pr_gate",
        "description": (
            "Gate 'gh pr create' and 'git push': requires a branch based on "
            "upstream/dev, a passing local CI result, and no direct push to "
            "main/dev."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The command about to run (gh pr create / git push).",
                }
            },
            "required": ["command"],
        },
    },
    {
        "name": "review_gate",
        "description": (
            "Detect self-review patterns: an active implementation task flag or "
            "implementation activity in this session."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "local_ci",
        "description": (
            "Run local CI in the project Docker image. Modes: quick "
            "(fmt+clippy+sync-lint), full (all architectures), or test with "
            "os+arch for a single QEMU suite."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["quick", "full", "test", "rebuild"],
                    "description": "CI mode to run (default: quick).",
                },
                "os": {
                    "type": "string",
                    "description": "For mode=test: arceos, starry, or axvisor.",
                },
                "arch": {
                    "type": "string",
                    "description": "For mode=test: aarch64, riscv64, x86_64, or loongarch64.",
                },
            },
        },
    },
    {
        "name": "syscall_diff",
        "description": (
            "Compare a Linux strace log with target OS output and report "
            "syscall-level differences."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "linux_trace": {
                    "type": "string",
                    "description": "Path to `strace -f -v -o` output.",
                },
                "os_output": {
                    "type": "string",
                    "description": "Path to target OS stdout/stderr capture.",
                },
                "json": {
                    "type": "boolean",
                    "description": "Emit JSON instead of a Markdown report.",
                },
            },
            "required": ["linux_trace", "os_output"],
        },
    },
    {
        "name": "generate_journal",
        "description": (
            "Build <task>-journal.md from log.md and the last local CI result, "
            "then clear log.md."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Task name used for the journal filename.",
                }
            },
            "required": ["task"],
        },
    },
]


def run_script(name: str, args: list[str], project_dir: str | None = None):
    """Run a bundled script and return (exit_code, combined_output)."""
    env = dict(os.environ)
    env["TGOSKITS_PLUGIN_ROOT"] = PLUGIN_ROOT
    if project_dir:
        env["TGOSKITS_PROJECT_DIR"] = project_dir

    path = os.path.join(SCRIPTS_DIR, name)
    command = [path, *args] if path.endswith(".sh") else [sys.executable, path, *args]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        cwd=project_dir or os.getcwd(),
        env=env,
    )
    output = "\n".join(
        part.strip() for part in (completed.stdout, completed.stderr) if part.strip()
    )
    return completed.returncode, output


def call_tool(name: str, arguments: dict):
    project_dir = arguments.get("project_dir")

    if name == "validate_deps":
        args = ["--project-dir", project_dir] if project_dir else []
        return run_script("validate-deps.py", args, project_dir)

    if name == "docker_check":
        return run_script("docker-check.py", [arguments["command"]], project_dir)

    if name == "pre_pr_gate":
        return run_script("pre-pr-gate.py", [arguments["command"]], project_dir)

    if name == "review_gate":
        return run_script("review-gate.py", [], project_dir)

    if name == "local_ci":
        mode = arguments.get("mode", "quick")
        args = [mode]
        if mode == "test":
            for key in ("os", "arch"):
                if not arguments.get(key):
                    return 1, f"local_ci mode=test requires '{key}'"
                args.append(arguments[key])
        return run_script("local-ci.sh", args, project_dir)

    if name == "syscall_diff":
        args = [arguments["linux_trace"], arguments["os_output"]]
        if arguments.get("json"):
            args.append("--json")
        return run_script("syscall-diff.py", args, project_dir)

    if name == "generate_journal":
        return run_script("journal-generator.py", [arguments["task"]], project_dir)

    return 1, f"unknown tool: {name}"


def tool_result(exit_code: int, output: str) -> dict:
    return {
        "content": [{"type": "text", "text": output or "(no output)"}],
        "isError": exit_code != 0,
    }


def handle(request: dict):
    """Return a JSON-RPC response, or None for notifications."""
    method = request.get("method")
    request_id = request.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": SERVER_INFO,
            },
        }

    if method == "notifications/initialized":
        return None

    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}

    if method == "tools/call":
        params = request.get("params") or {}
        name = params.get("name", "")
        arguments = params.get("arguments") or {}
        if name not in {tool["name"] for tool in TOOLS}:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32602, "message": f"unknown tool: {name}"},
            }
        exit_code, output = call_tool(name, arguments)
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": tool_result(exit_code, output),
        }

    if request_id is None:
        return None
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": f"method not found: {method}"},
    }


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as error:
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"parse error: {error}"},
            }
        else:
            response = handle(request)

        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()

    return 0


if __name__ == "__main__":
    sys.exit(main())
