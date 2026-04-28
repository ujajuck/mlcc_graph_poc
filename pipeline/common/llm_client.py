"""LiteLLM-backed client. Single entry point for both pipelines.

Why LiteLLM:
    - Local servers (Ollama, vLLM, LocalAI, TGI, llama.cpp) all speak some
      flavor of OpenAI-compatible HTTP, but the small differences (Ollama's
      /api/generate vs vLLM's /v1/chat/completions, embedding shapes, JSON
      mode quirks) are tedious to handle by hand.
    - LiteLLM normalizes everything behind `acompletion` / `aembedding`. We
      pass a model string like 'ollama/llama3:70b' or 'openai/Qwen2.5-32B-
      Instruct' (vLLM is OpenAI-compatible, so 'openai/...' with a custom
      base_url works) and stop thinking about it.

Env contract (set in `config/.env`):
    LLM_PROVIDER             optional. 'ollama' | 'vllm' | 'openai' | 'litellm-proxy'
                             only used to default the model prefix.
    LLM_MODEL                full LiteLLM model string, e.g. 'ollama/llama3:70b'
                             or 'openai/Qwen2.5-32B-Instruct'.
    LLM_BINDING_HOST         base_url. For Ollama: 'http://localhost:11434'.
                             For vLLM: 'http://localhost:8000/v1'.
    LLM_BINDING_API_KEY      API key. Most local servers ignore it but
                             LiteLLM still requires the field non-empty.
    LLM_TIMEOUT              seconds, default 240.

    EMBEDDING_MODEL          e.g. 'ollama/bge-m3' or 'openai/bge-m3'.
    EMBEDDING_BINDING_HOST   base_url for embedding server (often same as LLM).
    EMBEDDING_BINDING_API_KEY
    EMBEDDING_DIM            must match the model's actual output dim.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

import litellm
import numpy as np


# Be quiet by default; pipelines emit their own progress.
litellm.suppress_debug_info = True
litellm.set_verbose = False


@dataclass(frozen=True)
class LLMConfig:
    llm_model: str
    llm_base_url: str | None
    llm_api_key: str
    llm_timeout: int
    embedding_model: str
    embedding_base_url: str | None
    embedding_api_key: str
    embedding_dim: int

    @classmethod
    def from_env(cls) -> "LLMConfig":
        return cls(
            llm_model=os.environ.get("LLM_MODEL", "ollama/llama3"),
            llm_base_url=os.environ.get("LLM_BINDING_HOST") or None,
            llm_api_key=os.environ.get("LLM_BINDING_API_KEY", "sk-local-placeholder"),
            llm_timeout=int(os.environ.get("LLM_TIMEOUT", "240")),
            embedding_model=os.environ.get("EMBEDDING_MODEL", "ollama/bge-m3"),
            embedding_base_url=os.environ.get("EMBEDDING_BINDING_HOST") or None,
            embedding_api_key=os.environ.get(
                "EMBEDDING_BINDING_API_KEY", "sk-local-placeholder"
            ),
            embedding_dim=int(os.environ.get("EMBEDDING_DIM", "1024")),
        )


# ---------------------------------------------------------------------------
# Chat completion
# ---------------------------------------------------------------------------


async def chat(
    prompt: str,
    *,
    system: str | None = None,
    history: list[dict[str, str]] | None = None,
    response_format: dict[str, Any] | None = None,
    temperature: float = 0.0,
    max_tokens: int | None = None,
    cfg: LLMConfig | None = None,
) -> str:
    """Single-turn chat. Returns the assistant message string."""
    cfg = cfg or LLMConfig.from_env()
    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": prompt})

    kwargs: dict[str, Any] = {
        "model": cfg.llm_model,
        "messages": messages,
        "temperature": temperature,
        "timeout": cfg.llm_timeout,
        "api_key": cfg.llm_api_key,
    }
    if cfg.llm_base_url:
        kwargs["api_base"] = cfg.llm_base_url
    if max_tokens:
        kwargs["max_tokens"] = max_tokens
    if response_format:
        kwargs["response_format"] = response_format

    resp = await litellm.acompletion(**kwargs)
    return resp.choices[0].message.content or ""


async def chat_json(
    prompt: str,
    *,
    system: str | None = None,
    cfg: LLMConfig | None = None,
    temperature: float = 0.0,
    max_tokens: int | None = None,
) -> Any:
    """Chat that requests a JSON object response. Returns parsed JSON.

    Falls back to substring extraction if the model wraps JSON in prose
    (some local models ignore response_format={'type':'json_object'}).
    """
    text = await chat(
        prompt,
        system=system,
        response_format={"type": "json_object"},
        temperature=temperature,
        max_tokens=max_tokens,
        cfg=cfg,
    )
    return _parse_json_lenient(text)


def _parse_json_lenient(text: str) -> Any:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try to find the first balanced JSON object/array.
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError(f"could not parse JSON out of model output: {text[:300]}...")


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------


async def embed(texts: list[str], *, cfg: LLMConfig | None = None) -> np.ndarray:
    cfg = cfg or LLMConfig.from_env()
    kwargs: dict[str, Any] = {
        "model": cfg.embedding_model,
        "input": texts,
        "api_key": cfg.embedding_api_key,
        "timeout": cfg.llm_timeout,
    }
    if cfg.embedding_base_url:
        kwargs["api_base"] = cfg.embedding_base_url

    resp = await litellm.aembedding(**kwargs)
    vectors = [d["embedding"] for d in resp.data]
    return np.array(vectors, dtype=np.float32)


# ---------------------------------------------------------------------------
# LightRAG adapters
# ---------------------------------------------------------------------------
#
# LightRAG expects:
#   llm_model_func(prompt, system_prompt=None, history_messages=[], **kw) -> str
#   EmbeddingFunc(embedding_dim, max_token_size, func)
#       where func(texts: list[str]) -> np.ndarray
#
# We adapt our chat()/embed() to those signatures so LightRAG never needs to
# know that LiteLLM is in the middle.


async def lightrag_llm_func(
    prompt: str,
    system_prompt: str | None = None,
    history_messages: list[dict[str, str]] | None = None,
    **kwargs: Any,
) -> str:
    cfg = LLMConfig.from_env()
    return await chat(
        prompt,
        system=system_prompt,
        history=history_messages,
        cfg=cfg,
        max_tokens=kwargs.get("max_tokens"),
        temperature=kwargs.get("temperature", 0.0),
    )


def make_lightrag_embedding_func() -> Any:
    """Build LightRAG's EmbeddingFunc bound to our config.

    Imported lazily so that callers without lightrag installed (preprocessing,
    fact_store, score_answers, ...) do not pull it in.
    """
    from lightrag.utils import EmbeddingFunc

    cfg = LLMConfig.from_env()

    async def _func(texts: list[str]) -> np.ndarray:
        return await embed(texts, cfg=cfg)

    return EmbeddingFunc(
        embedding_dim=cfg.embedding_dim,
        max_token_size=int(os.environ.get("EMBEDDING_MAX_TOKEN_SIZE", "8192")),
        func=_func,
    )
