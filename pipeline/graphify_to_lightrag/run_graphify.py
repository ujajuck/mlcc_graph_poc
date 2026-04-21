"""Invoke the Graphify CLI on the preprocessed corpus.

claude.md A-2 input is the *preprocessed* markdown (tables already flattened
into facts) so Graphify sees deterministic sentences instead of ascii tables.
Outputs land in $GRAPHIFY_OUT_DIR.

Graphify is a Claude-Code skill today, installed via:
    uv tool install graphifyy && graphify install

If the CLI is not available on PATH this module raises a clear error rather
than silently producing an empty graph.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


class GraphifyNotInstalled(RuntimeError):
    pass


def run_graphify(processed_dir: Path, out_dir: Path) -> Path:
    cmd_name = os.environ.get("GRAPHIFY_CMD", "graphify")
    cmd_path = shutil.which(cmd_name)
    if cmd_path is None:
        raise GraphifyNotInstalled(
            f"'{cmd_name}' not found on PATH. Install with "
            "`uv tool install graphifyy && graphify install`, or set "
            "GRAPHIFY_CMD in .env."
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    # Graphify writes its artifacts into ./graphify-out relative to CWD. We
    # run it inside `out_dir` so repeated pipeline runs stay isolated.
    subprocess.run(
        [cmd_path, str(processed_dir.resolve()), "--update", "--directed"],
        cwd=out_dir,
        check=True,
    )

    graph_json = out_dir / "graphify-out" / "graph.json"
    if not graph_json.exists():
        raise FileNotFoundError(
            f"Graphify finished but {graph_json} is missing. "
            "Check GRAPHIFY_OUT_DIR and CLI version."
        )
    return graph_json
