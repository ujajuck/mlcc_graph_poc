"""Run the shared query set against both pipelines and emit a comparison report.

Writes:
    output/graphify_to_lightrag/answers.json
    output/lightrag_only/answers.json
    output/comparison/comparison_report.md

The report template intentionally leaves qualitative judgment columns blank -
claude.md requires a human reviewer to fill them in using the criteria in
"비교 기준" section.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import typer
import yaml
from dotenv import load_dotenv
from rich.console import Console

from pipeline.common.age_client import AgeClient, AgeConnectionConfig
from pipeline.graphify_to_lightrag.runner import query as query_a, WORKSPACE as WS_A
from pipeline.lightrag_only.runner import query as query_b, WORKSPACE as WS_B


app = typer.Typer(add_completion=False)
console = Console()


@dataclass
class Answer:
    query_id: str
    question: str
    mode: str
    pipeline: str
    answer: str


async def _run_one(pipeline: str, question: str, mode: str, working_dir: Path) -> str:
    fn = query_a if pipeline == "A" else query_b
    try:
        return await fn(question, mode, working_dir)
    except Exception as exc:  # noqa: BLE001
        return f"[error] {type(exc).__name__}: {exc}"


async def _graph_stats(workspace: str) -> dict[str, int]:
    cfg = AgeConnectionConfig.from_env(graph_name=workspace)
    client = AgeClient(cfg)
    try:
        return {
            "nodes": await client.node_count(),
            "edges": await client.edge_count(),
        }
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def _write_report(
    queries: list[dict[str, Any]],
    answers_a: list[Answer],
    answers_b: list[Answer],
    stats_a: dict[str, int],
    stats_b: dict[str, int],
    out_path: Path,
) -> None:
    lines = [
        "# Graphify->LightRAG vs LightRAG-only - Comparison Report",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Dataset",
        "",
        "See `data/raw/` and `data/processed/`. Both pipelines consume the same preprocessed corpus.",
        "",
        "## Graph size (Apache AGE)",
        "",
        f"- Pipeline A workspace `{WS_A}`: {stats_a}",
        f"- Pipeline B workspace `{WS_B}`: {stats_b}",
        "",
        "## Per-query answers",
        "",
    ]

    by_id_a = {(a.query_id, a.mode): a for a in answers_a}
    by_id_b = {(a.query_id, a.mode): a for a in answers_b}

    for q in queries:
        lines.append(f"### {q['id']} - {q['question']}")
        lines.append("")
        lines.append(f"_Expected:_ {q.get('expects', '')}")
        lines.append("")
        for mode in q.get("modes", ["hybrid"]):
            lines.append(f"#### mode=`{mode}`")
            lines.append("")
            a = by_id_a.get((q["id"], mode))
            b = by_id_b.get((q["id"], mode))
            lines.append("**Pipeline A (Graphify->LightRAG):**")
            lines.append("")
            lines.append("```")
            lines.append(a.answer if a else "(missing)")
            lines.append("```")
            lines.append("")
            lines.append("**Pipeline B (LightRAG-only):**")
            lines.append("")
            lines.append("```")
            lines.append(b.answer if b else "(missing)")
            lines.append("```")
            lines.append("")
            lines.append("| criterion | A | B | notes |")
            lines.append("| --- | --- | --- | --- |")
            for c in [
                "entity coverage",
                "relation correctness",
                "answer correctness",
                "citation quality",
                "table-data robustness",
            ]:
                lines.append(f"| {c} |  |  |  |")
            lines.append("")

    lines.extend(
        [
            "## Summary (fill in)",
            "",
            "- Strengths of A:",
            "- Strengths of B:",
            "- Next steps:",
            "",
        ]
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")


async def _main_async(queries_path: Path, out_dir: Path) -> None:
    queries = yaml.safe_load(queries_path.read_text(encoding="utf-8"))["queries"]

    work_a = Path("output/graphify_to_lightrag/rag_state")
    work_b = Path("output/lightrag_only/rag_state")

    answers_a: list[Answer] = []
    answers_b: list[Answer] = []

    for q in queries:
        for mode in q.get("modes", ["hybrid"]):
            console.print(f"[cyan]Q {q['id']} / mode={mode}[/cyan]")
            a = await _run_one("A", q["question"], mode, work_a)
            b = await _run_one("B", q["question"], mode, work_b)
            answers_a.append(Answer(q["id"], q["question"], mode, "A", a))
            answers_b.append(Answer(q["id"], q["question"], mode, "B", b))

    (out_dir / "graphify_to_lightrag").mkdir(parents=True, exist_ok=True)
    (out_dir / "lightrag_only").mkdir(parents=True, exist_ok=True)
    (out_dir / "graphify_to_lightrag" / "answers.json").write_text(
        json.dumps([asdict(a) for a in answers_a], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "lightrag_only" / "answers.json").write_text(
        json.dumps([asdict(a) for a in answers_b], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    stats_a = await _graph_stats(WS_A)
    stats_b = await _graph_stats(WS_B)

    _write_report(
        queries,
        answers_a,
        answers_b,
        stats_a,
        stats_b,
        out_dir / "comparison" / "comparison_report.md",
    )
    console.print(f"[green]Wrote {out_dir / 'comparison' / 'comparison_report.md'}[/green]")


@app.command()
def main(
    queries: Path = typer.Option(Path("config/queries.yaml"), exists=True),
    out_dir: Path = typer.Option(Path("output")),
    env_file: Path = typer.Option(Path("config/.env")),
) -> None:
    if env_file.exists():
        load_dotenv(env_file)
    asyncio.run(_main_async(queries, out_dir))


if __name__ == "__main__":
    app()
