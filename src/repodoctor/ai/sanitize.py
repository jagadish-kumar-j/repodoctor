"""Create the restricted payload sent to AI providers."""

from __future__ import annotations

import re

ENV_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")


def build_payload(result) -> dict:
    """Build a payload containing only diagnostic fields safe to send."""
    requirements = []
    ports = set()

    for req in result.requirements:
        item = {
            "tool": req.tool,
            "required": req.required,
            "installed": req.installed,
            "status": req.status,
        }
        requirements.append(item)
        if req.tool.lower() == "port" and req.required:
            ports.add(req.required)

    environment_variables = []
    for env in result.env:
        name = env.variable
        if not isinstance(name, str) or not ENV_NAME_RE.fullmatch(name):
            continue
        environment_variables.append({"name": name, "status": env.status})

    return {
        "requirements": requirements,
        "ports": sorted(ports, key=lambda value: int(value) if value.isdigit() else value),
        "environment_variables": environment_variables,
    }
