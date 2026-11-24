"""Read-only Node package requirement checking from node_modules."""

from __future__ import annotations

import json
import re
from pathlib import Path

NODE_NAME_RE = re.compile(r"^(@[a-z0-9][a-z0-9._~-]*/)?[a-z0-9][a-z0-9._~-]*$")


def parse_package_json(path: Path) -> dict | None:
    package_json = path / "package.json"
    if not package_json.is_file():
        return None
    try:
        if package_json.stat().st_size > 1_048_576:
            return None
        data = json.loads(package_json.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def get_dependencies(data: dict) -> dict[str, str]:
    dependencies = {}
    for key in ("dependencies", "devDependencies"):
        value = data.get(key)
        if isinstance(value, dict):
            dependencies.update(value)
    return dependencies


def is_safe_node_name(name: str) -> bool:
    return isinstance(name, str) and bool(NODE_NAME_RE.fullmatch(name))


def read_installed_version(path: Path, name: str) -> str | None:
    if not is_safe_node_name(name):
        return None
    module_root = path / "node_modules"
    package_json = module_root / name / "package.json"
    try:
        resolved = package_json.resolve()
        if not resolved.is_relative_to(module_root.resolve()):
            return None
    except (OSError, ValueError):
        return None
    if not package_json.is_file():
        return None
    try:
        if package_json.stat().st_size > 1_048_576:
            return None
        data = json.loads(package_json.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    version = data.get("version")
    return str(version) if isinstance(version, str) else None


def check_node_packages(path: Path) -> tuple[dict[str, str], bool]:
    """Return (dependency map, has_package_json)."""
    data = parse_package_json(path)
    if data is None:
        return {}, False
    return get_dependencies(data), True
