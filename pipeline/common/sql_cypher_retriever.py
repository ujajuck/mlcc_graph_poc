"""Deterministic retrieval over the canonical fact store.

Pipeline C contract:
    1. query_router.route(question) -> RoutedQuery
    2. SqlRetriever.find_products(routed.conditions) -> list[product rows]
    3. SqlRetriever.find_test_conditions(routed.conditions) -> list[test rows]
    4. (optional) cypher_neighbors() to fetch graph context for each product
    5. LightRAG explains the resulting structured payload

We expose two retrievers:
    - SqlRetriever:   facts.sqlite via FactStore
    - CypherRetriever: AGE workspace via AgeClient (read-only)

Numeric comparisons are resolved here, not by an LLM. That is the whole
point: '4.5V 이상' = WHERE rated_voltage_v >= 4.5, period.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from pipeline.common.fact_store import FactStore
from pipeline.common.query_router import Condition


_NUMERIC_FIELDS = {
    "rated_voltage_v",
    "board_flex_mm",
    "temperature_c",
    "humidity_pct_rh",
    "duration_h",
    "cycles",
    "capacitance_pf",
}

_PRODUCT_FIELDS = {
    "rated_voltage_v",
    "dielectric_eia",
    "family",
    "size",
}

_TEST_FIELDS = {
    "temperature_c",
    "humidity_pct_rh",
    "duration_h",
    "cycles",
    "board_flex_mm",
    "voltage_factor_vr",
}


@dataclass
class StructuredHit:
    kind: str  # 'product' | 'test_condition' | 'exception'
    payload: dict[str, Any]


class SqlRetriever:
    """Read side of FactStore. No writes."""

    def __init__(self, store: FactStore) -> None:
        self.store = store

    def find_products(self, conditions: Iterable[Condition]) -> list[StructuredHit]:
        where, params = _compile_where("products", conditions)
        sql = "SELECT * FROM products"
        if where:
            sql += f" WHERE {where}"
        sql += " ORDER BY product_id LIMIT 200;"
        return [StructuredHit("product", row) for row in self.store.query(sql, tuple(params))]

    def find_test_conditions(self, conditions: Iterable[Condition]) -> list[StructuredHit]:
        where, params = _compile_where("test_conditions", conditions)
        sql = "SELECT * FROM test_conditions"
        if where:
            sql += f" WHERE {where}"
        sql += " ORDER BY scope_id, test_name LIMIT 200;"
        return [StructuredHit("test_condition", row) for row in self.store.query(sql, tuple(params))]

    def find_exceptions(self, scope_ids: Iterable[str]) -> list[StructuredHit]:
        ids = list(scope_ids)
        if not ids:
            return []
        placeholders = ",".join("?" * len(ids))
        sql = f"SELECT * FROM exceptions WHERE scope_id IN ({placeholders}) ORDER BY severity DESC;"
        return [StructuredHit("exception", row) for row in self.store.query(sql, tuple(ids))]


class CypherRetriever:
    """Optional graph context for the products SQL has already filtered.

    Imports asyncpg lazily so the SQL-only path doesn't require it.
    """

    def __init__(self, workspace: str) -> None:
        from pipeline.common.age_client import AgeClient, AgeConnectionConfig

        self.cfg = AgeConnectionConfig.from_env(graph_name=workspace)
        self.client = AgeClient(self.cfg)

    async def neighbors(self, product_id: str, limit: int = 10) -> list[Any]:
        cypher = (
            f"MATCH (n {{entity_id:'{_escape(product_id)}'}})-[r]-(m) "
            "RETURN n, r, m"
        )
        return await self.client.run_cypher(
            f"{cypher} LIMIT {int(limit)}",
            return_cols="n agtype, r agtype, m agtype",
        )


# ---------------------------------------------------------------------------
# WHERE compiler
# ---------------------------------------------------------------------------


def _compile_where(table: str, conditions: Iterable[Condition]) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []

    for c in conditions:
        if table == "products" and c.field not in _PRODUCT_FIELDS:
            continue
        if table == "test_conditions" and c.field not in _TEST_FIELDS:
            continue

        col, val = _resolve_column(table, c)
        if col is None:
            continue

        if c.op in {">=", "<=", ">", "<", "="}:
            clauses.append(f"{col} {c.op} ?")
            params.append(val)
        elif c.op == "between":
            # 'between' arrives only with a single bound from router, treat as >=
            clauses.append(f"{col} >= ?")
            params.append(val)
        else:
            clauses.append(f"{col} = ?")
            params.append(val)

    return " AND ".join(clauses), params


def _resolve_column(table: str, c: Condition) -> tuple[str | None, Any]:
    """Map router's logical field onto the actual column name."""
    if c.field == "size":
        # 'size' may be inch (0603) or metric (1608); search both via OR is
        # awkward in a flat compiler, so we try inch first.
        s = str(c.value)
        if s in {"0201", "0402", "0603", "0805", "1206", "1210", "1808", "1812", "2220"}:
            return "size_inch", s
        return "size_metric", s
    if c.field == "family":
        # Router emits human-readable family text; we convert to family_id below.
        return "family_id", _family_text_to_id(str(c.value))
    if c.field == "dielectric_eia":
        return "dielectric_eia", str(c.value).upper()
    if c.field in _NUMERIC_FIELDS:
        return c.field, float(c.value)
    return None, None


def _family_text_to_id(s: str) -> str:
    s = s.lower()
    table = {
        "high level i": "high_level_1",
        "high level 1": "high_level_1",
        "high level ii": "high_level_2",
        "high level 2": "high_level_2",
        "aec-q200": "aec_q200",
        "mfc": "mfc",
        "lsc": "lsc",
        "low esl": "low_esl",
        "low acoustic noise": "low_acoustic_noise",
        "high bending": "high_bending",
        "soft termination": "high_bending",
        "standard": "standard",
    }
    return table.get(s, s.replace(" ", "_"))


def _escape(s: str) -> str:
    return s.replace("'", "''")
