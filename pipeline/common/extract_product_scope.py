"""Determine which Product / Family a fact belongs to.

The preprocessor sees rows in tables under headings. A heading like
"4. Reliability level 핵심 비교 > High Level II" implies family_id =
'high_level_2', and every row inside that section inherits that scope unless
the row itself names a different family.

For codebook tables ("Size code map", "Dielectric code map", ...) there is
no per-row product — the row IS a code definition. We tag those with
scope_kind='codebook' and rely on the spec key naming to distinguish them.

For new-product tables every row has a part number column whose value is the
product_id directly.

The mapping rules below are intentionally explicit and small. Adding
specificity is preferable to letting an LLM guess.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Iterable

from schema import Product, Source


_FAMILY_HINTS: tuple[tuple[str, str, str], ...] = (
    # (substring in heading or row, family_id, display_name)
    ("standard", "standard", "Normal Capacitors - Standard"),
    ("high level i", "high_level_1", "High Level I"),
    ("high level 1", "high_level_1", "High Level I"),
    ("high level ii", "high_level_2", "High Level II"),
    ("high level 2", "high_level_2", "High Level II"),
    ("aec-q200", "aec_q200", "AEC-Q200"),
    ("mfc", "mfc", "Molded Frame Capacitor"),
    ("lsc", "lsc", "Low-Profile / LSC"),
    ("low esl", "low_esl", "Low ESL"),
    ("low acoustic noise", "low_acoustic_noise", "Low Acoustic Noise"),
    ("high bending", "high_bending", "High Bending Strength"),
    ("soft termination", "high_bending", "High Bending Strength"),
)


_PART_NUMBER_RE = re.compile(r"^CL\d{2,3}[A-Z0-9]{6,}$")


@dataclass(frozen=True)
class Scope:
    """Outcome of scoping a single table row."""

    kind: str  # 'product' | 'codebook' | 'family' | 'global'
    product_id: str | None
    family_id: str | None
    section_path: str


def detect_family(*texts: str) -> str | None:
    blob = " ".join(t.lower() for t in texts if t)
    for needle, family_id, _ in _FAMILY_HINTS:
        if needle in blob:
            return family_id
    return None


def looks_like_part_number(s: str) -> bool:
    if not s:
        return False
    s = s.strip().rstrip("#").upper()
    return bool(_PART_NUMBER_RE.match(s))


def _stable_id(*parts: str) -> str:
    h = hashlib.sha1("||".join(parts).encode("utf-8")).hexdigest()
    return h[:12]


def derive_product_id(
    *,
    part_number: str | None,
    family_id: str | None,
    dielectric: str | None,
    size: str | None,
    voltage: str | None,
) -> str:
    """Stable product_id without a part number.

    Falls back to a hash of the discriminating fields, prefixed with the
    family so different families never collide.
    """
    if part_number:
        return part_number.strip().rstrip("#").upper()
    return f"{family_id or 'unknown'}::{_stable_id(family_id or '', dielectric or '', size or '', voltage or '')}"


def section_path_from(headings: Iterable[str]) -> str:
    return " > ".join(h for h in headings if h)


def is_codebook_section(heading: str) -> bool:
    h = heading.lower()
    return any(
        kw in h
        for kw in (
            "size code",
            "dielectric code",
            "voltage code",
            "tolerance code",
            "design code",
            "packaging code",
            "thickness code",
            "control code",
            "capacitance code",
        )
    )


def scope_for_row(
    *,
    headings: list[str],
    headers: list[str],
    row: dict[str, str],
    source: Source,
) -> tuple[Scope, Product | None]:
    """Classify a row and (optionally) emit a Product.

    Returns (Scope, Product or None). ``Product`` is None for codebook rows.
    """
    section_path = section_path_from(headings)
    nearest = headings[-1] if headings else ""

    if is_codebook_section(nearest):
        return Scope("codebook", None, None, section_path), None

    family_from_heading = detect_family(*headings)

    pn_candidates = [v for v in row.values() if looks_like_part_number(str(v))]
    part_number = pn_candidates[0].strip().rstrip("#").upper() if pn_candidates else None

    dielectric = _first_present(row, ("dielectric", "code", "TC", "온도특성", "Class"))
    size = _first_present(row, ("size", "size code", "size_inch", "Size"))
    voltage = _first_present(row, ("voltage", "rated voltage", "Vr", "정격전압"))

    family_from_row = detect_family(*row.values())
    family_id = family_from_row or family_from_heading

    if part_number is None and not family_id:
        return Scope("global", None, None, section_path), None

    product_id = derive_product_id(
        part_number=part_number,
        family_id=family_id,
        dielectric=dielectric,
        size=size,
        voltage=voltage,
    )

    product = Product(
        product_id=product_id,
        part_number=part_number,
        family_id=family_id,
        size_code=None,
        size_inch=None,
        size_metric=None,
        dielectric_code=None,
        dielectric_eia=dielectric,
        rated_voltage_code=None,
        rated_voltage_v=_voltage_to_float(voltage),
        capacitance_code=None,
        capacitance_pf=None,
        tolerance_code=None,
        thickness_code=None,
        design_code=None,
        product_control_code=None,
        control_code=None,
        packaging_code=None,
        source=source,
    )
    kind = "product" if part_number else ("family" if family_id else "global")
    return Scope(kind, product_id, family_id, section_path), product


def _first_present(row: dict[str, str], candidates: tuple[str, ...]) -> str | None:
    norm = {k.lower(): v for k, v in row.items()}
    for c in candidates:
        v = norm.get(c.lower())
        if v:
            return str(v)
    return None


_VOLT_NUM_RE = re.compile(r"(?P<n>\d+(?:\.\d+)?)\s*[Vv]")


def _voltage_to_float(s: str | None) -> float | None:
    if not s:
        return None
    m = _VOLT_NUM_RE.search(s)
    if not m:
        return None
    return float(m.group("n"))
