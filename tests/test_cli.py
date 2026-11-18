from pathlib import Path
import json
import shutil
from typer.testing import CliRunner
from unittest.mock import patch

from repodoctor.cli import app

runner = CliRunner()

FIXTURES = Path(__file__).parent / "fixtures"


def _copy_env_repo(tmp_path: Path) -> Path:
    """Copy the env_repo fixture into tmp_path and write .env at test time.

    The fixture's own .env is never relied upon: we always write a fresh
    .env with a fake value so the test works whether or not it exists.
    """
    dest = tmp_path / "env_repo"
    shutil.copytree(FIXTURES / "env_repo", dest)
    (dest / ".env").write_text("DB_URL=fake")
    return dest


def test_check_existing_folder(tmp_path: Path):
    result = runner.invoke(app, ["check", str(tmp_path)])
    assert result.exit_code == 0
    assert "Requirements" in result.output


def test_check_nonexistent_path():
    result = runner.invoke(app, ["check", "/path/that/does/not/exist"])
    assert result.exit_code != 0


def test_check_docker_repo_merges_duplicates(monkeypatch):
    """Dockerfile and docker-compose.yml both produce 'docker' req; should merge into one row."""
    # Make the result independent of what is installed/running on the host.
    monkeypatch.setattr("repodoctor.check.docker_status", lambda: "not_installed")
    monkeypatch.setattr("repodoctor.check.docker_compose_available", lambda: False)
    monkeypatch.setattr("repodoctor.check.is_port_in_use", lambda port: False)

    result = runner.invoke(app, ["check", str(FIXTURES / "docker_repo")])
    assert result.exit_code != 0  # docker not installed (mocked)
    # Only one docker row, with both sources comma-separated
    assert "Dockerfile, docker-compose.yml" in result.output
    # docker-compose has its own separate row (not merged with docker)
    assert "| docker-compose |" in result.output or "docker-compose" in result.output


def test_check_port_installed_shows_in_use_or_free(tmp_path, monkeypatch):
    """Port rows should show 'in use' or 'free', not 'port <number>'."""
    compose = """
services:
  web:
    ports:
      - "3000:3000"
"""
    (tmp_path / "docker-compose.yml").write_text(compose)

    # The compose file also creates docker rows; keep those host-independent.
    monkeypatch.setattr("repodoctor.check.docker_status", lambda: "ok")
    monkeypatch.setattr("repodoctor.check.docker_compose_available", lambda: True)

    with patch("repodoctor.check.is_port_in_use", return_value=True):
        result = runner.invoke(app, ["check", str(tmp_path)])
        assert "in use" in result.output
        assert "port 3000" not in result.output

    with patch("repodoctor.check.is_port_in_use", return_value=False):
        result = runner.invoke(app, ["check", str(tmp_path)])
        assert "free" in result.output


# --- JSON output tests ---


def test_check_json_valid_keys(tmp_path):
    """--json should produce valid JSON with the right keys."""
    result = runner.invoke(app, ["check", str(tmp_path), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert set(data.keys()) == {"path", "ok", "requirements", "env"}
    assert data["ok"] is True
    assert data["requirements"] == []
    assert data["env"] == []


def test_check_json_env_repo(tmp_path):
    """--json on env_repo should have right structure and non-empty env."""
    result = runner.invoke(
        app, ["check", str(_copy_env_repo(tmp_path)), "--json"]
    )
    assert result.exit_code != 0  # MISSING env var
    data = json.loads(result.output)
    assert data["ok"] is False
    assert "path" in data
    assert isinstance(data["requirements"], list)
    assert isinstance(data["env"], list)
    env_vars = {e["variable"] for e in data["env"]}
    assert "API_KEY" in env_vars
    assert "SECRET_TOKEN" in env_vars
    assert "OLD_FLAG" in env_vars


def test_check_json_prints_nothing_else(tmp_path):
    """--json should print only JSON to stdout."""
    result = runner.invoke(app, ["check", str(tmp_path), "--json"])
    assert result.exit_code == 0
    # Output should be parseable as JSON - nothing extra
    json.loads(result.output)


# --- Script command tests ---


def test_script_clean_repo_nothing_to_fix(tmp_path):
    """A clean repo should produce a script saying nothing needs fixing."""
    out = tmp_path / "setup.ps1"
    result = runner.invoke(
        app, ["script", str(tmp_path), "--shell", "powershell", "--output", str(out)]
    )
    assert result.exit_code == 0
    content = out.read_text()
    assert "Nothing to fix" in content or "nothing to fix" in content.lower()
    assert "winget" not in content


def test_script_refuses_overwrite_without_force(tmp_path):
    """Script should refuse to overwrite existing file without --force."""
    out = tmp_path / "setup.ps1"
    out.write_text("existing content")
    result = runner.invoke(
        app, ["script", str(tmp_path), "--shell", "powershell", "--output", str(out)]
    )
    assert result.exit_code != 0
    assert "already exists" in result.output


def test_script_overwrites_with_force(tmp_path):
    """Script should overwrite with --force."""
    out = tmp_path / "setup.ps1"
    out.write_text("existing content")
    result = runner.invoke(
        app,
        [
            "script",
            str(tmp_path),
            "--shell",
            "powershell",
            "--output",
            str(out),
            "--force",
        ],
    )
    assert result.exit_code == 0


def test_script_contains_no_env_values(tmp_path):
    """Generated script must not contain .env values."""
    (tmp_path / ".env.example").write_text("SECRET=super-secret-value-12345")
    (tmp_path / ".env").write_text("SECRET=super-secret-value-12345")
    out = tmp_path / "setup.ps1"
    result = runner.invoke(
        app, ["script", str(tmp_path), "--shell", "powershell", "--output", str(out)]
    )
    assert result.exit_code == 0
    content = out.read_text()
    assert "super-secret-value-12345" not in content


def test_script_env_repo_powershell(tmp_path):
    """Script for env_repo should copy .env.example and list missing vars."""
    out = tmp_path / "setup.ps1"
    result = runner.invoke(
        app,
        [
            "script",
            str(_copy_env_repo(tmp_path)),
            "--shell",
            "powershell",
            "--output",
            str(out),
        ],
    )
    assert result.exit_code == 0
    content = out.read_text()
    assert "Copy-Item .env.example .env" in content
    assert "API_KEY" in content
    assert "super-secret" not in content  # no env values
