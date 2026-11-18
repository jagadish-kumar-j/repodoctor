"""Tests for requirement detectors."""

from pathlib import Path

from repodoctor.detectors.node import detect as detect_node
from repodoctor.detectors.python import detect as detect_python

FIXTURES = Path(__file__).parent / "fixtures"


def test_node_detect_package_json_engines():
    reqs = detect_node(FIXTURES / "node_repo")
    assert len(reqs) == 1
    assert reqs[0].tool == "node"
    assert reqs[0].version_spec == ">=18"
    assert reqs[0].source == "package.json"


def test_node_detect_nvmrc(tmp_path):
    (tmp_path / ".nvmrc").write_text("18")
    reqs = detect_node(tmp_path)
    assert len(reqs) == 1
    assert reqs[0].tool == "node"
    assert reqs[0].version_spec == "18"
    assert reqs[0].source == ".nvmrc"


def test_node_detect_node_version(tmp_path):
    (tmp_path / ".node-version").write_text("18.17.0")
    reqs = detect_node(tmp_path)
    assert len(reqs) == 1
    assert reqs[0].tool == "node"
    assert reqs[0].version_spec == "18.17.0"
    assert reqs[0].source == ".node-version"


def test_node_detect_package_json_no_engines(tmp_path):
    (tmp_path / "package.json").write_text('{"name": "test"}')
    reqs = detect_node(tmp_path)
    assert len(reqs) == 1
    assert reqs[0].tool == "node"
    assert reqs[0].version_spec is None
    assert reqs[0].source == "package.json"


def test_node_detect_empty_repo():
    reqs = detect_node(FIXTURES / "empty_repo")
    assert reqs == []


def test_node_detect_malformed_package_json(tmp_path):
    (tmp_path / "package.json").write_text("{invalid json")
    reqs = detect_node(tmp_path)
    assert reqs == []


def test_python_detect_pyproject():
    reqs = detect_python(FIXTURES / "python_repo")
    assert len(reqs) == 1
    assert reqs[0].tool == "python"
    assert reqs[0].version_spec == ">=3.10"
    assert reqs[0].source == "pyproject.toml"


def test_python_detect_python_version(tmp_path):
    (tmp_path / ".python-version").write_text("3.11")
    reqs = detect_python(tmp_path)
    assert len(reqs) == 1
    assert reqs[0].tool == "python"
    assert reqs[0].version_spec == "3.11"
    assert reqs[0].source == ".python-version"


def test_python_detect_requirements_txt_only(tmp_path):
    (tmp_path / "requirements.txt").write_text("requests>=2.0")
    reqs = detect_python(tmp_path)
    assert len(reqs) == 1
    assert reqs[0].tool == "python"
    assert reqs[0].version_spec is None
    assert reqs[0].source == "requirements.txt"


def test_python_detect_empty_repo():
    reqs = detect_python(FIXTURES / "empty_repo")
    assert reqs == []
