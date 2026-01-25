try:
    import typer
except ImportError as e:
    raise ImportError(
        "CLI requires the 'cli' extra. Install with: pip install sparqlkit[cli]"
    ) from e

import importlib.metadata
from pathlib import Path
from typing import Annotated

from sparqlkit import SparqlSyntaxError, format_string

SPARQL_EXTENSIONS = (".rq", ".sparql")

app = typer.Typer(
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
    help="A CLI tool for formatting and checking SPARQL files.",
)


@app.command()
def version() -> None:
    """Show the sparqlkit version."""
    typer.echo(importlib.metadata.version("sparqlkit"))


def _collect_files(path: Path) -> list[Path]:
    """Collect SPARQL files from a file or directory path."""
    if path.is_file():
        return [path]
    if path.is_dir():
        files: list[Path] = []
        for ext in SPARQL_EXTENSIONS:
            files.extend(path.rglob(f"*{ext}"))
        return sorted(files)
    return []


@app.command()
def format(
    path: Annotated[Path, typer.Argument(help="File or directory to format")],
    check: Annotated[
        bool,
        typer.Option(
            "--check",
            help="Check if files are formatted without making changes. "
            "Exits non-zero if changes would be made.",
        ),
    ] = False,
) -> None:
    """Format SPARQL files in-place."""
    files = _collect_files(path)

    if not files:
        typer.echo(f"No SPARQL files found in {path}", err=True)
        raise typer.Exit(1)

    would_change = 0
    errors = 0
    for file in files:
        try:
            content = file.read_text(encoding="utf-8")
            formatted = format_string(content, parser_type=None)
            if check:
                if content != formatted:
                    typer.echo(f"Would reformat {file}", err=True)
                    would_change += 1
                else:
                    typer.echo(f"OK {file}")
            else:
                file.write_text(formatted, encoding="utf-8")
                typer.echo(f"Formatted {file}")
        except SparqlSyntaxError as e:
            typer.echo(f"Error in {file}: {e}", err=True)
            errors += 1

    if errors or (check and would_change):
        raise typer.Exit(1)

    if check:
        typer.echo(f"\nAll {len(files)} file(s) OK")
