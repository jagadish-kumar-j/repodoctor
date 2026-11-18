"""Tests for the Docker detector."""

from pathlib import Path

from repodoctor.detectors.docker import detect as detect_docker

FIXTURES = Path(__file__).parent / "fixtures"


def test_docker_detect_dockerfile_only(tmp_path):
    (tmp_path / "Dockerfile").write_text("FROM node:18")
    reqs = detect_docker(tmp_path)
    assert len(reqs) == 1
    assert reqs[0].tool == "docker"
    assert reqs[0].version_spec is None
    assert reqs[0].source == "Dockerfile"


def test_docker_detect_compose_only(tmp_path):
    (tmp_path / "docker-compose.yml").write_text("services:\n  web:\n    image: nginx")
    reqs = detect_docker(tmp_path)
    # Should return both docker and docker-compose requirements
    assert len(reqs) == 2
    tools = {r.tool for r in reqs}
    assert tools == {"docker", "docker-compose"}
    for r in reqs:
        assert r.version_spec is None
        assert r.source == "docker-compose.yml"


def test_docker_detect_dockerfile_and_compose(tmp_path):
    (tmp_path / "Dockerfile").write_text("FROM node:18")
    (tmp_path / "docker-compose.yml").write_text("services:\n  web:\n    image: nginx")
    reqs = detect_docker(tmp_path)
    tools = {r.tool for r in reqs}
    assert tools == {"docker", "docker-compose"}
    sources = {r.source for r in reqs}
    assert "Dockerfile" in sources
    assert "docker-compose.yml" in sources


def test_docker_detect_docker_repo_fixture():
    reqs = detect_docker(FIXTURES / "docker_repo")
    tools = {r.tool for r in reqs}
    assert tools == {"docker", "docker-compose"}
    assert len(reqs) == 3  # Dockerfile + docker (from compose) + docker-compose


def test_docker_detect_empty_repo():
    reqs = detect_docker(FIXTURES / "empty_repo")
    assert reqs == []


def test_docker_detect_bad_compose(tmp_path):
    """Malformed compose file should be skipped, not crash."""
    (tmp_path / "docker-compose.yml").write_text("services: [invalid: yaml")
    # No Dockerfile, malformed compose -> empty
    reqs = detect_docker(tmp_path)
    assert reqs == []


def test_docker_detect_bad_compose_repo_fixture():
    reqs = detect_docker(FIXTURES / "bad_compose_repo")
    assert reqs == []
