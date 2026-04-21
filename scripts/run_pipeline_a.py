"""Run pipeline A end-to-end (Graphify -> LightRAG on Apache AGE).

Assumes:
    - Apache AGE is up:           make age-up
    - .env is configured:         cp config/.env.example config/.env
    - Preprocess has been run:    make preprocess
    - Graphify CLI is installed:  uv tool install graphifyy && graphify install
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console

from pipeline.graphify_to_lightrag.runner import ingest


app = typer.Typer(add_completion=False)
console = Console()


@app.command()
def main(
    processed_dir: Path = typer.Option(Path("data/processed"), exists=True, file_okay=False),
    working_dir: Path = typer.Option(Path("output/graphify_to_lightrag/rag_state")),
    out_dir: Path = typer.Option(Path("output/graphify_to_lightrag")),
    env_file: Path = typer.Option(Path("config/.env")),
) -> None:
    if env_file.exists():
        load_dotenv(env_file)

    stats = asyncio.run(ingest(processed_dir, working_dir, out_dir))
    console.print(f"[green]Pipeline A ingest complete:[/green] {stats}")


if __name__ == "__main__":
    app()
