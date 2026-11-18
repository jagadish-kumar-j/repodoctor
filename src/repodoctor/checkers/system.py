"""System checker: detects installed tools and machine state.

Only inspects the machine; never executes anything from the target repo.
"""

from __future__ import annotations

import shutil
import socket
import subprocess
import sys
from typing import Optional


def get_installed_version(tool: str) -> str | None:
    """Return the installed version string for a tool, or None if not installed.

    For "python", returns the current interpreter version.
    For other tools (e.g. "node", "docker"), runs `<tool> --version` via subprocess.
    Uses shutil.which to check availability first, with a subprocess timeout.
    """
    if tool == "python":
        return sys.version.split()[0]

    if shutil.which(tool) is None:
        return None

    try:
        result = subprocess.run(
            [tool, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        output = (result.stdout or result.stderr or "").strip()
        return output or None
    except (subprocess.SubprocessError, OSError):
        return None


def docker_status() -> str:
    """Return "ok", "not_installed", or "not_running" for Docker."""
    if shutil.which("docker") is None:
        return "not_installed"

    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return "ok"
        return "not_running"
    except (subprocess.SubprocessError, OSError):
        return "not_running"


def docker_compose_available() -> bool:
    """Return True if `docker compose version` succeeds."""
    if shutil.which("docker") is None:
        return False
    try:
        result = subprocess.run(
            ["docker", "compose", "version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, OSError):
        return False


def is_port_in_use(port: int) -> bool:
    """Return True if the given TCP port is in use on 127.0.0.1."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1)
            result = sock.connect_ex(("127.0.0.1", port))
            return result == 0
    except OSError:
        return False
