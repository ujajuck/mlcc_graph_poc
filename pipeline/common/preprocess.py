"""Shared Markdown preprocessor.

Rules (from claude.md):
  - Markdown tables MUST be parsed by code, never handed to an LLM as raw text.
  - Both pipelines use the exact same preprocessing output.
  - Tables are flattened into row-oriented sentences so downstream extractors
    see structured, unit-normalized facts instead of ascii-art pipes.

The output for a given input file `foo.md` is:

    data/processed/foo.md              - cleaned markdown (tables replaced)
    data/processed/foo.tables.json     - structured table payload
    data/processed/foo.facts.txt       - one deterministic sentence per row,
                                         used as the *LLM-facing* replacement
                                         for the raw table
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
    heading: str
    headers: list[str]
    rows: list[dict[str, str]]
    start_line: int
    end_line: int

    def to_dict(self) -> dict:
        return {
            "heading": self.heading,
            "headers": self.headers,
            "rows": self.rows,
            "start_line": self.start_line,
            "end_line": self.end_line,
        }


@dataclass
class PreprocessResult:
    source_path: Path
    cleaned_markdown: str
    tables: list[ParsedTable] = field(default_factory=list)
    facts: list[str] = field(default_factory=list)


def _iter_tables(md_text: str) -> list[tuple[int, int, list[str], list[list[str]], str]]:
    """Return (start_line, end_line, headers, rows, nearest_heading) per table."""
    tokens = _md.parse(md_text)
    tables: list[tuple[int, int, list[str], list[list[str]], str]] = []
    current_heading = ""

    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.type == "heading_open":
            inline = tokens[i + 1]
            current_heading = inline.content.strip() if inline.type == "inline" else ""
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
            tables.append((start_line, end_line, headers, rows, current_heading))
            i = j + 1
            continue

        i += 1

    return tables


def _row_to_fact(heading: str, headers: list[str], row: list[str]) -> str:
    """Convert one row into a deterministic fact sentence.

    Example:
        heading = "Rated voltage code"
        headers = ["code", "voltage"]
        row     = ["P", "10Vdc"]
      =>  'Rated voltage code: code="P", voltage="10Vdc".'
    """
    safe_headers = [h if h else f"col{i}" for i, h in enumerate(headers)]
    pairs = []
    for h, v in zip(safe_headers, row):
        if v == "" or v is None:
            continue
        pairs.append(f'{h}="{normalize_cell(v)}"')
    scope = heading or "table"
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
    """Remove raw pipe tables from markdown so LLM-facing copies never see them.

    We keep the preceding heading intact and replace the table block with a
    single marker line that the fact-emitter inserts structured facts after.
    """
    out_lines: list[str] = []
    lines = md_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if _TABLE_LINE_RE.match(line) and i + 1 < len(lines) and _TABLE_SEP_RE.match(lines[i + 1]):
            out_lines.append("<!-- table removed by preprocessor; see .facts.txt -->")
            i += 2
            while i < len(lines) and _TABLE_LINE_RE.match(lines[i]):
                i += 1
            continue
        out_lines.append(line)
        i += 1
    return "\n".join(out_lines)


def preprocess_markdown(path: Path) -> PreprocessResult:
    md_text = path.read_text(encoding="utf-8")
    raw_tables = _iter_tables(md_text)

    parsed: list[ParsedTable] = []
    facts: list[str] = []
    for start, end, headers, rows, heading in raw_tables:
        row_objs = _rows_as_objects(headers, rows)
        parsed.append(
            ParsedTable(
                heading=heading,
                headers=headers,
                rows=row_objs,
                start_line=start,
                end_line=end,
            )
        )
        for r in rows:
            facts.append(_row_to_fact(heading, headers, r))

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

    combined = result.cleaned_markdown.rstrip() + "\n\n## Structured facts\n\n"
    combined += "\n".join(result.facts) + "\n"

    md_out.write_text(combined, encoding="utf-8")
    tables_out.write_text(
        json.dumps([t.to_dict() for t in result.tables], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    facts_out.write_text("\n".join(result.facts) + "\n", encoding="utf-8")

    return {"markdown": md_out, "tables": tables_out, "facts": facts_out}
