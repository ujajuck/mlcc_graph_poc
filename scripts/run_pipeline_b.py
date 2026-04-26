"""Run pipeline B end-to-end (LightRAG-only on Apache AGE).

Reads the same preprocessed corpus as pipeline A so input parity holds.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console

from pipeline.lightrag_only.runner import ingest


app = typer.Typer(add_completion=False)
console = Console()


@app.command()
def main(
    processed_dir: Path = typer.Option(Path("data/processed"), exists=True, file_okay=False),
    working_dir: Path = typer.Option(Path("output/lightrag_only/rag_state")),
    env_file: Path = typer.Option(Path("config/.env")),
) -> None:
    if env_file.exists():
        load_dotenv(env_file)

    stats = asyncio.run(ingest(processed_dir, working_dir))
    console.print(f"[green]Pipeline B ingest complete:[/green] {stats}")


if __name__ == "__main__":
    app()
