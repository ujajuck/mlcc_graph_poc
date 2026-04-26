"""Pipeline C: structured-first answering.

Flow:
    1. Route the question with `pipeline.common.query_router`.
    2. If it has conditions, run them through `SqlRetriever` against the
       fact store (and optionally `CypherRetriever` for graph context).
    3. If the question also wants explanation (intent='mixed' or
       'explanation'), build a *grounded* prompt — structured rows up top,
       explanation request below — and hand it to LightRAG.

This pipeline does NOT write to AGE. It reuses Pipeline B's workspace for
the explanation step so we don't duplicate ingest. The new contract is:

    structured retrieval gives the answer
    LightRAG only writes the prose around it
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from pipeline.common.fact_store import FactStore, FactStoreConfig
from pipeline.common.query_router import RoutedQuery, route
from pipeline.common.sql_cypher_retriever import SqlRetriever, StructuredHit
from pipeline.lightrag_only.runner import query as lightrag_query


WORKSPACE = "mlcc_lightrag_only"  # we read from B's KG for prose context


@dataclass
class StructuredAnswer:
    routed: dict[str, Any]
    structured_hits: list[dict[str, Any]]
    explanation: str
    prompt_to_lightrag: str | None


def _format_hits(hits: list[StructuredHit]) -> str:
    if not hits:
        return "(no structured rows matched)"
    lines = []
    for h in hits[:50]:
        kv = ", ".join(f"{k}={v}" for k, v in h.payload.items() if v is not None and v != "")
        lines.append(f"- [{h.kind}] {kv}")
    return "\n".join(lines)


async def answer(
    question: str,
    *,
    mode: str = "hybrid",
    working_dir: Path = Path("output/lightrag_only/rag_state"),
    store_path: Path | None = None,
) -> StructuredAnswer:
    routed: RoutedQuery = route(question)

    cfg = FactStoreConfig(db_path=store_path or FactStoreConfig.default().db_path)
    structured: list[StructuredHit] = []
    if routed.intent != "explanation":
        with FactStore(cfg) as store:
            sql = SqlRetriever(store)
            structured.extend(sql.find_products(routed.conditions))
            structured.extend(sql.find_test_conditions(routed.conditions))
            scope_ids = [
                h.payload.get("product_id") or h.payload.get("scope_id")
                for h in structured
                if h.payload.get("product_id") or h.payload.get("scope_id")
            ]
            structured.extend(sql.find_exceptions([s for s in scope_ids if s]))

    explanation = ""
    prompt = None
    if routed.intent in {"explanation", "mixed"} or not structured:
        prompt = (
            "다음 구조화 결과를 근거로만 사용해서 한국어로 설명해줘.\n"
            "결과에 없는 제품/수치는 새로 만들지 말 것.\n\n"
            f"[질문]\n{question}\n\n"
            "[구조화 결과]\n"
            f"{_format_hits(structured)}\n"
        )
        try:
            explanation = await lightrag_query(prompt, mode=mode, working_dir=working_dir)
        except Exception as exc:  # noqa: BLE001
            explanation = f"[lightrag-error] {type(exc).__name__}: {exc}"

    return StructuredAnswer(
        routed={
            "intent": routed.intent,
            "conditions": [asdict(c) for c in routed.conditions],
            "needs_explanation": routed.needs_explanation,
        },
        structured_hits=[
            {"kind": h.kind, "payload": h.payload} for h in structured
        ],
        explanation=explanation,
        prompt_to_lightrag=prompt,
    )


async def query(question: str, mode: str, working_dir: Path) -> str:
    """Compatibility wrapper so run_compare can call this like A/B."""
    sa = await answer(question, mode=mode, working_dir=working_dir)
    parts = [
        f"[intent={sa.routed['intent']} conditions={len(sa.routed['conditions'])}]",
        "Structured hits:",
        _format_hits([StructuredHit(h["kind"], h["payload"]) for h in sa.structured_hits]),
    ]
    if sa.explanation:
        parts.append("\nExplanation:\n" + sa.explanation)
    return "\n".join(parts)
