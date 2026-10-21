#!/usr/bin/env python3
"""Pre-tool gate: block PR creation and direct push unless the branch is clean
and local CI has passed.

Usage: ``pre-pr-gate.py [command...]``. Exits 0 silently for commands that are
not ``gh pr create`` or ``git push``."""
import subprocess
import sys

import plugin_env

tool_input = plugin_env.tool_input()

# Only gate gh pr create and git push commands
if "gh pr create" not in tool_input and "git push" not in tool_input:
    sys.exit(0)

workspace = plugin_env.project_dir()
# Cache is per-plugin (shared across projects), not per-project.
# local-ci.sh writes last-ci-result.json to the plugin cache directory.
plugin_root = plugin_env.plugin_root()
cache_dir = plugin_env.cache_dir()


def check_clean_base():
    """Verify current branch is based on upstream/dev HEAD."""
    try:
        subprocess.run(
            ["git", "fetch", "upstream", "dev"],
            capture_output=True, cwd=workspace, timeout=30
        )
    except Exception:
        pass

    result = subprocess.run(
        ["git", "rev-parse", "upstream/dev"],
        capture_output=True, text=True, cwd=workspace
    )
    if result.returncode != 0:
        print(
            "BLOCKED: Cannot reach upstream/dev.\n"
            "Configure the upstream remote first:\n"
            "  git remote add upstream https://github.com/rcore-os/tgoskits.git\n"
            "  git fetch upstream dev",
            file=sys.stderr,
        )
        return False

    upstream_head = result.stdout.strip()

    merge_base = subprocess.run(
        ["git", "merge-base", "HEAD", upstream_head],
        capture_output=True, text=True, cwd=workspace
    ).stdout.strip()

    if merge_base != upstream_head:
        print(
            "BLOCKED: Branch is not based on upstream/dev HEAD.\n"
            "Create a clean branch first:\n"
            "  git fetch upstream dev\n"
            "  git checkout -b <feature-branch> upstream/dev",
            file=sys.stderr
        )
        return False
    return True


def check_local_ci():
    """Check if local CI has passed."""
    ci_file = os.path.join(cache_dir, "last-ci-result.json")
    ci_script = os.path.join(plugin_root, "scripts", "local-ci.sh")
    if not os.path.exists(ci_file):
        print(
            "BLOCKED: Local CI has not been run.\n"
            "Run at minimum:\n"
            f"  bash {ci_script} quick",
            file=sys.stderr
        )
        return False

    import json
    try:
        with open(ci_file) as f:
            data = json.load(f)
        if data.get("status") != "pass":
            print(
                "BLOCKED: Local CI did not pass.\n"
                f"Status: {data.get('status', 'unknown')}\n"
                "Fix the issues and re-run CI.",
                file=sys.stderr
            )
            return False
    except (json.JSONDecodeError, KeyError):
        print(
            "BLOCKED: Local CI result file is corrupted.\n"
            f"Re-run: bash {ci_script} quick",
            file=sys.stderr
        )
        return False
    return True


def check_direct_push():
    """Block direct pushes to main/dev."""
    if "git push" in tool_input:
        # Check if pushing to main or dev
        current_branch = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, cwd=workspace
        ).stdout.strip()

        if current_branch in ("main", "dev"):
            print(
                "BLOCKED: Direct push to main/dev is forbidden.\n"
                "Use a feature branch and create a PR.",
                file=sys.stderr
            )
            return False
    return True


# Run checks
for check in (check_clean_base, check_local_ci, check_direct_push):
    if not check():
        sys.exit(1)

sys.exit(0)
