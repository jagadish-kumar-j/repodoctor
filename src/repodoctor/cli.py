import typer
from pathlib import Path
from rich.console import Console

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
    console.print(f"Checking {path_obj.resolve()}")
