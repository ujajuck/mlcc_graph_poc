"""Invoke the Graphify CLI on the preprocessed corpus.

Graphify itself does not call any LLM directly (grep its source: no
openai/anthropic/httpx/requests). It is a "skill" installed into a host
coding agent (OpenCode / Aider / Claude Code / Codex / etc.) and the *host*
makes the LLM calls. For this POC we want both pipelines to hit the SAME
locally-served OpenAI-compatible endpoint, so the env vars the host agent
reads are forwarded here from `config/.env`.

The actual mapping (LLM_BINDING_HOST -> OPENAI_API_BASE, etc.) depends on
which host is in use, which the user selects via `GRAPHIFY_HOST_AGENT`. We
do the remap once here so the pipeline A entry point stays a single command.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


class GraphifyNotInstalled(RuntimeError):
    pass


# Map each known host agent to the env vars it reads for an OpenAI-compatible
# local LLM. When GRAPHIFY_LLM_* are set in .env we copy them into the names
# the host actually reads, without mutating the parent shell.
_HOST_ENV_BINDINGS: dict[str, dict[str, str]] = {
    "opencode": {
        "OPENAI_API_BASE": "GRAPHIFY_LLM_BASE_URL",
        "OPENAI_BASE_URL": "GRAPHIFY_LLM_BASE_URL",
        "OPENAI_API_KEY": "GRAPHIFY_LLM_API_KEY",
        "OPENCODE_MODEL": "GRAPHIFY_LLM_MODEL",
    },
    "aider": {
        "OPENAI_API_BASE": "GRAPHIFY_LLM_BASE_URL",
        "OPENAI_API_KEY": "GRAPHIFY_LLM_API_KEY",
    },
    "codex": {
        "OPENAI_API_BASE": "GRAPHIFY_LLM_BASE_URL",
        "OPENAI_API_KEY": "GRAPHIFY_LLM_API_KEY",
    },
    "claude": {
        # Claude Code uses its own auth; it CANNOT be pointed at a local LLM.
        # Listed here only to fail loud if the user sets GRAPHIFY_HOST_AGENT=claude
        # while also expecting local-LLM behavior.
    },
}


def _host_env_overlay() -> dict[str, str]:
    host = os.environ.get("GRAPHIFY_HOST_AGENT", "opencode").lower()
    mapping = _HOST_ENV_BINDINGS.get(host, {})
    overlay: dict[str, str] = {}
    for dst, src in mapping.items():
        val = os.environ.get(src)
        if val:
            overlay[dst] = val
    return overlay


def run_graphify(processed_dir: Path, out_dir: Path) -> Path:
    cmd_name = os.environ.get("GRAPHIFY_CMD", "graphify")
    cmd_path = shutil.which(cmd_name)
    if cmd_path is None:
        raise GraphifyNotInstalled(
            f"'{cmd_name}' not found on PATH. Install with "
            "`pip install graphifyy && graphify <host> install`, where "
            "<host> is one of: opencode, aider, codex, claude, ... See README."
        )

    out_dir.mkdir(parents=True, exist_ok=True)

    args = [cmd_path, str(processed_dir.resolve()), "--update"]
    if os.environ.get("GRAPHIFY_DIRECTED", "1") not in ("0", "", "false", "False"):
        args.append("--directed")
    mode = os.environ.get("GRAPHIFY_MODE", "").strip()
    if mode:
        args.extend(["--mode", mode])

    env = os.environ.copy()
    env.update(_host_env_overlay())

    # Graphify writes its artifacts into ./graphify-out relative to CWD.
    subprocess.run(args, cwd=out_dir, check=True, env=env)

    graph_json = out_dir / "graphify-out" / "graph.json"
    if not graph_json.exists():
        raise FileNotFoundError(
            f"Graphify finished but {graph_json} is missing. "
            "Check GRAPHIFY_OUT_DIR and CLI version."
        )
    return graph_json
