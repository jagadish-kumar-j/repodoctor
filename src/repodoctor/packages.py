"""Read-only Python package requirement checking from a local venv."""

from __future__ import annotations

import re
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


def find_venv(path: Path) -> Path | None:
    for name in (".venv", "venv"):
        candidate = path / name
        if candidate.is_dir():
            return candidate
    return None


def find_dist_info_dirs(venv: Path) -> list[Path]:
    windows = venv / "Lib" / "site-packages"
    if windows.is_dir():
        return sorted((p for p in windows.glob("*.dist-info") if p.is_dir()), key=lambda p: p.name.lower())

    dirs: list[Path] = []
    lib = venv / "lib"
    if lib.is_dir():
        for python_dir in lib.glob("python*"):
            site_packages = python_dir / "site-packages"
            if site_packages.is_dir():
                dirs.extend(p for p in site_packages.glob("*.dist-info") if p.is_dir())
    return sorted(dirs, key=lambda p: p.name.lower())


def parse_installed_packages(venv: Path) -> dict[str, str]:
    installed: dict[str, str] = {}
    for directory in find_dist_info_dirs(venv):
        match = re.fullmatch(r"(.+)-([0-9][A-Za-z0-9.!+_-]*)\.dist-info", directory.name)
        if not match:
            continue
        name = canonicalize_name(match.group(1))
        installed[name] = match.group(2)
    return installed


def parse_requirements(path: Path) -> list[Requirement]:
    requirements_file = path / "requirements.txt"
    if not requirements_file.is_file():
        return []

    parsed: list[Requirement] = []
    try:
        lines = requirements_file.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        if "://" in line or line.startswith((".", "/", "\\")):
            continue
        try:
            requirement = Requirement(line)
        except Exception:
            continue
        if requirement.marker is not None:
            # Environment markers are ignored for matching, as requested.
            pass
        parsed.append(requirement)
    return parsed
