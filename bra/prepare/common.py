"""Shared helpers for reproducible preparation of normalized datasets."""

from __future__ import annotations

import csv
import hashlib
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..csv_io import Table, read_csv
from ..models import Severity
from ..parsing import (
    clean,
    format_number,
    format_timestamp,
    is_blank,
    is_not_applicable,
    normalise_header,
    parse_date,
    parse_number,
    parse_timestamp,
)


class PreparationError(RuntimeError):
    """Raised when a source cannot be prepared without guessing."""


@dataclass
class TransformResult:
    """One normalized output plus its transformation audit metadata."""

    name: str
    filename: str
    headers: tuple[str, ...]
    rows: list[dict[str, str]]
    sources: list[Path]
    column_map: dict[str, str] = field(default_factory=dict)
    rules: list[str] = field(default_factory=list)
    input_records: int = 0
    counts: Counter[str] = field(default_factory=Counter)
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def output_records(self) -> int:
        return len(self.rows)


def load_csv(path: Path) -> Table:
    """Read a source CSV and refuse to build derived data from broken structure."""

    table = read_csv(path)
    errors = [issue for issue in table.issues if issue.severity is Severity.ERROR]
    if errors:
        codes = ", ".join(sorted({issue.code for issue in errors}))
        raise PreparationError(f"Cannot prepare {path}: {codes}")
    return table


def source_header(table: Table, normalized: str) -> str:
    """Return the original header text for a normalized column name."""

    for raw in table.raw_headers:
        if normalise_header(raw) == normalized:
            return raw
    return normalized


def build_column_map(table: Table, mapping: dict[str, str]) -> dict[str, str]:
    """Map derived column names to the original source header text."""

    return {derived: source_header(table, source) for derived, source in mapping.items()}


def clean_text(
    row: dict[str, str],
    field: str,
    raw: str | None,
    result: TransformResult,
    *,
    identifier: bool = False,
) -> str:
    """Trim a text field and record the harmless transformation."""

    value = clean(raw)
    if raw is not None and raw != value:
        result.counts[f"trimmed_{field}"] += 1
        if identifier:
            add_flag(row, "identifier_whitespace_trimmed")
    return value


def date_text(
    row: dict[str, str],
    field: str,
    raw: str | None,
    result: TransformResult,
) -> str:
    """Return an ISO date, or blank plus a review flag when parsing fails."""

    if is_blank(raw) or is_not_applicable(raw):
        return ""
    parsed = parse_date(raw)
    if parsed is None:
        add_flag(row, "invalid_date")
        result.counts[f"invalid_date_{field}"] += 1
        return ""
    value = parsed.isoformat()
    if value != clean(raw):
        result.counts[f"dates_normalized_{field}"] += 1
    return value


def timestamp_text(
    row: dict[str, str],
    field: str,
    raw: str | None,
    result: TransformResult,
) -> str:
    """Return an ISO timestamp, or blank plus a review flag when parsing fails."""

    if is_blank(raw) or is_not_applicable(raw):
        return ""
    parsed = parse_timestamp(raw)
    if parsed is None:
        add_flag(row, "invalid_timestamp")
        result.counts[f"invalid_timestamp_{field}"] += 1
        return ""
    value = format_timestamp(parsed) or ""
    if value != clean(raw):
        result.counts[f"timestamps_normalized_{field}"] += 1
    return value


def number_text(
    row: dict[str, str],
    field: str,
    raw: str | None,
    result: TransformResult,
) -> str:
    """Return a canonical numeric string, or blank when the source is invalid."""

    if is_blank(raw) or is_not_applicable(raw):
        return ""
    parsed = parse_number(raw)
    if parsed is None:
        add_flag(row, "invalid_number")
        result.counts[f"invalid_number_{field}"] += 1
        return ""
    value = format_number(parsed)
    if value != clean(raw):
        result.counts[f"numbers_normalized_{field}"] += 1
    return value


def excel_date_text(
    row: dict[str, str],
    field: str,
    raw: str | None,
    result: TransformResult,
) -> str:
    """Convert an Excel serial or ordinary date to ISO, flagging failures."""

    from ..parsing import parse_excel_serial

    if is_blank(raw) or is_not_applicable(raw):
        return ""
    parsed = parse_excel_serial(raw)
    if parsed is None:
        parsed = parse_date(raw)
    if parsed is None:
        add_flag(row, "invalid_date")
        result.counts[f"invalid_date_{field}"] += 1
        return ""
    value = parsed.isoformat()
    if value != clean(raw):
        result.counts[f"dates_normalized_{field}"] += 1
    return value


def add_flag(row: dict[str, str], flag: str) -> None:
    """Add a review flag without duplicating it."""

    flags = [value for value in row.get("review_flags", "").split("|") if value]
    if flag not in flags:
        flags.append(flag)
    row["review_flags"] = "|".join(flags)


def add_flags(row: dict[str, str], flags: Iterable[str]) -> None:
    for flag in flags:
        add_flag(row, flag)


def split_flags(value: str) -> list[str]:
    return [flag for flag in value.split("|") if flag]


def write_csv_atomic(
    path: Path,
    headers: tuple[str, ...],
    rows: list[dict[str, str]],
) -> None:
    """Write a deterministic CSV through a temporary file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(headers)
            for row in rows:
                writer.writerow([row.get(column, "") for column in headers])
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def input_hashes(paths: Iterable[Path]) -> dict[str, str]:
    return {path.as_posix(): sha256_file(path) for path in sorted(paths)}
