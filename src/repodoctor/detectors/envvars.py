"""Environment variable detector.

Reads .env.example/.env.sample for documented vars, .env for set vars,
and scans source files for env var usage patterns.

Never reads or stores .env file VALUES - only variable names.
"""

from __future__ import annotations

import re
from pathlib import Path


SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "dist", "build", "__pycache__"}
MAX_FILE_SIZE = 1_048_576  # 1 MB

ENV_SOURCE_EXTS = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs"}

ENV_PATTERNS = [
    r'os\.environ\["([A-Z_][A-Z0-9_]*)"\]',
    r'os\.environ\.get\("([A-Z_][A-Z0-9_]*)"\)',
    r'os\.getenv\("([A-Z_][A-Z0-9_]*)"\)',
    r'process\.env\.([A-Z_][A-Z0-9_]*)',
    r'process\.env\["([A-Z_][A-Z0-9_]*)"\]',
    r'import\.meta\.env\.([A-Z_][A-Z0-9_]*)',
]


def _read_env_keys(path: Path) -> set[str]:
    """Read variable names from an env file.

    Only returns keys, never values.
    Ignores comments and blank lines. Strips leading "export ".
    """
    keys: set[str] = set()
    if not path.is_file():
        return keys
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return keys
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[len("export "):]
        if "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].strip()
        if key:
            keys.add(key)
    return keys


def _scan_code_for_env_vars(path: Path) -> dict[str, set[str]]:
    """Scan source files for env var usage patterns.

    Returns a dict mapping variable name to set of relative source file paths.
    Only matches UPPER_SNAKE_CASE names.
    Skips .git, node_modules, .venv, venv, dist, build, __pycache__.
    Skips files larger than 1 MB.
    """
    used: dict[str, set[str]] = {}
    if not path.is_dir():
        return used

    for root, dirs, files in path.walk():
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

        for fname in files:
            fpath = root / fname
            if fpath.suffix not in ENV_SOURCE_EXTS:
                continue
            try:
                if fpath.stat().st_size > MAX_FILE_SIZE:
                    continue
                content = fpath.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            rel_path = str(fpath.relative_to(path))
            for pattern in ENV_PATTERNS:
                for match in re.finditer(pattern, content):
                    var_name = match.group(1)
                    used.setdefault(var_name, set()).add(rel_path)

    return used


def detect(path: Path) -> dict:
    """Detect environment variable usage in a project.

    Returns a dict with:
    - documented: set of var names from .env.example/.env.sample
    - set_keys: set of var names from .env (values not kept)
    - used: dict mapping var name to set of source file paths
    - has_example: bool, whether .env.example exists
    """
    env_example = path / ".env.example"
    env_sample = path / ".env.sample"
    env_file = path / ".env"

    documented = _read_env_keys(env_example) | _read_env_keys(env_sample)
    set_keys = _read_env_keys(env_file)
    used = _scan_code_for_env_vars(path)

    return {
        "documented": documented,
        "set_keys": set_keys,
        "used": used,
        "has_example": env_example.is_file(),
    }


def compute_results(detection: dict) -> dict:
    """Compute missing, undocumented, unused sets from detection result.

    - missing: documented but not in .env (only if .env.example exists)
    - undocumented: used in code but not in .env.example
    - unused: documented but never found in code and not set in .env
    """
    documented = detection["documented"]
    set_keys = detection["set_keys"]
    used = detection["used"]
    has_example = detection["has_example"]

    missing = documented - set_keys if has_example else set()
    undocumented = set(used.keys()) - documented
    unused = (documented - set(used.keys())) - set_keys

    return {
        "missing": missing,
        "undocumented": undocumented,
        "unused": unused,
    }
