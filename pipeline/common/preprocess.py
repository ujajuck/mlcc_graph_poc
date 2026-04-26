"""Shared Markdown preprocessor.

Rules (from claude.md and docs/data_contract.md):
  - Markdown tables MUST be parsed by code, never handed to an LLM as raw text.
  - Both pipelines use the exact same preprocessing output.
  - Tables are flattened into row-oriented sentences so downstream extractors
    see structured, unit-normalized facts instead of ascii-art pipes.
  - Every fact carries a Source (source_doc, section_path, table_id, row_id,
    line_start, line_end). Without provenance, the fact is dropped.

The output for a given input file `foo.md` is:

    data/processed/foo.md              - cleaned markdown (tables replaced)
    data/processed/foo.tables.json     - structured table payload (with IDs)
    data/processed/foo.facts.txt       - one deterministic sentence per row,
                                         used as the *LLM-facing* replacement
                                         for the raw table
    data/processed/foo.facts.jsonl     - same facts, but with Source metadata
                                         per row (consumed by fact_store loader)
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from markdown_it import MarkdownIt
from mdit_py_plugins.front_matter import front_matter_plugin

from pipeline.common.normalize import normalize_cell


_md = MarkdownIt("commonmark", {"html": False}).enable("table").use(front_matter_plugin)


@dataclass
class ParsedTable:
    table_id: str
    heading: str
    section_path: list[str]
    headers: list[str]
    rows: list[dict[str, str]]
    row_ids: list[str]
    start_line: int
    end_line: int

    def to_dict(self) -> dict:
        return {
            "table_id": self.table_id,
            "heading": self.heading,
            "section_path": self.section_path,
            "headers": self.headers,
            "rows": self.rows,
            "row_ids": self.row_ids,
            "start_line": self.start_line,
            "end_line": self.end_line,
        }


@dataclass
class FactRecord:
    """Single sentence with full provenance (one per table row)."""

    sentence: str
    source_doc: str
    section_path: str
    table_id: str
    row_id: str
    line_start: int
    line_end: int

    def to_dict(self) -> dict:
        return {
            "sentence": self.sentence,
            "source": {
                "source_doc": self.source_doc,
                "section_path": self.section_path,
                "table_id": self.table_id,
                "row_id": self.row_id,
                "line_start": self.line_start,
                "line_end": self.line_end,
            },
        }


@dataclass
class PreprocessResult:
    source_path: Path
    cleaned_markdown: str
    tables: list[ParsedTable] = field(default_factory=list)
    facts: list[FactRecord] = field(default_factory=list)


# ---------------------------------------------------------------------------
# tokenize
# ---------------------------------------------------------------------------


def _iter_tables_with_path(
    md_text: str,
) -> list[tuple[int, int, list[str], list[list[str]], list[str]]]:
    """Return per-table tuples carrying the full heading path.

    (start_line, end_line, headers, rows, section_path)
    """
    tokens = _md.parse(md_text)
    out: list[tuple[int, int, list[str], list[list[str]], list[str]]] = []
    heading_stack: list[tuple[int, str]] = []  # (level, text)

    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.type == "heading_open":
            level = int(tok.tag[1:])  # 'h2' -> 2
            inline = tokens[i + 1]
            text = inline.content.strip() if inline.type == "inline" else ""
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, text))
            i += 3
            continue

        if tok.type == "table_open":
            start_line = tok.map[0] if tok.map else -1
            headers: list[str] = []
            rows: list[list[str]] = []
            in_head = False
            in_body = False
            current_row: list[str] = []
            j = i + 1
            while j < len(tokens) and tokens[j].type != "table_close":
                t = tokens[j]
                if t.type == "thead_open":
                    in_head = True
                elif t.type == "thead_close":
                    in_head = False
                elif t.type == "tbody_open":
                    in_body = True
                elif t.type == "tbody_close":
                    in_body = False
                elif t.type == "tr_open":
                    current_row = []
                elif t.type == "tr_close":
                    if in_head:
                        headers = current_row
                    elif in_body:
                        rows.append(current_row)
                elif t.type == "inline":
                    current_row.append(t.content.strip())
                j += 1
            end_line = tokens[j].map[1] if tokens[j].map else -1
            section_path = [t for _, t in heading_stack]
            out.append((start_line, end_line, headers, rows, section_path))
            i = j + 1
            continue

        i += 1
    return out


# ---------------------------------------------------------------------------
# emit
# ---------------------------------------------------------------------------


def _row_to_sentence(section_path: list[str], headers: list[str], row: list[str]) -> str:
    safe_headers = [h if h else f"col{i}" for i, h in enumerate(headers)]
    pairs: list[str] = []
    for h, v in zip(safe_headers, row):
        if v == "" or v is None:
            continue
        pairs.append(f'{h}="{normalize_cell(v)}"')
    scope = " > ".join(section_path) if section_path else "table"
    return f"{scope}: " + ", ".join(pairs) + "."


def _rows_as_objects(headers: list[str], rows: list[list[str]]) -> list[dict[str, str]]:
    safe_headers = [h if h else f"col{i}" for i, h in enumerate(headers)]
    out = []
    for r in rows:
        padded = list(r) + [""] * max(0, len(safe_headers) - len(r))
        out.append({h: normalize_cell(v) for h, v in zip(safe_headers, padded)})
    return out


_TABLE_LINE_RE = re.compile(r"^\s*\|.*\|\s*$")
_TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$")


def _strip_raw_tables(md_text: str) -> str:
    out_lines: list[str] = []
    lines = md_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if _TABLE_LINE_RE.match(line) and i + 1 < len(lines) and _TABLE_SEP_RE.match(lines[i + 1]):
            out_lines.append("<!-- table removed by preprocessor; see .facts.txt / .facts.jsonl -->")
            i += 2
            while i < len(lines) and _TABLE_LINE_RE.match(lines[i]):
                i += 1
            continue
        out_lines.append(line)
        i += 1
    return "\n".join(out_lines)


def preprocess_markdown(path: Path) -> PreprocessResult:
    md_text = path.read_text(encoding="utf-8")
    raw_tables = _iter_tables_with_path(md_text)

    parsed: list[ParsedTable] = []
    facts: list[FactRecord] = []
    source_doc = path.name

    for t_idx, (start, end, headers, rows, section_path) in enumerate(raw_tables, start=1):
        table_id = f"table_{t_idx:03d}"
        row_objs = _rows_as_objects(headers, rows)
        row_ids = [f"row_{r_idx:03d}" for r_idx, _ in enumerate(rows, start=1)]
        heading = section_path[-1] if section_path else ""
        parsed.append(
            ParsedTable(
                table_id=table_id,
                heading=heading,
                section_path=section_path,
                headers=headers,
                rows=row_objs,
                row_ids=row_ids,
                start_line=start,
                end_line=end,
            )
        )
        for row, row_id in zip(rows, row_ids):
            sentence = _row_to_sentence(section_path, headers, row)
            facts.append(
                FactRecord(
                    sentence=sentence,
                    source_doc=source_doc,
                    section_path=" > ".join(section_path),
                    table_id=table_id,
                    row_id=row_id,
                    line_start=start,
                    line_end=end,
                )
            )

    cleaned = _strip_raw_tables(md_text)

    return PreprocessResult(
        source_path=path,
        cleaned_markdown=cleaned,
        tables=parsed,
        facts=facts,
    )


def write_result(result: PreprocessResult, out_dir: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = result.source_path.stem

    md_out = out_dir / f"{stem}.md"
    tables_out = out_dir / f"{stem}.tables.json"
    facts_out = out_dir / f"{stem}.facts.txt"
    facts_jsonl_out = out_dir / f"{stem}.facts.jsonl"

    sentences = [f.sentence for f in result.facts]
    combined = result.cleaned_markdown.rstrip() + "\n\n## Structured facts\n\n"
    combined += "\n".join(sentences) + "\n"

    md_out.write_text(combined, encoding="utf-8")
    tables_out.write_text(
        json.dumps([t.to_dict() for t in result.tables], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    facts_out.write_text("\n".join(sentences) + "\n", encoding="utf-8")
    facts_jsonl_out.write_text(
        "\n".join(json.dumps(f.to_dict(), ensure_ascii=False) for f in result.facts) + "\n",
        encoding="utf-8",
    )

    return {
        "markdown": md_out,
        "tables": tables_out,
        "facts": facts_out,
        "facts_jsonl": facts_jsonl_out,
    }
