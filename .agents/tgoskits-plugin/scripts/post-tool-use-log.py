#!/usr/bin/env python3
"""Activity log: append a summary of working-tree changes to ``log.md``.

Run after edits so the journal generator has a change trail. ``log.md`` lives
in the project workspace, not in the plugin directory."""
import os
import sys
from datetime import datetime, timezone

import plugin_env

PLUGIN_ROOT = plugin_env.plugin_root()
WORKSPACE = plugin_env.project_dir()
LOG_PATH = os.path.join(WORKSPACE, "log.md")


def get_changed_files():
    """Get list of files modified in working tree (staged + unstaged vs HEAD)."""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True, text=True, cwd=WORKSPACE
        )
        staged = subprocess.run(
            ["git", "diff", "--name-only", "--cached"],
            capture_output=True, text=True, cwd=WORKSPACE
        )
        files = set()
        if result.stdout:
            files.update(f.strip() for f in result.stdout.strip().split("\n") if f.strip())
        if staged.stdout:
            files.update(f.strip() for f in staged.stdout.strip().split("\n") if f.strip())
        return sorted(files)
    except Exception:
        return []


def get_last_commit_message():
    """Get the last commit's subject line."""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%s"],
            capture_output=True, text=True, cwd=WORKSPACE
        )
        return result.stdout.strip()
    except Exception:
        return ""


def append_log(files, summary):
    """Append an entry to log.md."""
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y-%m-%d %H:%M")
    count = len(files)
    file_list = ", ".join(f"`{f}`" for f in files[:10])
    if len(files) > 10:
        file_list += f" (+{len(files) - 10} more)"
    summary = summary[:500]

    entry = f"""## {timestamp} — {count} file{'s' if count != 1 else ''} changed

**Files**: {file_list}

**Summary**: {summary}

---
"""
    # Deduplicate: skip only if identical to the immediately preceding entry
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH) as f:
            content = f.read()
        # Get last entry block (everything after the last "---" separator)
        last_sep = content.rfind("\n---\n")
        last_entry = content[last_sep + 1:].strip() if last_sep >= 0 else content.strip()
        if entry.strip() == last_entry:
            return

    with open(LOG_PATH, "a") as f:
        f.write(entry)


if __name__ == "__main__":
    files = get_changed_files()
    if not files:
        sys.exit(0)

    commit_msg = get_last_commit_message()
    summary = commit_msg if commit_msg else "Code changes (see git log for details)"
    append_log(files, summary)
