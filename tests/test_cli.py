from pathlib import Path
from typer.testing import CliRunner

from repodoctor.cli import app

runner = CliRunner()


def test_check_existing_folder(tmp_path: Path):
    result = runner.invoke(app, ["check", str(tmp_path)])
    assert result.exit_code == 0
    assert f"Checking {tmp_path.resolve()}" in result.output


def test_check_nonexistent_path():
    result = runner.invoke(app, ["check", "/path/that/does/not/exist"])
    assert result.exit_code != 0
