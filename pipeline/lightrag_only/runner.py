"""Pipeline B: feed preprocessed markdown straight to LightRAG-on-AGE.

Uses the same preprocessed artifacts (`data/processed/*.md`) that pipeline A
feeds into Graphify, so input parity is guaranteed.
"""
from __future__ import annotations

from pathlib import Path

from pipeline.common.lightrag_bootstrap import build_rag


WORKSPACE = "mlcc_lightrag_only"


async def ingest(processed_dir: Path, working_dir: Path) -> dict[str, int]:
    rag = await build_rag(workspace=WORKSPACE, working_dir=working_dir)
    try:
        md_files = sorted(processed_dir.glob("*.md"))
        contents = [p.read_text(encoding="utf-8") for p in md_files]
        file_paths = [str(p) for p in md_files]
        if not contents:
            return {"docs": 0}

        await rag.ainsert(contents, file_paths=file_paths)
        return {"docs": len(contents)}
    finally:
        await rag.finalize_storages()


async def query(question: str, mode: str, working_dir: Path) -> str:
    from lightrag import QueryParam

    rag = await build_rag(workspace=WORKSPACE, working_dir=working_dir)
    try:
        return await rag.aquery(question, param=QueryParam(mode=mode))
    finally:
        await rag.finalize_storages()
