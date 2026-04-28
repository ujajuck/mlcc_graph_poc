"""LLM-based KG extractor (LiteLLM → local Ollama/vLLM).

Replaces the host-agent-driven Graphify CLI dispatch. The output JSON is
shape-compatible with what `bridge.py` already expects (`nodes` + `edges`
with provenance metadata), so the rest of pipeline A is unchanged.

Why this exists:
    - Graphify the package does not call any LLM itself; it expects a host
      coding agent (OpenCode / Aider / Codex) to do that. The
      OpenCode/Aider/Codex stack does not fit our setup, so we run our own
      extractor against the local LLM via LiteLLM.

How it works:
    1. Read .facts.jsonl from the preprocessed dir (one row per source row,
       each carrying section_path/table_id/row_id).
    2. Batch facts in groups of N rows and ask the LLM to emit nodes/edges.
    3. Merge batch outputs into a single graph.json under
       `<out_dir>/graphify-out/graph.json` (path matches the legacy layout
       so bridge.py + runner.py keep working).
    4. Carry the source row provenance into every node and edge as `meta`.

Determinism:
    Temperature 0, fixed prompt template, fixed batch size. Two runs over
    the same input on the same model should produce nearly identical
    graphs (small variance from sampling jitter on most local models).
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from pipeline.common.llm_client import LLMConfig, chat_json


_SYSTEM_PROMPT = """You are an information extraction system for MLCC (multilayer ceramic capacitor) catalogs.
You receive a small batch of structured fact sentences and must return a JSON object describing entities and relationships.

Output schema (STRICT - return exactly this shape, no prose):
{
  "nodes": [
    {"id": "<canonical id>", "name": "<display name>", "type": "<one of: dielectric|size|voltage|family|product|spec|test|exception|concept>",
     "description": "<short fact-grounded summary>"}
  ],
  "edges": [
    {"source": "<node id>", "target": "<node id>",
     "type": "<one of: BELONGS_TO|HAS_SPEC|HAS_TEST_CONDITION|HAS_EXCEPTION|EQUIVALENT_TO|ALIAS_OF|PART_OF|APPLIES_TO|RECOMMENDED_FOR|INCOMPATIBLE_WITH|RELATED_TO>",
     "description": "<short sentence describing the relationship>",
     "confidence": <float 0..1>}
  ]
}

Rules:
- Only use entities and relationships that are directly supported by the input facts. Do not hallucinate part numbers, voltages, sizes, or test conditions.
- Prefer canonical EIA names (X7R not B, C0G not NP0).
- Do not output Markdown code fences. Output a single JSON object."""


def _format_batch(facts: list[dict[str, Any]]) -> str:
    lines = []
    for f in facts:
        src = f.get("source", {})
        loc = "/".join(
            x for x in [src.get("source_doc"), src.get("table_id"), src.get("row_id")] if x
        )
        lines.append(f"[{loc}] {f.get('sentence', '')}")
    return "\n".join(lines)


def _attach_provenance(nodes: list[dict[str, Any]], edges: list[dict[str, Any]],
                      facts: list[dict[str, Any]]) -> None:
    """Stamp each node/edge with the source(s) of the batch.

    bridge.py only needs the union — we attach all facts in the batch as
    fallback provenance, because the LLM may not echo source tags reliably.
    """
    sources = [f.get("source", {}) for f in facts]
    for n in nodes:
        n.setdefault("metadata", {}).setdefault("sources", sources)
    for e in edges:
        e.setdefault("metadata", {}).setdefault("sources", sources)


async def _extract_one_batch(facts: list[dict[str, Any]], cfg: LLMConfig) -> dict[str, Any]:
    user = (
        "Extract entities and relationships from these MLCC facts.\n"
        "Each line is prefixed with its source location.\n\n"
        f"{_format_batch(facts)}\n"
    )
    try:
        result = await chat_json(user, system=_SYSTEM_PROMPT, cfg=cfg)
    except Exception as exc:  # noqa: BLE001
        return {
            "nodes": [],
            "edges": [],
            "error": f"{type(exc).__name__}: {exc}",
        }
    if not isinstance(result, dict):
        return {"nodes": [], "edges": [], "error": "non-object JSON"}
    nodes = result.get("nodes") or []
    edges = result.get("edges") or []
    _attach_provenance(nodes, edges, facts)
    return {"nodes": nodes, "edges": edges}


def _merge_graphs(graphs: list[dict[str, Any]]) -> dict[str, Any]:
    nodes_by_id: dict[str, dict[str, Any]] = {}
    edges_seen: set[tuple[str, str, str]] = set()
    edges: list[dict[str, Any]] = []

    for g in graphs:
        for n in g.get("nodes", []):
            nid = str(n.get("id") or n.get("name") or "").strip()
            if not nid:
                continue
            existing = nodes_by_id.get(nid)
            if existing is None:
                nodes_by_id[nid] = dict(n)
            else:
                # Merge descriptions and source lists.
                if n.get("description") and n["description"] not in (existing.get("description") or ""):
                    existing["description"] = (
                        (existing.get("description") or "") + " | " + n["description"]
                    ).strip(" |")
                ex_meta = existing.setdefault("metadata", {})
                in_meta = n.get("metadata", {})
                ex_meta.setdefault("sources", []).extend(in_meta.get("sources", []))
        for e in g.get("edges", []):
            key = (str(e.get("source")), str(e.get("target")), str(e.get("type")).upper())
            if key in edges_seen:
                continue
            edges_seen.add(key)
            edges.append(e)

    return {"nodes": list(nodes_by_id.values()), "edges": edges}


async def extract(
    processed_dir: Path,
    out_dir: Path,
    *,
    batch_size: int | None = None,
    max_concurrency: int | None = None,
) -> Path:
    """Extract a KG from preprocessed facts. Writes <out_dir>/graphify-out/graph.json."""
    cfg = LLMConfig.from_env()
    batch_size = batch_size or int(os.environ.get("KG_BATCH_SIZE", "20"))
    max_concurrency = max_concurrency or int(os.environ.get("KG_MAX_CONCURRENCY", "4"))

    fact_files = sorted(processed_dir.glob("*.facts.jsonl"))
    if not fact_files:
        raise FileNotFoundError(
            f"No *.facts.jsonl in {processed_dir}. Run `make preprocess` first."
        )

    all_facts: list[dict[str, Any]] = []
    for f in fact_files:
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                all_facts.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    batches = [all_facts[i : i + batch_size] for i in range(0, len(all_facts), batch_size)]
    semaphore = asyncio.Semaphore(max_concurrency)

    async def _bounded(batch: list[dict[str, Any]]) -> dict[str, Any]:
        async with semaphore:
            return await _extract_one_batch(batch, cfg)

    results = await asyncio.gather(*[_bounded(b) for b in batches]) if batches else []
    merged = _merge_graphs(results)

    target_dir = out_dir / "graphify-out"
    target_dir.mkdir(parents=True, exist_ok=True)
    graph_path = target_dir / "graph.json"
    graph_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")

    # Sidecar stats so `make compare` can surface batch-level errors.
    stats = {
        "facts_in": len(all_facts),
        "batches": len(batches),
        "nodes_out": len(merged["nodes"]),
        "edges_out": len(merged["edges"]),
        "batch_errors": [r.get("error") for r in results if r.get("error")],
        "model": cfg.llm_model,
    }
    (target_dir / "extract_stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return graph_path
