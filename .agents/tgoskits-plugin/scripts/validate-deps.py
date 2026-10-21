#!/usr/bin/env python3
"""Validate the plugin's local dependencies.

The plugin consumes this repository's agent skills and ships its own agents,
prompts, scripts, and MCP server. This check makes broken wiring loud
immediately instead of failing later inside a gate script.

Checks:
  1. Every required repository skill exists with a ``SKILL.md``.
  2. Every bundled agent, prompt, and gate script is present.

Exits 0 when all dependencies are satisfied; exits 1 with a clear report
otherwise. Importable (exposes ``check_dependencies()``) and executable.

Usage: ``validate-deps.py [--project-dir DIR]``
"""

from __future__ import annotations

import argparse
import os
import sys

import plugin_env

# Repository skills this plugin delegates to. Each entry maps a skill name to
# the workflow that depends on it, so a failure message names the broken link.
REQUIRED_SKILLS = {
    "review-single-pr": "pr-review and review workflows",
    "review-open-prs": "batch PR review and triage",
    "starry-test-suit": "starry test placement",
    "arceos-test-adapter": "arceos test adaptation",
    "cross-kernel-driver": "driver layering audits",
    "test-quality": "test necessity and deduplication",
    "update-std-tests": "std test whitelist maintenance",
}

# Files bundled with this plugin. Paths are relative to the plugin root.
REQUIRED_BUNDLED_FILES = (
    "agents/pr-review.md",
    "agents/bug-hunt.md",
    "agents/impl.md",
    "agents/test-gen.md",
    "agents/driver-audit.md",
    "agents/self-evolve.md",
    "prompts/test.md",
    "prompts/pr-prep.md",
    "scripts/local-ci.sh",
    "scripts/pre-pr-gate.py",
    "scripts/review-gate.py",
    "scripts/docker-check.py",
    "mcp/server.py",
    "config/docker-ci.toml",
)


def resolve_skills_root(project_dir: str) -> str:
    """Directory holding repository skills: ``<project>/.agents/skills``."""
    return os.path.join(project_dir, ".agents", "skills")


def check_skills(project_dir: str) -> list[str]:
    skills_root = resolve_skills_root(project_dir)
    problems = []
    for name, workflow in REQUIRED_SKILLS.items():
        skill_file = os.path.join(skills_root, name, "SKILL.md")
        if not os.path.isfile(skill_file):
            problems.append(
                f"skill '{name}' missing: expected {skill_file} (needed by {workflow})"
            )
    return problems


def check_bundled_files(plugin_root: str) -> list[str]:
    problems = []
    for relative_path in REQUIRED_BUNDLED_FILES:
        path = os.path.join(plugin_root, relative_path)
        if not os.path.isfile(path):
            problems.append(f"bundled file missing: {path}")
    return problems


def check_dependencies(project_dir: str | None = None) -> bool:
    project_dir = project_dir or plugin_env.project_dir()
    plugin_root = plugin_env.plugin_root()

    problems = check_skills(project_dir) + check_bundled_files(plugin_root)
    if problems:
        print("BLOCKED: plugin dependencies are not satisfied:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        print(
            "\nRun this check from the repository root, or pass --project-dir.",
            file=sys.stderr,
        )
        return False

    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-dir",
        default=None,
        help="repository root containing .agents/skills (default: project dir)",
    )
    args = parser.parse_args(argv)
    return 0 if check_dependencies(args.project_dir) else 1


if __name__ == "__main__":
    sys.exit(main())
