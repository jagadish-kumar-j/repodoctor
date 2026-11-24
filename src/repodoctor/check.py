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
from packaging.utils import canonicalize_name


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

    # --- Python packages from requirements.txt and a local venv ---
    from repodoctor.packages import find_venv, parse_installed_packages, parse_requirements

    package_problem_count = 0
    package_total = 0
    package_venv = find_venv(path)
    if package_venv is not None:
        installed_packages = parse_installed_packages(package_venv)
        parsed_requirements = parse_requirements(path)
        package_total = len(parsed_requirements)
        ok_packages = 0

        for requirement in parsed_requirements:
            name = canonicalize_name(requirement.name)
            display_name = requirement.name
            installed_version = installed_packages.get(name)

            if installed_version is None:
                status = "MISSING"
                installed = None
                has_failure = True
                package_problem_count += 1
            else:
                installed = installed_version
                specifier = requirement.specifier
                if not str(specifier):
                    status = "OK"
                    ok_packages += 1
                else:
                    try:
                        satisfied = specifier.contains(installed_version, prereleases=True)
                    except Exception:
                        status = "UNKNOWN"
                    else:
                        if satisfied:
                            status = "OK"
                            ok_packages += 1
                        else:
                            status = "VERSION MISMATCH"
                            has_failure = True
                            package_problem_count += 1

            if status != "OK":
                requirement_results.append(
                    RequirementResult(
                        tool=f"pip: {display_name}",
                        required=str(requirement.specifier) or None,
                        installed=installed,
                        status=status,
                        found_in=["requirements.txt"],
                    )
                )

        if package_problem_count == 0:
            requirement_results.append(
                RequirementResult(
                    tool="python packages",
                    required=f"{ok_packages} of {package_total} OK",
                    installed=None,
                    status="OK",
                    found_in=["requirements.txt"],
                )
            )

    # --- Node packages from package.json and node_modules ---
    from repodoctor.node_packages import check_node_packages, get_dependencies, is_safe_node_name, read_installed_version
    from repodoctor.checkers.versions import satisfies as _node_satisfies

    node_dependency_data = check_node_packages(path)
    node_dependencies, has_package_json = node_dependency_data
    node_modules = path / "node_modules"
    if has_package_json and node_dependencies:
        if not node_modules.is_dir():
            print("Node package check skipped: no node_modules folder found in this folder.")
        else:
            node_problem_count = 0
            node_total = 0
            node_evaluable_total = 0
            node_ok = 0
            node_skipped = 0

            for raw_name, spec in node_dependencies.items():
                if not is_safe_node_name(raw_name):
                    continue
                node_total += 1
                installed_version = read_installed_version(path, raw_name)
                if installed_version is None:
                    status = "MISSING"
                    installed = None
                    has_failure = True
                    node_problem_count += 1
                else:
                    installed = installed_version
                    sat = _node_satisfies(installed_version, str(spec))
                    if sat is None:
                        status = "UNKNOWN"
                        node_skipped += 1
                    elif sat:
                        status = "OK"
                        node_ok += 1
                        node_evaluable_total += 1
                    else:
                        status = "VERSION MISMATCH"
                        has_failure = True
                        node_problem_count += 1
                        node_evaluable_total += 1

                if status != "OK":
                    requirement_results.append(
                        RequirementResult(
                            tool=f"npm: {raw_name}",
                            required=str(spec) if spec is not None else None,
                            installed=installed,
                            status=status,
                            found_in=["package.json"],
                        )
                    )

            if node_problem_count == 0:
                required_text = f"{node_ok} of {node_evaluable_total} OK"
                if node_skipped > 0:
                    required_text += f", {node_skipped} skipped"
                requirement_results.append(
                    RequirementResult(
                        tool="node packages",
                        required=required_text,
                        installed=None,
                        status="OK",
                        found_in=["package.json"],
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


def format_result_html(result: CheckResult) -> str:
    """Render a self-contained HTML report, escaping every dynamic value."""
    import html

    def esc(value) -> str:
        return html.escape("" if value is None else str(value), quote=True)

    ok_count = sum(req.status == "OK" for req in result.requirements)
    warning_statuses = {"UNDOCUMENTED", "UNUSED", "UNKNOWN"}
    failure_statuses = {"MISSING", "NOT RUNNING", "VERSION MISMATCH", "PORT IN USE"}
    warning_count = sum(req.status in warning_statuses for req in result.requirements)
    warning_count += sum(env.status in warning_statuses for env in result.env)
    failure_count = sum(req.status in failure_statuses for req in result.requirements)
    failure_count += sum(env.status in failure_statuses for env in result.env)

    def badge(status: str) -> str:
        safe_status = esc(status)
        if status == "OK":
            cls = "ok"
        elif status in failure_statuses or status == "MISSING":
            cls = "failure"
        else:
            cls = "warning"
        return f'<span class="badge {cls}">{safe_status}</span>'

    requirement_rows = "".join(
        "<tr>"
        f"<td>{esc(req.tool)}</td>"
        f"<td>{esc(req.required if req.required is not None else '-')}</td>"
        f"<td>{esc(req.installed if req.installed is not None else '-')}</td>"
        f"<td>{badge(req.status)}</td>"
        f"<td>{esc(', '.join(req.found_in))}</td>"
        "</tr>"
        for req in result.requirements
    )
    env_rows = "".join(
        "<tr>"
        f"<td>{esc(env.variable)}</td>"
        f"<td>{badge(env.status)}</td>"
        f"<td>{esc(env.where)}</td>"
        "</tr>"
        for env in result.env
    )

    requirements_section = ""
    if result.requirements:
        requirements_section = (
            "<h2>Requirements</h2>"
            '<table><thead><tr><th>Tool</th><th>Required</th><th>Installed</th><th>Status</th><th>Found in</th></tr></thead>'
            f"<tbody>{requirement_rows}</tbody></table>"
        )

    env_section = ""
    if result.env:
        env_section = (
            "<h2>Environment variables</h2>"
            "<table><thead><tr><th>Variable</th><th>Status</th><th>Where</th></tr></thead>"
            f"<tbody>{env_rows}</tbody></table>"
        )

    if not result.requirements and not result.env:
        content = '<p class="clean">Nothing to check in this folder.</p>'
    else:
        content = requirements_section + env_section

    folder_name = esc(Path(result.path).name or ".")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>repodoctor report - {folder_name}</title>
<style>
:root {{ --bg:#ffffff; --text:#172033; --panel:#f6f8fa; --border:#d0d7de; --ok:#16794f; --ok-bg:#daf5e7; --failure:#b42318; --failure-bg:#fee4e2; --warning:#9a6700; --warning-bg:#fff1b8; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#0d1117; --text:#e6edf3; --panel:#161b22; --border:#30363d; --ok:#3fb950; --ok-bg:#193c2b; --failure:#ff7b72; --failure-bg:#4a1f1f; --warning:#e3b341; --warning-bg:#4a3a18; }} }}
body {{ margin:0; padding:24px; background:var(--bg); color:var(--text); font-family:system-ui,-apple-system,"Segoe UI",sans-serif; }}
main {{ max-width:1100px; margin:auto; }}
h1 {{ font-size:1.6rem; }}
.summary {{ background:var(--panel); border:1px solid var(--border); padding:12px; border-radius:8px; }}
table {{ width:100%; border-collapse:collapse; margin:16px 0 24px; }}
th, td {{ border:1px solid var(--border); padding:8px; text-align:left; }}
th {{ background:var(--panel); }}
.badge {{ display:inline-block; padding:2px 8px; border-radius:999px; font-weight:700; }}
.badge.ok {{ color:var(--ok); background:var(--ok-bg); }}
.badge.failure {{ color:var(--failure); background:var(--failure-bg); }}
.badge.warning {{ color:var(--warning); background:var(--warning-bg); }}
</style>
</head>
<body><main>
<h1>repodoctor report: {folder_name}</h1>
<p class="summary">Summary: {ok_count} OK, {warning_count} warnings, {failure_count} failures</p>
{content}
</main></body>
</html>
"""


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

    if result.requirements:
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
