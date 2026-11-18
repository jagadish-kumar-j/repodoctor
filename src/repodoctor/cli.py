import typer
from pathlib import Path
from rich.console import Console
from rich.table import Table

from repodoctor.checkers.system import get_installed_version
from repodoctor.checkers.versions import satisfies
from repodoctor.detectors.node import detect as detect_node
from repodoctor.detectors.python import detect as detect_python
from repodoctor.models import Requirement

console = Console(width=500)
app = typer.Typer()


@app.callback()
def root():
    pass


@app.command()
def check(path: str = typer.Argument(".", help="Path to check")):
    path_obj = Path(path)
    if not path_obj.exists():
        console.print(f"[red]Error: Path does not exist: {path}[/red]")
        raise typer.Exit(code=1)

    detectors = [detect_node, detect_python]
    requirements: list[Requirement] = []
    for detect in detectors:
        requirements.extend(detect(path_obj))

    table = Table(title="Requirements")
    table.add_column("Tool")
    table.add_column("Required")
    table.add_column("Installed")
    table.add_column("Status")
    table.add_column("Found in")

    has_failure = False
    for req in requirements:
        installed = get_installed_version(req.tool)
        if installed is None:
            status = "MISSING"
            has_failure = True
        else:
            sat = satisfies(installed, req.version_spec)
            if sat is None:
                status = "UNKNOWN"
            elif sat:
                status = "OK"
            else:
                status = "VERSION MISMATCH"
                has_failure = True

        table.add_row(
            req.tool,
            req.version_spec or "-",
            installed or "-",
            status,
            req.source,
        )

    console.print(table)
    raise typer.Exit(code=1 if has_failure else 0)
