"""Pydantic models for canonical MLCC facts.

The whole point of these models is to make the fact_store deterministic.
Every row that the preprocessor extracts becomes one Spec / Exception /
TestCondition tied to a Product, and every record carries its Source so we
can audit where a value came from. RAG/LLM may explain or rephrase — it
must not be the source of truth for these fields.

Field naming follows docs/data_contract.md.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)


class Source(_Strict):
    """Where a fact came from. Required on every fact."""

    source_doc: str = Field(description="basename of the source markdown")
    section_path: str = Field(description="hierarchical heading path, '>' separated")
    table_id: Optional[str] = Field(default=None, description="stable id within doc, e.g. table_03")
    row_id: Optional[str] = Field(default=None, description="stable id within table, e.g. row_07")
    source_page: Optional[str] = Field(default=None, description="PDF page or md heading anchor")
    line_start: Optional[int] = None
    line_end: Optional[int] = None


class TemperatureCharacteristic(_Strict):
    """Class II / Class I dielectric code mapping."""

    code: str = Field(description="single-letter code, e.g. 'B'")
    eia_name: str = Field(description="EIA designation, e.g. 'X7R'")
    dielectric_class: str = Field(description="'I' or 'II'")
    temp_min_c: int
    temp_max_c: int
    cap_change_pct: Optional[str] = Field(
        default=None,
        description="e.g. '±15%' or '-33 ~ +22%'. Free text because formats vary.",
    )


class ProductFamily(_Strict):
    """Big-picture lineup classification (Standard, High Level I/II, MFC, LSC, ...).

    Used by the dispatch/skill logic and by query routing.
    """

    family_id: str = Field(description="stable lower-snake id, e.g. 'high_level_2'")
    display_name: str
    application_guide: str = ""
    aliases: list[str] = Field(default_factory=list)


class Product(_Strict):
    """A single MLCC SKU or part-number stub.

    `product_id` is the canonical identity. For new-product tables we use the
    full part number; for codebook rows there is no PN, so we fall back to a
    deterministic string derived from (family, dielectric, size, voltage).
    """

    product_id: str
    part_number: Optional[str] = None
    family_id: Optional[str] = None
    size_code: Optional[str] = Field(default=None, description="e.g. '10' for 0603/1608")
    size_inch: Optional[str] = Field(default=None, description="e.g. '0603'")
    size_metric: Optional[str] = Field(default=None, description="e.g. '1608'")
    dielectric_code: Optional[str] = None
    dielectric_eia: Optional[str] = None
    rated_voltage_code: Optional[str] = None
    rated_voltage_v: Optional[float] = None
    capacitance_code: Optional[str] = None
    capacitance_pf: Optional[float] = None
    tolerance_code: Optional[str] = None
    thickness_code: Optional[str] = None
    design_code: Optional[str] = None
    product_control_code: Optional[str] = None
    control_code: Optional[str] = None
    packaging_code: Optional[str] = None
    source: Source


class Spec(_Strict):
    """Single (key, value) pair on a Product.

    Examples:
      key='operating_temp_max_c', value='125', unit='degC'
      key='dc_bias_change_pct',   value='-50', unit='%'
      key='board_flex_mm',        value='2',   unit='mm'
    """

    spec_id: str
    product_id: str
    key: str
    value_text: str = Field(description="post-normalize string form")
    value_num: Optional[float] = None
    unit: Optional[str] = None
    notes: Optional[str] = None
    source: Source


class Exception_(_Strict):
    """Documented exception / caveat tied to a product or family.

    ``Exception`` clashes with the builtin so we name the class
    ``Exception_`` and re-export it under ``Exception_`` only.
    """

    exception_id: str
    scope_kind: str = Field(description="'product' | 'family' | 'global'")
    scope_id: str = Field(description="product_id or family_id, or 'global'")
    summary: str
    severity: str = Field(default="info", description="info|warn|block")
    source: Source


class TestCondition(_Strict):
    """A reliability / mounting / storage condition entry.

    Distinct from Spec because tests have multi-axis params (temperature,
    humidity, voltage, duration, cycles) and we want them queryable as a unit.
    """

    test_id: str
    scope_kind: str = Field(description="'product' | 'family' | 'global'")
    scope_id: str
    test_name: str = Field(description="e.g. 'humidity', 'temperature_cycling'")
    temperature_c: Optional[float] = None
    humidity_pct_rh: Optional[float] = None
    voltage_factor_vr: Optional[float] = Field(
        default=None, description="multiple of rated voltage, e.g. 1.0 = 1Vr"
    )
    duration_h: Optional[float] = None
    cycles: Optional[int] = None
    board_flex_mm: Optional[float] = None
    raw_text: str = Field(description="original phrasing for traceability")
    source: Source
