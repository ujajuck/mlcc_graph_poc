"""Deterministic unit and string normalization.

claude.md rule: numeric/unit comparisons must NOT be delegated to the LLM.
All unit conversions live here, so both pipelines see the same normalized
values. Claude.md lists concrete rules in section 4 of the RAG guide:

    - length:   um -> mm
    - voltage:  "4V" / "4.0V" / "4Vdc"  ->  "4.0Vdc"
    - capacitance symbols: uF / μF / ㎌  ->  "uF"
"""
from __future__ import annotations

import re
from dataclasses import dataclass


_MICRO_FORMS = ["μF", "㎌", "uF", "uf"]
_VOLTAGE_RE = re.compile(r"(?P<n>\d+(?:\.\d+)?)\s*[Vv](?:dc|DC)?")
_LENGTH_UM_RE = re.compile(r"(?P<n>\d+(?:\.\d+)?)\s*(?:um|µm|μm)")
_CAP_MICRO_RE = re.compile(r"(?P<n>\d+(?:\.\d+)?)\s*(?:μF|㎌|uF)")
_GB_TB_RE = re.compile(r"(?P<n>\d+(?:\.\d+)?)\s*(?P<u>TB|GB|MB|KB)", re.IGNORECASE)


def normalize_voltage(s: str) -> str:
    def repl(m: re.Match[str]) -> str:
        n = float(m.group("n"))
        return f"{n:.1f}Vdc"
    return _VOLTAGE_RE.sub(repl, s)


def normalize_length_um_to_mm(s: str) -> str:
    def repl(m: re.Match[str]) -> str:
        n = float(m.group("n"))
        return f"{n / 1000:.3f} mm"
    return _LENGTH_UM_RE.sub(repl, s)


def normalize_capacitance_micro(s: str) -> str:
    def repl(m: re.Match[str]) -> str:
        return f"{m.group('n')}uF"
    return _CAP_MICRO_RE.sub(repl, s)


def normalize_storage_to_gb(s: str) -> str:
    """VRAM/RAM/storage -> GB, matching the claude.md example."""
    def repl(m: re.Match[str]) -> str:
        n = float(m.group("n"))
        u = m.group("u").upper()
        gb = {"TB": n * 1024, "GB": n, "MB": n / 1024, "KB": n / (1024 * 1024)}[u]
        return f"{gb:g}GB"
    return _GB_TB_RE.sub(repl, s)


def normalize_cell(s: str) -> str:
    """Full cell-level normalization chain - applied to every table cell."""
    if s is None:
        return ""
    s = s.strip()
    s = s.replace(" ", " ")
    s = normalize_length_um_to_mm(s)
    s = normalize_capacitance_micro(s)
    s = normalize_voltage(s)
    s = normalize_storage_to_gb(s)
    return s


@dataclass(frozen=True)
class EntityAlias:
    canonical: str
    aliases: tuple[str, ...]


# Minimal MLCC-aware alias table. Used by the Graphify -> LightRAG bridge to
# collapse entity duplicates ("X7R", "B (X7R)", "code B") before building the
# custom_kg payload.
ENTITY_ALIASES: tuple[EntityAlias, ...] = (
    EntityAlias("X7R", ("X7R", "code B", "B (X7R)", "dielectric B")),
    EntityAlias("X5R", ("X5R", "code A", "A (X5R)", "dielectric A")),
    EntityAlias("C0G", ("C0G", "NP0", "code C", "C (C0G)", "dielectric C")),
    EntityAlias("0603", ("0603", "1608", "0603 (1608)", "size 03")),
    EntityAlias("0402", ("0402", "1005", "size 05", "0402 (1005)")),
    EntityAlias("High Level I", ("High Level I", "HL1", "high-level-1")),
    EntityAlias("High Level II", ("High Level II", "HL2", "high-level-2")),
)


def canonicalize_entity(name: str) -> str:
    key = name.strip().lower()
    for alias in ENTITY_ALIASES:
        for a in alias.aliases:
            if a.lower() == key:
                return alias.canonical
    return name.strip()
