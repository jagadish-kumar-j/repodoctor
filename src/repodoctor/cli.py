"""CLI entry point for repodoctor."""

from __future__ import annotations

import json
import os
import typer
from pathlib import Path
from typing import Annotated

from repodoctor.check import run_check, format_result_rich, format_result_json
from repodoctor.script import generate_script, write_script

app = typer.Typer()


@app.callback()
def root():
    pass


@app.command()
def check(
    path: str = typer.Argument(".", help="Path to check"),
    json: Annotated[bool, typer.Option("--json", help="Output JSON only")] = False,
):
    path_obj = Path(path)
    if not path_obj.exists():
        if json:
            print(
                json.dumps(
                    {
                        "path": str(path_obj.resolve()),
                        "ok": False,
                        "requirements": [],
                        "env": [],
                        "error": f"Path does not exist: {path}",
                    }
                )
            )
        else:
            from rich.console import Console

            Console().print(f"[red]Error: Path does not exist: {path}[/red]")
        raise typer.Exit(code=1)

    result = run_check(path_obj)

    if json:
        print(format_result_json(result))
    else:
        format_result_rich(result)

    raise typer.Exit(code=0 if result.ok else 1)


@app.command()
def script(
    path: str = typer.Argument(".", help="Path to check"),
    shell: str = typer.Option(
        "powershell" if os.name == "nt" else "bash",
        "--shell",
        help='Shell type: "powershell" or "bash"',
    ),
    output: Path = typer.Option(None, "--output", "-o", help="Output file path"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing file"),
):
    path_obj = Path(path)
    if not path_obj.exists():
        from rich.console import Console

        Console().print(f"[red]Error: Path does not exist: {path}[/red]")
        raise typer.Exit(code=1)

    if shell not in ("powershell", "bash"):
        from rich.console import Console

        Console().print('[red]Error: --shell must be "powershell" or "bash"[/red]')
        raise typer.Exit(code=1)

    result = run_check(path_obj)
    content = generate_script(result, shell, output)

    if output is None:
        output = Path("setup.ps1") if shell == "powershell" else Path("setup.sh")

    try:
        write_script(content, output, force)
    except FileExistsError as e:
        from rich.console import Console

        Console().print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)

    from rich.console import Console

    Console().print(f"Wrote setup script to {output}")
