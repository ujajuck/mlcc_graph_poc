"""Thin async wrapper around Apache AGE for ad-hoc Cypher from our pipelines.

LightRAG's PGGraphStorage owns ingest and query during retrieval. We only use
this client for:
  - verifying that the AGE extension is loaded and the target graph exists
  - sanity-check Cypher queries (node counts, degree distribution) for the
    comparison report
  - optional manual inspection during experiments

Every session must `SET search_path = ag_catalog, "$user", public;` and
`LOAD 'age';` before issuing Cypher, which mirrors what PGGraphStorage does
internally.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator

import asyncpg


@dataclass(frozen=True)
class AgeConnectionConfig:
    host: str
    port: int
    user: str
    password: str
    database: str
    graph_name: str

    @classmethod
    def from_env(cls, graph_name: str | None = None) -> "AgeConnectionConfig":
        return cls(
            host=os.environ.get("POSTGRES_HOST", "localhost"),
            port=int(os.environ.get("POSTGRES_PORT", "5432")),
            user=os.environ.get("POSTGRES_USER", "lightrag"),
            password=os.environ.get("POSTGRES_PASSWORD", "lightrag"),
            database=os.environ.get("POSTGRES_DATABASE", "lightrag_db"),
            graph_name=graph_name
            or os.environ.get("POSTGRES_WORKSPACE")
            or "mlcc_graph",
        )


class AgeClient:
    def __init__(self, cfg: AgeConnectionConfig) -> None:
        self.cfg = cfg

    @asynccontextmanager
    async def connection(self) -> AsyncIterator[asyncpg.Connection]:
        conn = await asyncpg.connect(
            host=self.cfg.host,
            port=self.cfg.port,
            user=self.cfg.user,
            password=self.cfg.password,
            database=self.cfg.database,
        )
        try:
            await conn.execute("LOAD 'age';")
            await conn.execute('SET search_path = ag_catalog, "$user", public;')
            yield conn
        finally:
            await conn.close()

    async def ensure_graph(self) -> None:
        async with self.connection() as conn:
            exists = await conn.fetchval(
                "SELECT 1 FROM ag_catalog.ag_graph WHERE name = $1",
                self.cfg.graph_name,
            )
            if not exists:
                await conn.execute(f"SELECT create_graph('{self.cfg.graph_name}');")

    async def run_cypher(self, cypher: str, return_cols: str = "v agtype") -> list[Any]:
        """Run a raw Cypher statement and return rows.

        `return_cols` describes the AGE column list, e.g. ``"v agtype"`` or
        ``"n agtype, m agtype"``. AGE requires the caller to declare the shape
        of the Cypher RETURN clause at the SQL level.
        """
        sql = (
            "SELECT * FROM cypher($1, $$\n"
            f"{cypher}\n"
            f"$$) AS ({return_cols});"
        )
        async with self.connection() as conn:
            return await conn.fetch(sql, self.cfg.graph_name)

    async def node_count(self) -> int:
        rows = await self.run_cypher(
            "MATCH (n) RETURN count(n)", return_cols="c agtype"
        )
        if not rows:
            return 0
        # agtype comes back as a string like "123"; strip potential quotes.
        return int(str(rows[0]["c"]).strip('"'))

    async def edge_count(self) -> int:
        rows = await self.run_cypher(
            "MATCH ()-[r]->() RETURN count(r)", return_cols="c agtype"
        )
        if not rows:
            return 0
        return int(str(rows[0]["c"]).strip('"'))
