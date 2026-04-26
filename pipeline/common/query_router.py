"""Classify a natural-language query into condition vs explanation.

Pipeline C ('rule first, RAG second') uses this. The split is deliberately
narrow:

  - 'condition' = the question can be answered by SQL/Cypher filters over
    structured facts (voltage >= 4.5V, size = 0603, dielectric = X7R, ...).
  - 'explanation' = the question wants a free-form description, comparison,
    or reasoning. RAG/LLM is appropriate.
  - 'mixed' = condition filter + explanation needed (most realistic
    workflow). Pipeline C answers structurally first, then asks LightRAG to
    explain the filtered set with grounded context.

Heuristic-only on purpose: this module must be auditable and stable across
runs. We never delegate the routing decision itself to an LLM.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal


Intent = Literal["condition", "explanation", "mixed"]


# A 'numeric condition' = number + unit + (>=, <=, =, range)
_NUM_COND_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*"
    r"(V|Vdc|VDC|mm|um|µm|μm|kHz|MHz|°C|degC|℃|%|h|hours?|cycles?|pF|nF|uF|μF|㎌)"
    r"\s*(이상|이하|초과|미만|보다|>=|<=|>|<|~|to)?",
    re.IGNORECASE,
)

_DIELECTRIC_TOKENS = (
    "X5R", "X6S", "X6T", "X7R", "X7S", "X7T", "X8L", "X8M", "Y5V",
    "C0G", "NP0", "JIS-B",
)
_SIZE_TOKENS = (
    "008004", "0201", "01005", "0402", "0603", "0805", "1005",
    "1206", "1210", "1608", "1808", "1812", "2012", "2220",
    "3216", "3225", "4520", "4532", "5750",
)
_FAMILY_TOKENS = (
    "high level i", "high level 1", "high level ii", "high level 2",
    "aec-q200", "mfc", "lsc", "low esl", "low acoustic noise",
    "high bending", "soft termination", "standard",
)

_EXPLAIN_HINTS = (
    "설명", "이유", "왜", "차이", "비교", "장점", "단점", "어떻게",
    "explain", "describe", "compare", "why", "how does", "advantage",
)
_LIST_HINTS = (
    "목록", "리스트", "알려줘", "찾아", "추천", "선정",
    "list", "show", "find", "select", "recommend",
)


@dataclass(frozen=True)
class Condition:
    field: str
    op: str
    value: str | float


@dataclass(frozen=True)
class RoutedQuery:
    raw: str
    intent: Intent
    conditions: list[Condition] = field(default_factory=list)
    needs_explanation: bool = False


def route(question: str) -> RoutedQuery:
    q = question.strip()
    q_low = q.lower()

    conds: list[Condition] = []

    # Numeric voltage conditions: '4.5V 이상', '>= 4.5V', '4.5Vdc 초과'
    for m in _NUM_COND_RE.finditer(q_low):
        n = float(m.group(1))
        unit = m.group(2).lower()
        comparator_word = (m.group(3) or "").strip()
        comparator = _norm_comparator(comparator_word)
        field_name = _field_for_unit(unit)
        if field_name is None:
            continue
        conds.append(Condition(field=field_name, op=comparator, value=n))

    # Dielectric / size / family token presence
    for tok in _DIELECTRIC_TOKENS:
        if tok.lower() in q_low:
            conds.append(Condition(field="dielectric_eia", op="=", value=tok))
    for tok in _SIZE_TOKENS:
        if tok in q:  # numeric tokens, case-insensitive doesn't matter
            conds.append(Condition(field="size", op="=", value=tok))
    for tok in _FAMILY_TOKENS:
        if tok in q_low:
            conds.append(Condition(field="family", op="=", value=tok))

    has_conditions = bool(conds)
    wants_explanation = any(h in q_low for h in _EXPLAIN_HINTS)
    wants_list = any(h in q_low for h in _LIST_HINTS)

    if has_conditions and wants_explanation:
        intent: Intent = "mixed"
    elif has_conditions and (wants_list or not wants_explanation):
        intent = "condition"
    else:
        intent = "explanation"

    return RoutedQuery(
        raw=question,
        intent=intent,
        conditions=conds,
        needs_explanation=wants_explanation or intent != "condition",
    )


def _norm_comparator(word: str) -> str:
    w = word.strip().lower()
    if w in {"이상", ">=", "보다"}:
        return ">="
    if w in {"이하", "<="}:
        return "<="
    if w in {"초과", ">"}:
        return ">"
    if w in {"미만", "<"}:
        return "<"
    if w in {"~", "to"}:
        return "between"
    return "="


def _field_for_unit(unit: str) -> str | None:
    u = unit.lower()
    if u in {"v", "vdc"}:
        return "rated_voltage_v"
    if u in {"mm"}:
        return "board_flex_mm"
    if u in {"°c", "degc", "℃"}:
        return "temperature_c"
    if u in {"%"}:
        return "humidity_pct_rh"
    if u in {"h", "hour", "hours"}:
        return "duration_h"
    if u in {"cycle", "cycles"}:
        return "cycles"
    if u in {"pf"}:
        return "capacitance_pf"
    if u in {"uf", "μf", "㎌"}:
        return "capacitance_uf"
    if u in {"nf"}:
        return "capacitance_nf"
    return None
