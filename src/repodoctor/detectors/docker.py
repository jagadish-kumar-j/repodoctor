"""Docker requirement detector."""

from __future__ import annotations

from pathlib import Path

import yaml

from repodoctor.models import Requirement

COMPOSE_FILENAMES = ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml")


def _find_compose_file(path: Path) -> str | None:
    for name in COMPOSE_FILENAMES:
        if (path / name).is_file():
            return name
    return None


def _parse_compose(path: Path) -> dict | None:
    compose_file = _find_compose_file(path)
    if compose_file is None:
        return None
    try:
        data = yaml.safe_load((path / compose_file).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        return data
    except Exception:
        return None


def detect(path: Path) -> list[Requirement]:
    """Detect Docker-related requirements in the given directory."""
    requirements: list[Requirement] = []

    dockerfile = path / "Dockerfile"
    if dockerfile.is_file():
        requirements.append(
            Requirement(tool="docker", version_spec=None, source="Dockerfile")
        )

    compose_data = _parse_compose(path)
    if compose_data is not None:
        compose_file = _find_compose_file(path)
        if compose_file is not None:
            requirements.append(
                Requirement(
                    tool="docker",
                    version_spec=None,
                    source=compose_file,
                )
            )
            requirements.append(
                Requirement(
                    tool="docker-compose",
                    version_spec=None,
                    source=compose_file,
                )
            )

    return requirements
