"""Automated scoring against config/golden_queries.yaml.

Reads the answers JSON files emitted by run_compare.py, joins each row
against the matching golden entry, and writes a markdown scoreboard plus a
machine-readable JSON.

The scoring is intentionally simple — no LLM-as-judge, no semantic
similarity. Every check is a substring or numeric comparison so the result
is reproducible.

Score columns:
    must_include_hit      = matched / required
    must_not_include_leak = leaked / forbidden
    num_violations        = answer text contradicts a numeric_condition
    overall_pass          = must_include_hit == 1.0 AND leak == 0 AND violations == 0

Usage:
    python -m scripts.compare.score_answers \
        --answers output/lightrag_only/answers.json \
        --label B \
        --gold config/golden_queries.yaml
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.table import Table


app = typer.Typer(add_completion=False)
console = Console()


_NUM_RE = re.compile(r"(\d+(?:\.\d+)?)")


@dataclass
class QueryScore:
    query_id: str
    mode: str
    pipeline: str
    must_include_hit: float
    must_not_include_leak: int
    num_violations: int
    matched_terms: list[str] = field(default_factory=list)
    leaked_terms: list[str] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)

    @property
    def overall_pass(self) -> bool:
        return (
            self.must_include_hit >= 1.0
            and self.must_not_include_leak == 0
            and self.num_violations == 0
        )


def _score_one(answer: str, gold: dict, *, query_id: str, mode: str, pipeline: str) -> QueryScore:
    text = answer.lower()
    must_inc = [s.lower() for s in gold.get("must_include") or []]
    must_not = [s.lower() for s in gold.get("must_not_include") or []]
    num_conds = gold.get("numeric_conditions") or []

    matched = [s for s in must_inc if s in text]
    leaked = [s for s in must_not if s in text]

    violations: list[str] = []
    for nc in num_conds:
        if _violates(text, nc):
            violations.append(f"{nc['field']} {nc['op']} {nc['value']}")

    hit = (len(matched) / len(must_inc)) if must_inc else 1.0

    return QueryScore(
        query_id=query_id,
        mode=mode,
        pipeline=pipeline,
        must_include_hit=hit,
        must_not_include_leak=len(leaked),
        num_violations=len(violations),
        matched_terms=matched,
        leaked_terms=leaked,
        violations=violations,
    )


def _violates(answer: str, nc: dict) -> bool:
    """Heuristic: detect when an answer text contradicts a numeric condition.

    For op '>=' with value v on field rated_voltage_v: any '<v' voltage
    mention in the answer is a violation. We detect numbers immediately
    preceding 'v' / 'vdc'.
    """
    field_name = nc["field"]
    op = nc["op"]
    target = float(nc["value"])

    if field_name == "rated_voltage_v":
        for m in re.finditer(r"(\d+(?:\.\d+)?)\s*v", answer):
            v = float(m.group(1))
            if not _passes(v, op, target):
                return True
        return False

    if field_name in {"temperature_c", "humidity_pct_rh"}:
        # Looser check: only flag if the explicit number+unit appears with a
        # contradictory neighbor. Easy false positives, so we only flag when
        # the answer explicitly contradicts (e.g. '40C, 95%RH' for HL2).
        if op == "=":
            return f"{int(target)}" not in answer
        return False

    if field_name == "duration_h":
        if op == "=":
            return f"{int(target)}h" not in answer and f"{int(target)} h" not in answer
        return False

    if field_name == "cycles":
        if op == "=":
            return f"{int(target)} cycle" not in answer
        return False

    if field_name == "dielectric_eia" and op == "=":
        return str(nc["value"]).lower() not in answer

    return False


def _passes(v: float, op: str, target: float) -> bool:
    if op == ">=":
        return v >= target
    if op == "<=":
        return v <= target
    if op == ">":
        return v > target
    if op == "<":
        return v < target
    if op == "=":
        return v == target
    return True


@app.command()
def main(
    answers: Path = typer.Option(..., exists=True, help="answers.json from run_compare"),
    gold: Path = typer.Option(Path("config/golden_queries.yaml"), exists=True),
    label: str = typer.Option("?", help="pipeline label, e.g. A / B / C"),
    out_dir: Path = typer.Option(Path("output/comparison")),
) -> None:
    answers_data = json.loads(answers.read_text(encoding="utf-8"))
    gold_data = yaml.safe_load(gold.read_text(encoding="utf-8"))
    by_id = {q["id"]: q for q in gold_data["queries"]}

    scores: list[QueryScore] = []
    for a in answers_data:
        g = by_id.get(a["query_id"])
        if g is None:
            continue
        scores.append(
            _score_one(
                a.get("answer", ""),
                g,
                query_id=a["query_id"],
                mode=a.get("mode", ""),
                pipeline=label,
            )
        )

    table = Table(title=f"Score - pipeline {label}")
    table.add_column("query_id")
    table.add_column("mode")
    table.add_column("inc_hit")
    table.add_column("leak")
    table.add_column("violations")
    table.add_column("pass")
    for s in scores:
        table.add_row(
            s.query_id,
            s.mode,
            f"{s.must_include_hit:.2f}",
            str(s.must_not_include_leak),
            str(s.num_violations),
            "Y" if s.overall_pass else "N",
        )
    console.print(table)

    out_dir.mkdir(parents=True, exist_ok=True)
    out_json = out_dir / f"score_{label}.json"
    out_json.write_text(
        json.dumps(
            [
                {
                    "query_id": s.query_id,
                    "mode": s.mode,
                    "pipeline": s.pipeline,
                    "must_include_hit": s.must_include_hit,
                    "must_not_include_leak": s.must_not_include_leak,
                    "num_violations": s.num_violations,
                    "matched_terms": s.matched_terms,
                    "leaked_terms": s.leaked_terms,
                    "violations": s.violations,
                    "overall_pass": s.overall_pass,
                }
                for s in scores
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    console.print(f"[green]Wrote {out_json}[/green]")


if __name__ == "__main__":
    app()
