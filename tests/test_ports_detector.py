"""Tests for the ports detector."""

from pathlib import Path
from unittest.mock import patch

from repodoctor.detectors.ports import detect as detect_ports

FIXTURES = Path(__file__).parent / "fixtures"


def test_ports_detect_docker_repo_fixture():
    reqs = detect_ports(FIXTURES / "docker_repo")
    ports = {r.version_spec for r in reqs}
    assert ports == {"3000", "5432", "8080"}


def test_ports_detect_host_port_not_container_port():
    """From '127.0.0.1:8080:80', host port is 8080, not 80."""
    reqs = detect_ports(FIXTURES / "docker_repo")
    port_entries = {r.version_spec for r in reqs}
    assert "8080" in port_entries
    assert "80" not in port_entries


def test_ports_detect_skips_variable_ports(tmp_path):
    """Ports like ${PORT}:3000 should be skipped."""
    compose = """
services:
  web:
    ports:
      - "${PORT}:3000"
      - "3000:3000"
"""
    (tmp_path / "docker-compose.yml").write_text(compose)
    reqs = detect_ports(tmp_path)
    ports = {r.version_spec for r in reqs}
    assert ports == {"3000"}


def test_ports_detect_skips_ranges(tmp_path):
    """Port ranges like 3000-3001:3000 should be skipped."""
    compose = """
services:
  web:
    ports:
      - "3000-3001:3000"
"""
    (tmp_path / "docker-compose.yml").write_text(compose)
    reqs = detect_ports(tmp_path)
    assert reqs == []


def test_ports_detect_dict_form(tmp_path):
    """Dict form ports: {published: 3000, target: 3000}."""
    compose = """
services:
  web:
    ports:
      - published: 3000
        target: 3000
"""
    (tmp_path / "docker-compose.yml").write_text(compose)
    reqs = detect_ports(tmp_path)
    assert len(reqs) == 1
    assert reqs[0].version_spec == "3000"


def test_ports_detect_env_example(tmp_path):
    """PORT=3000 and DB_PORT=5432 from .env.example."""
    (tmp_path / ".env.example").write_text("PORT=3000\nDB_PORT=5432\nOTHER=value")
    reqs = detect_ports(tmp_path)
    ports = {r.version_spec for r in reqs}
    assert ports == {"3000", "5432"}


def test_ports_detect_env_sample(tmp_path):
    """PORT=8080 from .env.sample."""
    (tmp_path / ".env.sample").write_text("PORT=8080")
    reqs = detect_ports(tmp_path)
    assert len(reqs) == 1
    assert reqs[0].version_spec == "8080"


def test_ports_detect_duplicate_removal(tmp_path):
    """Same port from compose and .env.example should appear once (first source wins)."""
    (tmp_path / "docker-compose.yml").write_text("services:\n  web:\n    ports:\n      - \"3000:3000\"")
    (tmp_path / ".env.example").write_text("PORT=3000")
    reqs = detect_ports(tmp_path)
    port_reqs = [r for r in reqs if r.version_spec == "3000"]
    assert len(port_reqs) == 1
    assert port_reqs[0].source == "docker-compose.yml"


def test_ports_detect_empty_repo():
    reqs = detect_ports(FIXTURES / "empty_repo")
    assert reqs == []


def test_ports_detect_malformed_compose(tmp_path):
    """Malformed compose YAML should not crash."""
    (tmp_path / "docker-compose.yml").write_text("services: [invalid")
    reqs = detect_ports(tmp_path)
    assert reqs == []


@patch("repodoctor.checkers.system.socket")
def test_is_port_in_use_mocked(mock_socket):
    """Port detection should work with mocked socket."""
    from repodoctor.checkers.system import is_port_in_use

    mock_sock = mock_socket.socket.return_value.__enter__.return_value
    mock_sock.connect_ex.return_value = 0  # port in use
    assert is_port_in_use(3000) is True

    mock_sock.connect_ex.return_value = 1  # port free
    assert is_port_in_use(3001) is False
