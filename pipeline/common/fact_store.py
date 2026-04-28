"""Deterministic store for canonical MLCC facts.

Backed by SQLite by default — zero-setup, file-based, perfect for the POC.
The same schema can later be mirrored into Postgres tables alongside the
AGE graph; the SQL stays portable since we avoid SQLite-specific syntax
where possible.

This is the source-of-truth layer that the evaluation feedback called for:
'tables.json → canonical facts → deterministic insert'. RAG/LLM may explain
results, but condition queries (voltage >= 4.5V, size = 0603, ...) MUST hit
this store, never the LLM.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from schema import Exception_, Product, Source, Spec, TestCondition


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS products (
    product_id            TEXT PRIMARY KEY,
    part_number           TEXT,
    family_id             TEXT,
    size_code             TEXT,
    size_inch             TEXT,
    size_metric           TEXT,
    dielectric_code       TEXT,
    dielectric_eia        TEXT,
    rated_voltage_code    TEXT,
    rated_voltage_v       REAL,
    capacitance_code      TEXT,
    capacitance_pf        REAL,
    tolerance_code        TEXT,
    thickness_code        TEXT,
    design_code           TEXT,
    product_control_code  TEXT,
    control_code          TEXT,
    packaging_code        TEXT,
    source_json           TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_products_family ON products(family_id);
CREATE INDEX IF NOT EXISTS idx_products_dielectric ON products(dielectric_eia);
CREATE INDEX IF NOT EXISTS idx_products_voltage ON products(rated_voltage_v);
CREATE INDEX IF NOT EXISTS idx_products_size_inch ON products(size_inch);

CREATE TABLE IF NOT EXISTS specs (
    spec_id      TEXT PRIMARY KEY,
    product_id   TEXT NOT NULL,
    key          TEXT NOT NULL,
    value_text   TEXT NOT NULL,
    value_num    REAL,
    unit         TEXT,
    notes        TEXT,
    source_json  TEXT NOT NULL,
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

CREATE INDEX IF NOT EXISTS idx_specs_product ON specs(product_id);
CREATE INDEX IF NOT EXISTS idx_specs_key ON specs(key);

CREATE TABLE IF NOT EXISTS exceptions (
    exception_id  TEXT PRIMARY KEY,
    scope_kind    TEXT NOT NULL,
    scope_id      TEXT NOT NULL,
    summary       TEXT NOT NULL,
    severity      TEXT NOT NULL,
    source_json   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_exceptions_scope ON exceptions(scope_kind, scope_id);

CREATE TABLE IF NOT EXISTS test_conditions (
    test_id          TEXT PRIMARY KEY,
    scope_kind       TEXT NOT NULL,
    scope_id         TEXT NOT NULL,
    test_name        TEXT NOT NULL,
    temperature_c    REAL,
    humidity_pct_rh  REAL,
    voltage_factor_vr REAL,
    duration_h       REAL,
    cycles           INTEGER,
    board_flex_mm    REAL,
    raw_text         TEXT NOT NULL,
    source_json      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tests_scope ON test_conditions(scope_kind, scope_id);
CREATE INDEX IF NOT EXISTS idx_tests_name ON test_conditions(test_name);
"""


@dataclass(frozen=True)
class FactStoreConfig:
    db_path: Path

    @classmethod
    def default(cls) -> "FactStoreConfig":
        return cls(db_path=Path("output/fact_store.sqlite"))


class FactStore:
    """SQLite-backed store. Use as a context manager to commit safely."""

    def __init__(self, cfg: FactStoreConfig) -> None:
        self.cfg = cfg
        self.cfg.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(cfg.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA_SQL)
        self._conn.commit()

    # --- lifecycle -------------------------------------------------------

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "FactStore":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type is None:
            self._conn.commit()
        else:
            self._conn.rollback()
        self.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        try:
            yield self._conn
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    # --- writers ---------------------------------------------------------

    def upsert_product(self, p: Product) -> None:
        self._conn.execute(
            """
            INSERT INTO products (
                product_id, part_number, family_id, size_code, size_inch,
                size_metric, dielectric_code, dielectric_eia,
                rated_voltage_code, rated_voltage_v, capacitance_code,
                capacitance_pf, tolerance_code, thickness_code, design_code,
                product_control_code, control_code, packaging_code, source_json
            ) VALUES (
                :product_id, :part_number, :family_id, :size_code, :size_inch,
                :size_metric, :dielectric_code, :dielectric_eia,
                :rated_voltage_code, :rated_voltage_v, :capacitance_code,
                :capacitance_pf, :tolerance_code, :thickness_code, :design_code,
                :product_control_code, :control_code, :packaging_code, :source_json
            )
            ON CONFLICT(product_id) DO UPDATE SET
                part_number          = COALESCE(excluded.part_number, products.part_number),
                family_id            = COALESCE(excluded.family_id, products.family_id),
                size_code            = COALESCE(excluded.size_code, products.size_code),
                size_inch            = COALESCE(excluded.size_inch, products.size_inch),
                size_metric          = COALESCE(excluded.size_metric, products.size_metric),
                dielectric_code      = COALESCE(excluded.dielectric_code, products.dielectric_code),
                dielectric_eia       = COALESCE(excluded.dielectric_eia, products.dielectric_eia),
                rated_voltage_code   = COALESCE(excluded.rated_voltage_code, products.rated_voltage_code),
                rated_voltage_v      = COALESCE(excluded.rated_voltage_v, products.rated_voltage_v),
                capacitance_code     = COALESCE(excluded.capacitance_code, products.capacitance_code),
                capacitance_pf       = COALESCE(excluded.capacitance_pf, products.capacitance_pf),
                tolerance_code       = COALESCE(excluded.tolerance_code, products.tolerance_code),
                thickness_code       = COALESCE(excluded.thickness_code, products.thickness_code),
                design_code          = COALESCE(excluded.design_code, products.design_code),
                product_control_code = COALESCE(excluded.product_control_code, products.product_control_code),
                control_code         = COALESCE(excluded.control_code, products.control_code),
                packaging_code       = COALESCE(excluded.packaging_code, products.packaging_code)
            ;
            """,
            {**p.model_dump(exclude={"source"}), "source_json": _src(p.source)},
        )

    def upsert_spec(self, s: Spec) -> None:
        self._conn.execute(
            """
            INSERT OR REPLACE INTO specs
            (spec_id, product_id, key, value_text, value_num, unit, notes, source_json)
            VALUES (:spec_id, :product_id, :key, :value_text, :value_num, :unit, :notes, :source_json);
            """,
            {**s.model_dump(exclude={"source"}), "source_json": _src(s.source)},
        )

    def upsert_exception(self, e: Exception_) -> None:
        self._conn.execute(
            """
            INSERT OR REPLACE INTO exceptions
            (exception_id, scope_kind, scope_id, summary, severity, source_json)
            VALUES (:exception_id, :scope_kind, :scope_id, :summary, :severity, :source_json);
            """,
            {**e.model_dump(exclude={"source"}), "source_json": _src(e.source)},
        )

    def upsert_test_condition(self, t: TestCondition) -> None:
        self._conn.execute(
            """
            INSERT OR REPLACE INTO test_conditions
            (test_id, scope_kind, scope_id, test_name, temperature_c,
             humidity_pct_rh, voltage_factor_vr, duration_h, cycles,
             board_flex_mm, raw_text, source_json)
            VALUES (:test_id, :scope_kind, :scope_id, :test_name, :temperature_c,
                    :humidity_pct_rh, :voltage_factor_vr, :duration_h, :cycles,
                    :board_flex_mm, :raw_text, :source_json);
            """,
            {**t.model_dump(exclude={"source"}), "source_json": _src(t.source)},
        )

    # --- readers ---------------------------------------------------------

    def query(self, sql: str, params: tuple = ()) -> list[dict]:
        cur = self._conn.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]

    def count(self, table: str) -> int:
        cur = self._conn.execute(f"SELECT COUNT(*) AS c FROM {table}")
        return int(cur.fetchone()[0])


def _src(s: Source) -> str:
    return json.dumps(s.model_dump(), ensure_ascii=False)
