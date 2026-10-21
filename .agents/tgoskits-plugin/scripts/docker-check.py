#!/usr/bin/env python3
"""Pre-tool gate: ensure Docker is running before executing docker commands.

Usage: ``docker-check.py [command...]``. Exits 0 silently when the command
needs no Docker or Docker is available, and exits 1 with instructions when a
docker command cannot run."""
import subprocess
import sys

import plugin_env


def docker_running():
    """Check if Docker daemon is reachable."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except FileNotFoundError:
        print(
            "BLOCKED: docker CLI not found in PATH.\n"
            "Install Docker: https://docs.docker.com/engine/install/",
            file=sys.stderr
        )
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print(
            "BLOCKED: Docker daemon is not responding (timeout).\n"
            "Start the daemon first:\n"
            "  sudo systemctl start docker",
            file=sys.stderr
        )
        sys.exit(1)
    except Exception as e:
        print(f"BLOCKED: Cannot connect to Docker: {e}", file=sys.stderr)
        sys.exit(1)


tool_input = plugin_env.tool_input()

# Only gate docker commands (not cargo, git, gh, etc.)
if "docker" not in tool_input:
    sys.exit(0)

if not docker_running():
    print(
        "BLOCKED: Docker daemon is not running.\n"
        "Start it before running Docker commands:\n"
        "  sudo systemctl start docker\n\n"
        "Do NOT fall back to running tests on the host machine.",
        file=sys.stderr
    )
    sys.exit(1)

sys.exit(0)
