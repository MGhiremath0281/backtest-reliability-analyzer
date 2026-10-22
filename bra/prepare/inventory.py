"""Read-only inventory of every collected CSV and workbook sheet.

The inventory is intentionally descriptive. It does not decide whether a
dataset is good or bad; it records what is present, how complete it is, and
where a downstream audit should look. Raw and derived files are discovered
separately so their findings never get mixed together.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from ..csv_io import Table, read_csv
from ..parsing import (
    clean,
    is_blank,
    is_not_applicable,
    parse_date,
    parse_excel_serial,
    parse_timestamp,
)
from ..xlsx_io import XlsxError, read_xlsx
from .common import sha256_file

ISIN_COLUMN_HINTS = ("isin",)
SYMBOL_COLUMN_HINTS = ("symbol", "old symbol", "new symbol")
ENTITY_COLUMN_HINTS = ("symbol", "company name", "name of company", "name of the company")
DATE_COLUMN_HINTS = (
    "date",
    "period ended",
    "quarter end date",
    "period end date",
)
TIMESTAMP_COLUMN_HINTS = ("time", "datetime")


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _inventory_sort_key(path: Path, root: Path) -> tuple[str, str]:
    """Return a platform-independent key for inventory paths.

    ``Path`` ordering follows the host filesystem's case rules, so sorting
    ``Path`` objects directly produces different inventory order on Linux and
    Windows for names such as ``CF-FR.csv`` and ``additional.csv``. Sort by the
    relative POSIX path instead, case-insensitively with a raw-path tie-breaker.
    """

    relative = _relative(path, root)
    return (relative.casefold(), relative)


def _is_identifier_column(header: str) -> bool:
    lowered = header.casefold()
    return "symbol" in lowered or "isin" in lowered or lowered == "series"


def _is_date_column(header: str) -> bool:
    lowered = header.casefold()
    if _is_timestamp_column(header):
        return False
    return any(hint in lowered for hint in DATE_COLUMN_HINTS)


def _is_timestamp_column(header: str) -> bool:
    lowered = header.casefold()
    if lowered in {"time taken"}:
        return False
    return "time" in lowered or "datetime" in lowered


def _parse_date_value(value: str | None):
    if is_blank(value) or is_not_applicable(value):
        return None
    parsed = parse_date(value)
    if parsed is not None:
        return parsed
    return parse_excel_serial(value)


def _parse_timestamp_value(value: str | None):
    if is_blank(value) or is_not_applicable(value):
        return None
    parsed = parse_timestamp(value)
    if parsed is not None:
        return parsed
    return None


def _entity_column(headers: list[str]) -> str | None:
    for candidate in ENTITY_COLUMN_HINTS:
        for header in headers:
            if header.casefold() == candidate:
                return header
    return None


def _record_profile(
    headers: list[str],
    rows: list[dict[str, str]],
) -> dict[str, Any]:
    """Summarise completeness, identifiers, duplicates, and date coverage."""

    profile: dict[str, Any] = {
        "row_count": len(rows),
        "blank_rows": sum(
            1 for row in rows if all(is_blank(row.get(header)) for header in headers)
        ),
    }

    exact_counts = Counter(
        tuple(clean(row.get(header)) for header in headers) for row in rows
    )
    duplicate_groups = {key: count for key, count in exact_counts.items() if count > 1}
    profile["exact_duplicate_groups"] = len(duplicate_groups)
    profile["exact_duplicate_extra_records"] = sum(
        count - 1 for count in duplicate_groups.values()
    )

    identifiers: dict[str, Any] = {}
    for header in headers:
        if not _is_identifier_column(header):
            continue
        values = [clean(row.get(header)) for row in rows]
        non_blank = [value for value in values if value]
        details: dict[str, Any] = {
            "missing": len(values) - len(non_blank),
            "distinct": len(set(non_blank)),
            "whitespace_padded": sum(
                1
                for row in rows
                if row.get(header) and row.get(header) != clean(row.get(header))
            ),
        }
        if "isin" in header.casefold():
            details["malformed"] = sum(
                1
                for value in non_blank
                if not (
                    len(value) == 12
                    and value[:2].isalpha()
                    and value[2:11].isalnum()
                    and value[-1].isdigit()
                )
            )
        identifiers[header] = details
    profile["identifiers"] = identifiers

    date_columns: dict[str, Any] = {}
    for header in headers:
        if not _is_date_column(header):
            continue
        parsed_values = []
        invalid = 0
        blank = 0
        for row in rows:
            raw = row.get(header)
            if is_blank(raw) or is_not_applicable(raw):
                blank += 1
                continue
            parsed = _parse_date_value(raw)
            if parsed is None:
                invalid += 1
            else:
                parsed_values.append(parsed)
        dates = sorted(parsed_values)
        date_columns[header] = {
            "blank": blank,
            "invalid": invalid,
            "start": dates[0].isoformat() if dates else None,
            "end": dates[-1].isoformat() if dates else None,
            "per_year": dict(
                sorted(Counter(value.year for value in parsed_values).items())
            ),
        }
    profile["date_columns"] = date_columns

    timestamp_columns: dict[str, Any] = {}
    for header in headers:
        if not _is_timestamp_column(header):
            continue
        parsed_times = []
        invalid = 0
        blank = 0
        for row in rows:
            raw = row.get(header)
            if is_blank(raw) or is_not_applicable(raw):
                blank += 1
                continue
            parsed = _parse_timestamp_value(raw)
            if parsed is None:
                invalid += 1
            else:
                parsed_times.append(parsed)
        timestamps = sorted(parsed_times)
        timestamp_columns[header] = {
            "blank": blank,
            "invalid": invalid,
            "start": timestamps[0].isoformat(sep=" ") if timestamps else None,
            "end": timestamps[-1].isoformat(sep=" ") if timestamps else None,
        }
    profile["timestamp_columns"] = timestamp_columns

    entity_column = _entity_column(headers)
    if entity_column:
        counts = Counter(
            clean(row.get(entity_column))
            for row in rows
            if clean(row.get(entity_column))
        )
        profile["entity"] = {
            "column": entity_column,
            "distinct": len(counts),
            "counts": dict(sorted(counts.items())),
        }
    else:
        profile["entity"] = None

    return profile


def _csv_issues(table: Table) -> list[dict[str, Any]]:
    return [
        {
            "code": issue.code,
            "severity": issue.severity.value,
            "row": issue.row,
            "message": issue.message,
        }
        for issue in table.issues
    ]


def inventory_csv(path: Path, root: Path) -> dict[str, Any]:
    """Inventory one CSV file without modifying it."""

    table = read_csv(path)
    rows = [{header: row.get(header) for header in table.headers} for row in table.rows]
    return {
        "path": _relative(path, root),
        "format": "csv",
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "readable": table.readable,
        "headers_ok": table.headers_ok,
        "headers": table.headers,
        "raw_headers": table.raw_headers,
        "data_records_seen": table.data_records_seen,
        **_record_profile(table.headers, rows),
        "issues": _csv_issues(table),
    }


def _xlsx_rows(sheet_rows: list[list[str]]) -> tuple[list[str], list[dict[str, str]]]:
    if not sheet_rows:
        return [], []
    headers = [clean(value) for value in sheet_rows[0]]
    records: list[dict[str, str]] = []
    for values in sheet_rows[1:]:
        padded = list(values) + [""] * (len(headers) - len(values))
        records.append(dict(zip(headers, padded)))
    return headers, records


def inventory_workbook(path: Path, root: Path) -> dict[str, Any]:
    """Inventory every sheet in one XLSX workbook."""

    try:
        workbook = read_xlsx(path)
    except XlsxError as exc:
        return {
            "path": _relative(path, root),
            "format": "xlsx",
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
            "readable": False,
            "error": str(exc),
            "sheets": [],
        }

    sheets: list[dict[str, Any]] = []
    for sheet in workbook.sheets:
        headers, records = _xlsx_rows(sheet.rows)
        sheets.append(
            {
                "name": sheet.name,
                "headers": headers,
                "physical_row_count": len(sheet.rows),
                **_record_profile(headers, records),
            }
        )

    return {
        "path": _relative(path, root),
        "format": "xlsx",
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "readable": True,
        "properties": workbook.properties,
        "sheet_count": len(sheets),
        "sheets": sheets,
    }


def _is_within(path: Path, directories: Iterable[Path]) -> bool:
    for directory in directories:
        try:
            path.relative_to(directory)
            return True
        except ValueError:
            continue
    return False


def build_inventory(
    root: Path,
    *,
    exclude_directories: Iterable[Path] = (),
) -> dict[str, Any]:
    """Inventory every CSV/XLSX file under ``root`` in stable order."""

    excluded = [path.resolve() for path in exclude_directories]
    files: list[dict[str, Any]] = []
    for path in sorted(
        root.rglob("*"),
        key=lambda item: _inventory_sort_key(item, root),
    ):
        if not path.is_file() or _is_within(path.resolve(), excluded):
            continue
        suffix = path.suffix.casefold()
        if suffix == ".csv":
            files.append(inventory_csv(path, root))
        elif suffix == ".xlsx":
            files.append(inventory_workbook(path, root))

    return {
        "root": str(root),
        "file_count": len(files),
        "formats": dict(
            sorted(Counter(item["format"] for item in files).items())
        ),
        "files": files,
    }
