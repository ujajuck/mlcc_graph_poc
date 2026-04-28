"""Build and initialize a LightRAG instance wired to Apache AGE + LiteLLM.

Both pipelines use this helper. The only thing they vary is the workspace
name — that's what keeps their graphs isolated inside the same AGE instance.

LightRAG's PGGraphStorage derives the AGE graph name from POSTGRES_WORKSPACE
(see lightrag/kg/postgres_impl.py `_get_workspace_graph_name`), so setting
the workspace before calling `initialize_storages` is sufficient.

LLM and embedding calls go through `pipeline.common.llm_client`, which
fronts a local Ollama or vLLM via LiteLLM. We inject our own
`llm_model_func` and `embedding_func` so LightRAG never touches the
host-agent path. Callers can still override either by passing them
explicitly.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Awaitable, Callable

from pipeline.common.llm_client import lightrag_llm_func, make_lightrag_embedding_func


async def build_rag(
    *,
    workspace: str,
    working_dir: Path,
    llm_model_func: Callable[..., Awaitable[str]] | None = None,
    embedding_func: Any | None = None,
) -> Any:
    """Return an initialized LightRAG bound to AGE with the given workspace.

    Imports happen inside the function so the rest of the repo can be imported
    (for tests, preprocessing) without LightRAG being installed.
    """
    from lightrag import LightRAG
    from lightrag.kg.shared_storage import initialize_pipeline_status

    os.environ["POSTGRES_WORKSPACE"] = workspace
    working_dir.mkdir(parents=True, exist_ok=True)

    kv = os.environ.get("LIGHTRAG_KV_STORAGE", "PGKVStorage")
    vec = os.environ.get("LIGHTRAG_VECTOR_STORAGE", "NanoVectorDBStorage")
    graph = os.environ.get("LIGHTRAG_GRAPH_STORAGE", "PGGraphStorage")
    docs = os.environ.get("LIGHTRAG_DOC_STATUS_STORAGE", "PGDocStatusStorage")

    kwargs: dict[str, Any] = dict(
        working_dir=str(working_dir),
        kv_storage=kv,
        vector_storage=vec,
        graph_storage=graph,
        doc_status_storage=docs,
        llm_model_func=llm_model_func or lightrag_llm_func,
        embedding_func=embedding_func or make_lightrag_embedding_func(),
    )

    rag = LightRAG(**kwargs)
    await rag.initialize_storages()
    await initialize_pipeline_status()
    return rag
