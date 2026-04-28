"""Pipeline A: LiteLLM-based KG extraction → postprocess → LightRAG-on-AGE.

Steps, matching claude.md section A:
    A-1  preprocess markdown (shared, handled by scripts/preprocess)
    A-2  run our own LLM-driven KG extractor (LiteLLM → local Ollama/vLLM)
    A-3  normalize entity names / units in graph.json
    A-4  build a LightRAG custom_kg payload
    A-5  insert_custom_kg into the AGE-backed workspace

The legacy host-agent dispatch (OpenCode/Aider/Codex) has been removed; see
`pipeline/graphify_to_lightrag/kg_extractor.py` for the replacement.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from pipeline.common.lightrag_bootstrap import build_rag
from pipeline.graphify_to_lightrag.bridge import build_custom_kg, load_graph, write_custom_kg
from pipeline.graphify_to_lightrag.kg_extractor import extract


WORKSPACE = "mlcc_graphify_to_lightrag"


async def ingest(processed_dir: Path, working_dir: Path, out_dir: Path) -> dict[str, int]:
    out_dir.mkdir(parents=True, exist_ok=True)

    extract_root = Path(os.environ.get("GRAPHIFY_OUT_DIR", out_dir / "graphify_raw"))
    extract_root.mkdir(parents=True, exist_ok=True)
    graph_json = await extract(processed_dir, extract_root)

    graph = load_graph(graph_json)
    kg = build_custom_kg(
        graph,
        source_doc=str(processed_dir.name),
        min_edge_confidence=float(os.environ.get("MIN_EDGE_CONFIDENCE", "0.0")),
        drop_ambiguous=True,
    )
    kg_path = write_custom_kg(kg, out_dir / "custom_kg.json")

    rag = await build_rag(workspace=WORKSPACE, working_dir=working_dir)
    try:
        payload = json.loads(kg_path.read_text(encoding="utf-8"))
        rag.insert_custom_kg(payload)
    finally:
        await rag.finalize_storages()

    return {
        "entities": len(kg.entities),
        "relationships": len(kg.relationships),
        "chunks": len(kg.chunks),
    }


async def query(question: str, mode: str, working_dir: Path) -> str:
    from lightrag import QueryParam

    rag = await build_rag(workspace=WORKSPACE, working_dir=working_dir)
    try:
        return await rag.aquery(question, param=QueryParam(mode=mode))
    finally:
        await rag.finalize_storages()
