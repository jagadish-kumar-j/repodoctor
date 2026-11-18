"""Port requirement detector.

Parses compose files and .env.example / .env.sample files to find host ports.
"""

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


def _extract_host_port(ports_entry) -> str | None:
    """Extract the host port from a compose ports entry.

    Supports:
    - "3000:3000" -> host port "3000"
    - "127.0.0.1:8080:80" -> host port "8080"
    - dict form: {"published": "3000", "target": 3000} -> host port "3000"
    Skips ranges (e.g. "3000-3001:3000") and variables like ${PORT}.
    """
    if isinstance(ports_entry, str):
        port_str = ports_entry.strip()
        # Skip ranges
        if "-" in port_str.split(":")[0]:
            return None
        # Skip variables
        if "${" in port_str:
            return None
        parts = port_str.split(":")
        if len(parts) == 2:
            # "3000:3000" -> host port is first
            return parts[0]
        if len(parts) == 3:
            # "127.0.0.1:8080:80" -> host port is middle
            return parts[1]
        return None

    if isinstance(ports_entry, dict):
        published = ports_entry.get("published")
        if published is not None:
            published_str = str(published).strip()
            if "${" in published_str or "-" in published_str:
                return None
            return published_str
        return None

    return None


def _parse_compose_ports(path: Path, seen: set[tuple[str, str]], requirements: list[Requirement]) -> None:
    """Parse ports from a compose file, using shared seen set for dedup."""
    compose_data = _parse_compose(path)
    if compose_data is None:
        return

    services = compose_data.get("services", {})
    if not isinstance(services, dict):
        return

    compose_file = _find_compose_file(path)
    if compose_file is None:
        return

    for _service_name, service_config in services.items():
        if not isinstance(service_config, dict):
            continue
        ports = service_config.get("ports", [])
        if not isinstance(ports, list):
            continue
        for entry in ports:
            host_port = _extract_host_port(entry)
            if host_port is not None:
                key = ("port", host_port)
                if key not in seen:
                    seen.add(key)
                    requirements.append(
                        Requirement(
                            tool="port",
                            version_spec=host_port,
                            source=compose_file,
                        )
                    )


def _parse_env_ports(path: Path, filename: str, seen: set[tuple[str, str]], requirements: list[Requirement]) -> None:
    """Parse PORT= or *_PORT= lines from an env file, using shared seen set for dedup."""
    env_file = path / filename
    if not env_file.is_file():
        return

    try:
        lines = env_file.read_text(encoding="utf-8").splitlines()
    except OSError:
        return

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        # Skip variables
        if "${" in value:
            continue

        # Match PORT= or *_PORT=
        if key == "PORT" or key.endswith("_PORT"):
            key_tuple = ("port", value)
            if key_tuple not in seen:
                seen.add(key_tuple)
                requirements.append(
                    Requirement(
                        tool="port",
                        version_spec=value,
                        source=filename,
                    )
                )


def detect(path: Path) -> list[Requirement]:
    """Detect port requirements in the given directory."""
    requirements: list[Requirement] = []
    seen: set[tuple[str, str]] = set()

    _parse_compose_ports(path, seen, requirements)
    _parse_env_ports(path, ".env.example", seen, requirements)
    _parse_env_ports(path, ".env.sample", seen, requirements)

    return requirements
