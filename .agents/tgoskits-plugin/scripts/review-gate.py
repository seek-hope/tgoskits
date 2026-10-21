#!/usr/bin/env python3
"""review-gate.py — detect and warn about self-review patterns."""

import os
import sys

import plugin_env


def check_self_review(workspace, plugin_root):
    """Returns (is_self_review, reason)."""

    # Check 1: task-active.flag exists (implementation session in progress)
    # Written by the pr-prep flow to the plugin cache directory.
    flag_path = os.path.join(plugin_root, "cache", "task-active.flag")
    if os.path.exists(flag_path):
        with open(flag_path) as f:
            task = f.read().strip()
        if task:
            return True, f"Implementation session active for '{task}'."

    # Check 2: log.md has recent Edit/Write activity
    log_path = os.path.join(workspace, "log.md")
    if os.path.exists(log_path) and os.path.getsize(log_path) > 0:
        return True, "Session has implementation activity (log.md non-empty)."

    return False, ""


def main():
    workspace = plugin_env.project_dir()
    plugin_root = plugin_env.plugin_root()

    is_self, reason = check_self_review(workspace, plugin_root)
    if is_self:
        print(
            f"[review-gate] Implementation session detected: {reason}",
            file=sys.stderr,
        )
        print(
            "[review-gate] For unbiased review, start a new session or spawn an "
            "isolated sub-agent.",
            file=sys.stderr,
        )

    sys.exit(0)


if __name__ == "__main__":
    main()
