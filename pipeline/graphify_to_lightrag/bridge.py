"""Graphify graph.json  ->  LightRAG custom_kg.

claude.md rule A-3 / A-4: do not feed Graphify output straight into LightRAG.
Post-process first: normalize entity names, canonicalize units, drop stray
relations, validate relation types against an allow-list, attach source row
provenance, and emit a custom_kg payload that LightRAG accepts via
`insert_custom_kg`.

Schema assumptions
------------------
The exact shape of `graph.json` is not pinned by Graphify's README, so this
module accepts either

    {"nodes": [...], "edges": [...]}

or

    {"nodes": [...], "relationships": [...]}

with a handful of common property names per node/edge. Anything we don't
recognise is dropped (with a counter), not papered over.

Provenance
----------
Each entity and relationship is tagged with:

  - source_id: 'graphify::{source_doc}'
  - meta.source_row_id: the table_id/row_id this fact came from, if Graphify
    surfaced it (we look in 'metadata' / 'meta' / 'provenance' subobjects)

Without source_id the row is still emitted (graphs without provenance are
better than no graphs at all), but it counts toward `unsourced_*` so the
runner can surface it in the comparison report.

Relation type validation
------------------------
We keep an allow-list of MLCC-relevant relation types. Edges with a
relation outside the allow-list are kept but flagged 'OTHER' so they don't
contaminate downstream analytics that bucket by relation type. AMBIGUOUS
edges are dropped by default (claude.md rule A-3).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pipeline.common.normalize import canonicalize_entity, normalize_cell


# Relation types we consider meaningful for MLCC reasoning. Order doesn't
# matter; everything that hits this set is preserved verbatim. Anything else
# becomes 'OTHER'.
_ALLOWED_RELATIONS: frozenset[str] = frozenset(
    {
        "BELONGS_TO",
        "HAS_SPEC",
        "HAS_TEST_CONDITION",
        "HAS_EXCEPTION",
        "EQUIVALENT_TO",
        "ALIAS_OF",
        "PART_OF",
        "APPLIES_TO",
        "RECOMMENDED_FOR",
        "INCOMPATIBLE_WITH",
        "RELATED_TO",
    }
)


@dataclass
class CustomKG:
    chunks: list[dict[str, Any]] = field(default_factory=list)
    entities: list[dict[str, Any]] = field(default_factory=list)
    relationships: list[dict[str, Any]] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)

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


def _provenance(obj: dict[str, Any]) -> dict[str, str]:
    """Pull source_doc/table_id/row_id out of common metadata locations."""
    out: dict[str, str] = {}
    for parent_key in ("metadata", "meta", "provenance", "source"):
        parent = obj.get(parent_key)
        if isinstance(parent, dict):
            for k in ("source_doc", "table_id", "row_id", "section_path", "line_start", "line_end"):
                v = parent.get(k)
                if v is not None and v != "":
                    out[k] = str(v)
    # Also accept top-level keys (some extractors flatten metadata).
    for k in ("source_doc", "table_id", "row_id", "section_path"):
        v = obj.get(k)
        if v is not None and v != "" and k not in out:
            out[k] = str(v)
    return out


def _normalize_relation(label: str) -> tuple[str, bool]:
    """Return (canonical_label, in_allowlist)."""
    s = (label or "").strip().upper().replace(" ", "_").replace("-", "_")
    if not s:
        return "RELATED_TO", True
    if s in _ALLOWED_RELATIONS:
        return s, True
    return "OTHER", False


def _edge_fields(
    edge: dict[str, Any],
) -> tuple[str, str, str, str, float, str, dict[str, str]]:
    src = edge.get("source") or edge.get("src") or edge.get("from") or edge.get("start")
    tgt = edge.get("target") or edge.get("dst") or edge.get("to") or edge.get("end")
    raw_rel = edge.get("type") or edge.get("relation") or edge.get("label") or "RELATED_TO"
    desc = edge.get("description") or edge.get("summary") or ""
    conf = float(edge.get("confidence", edge.get("weight", 1.0)) or 1.0)
    rel, _in_allow = _normalize_relation(str(raw_rel))
    prov = _provenance(edge)
    return str(src), str(tgt), rel, normalize_cell(str(desc)), conf, str(raw_rel), prov


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
    stats = {
        "nodes_in": len(nodes),
        "edges_in": len(edges),
        "edges_dropped_ambiguous": 0,
        "edges_dropped_low_confidence": 0,
        "edges_dropped_self_loop": 0,
        "edges_relabeled_other": 0,
        "edges_unsourced": 0,
        "entities_unsourced": 0,
    }

    id_to_canonical: dict[str, str] = {}
    seen_entities: dict[str, dict[str, Any]] = {}

    for n in nodes:
        raw_name = _node_name(n)
        canonical = canonicalize_entity(raw_name)
        id_to_canonical[str(n.get("id", raw_name))] = canonical
        id_to_canonical[raw_name] = canonical

        prov = _provenance(n)
        if not prov:
            stats["entities_unsourced"] += 1

        existing = seen_entities.get(canonical)
        if existing is None:
            seen_entities[canonical] = {
                "entity_name": canonical,
                "entity_type": _node_type(n),
                "description": _node_description(n)
                or f"Entity extracted by Graphify from {source_doc}.",
                "source_id": f"graphify::{source_doc}",
                "meta": prov,
            }
        else:
            desc = _node_description(n)
            if desc and desc not in existing["description"]:
                existing["description"] = f"{existing['description']} | {desc}"
            # Merge provenance so multiple-alias mentions accumulate sources.
            for k, v in prov.items():
                existing["meta"].setdefault(k, v)

    kg.entities.extend(seen_entities.values())

    seen_triples: set[tuple[str, str, str]] = set()
    for e in edges:
        if drop_ambiguous and str(e.get("tag", "")).upper() == "AMBIGUOUS":
            stats["edges_dropped_ambiguous"] += 1
            continue
        src_raw, tgt_raw, rel, desc, conf, raw_rel, prov = _edge_fields(e)
        if conf < min_edge_confidence:
            stats["edges_dropped_low_confidence"] += 1
            continue
        src = id_to_canonical.get(src_raw, canonicalize_entity(src_raw))
        tgt = id_to_canonical.get(tgt_raw, canonicalize_entity(tgt_raw))
        if not src or not tgt or src == tgt:
            stats["edges_dropped_self_loop"] += 1
            continue
        if rel == "OTHER":
            stats["edges_relabeled_other"] += 1
        if not prov:
            stats["edges_unsourced"] += 1

        key = (src, tgt, rel)
        if key in seen_triples:
            continue
        seen_triples.add(key)

        kg.relationships.append(
            {
                "src_id": src,
                "tgt_id": tgt,
                "description": desc or _natural_sentence(src, raw_rel, tgt),
                "keywords": rel,
                "weight": conf,
                "source_id": f"graphify::{source_doc}",
                "meta": {**prov, "raw_relation": raw_rel},
            }
        )

    for rel_row in kg.relationships:
        kg.chunks.append(
            {
                "content": rel_row["description"],
                "source_id": rel_row["source_id"],
            }
        )

    kg.stats = stats
    return kg


def _natural_sentence(src: str, rel: str, tgt: str) -> str:
    return f"{src} {rel.lower().replace('_', ' ')} {tgt}."


def write_custom_kg(kg: CustomKG, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(kg.as_payload(), ensure_ascii=False, indent=2), encoding="utf-8")
    # Sidecar stats so the comparison report can show what we dropped.
    stats_path = out_path.with_suffix(".stats.json")
    stats_path.write_text(json.dumps(kg.stats, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path
