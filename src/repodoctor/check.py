"""Core check logic, separated from output formatting.

Returns structured results that can be rendered as Rich tables or JSON.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import OrderedDict

from repodoctor.checkers.system import (
    get_installed_version,
    docker_status,
    docker_compose_available,
    is_port_in_use,
)
from repodoctor.checkers.versions import satisfies
from repodoctor.detectors.envvars import detect as detect_envvars
from repodoctor.detectors.envvars import compute_results as compute_env_results
from repodoctor.detectors.node import detect as detect_node
from repodoctor.detectors.python import detect as detect_python
from repodoctor.detectors.docker import detect as detect_docker
from repodoctor.detectors.ports import detect as detect_ports
from repodoctor.models import Requirement


@dataclass
class RequirementResult:
    tool: str
    required: str | None
    installed: str | None
    status: str
    found_in: list[str]


@dataclass
class EnvResult:
    variable: str
    status: str
    where: str


@dataclass
class CheckResult:
    path: str
    ok: bool
    requirements: list[RequirementResult] = field(default_factory=list)
    env: list[EnvResult] = field(default_factory=list)


def _simple_version_from_spec(spec: str | None) -> str | None:
    """Extract a simple version number from a spec like '>=18' or '18.17.0'.

    Returns None if the spec isn't a simple single-version string.
    """
    if spec is None:
        return None
    import re

    m = re.fullmatch(r"\s*(>=|>|<|<=|==|!=|~=|\^|~)?\s*(\d+(?:\.\d+)*)", spec)
    if m:
        return m.group(2)
    return None


def run_check(path: Path) -> CheckResult:
    """Run all detectors and checkers against `path`.

    Returns a structured CheckResult. Does not print anything.
    """
    path_str = str(path.resolve())
    detectors = [detect_node, detect_python, detect_docker, detect_ports]
    requirements: list[Requirement] = []
    for detect in detectors:
        requirements.extend(detect(path))

    # Group by (tool, version_spec), collecting all sources.
    groups: "OrderedDict[tuple[str, str | None], list[str]]" = OrderedDict()
    for req in requirements:
        key = (req.tool, req.version_spec)
        if key not in groups:
            groups[key] = []
        groups[key].append(req.source)

    requirement_results: list[RequirementResult] = []
    has_failure = False

    for (tool, version_spec), sources in groups.items():
        found_in = list(sources)

        if tool == "docker":
            status_value = docker_status()
            if status_value == "not_installed":
                installed = None
                status = "MISSING"
                has_failure = True
            elif status_value == "not_running":
                installed = "installed"
                status = "NOT RUNNING"
                has_failure = True
            else:
                installed = "ok"
                status = "OK"
                if not docker_compose_available():
                    installed = "compose n/a"
                    status = "MISSING"
                    has_failure = True
        elif tool == "docker-compose":
            status_value = docker_status()
            if status_value == "not_installed":
                installed = None
                status = "MISSING"
                has_failure = True
            elif status_value == "not_running":
                installed = "installed"
                status = "NOT RUNNING"
                has_failure = True
            else:
                installed = "ok"
                if not docker_compose_available():
                    installed = "compose n/a"
                    status = "MISSING"
                    has_failure = True
                else:
                    status = "OK"
        elif tool == "port":
            port_num = int(version_spec)  # type: ignore[arg-type]
            if is_port_in_use(port_num):
                installed = "in use"
                status = "PORT IN USE"
                has_failure = True
            else:
                installed = "free"
                status = "OK"
        else:
            installed = get_installed_version(tool)
            if installed is None:
                status = "MISSING"
                has_failure = True
            else:
                sat = satisfies(installed, version_spec)
                if sat is None:
                    status = "UNKNOWN"
                elif sat:
                    status = "OK"
                else:
                    status = "VERSION MISMATCH"
                    has_failure = True

        requirement_results.append(
            RequirementResult(
                tool=tool,
                required=version_spec,
                installed=installed,
                status=status,
                found_in=found_in,
            )
        )

    # --- Environment variables ---
    env_detection = detect_envvars(path)
    env_results = compute_env_results(env_detection)

    missing = env_results["missing"]
    undocumented = env_results["undocumented"]
    unused = env_results["unused"]

    has_example = env_detection["has_example"]
    used_files = env_detection["used"]

    show_env_section = has_example or bool(used_files)

    env_results_list: list[EnvResult] = []
    if show_env_section and (missing or undocumented or unused):
        example_file = (
            ".env.example"
            if (path / ".env.example").is_file()
            else ".env.sample"
        )

        # Assign each variable to exactly one category with priority:
        # UNDOCUMENTED > UNUSED > MISSING
        assigned: set[str] = set()

        for var in sorted(undocumented):
            files = used_files.get(var, set())
            where = ", ".join(sorted(files)) if files else "code"
            env_results_list.append(EnvResult(var, "UNDOCUMENTED", where))
            assigned.add(var)

        for var in sorted(unused):
            if var in assigned:
                continue
            env_results_list.append(EnvResult(var, "UNUSED", example_file))
            assigned.add(var)

        for var in sorted(missing):
            if var in assigned:
                continue
            env_results_list.append(EnvResult(var, "MISSING", example_file))
            has_failure = True
            assigned.add(var)

    return CheckResult(
        path=path_str,
        ok=not has_failure,
        requirements=requirement_results,
        env=env_results_list,
    )


def format_result_rich(result: CheckResult) -> None:
    """Print a CheckResult using Rich tables."""
    from rich.console import Console
    from rich.table import Table

    console = Console(width=500)

    table = Table(title="Requirements")
    table.add_column("Tool")
    table.add_column("Required")
    table.add_column("Installed")
    table.add_column("Status")
    table.add_column("Found in")

    for req in result.requirements:
        table.add_row(
            req.tool,
            req.required or "-",
            req.installed or "-",
            req.status,
            ", ".join(req.found_in),
        )

    console.print(table)

    if result.env:
        env_table = Table(title="Environment variables")
        env_table.add_column("Variable")
        env_table.add_column("Status")
        env_table.add_column("Where")

        for env in result.env:
            env_table.add_row(env.variable, env.status, env.where)

        console.print(env_table)


def format_result_json(result: CheckResult) -> str:
    """Render a CheckResult as JSON string."""
    import json

    return json.dumps(
        {
            "path": result.path,
            "ok": result.ok,
            "requirements": [
                {
                    "tool": req.tool,
                    "required": req.required,
                    "installed": req.installed,
                    "status": req.status,
                    "found_in": req.found_in,
                }
                for req in result.requirements
            ],
            "env": [
                {
                    "variable": env.variable,
                    "status": env.status,
                    "where": env.where,
                }
                for env in result.env
            ],
        },
        indent=2,
    )
