"""Tests for the environment variable detector."""

from __future__ import annotations

from pathlib import Path

from repodoctor.detectors.envvars import detect, compute_results

FIXTURES = Path(__file__).parent / "fixtures"


def test_env_detect_env_repo():
    result = detect(FIXTURES / "env_repo")
    assert result["documented"] == {"API_KEY", "DB_URL", "OLD_FLAG"}
    assert result["set_keys"] == {"DB_URL"}
    assert "API_KEY" in result["used"]
    assert "SECRET_TOKEN" in result["used"]

    computed = compute_results(result)
    assert computed["missing"] == {"API_KEY", "OLD_FLAG"}
    assert computed["undocumented"] == {"SECRET_TOKEN"}
    assert computed["unused"] == {"OLD_FLAG"}


def test_env_patterns_all(tmp_path):
    """All env var usage patterns should be detected."""
    (tmp_path / "app.py").write_text(
        'import os\n'
        'a = os.environ["API_KEY"]\n'
        'b = os.environ.get("DB_URL")\n'
        'c = os.getenv("REDIS_URL")\n'
    )
    (tmp_path / "app.js").write_text(
        'const d = process.env.NODE_ENV;\n'
        'const e = process.env["PORT"];\n'
        'const f = import.meta.env.VITE_APP_TITLE;\n'
    )
    result = detect(tmp_path)
    used = set(result["used"].keys())
    assert "API_KEY" in used
    assert "DB_URL" in used
    assert "REDIS_URL" in used
    assert "NODE_ENV" in used
    assert "PORT" in used
    assert "VITE_APP_TITLE" in used


def test_env_comments_and_export(tmp_path):
    """Comments and export lines should be handled correctly."""
    (tmp_path / ".env.example").write_text(
        "# This is a comment\n"
        "export FOO=bar\n"
        "BAZ=qux\n"
        "\n"
        "# another comment\n"
        "export QUUX=corge\n"
    )
    result = detect(tmp_path)
    assert result["documented"] == {"FOO", "BAZ", "QUUX"}


def test_env_skips_git_folder(tmp_path):
    """Files in .git should be skipped."""
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "config.py").write_text('os.environ["SECRET_KEY"]')
    (tmp_path / "main.py").write_text('os.environ["PUBLIC_KEY"]')
    result = detect(tmp_path)
    assert "SECRET_KEY" not in result["used"]
    assert "PUBLIC_KEY" in result["used"]


def test_env_skips_node_modules(tmp_path):
    """Files in node_modules should be skipped."""
    nm_dir = tmp_path / "node_modules"
    nm_dir.mkdir()
    (nm_dir / "lib.js").write_text('process.env.NM_VAR')
    (tmp_path / "index.js").write_text('process.env.APP_VAR')
    result = detect(tmp_path)
    assert "NM_VAR" not in result["used"]
    assert "APP_VAR" in result["used"]


def test_env_skips_venv_folders(tmp_path):
    """Files in .venv and venv should be skipped."""
    for venv_name in (".venv", "venv"):
        vdir = tmp_path / venv_name
        vdir.mkdir()
        (vdir / "config.py").write_text('os.environ["VENV_VAR"]')
    (tmp_path / "main.py").write_text('os.environ["REAL_VAR"]')
    result = detect(tmp_path)
    assert "VENV_VAR" not in result["used"]
    assert "REAL_VAR" in result["used"]


def test_env_skips_dist_build_pycache(tmp_path):
    """Files in dist, build, __pycache__ should be skipped."""
    for skip_name in ("dist", "build", "__pycache__"):
        sdir = tmp_path / skip_name
        sdir.mkdir()
        (sdir / "mod.py").write_text('os.environ["SKIP_ME"]')
    (tmp_path / "keep.py").write_text('os.environ["KEEP_ME"]')
    result = detect(tmp_path)
    assert "SKIP_ME" not in result["used"]
    assert "KEEP_ME" in result["used"]


def test_env_skips_large_files(tmp_path):
    """Files larger than 1 MB should be skipped."""
    big_file = tmp_path / "big.py"
    big_file.write_text("x = 1\n" * 200000)  # > 1 MB
    (big_file).write_text(big_file.read_text() + 'os.environ["BIG_VAR"]\n')
    (tmp_path / "small.py").write_text('os.environ["SMALL_VAR"]')
    result = detect(tmp_path)
    assert "BIG_VAR" not in result["used"]
    assert "SMALL_VAR" in result["used"]


def test_env_no_example_no_usage_shows_nothing(tmp_path):
    """If no .env.example and no env usage, result should be empty."""
    (tmp_path / "main.py").write_text("print('hello')")
    result = detect(tmp_path)
    assert result["documented"] == set()
    assert result["set_keys"] == set()
    assert result["used"] == {}
    assert result["has_example"] is False
    computed = compute_results(result)
    assert computed["missing"] == set()
    assert computed["undocumented"] == set()
    assert computed["unused"] == set()


def test_env_no_values_in_output(tmp_path):
    """No .env value should ever appear in detection output."""
    (tmp_path / ".env.example").write_text("SECRET=super-secret-value-12345")
    (tmp_path / ".env").write_text("SECRET=super-secret-value-12345")
    result = detect(tmp_path)
    output_str = str(result)
    assert "super-secret-value-12345" not in output_str
    assert result["documented"] == {"SECRET"}
    assert result["set_keys"] == {"SECRET"}


def test_env_only_sample_file(tmp_path):
    """Should work with only .env.sample (no .env.example)."""
    (tmp_path / ".env.sample").write_text("SAMPLE_VAR=hello")
    (tmp_path / ".env").write_text("SAMPLE_VAR=world")
    result = detect(tmp_path)
    assert result["documented"] == {"SAMPLE_VAR"}
    assert result["set_keys"] == {"SAMPLE_VAR"}
    assert result["has_example"] is False
    computed = compute_results(result)
    assert computed["missing"] == set()  # no .env.example, so no missing


def test_env_case_sensitive(tmp_path):
    """Only UPPER_SNAKE_CASE names should match."""
    (tmp_path / "app.py").write_text(
        'os.environ["API_KEY"]\n'
        'os.environ["api_key"]\n'
        'os.environ["ApiKey"]\n'
        'os.environ["MIXED_CASE"]\n'
    )
    result = detect(tmp_path)
    used = set(result["used"].keys())
    assert "API_KEY" in used
    assert "api_key" not in used
    assert "ApiKey" not in used
    assert "MIXED_CASE" in used  # still UPPER_SNAKE_CASE
