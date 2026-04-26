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
from pipeline.structured_first.runner import query as query_c


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
    fn = {"A": query_a, "B": query_b, "C": query_c}[pipeline]
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
    answers_c: list[Answer],
    stats_a: dict[str, int],
    stats_b: dict[str, int],
    out_path: Path,
) -> None:
    lines = [
        "# Pipeline comparison report (A: Graphify->LightRAG, B: LightRAG-only, C: structured-first)",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Dataset",
        "",
        "See `data/raw/` and `data/processed/`. All pipelines consume the same preprocessed corpus.",
        "Pipeline C additionally reads the canonical fact store at `output/fact_store.sqlite`.",
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
    by_id_c = {(a.query_id, a.mode): a for a in answers_c}

    for q in queries:
        lines.append(f"### {q['id']} - {q['question']}")
        lines.append("")
        lines.append(f"_Expected:_ {q.get('expects', '')}")
        lines.append("")
        for mode in q.get("modes", ["hybrid"]):
            lines.append(f"#### mode=`{mode}`")
            lines.append("")
            for label, by_id, title in (
                ("A", by_id_a, "Pipeline A (Graphify->LightRAG)"),
                ("B", by_id_b, "Pipeline B (LightRAG-only)"),
                ("C", by_id_c, "Pipeline C (structured-first + LightRAG explanation)"),
            ):
                ans = by_id.get((q["id"], mode))
                lines.append(f"**{title}:**")
                lines.append("")
                lines.append("```")
                lines.append(ans.answer if ans else "(missing)")
                lines.append("```")
                lines.append("")
            lines.append("| criterion | A | B | C | notes |")
            lines.append("| --- | --- | --- | --- | --- |")
            for c in [
                "entity coverage",
                "relation correctness",
                "answer correctness",
                "citation quality",
                "table-data robustness",
            ]:
                lines.append(f"| {c} |  |  |  |  |")
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


async def _main_async(queries_path: Path, out_dir: Path, pipelines: tuple[str, ...]) -> None:
    queries = yaml.safe_load(queries_path.read_text(encoding="utf-8"))["queries"]

    work_a = Path("output/graphify_to_lightrag/rag_state")
    work_b = Path("output/lightrag_only/rag_state")
    work_c = Path("output/lightrag_only/rag_state")  # C reuses B's KG

    answers_a: list[Answer] = []
    answers_b: list[Answer] = []
    answers_c: list[Answer] = []

    for q in queries:
        for mode in q.get("modes", ["hybrid"]):
            console.print(f"[cyan]Q {q['id']} / mode={mode}[/cyan]")
            if "A" in pipelines:
                a = await _run_one("A", q["question"], mode, work_a)
                answers_a.append(Answer(q["id"], q["question"], mode, "A", a))
            if "B" in pipelines:
                b = await _run_one("B", q["question"], mode, work_b)
                answers_b.append(Answer(q["id"], q["question"], mode, "B", b))
            if "C" in pipelines:
                c = await _run_one("C", q["question"], mode, work_c)
                answers_c.append(Answer(q["id"], q["question"], mode, "C", c))

    (out_dir / "graphify_to_lightrag").mkdir(parents=True, exist_ok=True)
    (out_dir / "lightrag_only").mkdir(parents=True, exist_ok=True)
    (out_dir / "structured_first").mkdir(parents=True, exist_ok=True)
    (out_dir / "graphify_to_lightrag" / "answers.json").write_text(
        json.dumps([asdict(a) for a in answers_a], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "lightrag_only" / "answers.json").write_text(
        json.dumps([asdict(a) for a in answers_b], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "structured_first" / "answers.json").write_text(
        json.dumps([asdict(a) for a in answers_c], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    stats_a = await _graph_stats(WS_A) if "A" in pipelines else {"skipped": True}
    stats_b = await _graph_stats(WS_B) if "B" in pipelines else {"skipped": True}

    _write_report(
        queries,
        answers_a,
        answers_b,
        answers_c,
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
    pipelines: str = typer.Option("A,B,C", help="comma-separated subset of A,B,C"),
) -> None:
    if env_file.exists():
        load_dotenv(env_file)
    selected = tuple(p.strip().upper() for p in pipelines.split(",") if p.strip())
    asyncio.run(_main_async(queries, out_dir, selected))


if __name__ == "__main__":
    app()
