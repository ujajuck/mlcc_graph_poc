"""Run the shared markdown preprocessor over data/raw/*.md.

Outputs land in data/processed/. Both pipelines read from there, which is how
claude.md's "두 파이프라인은 동일한 전처리 규칙" is enforced.
"""
from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from pipeline.common.preprocess import preprocess_markdown, write_result


app = typer.Typer(add_completion=False)
console = Console()


@app.command()
def main(
    raw_dir: Path = typer.Option(Path("data/raw"), exists=True, file_okay=False),
    out_dir: Path = typer.Option(Path("data/processed"), file_okay=False),
) -> None:
    files = sorted(raw_dir.glob("*.md"))
    if not files:
        console.print(f"[yellow]No .md files in {raw_dir}[/yellow]")
        raise typer.Exit(code=1)

    for f in files:
        result = preprocess_markdown(f)
        paths = write_result(result, out_dir)
        console.print(
            f"[green]{f.name}[/green] -> "
            f"{len(result.tables)} tables, {len(result.facts)} facts "
            f"-> {paths['markdown'].name}"
        )


if __name__ == "__main__":
    app()
