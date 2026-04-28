"""Run pipeline C end-to-end (structured-first + LightRAG explanation).

Two phases:
    1. load:  data/processed → output/fact_store.sqlite
    2. (no separate ingest into AGE — pipeline C reuses pipeline B's workspace
        for explanation context)

Usage:
    python -m scripts.run_pipeline_c load
"""
from __future__ import annotations

from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console

from pipeline.structured_first.loader import load_processed_dir


app = typer.Typer(add_completion=False)
console = Console()


@app.command()
def load(
    processed_dir: Path = typer.Option(Path("data/processed"), exists=True, file_okay=False),
    store_path: Path = typer.Option(Path("output/fact_store.sqlite")),
    env_file: Path = typer.Option(Path("config/.env")),
) -> None:
    if env_file.exists():
        load_dotenv(env_file)
    counts = load_processed_dir(processed_dir, store_path=store_path)
    console.print(f"[green]Pipeline C load complete:[/green] {counts}")
    console.print(f"  store: {store_path}")


if __name__ == "__main__":
    app()
