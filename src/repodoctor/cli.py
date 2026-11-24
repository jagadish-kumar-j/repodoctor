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
    html: Path = typer.Option(None, "--html", help="Write a self-contained HTML report"),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing HTML report"),
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

    if html is not None:
        if html.exists() and not force:
            from rich.console import Console
            Console().print(f"[red]Error: Output file '{html}' already exists. Use --force to overwrite.[/red]")
            raise typer.Exit(code=1)
        try:
            from repodoctor.check import format_result_html
            html.write_text(format_result_html(result), encoding="utf-8")
        except OSError as exc:
            from rich.console import Console
            Console().print(f"[red]Error: Could not write HTML report: {exc}[/red]")
            raise typer.Exit(code=1)

    if json:
        print(format_result_json(result))
    elif not result.requirements and not result.env:
        print("Nothing to check in this folder.")
        if not (path_obj / ".venv").is_dir() and not (path_obj / "venv").is_dir():
            print("Package check skipped: no .venv or venv folder found in this folder.")
        if (path_obj / "package.json").is_file() and not (path_obj / "node_modules").is_dir():
            print("Node package check skipped: no node_modules folder found in this folder.")
        raise typer.Exit(code=0)
    else:
        format_result_rich(result)
        if not (path_obj / ".venv").is_dir() and not (path_obj / "venv").is_dir():
            print("Package check skipped: no .venv or venv folder found in this folder.")
        if (path_obj / "package.json").is_file() and not (path_obj / "node_modules").is_dir():
            print("Node package check skipped: no node_modules folder found in this folder.")

    raise typer.Exit(code=0 if result.ok else 1)


@app.command()
def explain(
    path: str = typer.Argument(".", help="Path to check"),
    provider: str = typer.Option(
        "ollama",
        "--provider",
        help='AI provider: "ollama" or "openai-compat"',
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print the sanitized payload without sending it"),
):
    path_obj = Path(path)
    if not path_obj.exists():
        from rich.console import Console
        Console().print(f"[red]Error: Path does not exist: {path}[/red]")
        raise typer.Exit(code=1)

    if provider not in ("ollama", "openai-compat"):
        from rich.console import Console
        Console().print('[red]Error: --provider must be "ollama" or "openai-compat"[/red]')
        raise typer.Exit(code=1)

    result = run_check(path_obj)
    if result.ok:
        print("Nothing to explain: no problems found.")
        raise typer.Exit(code=0)

    from repodoctor.ai.sanitize import build_payload
    payload = build_payload(result)

    if dry_run:
        print(f"Provider: {provider}")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        raise typer.Exit(code=0)

    from repodoctor.ai.provider import OllamaProvider, OpenAICompatProvider, ProviderError
    answer = None
    try:
        ai_provider = OllamaProvider() if provider == "ollama" else OpenAICompatProvider()
        answer = ai_provider.explain(payload)
    except ProviderError:
        pass
    except Exception:
        pass

    print("Summary")
    if answer:
        from repodoctor.ai.safety import answer_contains_destructive_command, DESTRUCTIVE_WARNING
        if answer_contains_destructive_command(answer):
            print(DESTRUCTIVE_WARNING)
        print(answer)
    else:
        print("Summary unavailable: the AI provider could not be reached.")

    from repodoctor.ai.fixes import fixed_fix

    for req in result.requirements:
        if req.status == "OK" or req.status == "UNKNOWN":
            continue
        name = req.required if req.tool == "port" else req.tool
        template = fixed_fix("port" if req.tool == "port" else "tool", name, req.status)
        print()
        print(f"Problem: {req.tool} {req.status}")
        print(f"What it means: {template['what']}")
        if "powershell" in template:
            print(f"Fix (PowerShell): {template['powershell']}")
            print(f"Fix (bash): {template['bash']}")
            if "note" in template:
                print(template["note"])

    for env in result.env:
        template = fixed_fix("env", env.variable, env.status)
        print()
        print(f"Problem: {env.variable} {env.status}")
        print(f"What it means: {template['what']}")
        if "powershell" in template:
            print(f"Fix (PowerShell): {template['powershell']}")
            print(f"Fix (bash): {template['bash']}")
            if "note" in template:
                print(template["note"])

    if answer:
        print("AI-generated summary. Commands are fixed templates, but verify before running.")
    else:
        print("Commands are fixed templates. Verify before running.")
    raise typer.Exit(code=0)


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
