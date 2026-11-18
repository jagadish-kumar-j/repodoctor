"""System checker: detects installed versions of tools.

Only inspects the machine; never executes anything from the target repo.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from typing import Optional


def get_installed_version(tool: str) -> str | None:
    """Return the installed version string for a tool, or None if not installed.

    For "python", returns the current interpreter version.
    For other tools (e.g. "node"), runs `<tool> --version` via subprocess.
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
