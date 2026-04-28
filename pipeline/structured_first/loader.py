"""Load *.facts.jsonl + *.tables.json into the fact store.

Walks data/processed/ for the artifacts produced by
`pipeline.common.preprocess`, classifies each table row with
`extract_product_scope`, and writes canonical Products / Specs into the
SQLite fact store. Codebook rows skip Product creation but still leave a
row in `specs` keyed by (`source_doc::section_path`, code).

Idempotent: re-running upserts in place using deterministic IDs.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pipeline.common.extract_product_scope import (
    Scope,
    is_codebook_section,
    scope_for_row,
)
from pipeline.common.fact_store import FactStore, FactStoreConfig
from schema import Source, Spec


def _sid(*parts: str) -> str:
    return hashlib.sha1("||".join(parts).encode("utf-8")).hexdigest()[:16]


def _row_source(*, source_doc: str, section_path: list[str], table_id: str, row_id: str,
                line_start: int, line_end: int) -> Source:
    return Source(
        source_doc=source_doc,
        section_path=" > ".join(section_path),
        table_id=table_id,
        row_id=row_id,
        line_start=line_start,
        line_end=line_end,
    )


def load_processed_dir(processed_dir: Path, *, store_path: Path | None = None) -> dict[str, int]:
    cfg = FactStoreConfig(db_path=store_path or FactStoreConfig.default().db_path)
    counts = {"products": 0, "specs": 0, "codebook_rows": 0, "skipped": 0}
    with FactStore(cfg) as store, store.transaction():
        for tables_json in sorted(processed_dir.glob("*.tables.json")):
            source_doc = tables_json.stem.replace(".tables", "") + ".md"
            tables = json.loads(tables_json.read_text(encoding="utf-8"))
            for tbl in tables:
                section_path = tbl.get("section_path") or []
                heading = tbl.get("heading", "")
                table_id = tbl["table_id"]
                rows: list[dict[str, str]] = tbl["rows"]
                row_ids: list[str] = tbl["row_ids"]
                headers: list[str] = tbl["headers"]
                start = int(tbl.get("start_line") or -1)
                end = int(tbl.get("end_line") or -1)

                for row, row_id in zip(rows, row_ids):
                    src = _row_source(
                        source_doc=source_doc,
                        section_path=section_path,
                        table_id=table_id,
                        row_id=row_id,
                        line_start=start,
                        line_end=end,
                    )

                    if is_codebook_section(heading):
                        # Emit one Spec per row keyed by (source_doc, table_id).
                        # We synthesize a 'codebook' product so foreign keys hold.
                        cb_product = f"codebook::{source_doc}::{table_id}"
                        for k, v in row.items():
                            if not v:
                                continue
                            spec_id = _sid(cb_product, k, v)
                            store.upsert_spec(
                                Spec(
                                    spec_id=spec_id,
                                    product_id=cb_product,
                                    key=k,
                                    value_text=v,
                                    value_num=_maybe_float(v),
                                    unit=None,
                                    notes=None,
                                    source=src,
                                )
                            )
                            counts["codebook_rows"] += 1
                        continue

                    scope, product = scope_for_row(
                        headings=section_path,
                        headers=headers,
                        row=row,
                        source=src,
                    )

                    if scope.kind == "global" or product is None:
                        counts["skipped"] += 1
                        continue

                    store.upsert_product(product)
                    counts["products"] += 1

                    for k, v in row.items():
                        if not v or k == "":
                            continue
                        spec_id = _sid(product.product_id, k, v)
                        store.upsert_spec(
                            Spec(
                                spec_id=spec_id,
                                product_id=product.product_id,
                                key=k,
                                value_text=v,
                                value_num=_maybe_float(v),
                                unit=None,
                                notes=None,
                                source=src,
                            )
                        )
                        counts["specs"] += 1
    return counts


def _maybe_float(s: str) -> float | None:
    try:
        return float(s.replace(",", "").strip())
    except (TypeError, ValueError):
        return None
