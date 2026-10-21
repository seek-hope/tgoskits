"""Resolve plugin and project paths for any agent runtime.

The gate scripts are harness agnostic. They read their locations from
environment variables so any agent runner (or the bundled MCP server) can
invoke them, and they keep reading the historical ``CLAUDE_*`` variables as a
fallback so existing Claude Code hook wiring keeps working.

Environment variables, in priority order:

``TGOSKITS_PLUGIN_ROOT`` / ``CLAUDE_PLUGIN_ROOT``
    Root of this plugin directory (contains ``scripts/`` and ``config/``).
``TGOSKITS_PROJECT_DIR`` / ``CLAUDE_PROJECT_DIR``
    Workspace the gates inspect. Defaults to the current directory.
``TGOSKITS_TOOL_INPUT`` / ``CLAUDE_TOOL_INPUT``
    Command text a pre-tool gate should inspect. ``None`` when absent.
"""

from __future__ import annotations

import json
import os
import sys

_PLUGIN_ROOT_ENV = ("TGOSKITS_PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT")
_PROJECT_DIR_ENV = ("TGOSKITS_PROJECT_DIR", "CLAUDE_PROJECT_DIR")
_TOOL_INPUT_ENV = ("TGOSKITS_TOOL_INPUT", "CLAUDE_TOOL_INPUT")


def _first_env(names: tuple[str, ...]) -> str | None:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return None


def default_plugin_root() -> str:
    """Plugin root derived from this file: ``<root>/scripts/plugin_env.py``."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def plugin_root() -> str:
    return _first_env(_PLUGIN_ROOT_ENV) or default_plugin_root()


def project_dir() -> str:
    return _first_env(_PROJECT_DIR_ENV) or os.getcwd()


def cache_dir() -> str:
    """Shared gate cache: CI results, the task-active flag, image hashes."""
    return os.path.join(plugin_root(), "cache")


def tool_input(argv: list[str] | None = None) -> str:
    """Command text to gate, from arguments, environment, or stdin JSON.

    Positional arguments win so an MCP tool call can pass the command
    explicitly. Without arguments the historical hook protocols are honored.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    if args:
        return " ".join(args)

    env_value = _first_env(_TOOL_INPUT_ENV)
    if env_value:
        return env_value

    if sys.stdin is None or sys.stdin.isatty():
        return ""
    try:
        data = json.load(sys.stdin)
    except Exception:
        return ""
    if isinstance(data, dict):
        return str(data.get("input") or data.get("command") or "")
    return ""
