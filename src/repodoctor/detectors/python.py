"""Python requirement detector.

Reads pyproject.toml (project.requires-python) and .python-version.
Falls back to requirements.txt if no other Python indicator exists.
"""

from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

from repodoctor.models import Requirement


def detect(path: Path) -> list[Requirement]:
    """Detect Python requirements in the given directory.

    Priority:
    1. pyproject.toml "project.requires-python"
    2. .python-version
    3. requirements.txt (only if no other Python indicator found)
    """
    found_spec: str | None = None
    found_source: str | None = None

    pyproject = path / "pyproject.toml"
    if pyproject.is_file():
        try:
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            requires_python = data.get("project", {}).get("requires-python")
            if requires_python:
                found_spec = str(requires_python)
                found_source = "pyproject.toml"
        except Exception:
            pass

    if found_spec is None:
        python_version = path / ".python-version"
        if python_version.is_file():
            try:
                spec = python_version.read_text(encoding="utf-8").strip()
                if spec:
                    found_spec = spec
                    found_source = ".python-version"
            except OSError:
                pass

    if found_spec is not None:
        return [
            Requirement(
                tool="python",
                version_spec=found_spec,
                source=found_source,
            )
        ]

    requirements_txt = path / "requirements.txt"
    if requirements_txt.is_file():
        return [
            Requirement(
                tool="python",
                version_spec=None,
                source="requirements.txt",
            )
        ]

    return []
