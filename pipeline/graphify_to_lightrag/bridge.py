"""Graphify graph.json  ->  LightRAG custom_kg.

claude.md rule A-3 / A-4: do not feed Graphify output straight into LightRAG.
Post-process first: normalize entity names, canonicalize units, drop stray
relations, rewrite as natural-language triples, and emit a custom_kg payload
that LightRAG accepts via `insert_custom_kg`.

The exact shape of `graph.json` is not pinned by Graphify's README, so this
module treats the structure defensively: it accepts either

    {"nodes": [...], "edges": [...]}

or

    {"nodes": [...], "relationships": [...]}

and picks up a handful of common property names. If Graphify's schema changes,
tweak `_node_name` / `_edge_fields` in one place here rather than in the
pipeline runner.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pipeline.common.normalize import canonicalize_entity, normalize_cell


@dataclass
class CustomKG:
    chunks: list[dict[str, Any]] = field(default_factory=list)
    entities: list[dict[str, Any]] = field(default_factory=list)
    relationships: list[dict[str, Any]] = field(default_factory=list)

    def as_payload(self) -> dict[str, Any]:
        return {
            "chunks": self.chunks,
            "entities": self.entities,
            "relationships": self.relationships,
        }


def _node_name(node: dict[str, Any]) -> str:
    for key in ("name", "label", "id", "title"):
        v = node.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return str(node.get("id", "unknown"))


def _node_type(node: dict[str, Any]) -> str:
    for key in ("type", "entity_type", "category", "kind"):
        v = node.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return "concept"


def _node_description(node: dict[str, Any]) -> str:
    for key in ("description", "summary", "docstring"):
        v = node.get(key)
        if isinstance(v, str) and v.strip():
            return normalize_cell(v)
    return ""


def _edge_fields(edge: dict[str, Any]) -> tuple[str, str, str, str, float]:
    src = edge.get("source") or edge.get("src") or edge.get("from") or edge.get("start")
    tgt = edge.get("target") or edge.get("dst") or edge.get("to") or edge.get("end")
    rel = edge.get("type") or edge.get("relation") or edge.get("label") or "RELATED_TO"
    desc = edge.get("description") or edge.get("summary") or ""
    conf = float(edge.get("confidence", edge.get("weight", 1.0)) or 1.0)
    return str(src), str(tgt), str(rel), normalize_cell(str(desc)), conf


def load_graph(graph_json_path: Path) -> dict[str, Any]:
    return json.loads(graph_json_path.read_text(encoding="utf-8"))


def build_custom_kg(
    graph: dict[str, Any],
    *,
    source_doc: str,
    min_edge_confidence: float = 0.0,
    drop_ambiguous: bool = True,
) -> CustomKG:
    nodes = graph.get("nodes") or graph.get("entities") or []
    edges = (
        graph.get("edges")
        or graph.get("relationships")
        or graph.get("relations")
        or graph.get("links")
        or []
    )

    kg = CustomKG()
    id_to_canonical: dict[str, str] = {}
    seen_entities: dict[str, dict[str, Any]] = {}

    for n in nodes:
        raw_name = _node_name(n)
        canonical = canonicalize_entity(raw_name)
        id_to_canonical[str(n.get("id", raw_name))] = canonical
        id_to_canonical[raw_name] = canonical

        existing = seen_entities.get(canonical)
        if existing is None:
            seen_entities[canonical] = {
                "entity_name": canonical,
                "entity_type": _node_type(n),
                "description": _node_description(n) or f"Entity extracted by Graphify from {source_doc}.",
                "source_id": f"graphify::{source_doc}",
            }
        else:
            # Merge descriptions when the same canonical appears under aliases.
            desc = _node_description(n)
            if desc and desc not in existing["description"]:
                existing["description"] = f"{existing['description']} | {desc}"

    kg.entities.extend(seen_entities.values())

    seen_triples: set[tuple[str, str, str]] = set()
    for e in edges:
        if drop_ambiguous and str(e.get("tag", "")).upper() == "AMBIGUOUS":
            continue
        src_raw, tgt_raw, rel, desc, conf = _edge_fields(e)
        if conf < min_edge_confidence:
            continue
        src = id_to_canonical.get(src_raw, canonicalize_entity(src_raw))
        tgt = id_to_canonical.get(tgt_raw, canonicalize_entity(tgt_raw))
        if not src or not tgt or src == tgt:
            continue
        key = (src, tgt, rel.upper())
        if key in seen_triples:
            continue
        seen_triples.add(key)

        kg.relationships.append(
            {
                "src_id": src,
                "tgt_id": tgt,
                "description": desc or f"{src} {rel.lower().replace('_', ' ')} {tgt}.",
                "keywords": rel,
                "weight": conf,
                "source_id": f"graphify::{source_doc}",
            }
        )

    # Emit one chunk per natural-language triple - this is how LightRAG stitches
    # custom_kg back into its retriever context during the vector/graph blend.
    for rel_row in kg.relationships:
        sentence = rel_row["description"]
        kg.chunks.append(
            {
                "content": sentence,
                "source_id": rel_row["source_id"],
            }
        )

    return kg


def write_custom_kg(kg: CustomKG, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(kg.as_payload(), ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path
