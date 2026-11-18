"""Node.js requirement detector.

Reads package.json (engines.node), .nvmrc, and .node-version files.
"""

from __future__ import annotations

import json
from pathlib import Path

from repodoctor.models import Requirement


def detect(path: Path) -> list[Requirement]:
    """Detect Node.js requirements in the given directory.

    Priority:
    1. package.json "engines.node"
    2. .nvmrc
    3. .node-version
    4. If package.json exists but none of the above, version_spec=None
    """
    package_json = path / "package.json"
    engines_spec = None
    can_read_package_json = False

    if package_json.is_file():
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
            can_read_package_json = True
            if isinstance(data, dict):
                engines = data.get("engines", {})
                if isinstance(engines, dict):
                    engines_spec = engines.get("node")
        except (json.JSONDecodeError, OSError, UnicodeDecodeError, ValueError):
            can_read_package_json = False

    if engines_spec is not None:
        return [
            Requirement(
                tool="node",
                version_spec=str(engines_spec),
                source="package.json",
            )
        ]

    nvmrc = path / ".nvmrc"
    if nvmrc.is_file():
        try:
            spec = nvmrc.read_text(encoding="utf-8").strip()
            if spec:
                return [
                    Requirement(
                        tool="node",
                        version_spec=spec,
                        source=".nvmrc",
                    )
                ]
        except OSError:
            pass

    node_version = path / ".node-version"
    if node_version.is_file():
        try:
            spec = node_version.read_text(encoding="utf-8").strip()
            if spec:
                return [
                    Requirement(
                        tool="node",
                        version_spec=spec,
                        source=".node-version",
                    )
                ]
        except OSError:
            pass

    if can_read_package_json and engines_spec is None:
        return [
            Requirement(
                tool="node",
                version_spec=None,
                source="package.json",
            )
        ]

    return []
