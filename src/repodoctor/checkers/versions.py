"""Version satisfaction checker.

Supports Node.js spec formats (exact, >=, ^, ~, .x, v-prefixed, ranges)
and Python spec formats via the packaging library.
Returns None for specs that cannot be parsed (meaning "unknown").
"""

from __future__ import annotations

import re
from typing import Optional

from packaging.specifiers import SpecifierSet
from packaging.version import InvalidVersion, Version


def _node_parts(version_str: str) -> tuple[int, int, int] | None:
    """Parse a Node version string like 'v18.17.0' into (major, minor, patch)."""
    cleaned = version_str.lstrip("vV")
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)", cleaned)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def satisfies(installed: str, spec: str | None) -> bool | None:
    """Check if the installed version satisfies the spec.

    Returns True if satisfied, False if not, None if unknown/unparseable.
    """
    if spec is None:
        return None

    spec = spec.strip()

    # Try Python packaging library first (handles >=, ==, ~=, !=, ===, etc.)
    try:
        specifier_set = SpecifierSet(spec)
        installed_version = Version(installed.lstrip("vV"))
        return installed_version in specifier_set
    except (InvalidVersion, ValueError):
        pass

    # Node-specific formats
    installed_parts = _node_parts(installed)
    installed_major = installed_parts[0] if installed_parts else None

    # "18.x" - major version match
    match = re.fullmatch(r"(\d+)\.x", spec)
    if match:
        if installed_major is None:
            return None
        return installed_major == int(match.group(1))

    # "v18" - major version with v prefix
    match = re.fullmatch(r"v(\d+)", spec, re.IGNORECASE)
    if match:
        if installed_major is None:
            return None
        return installed_major == int(match.group(1))

    # "^18.0.0" - semver caret: >=18.0.0 <19.0.0 (major must match)
    match = re.fullmatch(r"\^(\d+)\.(\d+)\.(\d+)", spec)
    if match:
        if installed_major is None:
            return None
        return installed_major == int(match.group(1))

    # "~18.17.0" - semver tilde: >=18.17.0 <18.18.0
    match = re.fullmatch(r"~(\d+)\.(\d+)\.(\d+)", spec)
    if match:
        if installed_major is None:
            return None
        major = int(match.group(1))
        minor = int(match.group(2))
        if installed_major != major:
            return False
        if installed_parts is None:
            return None
        return installed_parts[1] == minor and installed_parts[2] >= int(match.group(3))

    # ">=18 <21" - major version range
    match = re.fullmatch(r">=\s*(\d+)\s*<\s*(\d+)", spec)
    if match:
        if installed_major is None:
            return None
        return int(match.group(1)) <= installed_major < int(match.group(2))

    # ">=18" - major version gte
    match = re.fullmatch(r">=\s*(\d+)", spec)
    if match:
        if installed_major is None:
            return None
        return installed_major >= int(match.group(1))

    # Exact version "18.17.0"
    match = re.fullmatch(r"\d+\.\d+\.\d+", spec)
    if match:
        if installed_parts is None:
            return None
        spec_parts = _node_parts(spec)
        if spec_parts is None:
            return None
        return installed_parts == spec_parts

    return None
