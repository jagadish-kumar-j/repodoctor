"""Fixed, non-destructive fix templates."""

from __future__ import annotations

import re

ENV_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")


def fixed_fix(kind: str, name: str, status: str) -> dict:
    """Return fixed problem text and commands for one report item."""
    kind = (kind or "").lower()
    status = (status or "").upper()

    if kind == "env" and isinstance(name, str) and ENV_NAME_RE.fullmatch(name):
        if status == "MISSING":
            return {
                "what": "The code needs this variable, but it is not set in .env.",
                "powershell": f'Add-Content .env "{name}=<your-value>"',
                "bash": f"echo '{name}=<your-value>' >> .env",
            }
        if status == "UNDOCUMENTED":
            return {
                "what": "The code reads this variable, but .env.example does not list it.",
                "powershell": f'Add-Content .env.example "{name}="',
                "bash": f"echo '{name}=' >> .env.example",
            }
        if status == "UNUSED":
            return {
                "what": "This variable is listed in .env.example but no code reads it.",
                "powershell": f"Get-ChildItem -Recurse -File | Select-String -Pattern {name}",
                "bash": f"grep -rn {name} .",
                "note": "If nothing uses it, remove that line from .env.example by hand.",
            }

    if kind == "tool":
        tool = str(name or "")
        if status == "MISSING":
            return {
                "what": f"{tool} is not installed.",
                "powershell": f"{tool} --version",
                "bash": f"{tool} --version",
                "note": "Install it from the official site, then open a new terminal.",
            }
        if status == "VERSION MISMATCH":
            return {
                "what": f"The installed {tool} version does not satisfy the required one.",
                "powershell": f"{tool} --version",
                "bash": f"{tool} --version",
                "note": "Install a version that satisfies the required one.",
            }
        if status == "NOT RUNNING":
            return {
                "what": "Docker is installed, but its daemon is not running.",
                "powershell": "docker info",
                "bash": "docker info",
                "note": "Start Docker Desktop, then run repodoctor check again.",
            }

    if kind == "port" and status == "PORT IN USE":
        port = str(name or "")
        return {
            "what": f"Something is already listening on port {port}.",
            "powershell": f"netstat -ano | findstr :{port}",
            "bash": f"lsof -i :{port}",
            "note": "It may be this project's own service. Check before stopping anything.",
        }

    return {"what": f"The report status is {status}."}
