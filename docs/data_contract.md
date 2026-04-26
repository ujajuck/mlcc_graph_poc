# MLCC fact-store data contract

This document is the source of truth for how raw markdown becomes canonical
facts. Every change to `pipeline/common/preprocess.py`,
`extract_product_scope.py`, or the Pydantic models in `schema/` must update
this contract first.

The contract covers:

1. ID rules (product, family, spec, exception, test_condition)
2. Column / unit normalization
3. Aliases
4. Source / provenance
5. Schema version

---

## 1. ID rules

### 1.1 `product_id`

- If the row has a Samsung MLCC part number (regex `^CL\d{2,3}[A-Z0-9]{6,}$`)
  in any cell, `product_id` = the part number, uppercased, with a trailing
  `#` stripped.
- Otherwise: `product_id = "{family_id}::{sha1(family|dielectric|size|voltage)[:12]}"`.
- IDs are stable across runs: the same row always produces the same ID.

### 1.2 `family_id`

Lower-snake-case. Allowed values are pinned in
`pipeline/common/extract_product_scope.py::_FAMILY_HINTS`:

| family_id              | display_name                  |
|------------------------|-------------------------------|
| `standard`             | Normal Capacitors – Standard  |
| `high_level_1`         | High Level I                  |
| `high_level_2`         | High Level II                 |
| `aec_q200`             | AEC-Q200                      |
| `mfc`                  | Molded Frame Capacitor        |
| `lsc`                  | Low-Profile / LSC             |
| `low_esl`              | Low ESL                       |
| `low_acoustic_noise`   | Low Acoustic Noise            |
| `high_bending`         | High Bending Strength         |

### 1.3 `spec_id`, `exception_id`, `test_id`

All deterministic hashes:

- `spec_id      = sha1("{product_id}|{key}|{value_text}")[:16]`
- `exception_id = sha1("{scope_kind}|{scope_id}|{summary}")[:16]`
- `test_id      = sha1("{scope_kind}|{scope_id}|{test_name}|{raw_text}")[:16]`

Re-ingesting the same row therefore upserts in place — never duplicates.

---

## 2. Column / unit normalization

Applied in `pipeline/common/normalize.py` before any value reaches the
fact store.

| Field family    | Stored as           | Notes                                      |
|-----------------|---------------------|--------------------------------------------|
| Voltage         | `float V`           | "4Vdc", "4.0V", "4V" all → `4.0`           |
| Length (board)  | `float mm`          | µm cells normalized via `um → mm` first    |
| Capacitance     | `float pF`          | code → pF via the part-number rule, also accepts uF (×1e6), nF (×1e3) |
| Temperature     | `float °C`          | always Celsius                             |
| Humidity        | `float %RH`         | percent, never fraction                    |
| Duration        | `float hours`       | "500h" → 500.0                             |
| Cycles          | `int`               |                                            |
| Voltage factor  | `float (× Vr)`      | "1Vr" → 1.0, "1.5Vr" → 1.5                 |

If a value is genuinely range-typed ("1.0~1.5Vr"), store the maximum in the
numeric column and the original text in `value_text` / `raw_text`.

---

## 3. Aliases

The canonicalization table lives in `pipeline/common/normalize.py::ENTITY_ALIASES`.
Adding an alias is a contract change — bump the schema version below.

Current canonical entities:

- Dielectric: `X7R`, `X5R`, `C0G` (incl. `NP0`, code letters)
- Size: `0603`, `0402`
- Family/level: `High Level I`, `High Level II`

---

## 4. Source / provenance

Every row in `products`, `specs`, `exceptions`, `test_conditions` carries a
`source_json` blob (Pydantic `Source`):

```json
{
  "source_doc": "mlcc_catalog_rag_master_ko.md",
  "section_path": "4. Reliability level 핵심 비교 > High Level II",
  "table_id": "table_03",
  "row_id": "row_07",
  "source_page": null,
  "line_start": 213,
  "line_end": 220
}
```

`table_id` and `row_id` are 1-indexed counters within a (doc, section).
They never reset between sections of the same doc.

Rule: if source can't be reconstructed for a fact, the fact is not written.
We prefer fewer high-confidence facts to many provenance-less ones.

---

## 5. Schema version

Current: **v1.0**.

Bump rules:

- Patch (v1.0 → v1.1): adding optional columns or aliases.
- Minor (v1.x → v1.y): adding new tables.
- Major (v1 → v2): renaming/removing columns, changing ID derivation.

The version string lives in `schema/__init__.py` as `SCHEMA_VERSION`
(add this when v2 lands; until then, this doc is the source).

---

## 6. Known follow-ups (not yet contract-covered)

- The current `data/raw/mlcc_catalog_rag_master_ko.md` expresses tabular
  data as bullet lists, not GFM pipe tables. The preprocessor's table
  extractor only reads pipe tables, so the fact store starts empty until a
  bullet-list-to-row extractor lands. Tracked separately; the schema
  itself is unaffected.
- `Spec.value_num` is currently best-effort (uses `_maybe_float`). The
  full unit-aware parser (V/mm/h/cycles → numeric column) lives in
  `pipeline/common/normalize.py` and will be wired into the loader before
  the first golden-query auto-pass.

---

## 7. What does NOT belong here

- Free-text descriptions, comparisons, and reasoning. Those stay in the
  cleaned markdown fed to LightRAG.
- LLM-generated relationships from Graphify. Those go to AGE workspace
  `mlcc_graphify_to_lightrag`, never the canonical fact store.
- "Approximate" facts derived by the LLM. If preprocessing can't extract a
  value deterministically, it stays unstructured.
