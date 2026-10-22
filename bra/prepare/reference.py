"""Preparation of normalized listing, change-history, and delisting datasets."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from ..derived_schema import DERIVED_HEADERS
from ..parsing import clean, parse_date, parse_excel_serial
from ..xlsx_io import Sheet, read_xlsx
from .common import (
    TransformResult,
    add_flag,
    build_column_map,
    clean_text,
    date_text,
    excel_date_text,
    load_csv,
    number_text,
    split_flags,
)

ISIN_PATTERN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")
NAME_CHANGE_COLUMNS = (
    "SYMBOL",
    "OLD NAME OF THE COMPANY",
    "NEW NAME OF THE COMPANY",
    "EFFECTIVE DATE",
)


def _relative(path: Path, data_root: Path) -> str:
    try:
        return path.relative_to(data_root).as_posix()
    except ValueError:
        return path.name


def prepare_current_listings(
    data_root: Path,
    delisting_rows: list[dict[str, str]] | None = None,
) -> TransformResult:
    """Normalize the current listing snapshot without treating it as history."""

    path = data_root / "reference/listing_history/EQUITY_L.csv"
    table = load_csv(path)
    result = TransformResult(
        name="current_listings",
        filename="current_listings.csv",
        headers=DERIVED_HEADERS["derived_current_listings"],
        rows=[],
        sources=[path],
        column_map=build_column_map(
            table,
            {
                "symbol": "SYMBOL",
                "company_name": "NAME OF COMPANY",
                "series": "SERIES",
                "listing_date": "DATE OF LISTING",
                "paid_up_value": "PAID UP VALUE",
                "market_lot": "MARKET LOT",
                "isin": "ISIN NUMBER",
                "face_value": "FACE VALUE",
            },
        ),
        rules=[
            "Read the current EQUITY_L.csv listing snapshot.",
            "This file is a current snapshot, not a historical constituent universe.",
            "Trim identifiers and normalize listing dates to ISO 8601.",
            "Preserve ISIN values verbatim after trimming; flag malformed values.",
            "Flag identifiers that also occur in the delisting history.",
            "Keep every source row; no listing records are removed.",
        ],
    )

    delisting_symbols = {row["symbol"] for row in delisting_rows or [] if row["symbol"]}
    delisting_isins = {row["isin"] for row in delisting_rows or [] if row["isin"]}
    delistings_by_symbol: dict[str, list[dict[str, str]]] = defaultdict(list)
    delistings_by_isin: dict[str, list[dict[str, str]]] = defaultdict(list)
    for delisting in delisting_rows or []:
        if delisting.get("symbol"):
            delistings_by_symbol[delisting["symbol"]].append(delisting)
        if delisting.get("isin"):
            delistings_by_isin[delisting["isin"]].append(delisting)
    cross_hits: list[dict[str, Any]] = []
    source_file = _relative(path, data_root)

    for source_row in table.rows:
        row = {"review_flags": ""}
        row["symbol"] = clean_text(
            row, "symbol", source_row.get("SYMBOL"), result, identifier=True
        )
        row["company_name"] = clean_text(
            row, "company_name", source_row.get("NAME OF COMPANY"), result
        )
        row["series"] = clean_text(
            row, "series", source_row.get("SERIES"), result, identifier=True
        )
        row["listing_date"] = date_text(
            row, "listing_date", source_row.get("DATE OF LISTING"), result
        )
        row["paid_up_value"] = number_text(
            row, "paid_up_value", source_row.get("PAID UP VALUE"), result
        )
        row["market_lot"] = number_text(
            row, "market_lot", source_row.get("MARKET LOT"), result
        )
        row["isin"] = clean_text(
            row, "isin", source_row.get("ISIN NUMBER"), result, identifier=True
        )
        row["face_value"] = number_text(
            row, "face_value", source_row.get("FACE VALUE"), result
        )
        if not row["symbol"]:
            add_flag(row, "missing_symbol")
        if not row["company_name"]:
            add_flag(row, "missing_company_name")
        if not row["isin"]:
            add_flag(row, "missing_isin")
        elif not ISIN_PATTERN.fullmatch(row["isin"]):
            add_flag(row, "malformed_isin")
        if (
            row["symbol"] in delisting_symbols
            or row["isin"] in delisting_isins
        ):
            add_flag(row, "relisted_or_reused_identifier")
            matches: list[dict[str, str]] = []
            seen: set[tuple[str, str, str]] = set()
            for delisting in (
                delistings_by_symbol.get(row["symbol"], [])
                + delistings_by_isin.get(row["isin"], [])
            ):
                key = (
                    delisting.get("symbol", ""),
                    delisting.get("isin", ""),
                    delisting.get("delisted_date", ""),
                )
                if key in seen:
                    continue
                seen.add(key)
                matches.append(
                    {
                        "symbol": delisting.get("symbol", ""),
                        "isin": delisting.get("isin", ""),
                        "delisted_date": delisting.get("delisted_date", ""),
                        "board": delisting.get("board", ""),
                    }
                )
            cross_hits.append(
                {
                    "symbol": row["symbol"],
                    "isin": row["isin"],
                    "listing_date": row["listing_date"],
                    "matched_delistings": matches,
                }
            )
        row["source_file"] = source_file
        row["source_line"] = str(source_row.number)
        result.rows.append(row)
        result.input_records += 1

    result.details["delisting_cross_references"] = cross_hits
    return result


def prepare_name_changes(data_root: Path) -> TransformResult:
    """Normalize name changes and collapse only exact duplicate records."""

    path = data_root / "reference/listing_history/namechange.csv"
    table = load_csv(path)
    result = TransformResult(
        name="name_changes",
        filename="name_changes.csv",
        headers=DERIVED_HEADERS["derived_name_changes"],
        rows=[],
        sources=[path],
        column_map=build_column_map(
            table,
            {
                "symbol": "SYMBOL",
                "old_name": "OLD NAME OF THE COMPANY",
                "new_name": "NEW NAME OF THE COMPANY",
                "effective_date": "EFFECTIVE DATE",
            },
        ),
        rules=[
            "Read the complete name-change history.",
            "Trim surrounding whitespace and normalize effective dates to ISO 8601.",
            "Collapse only groups whose four normalized fields are identical.",
            "Record every collapsed source line in source_lines and its count.",
            "Retain conflicting spellings and shared events across symbols; flag them.",
            "Never choose a 'correct' company-name spelling.",
        ],
    )
    source_file = _relative(path, data_root)
    records: list[tuple[dict[str, str], tuple[str, ...]]] = []

    for source_row in table.rows:
        row = {"review_flags": ""}
        row["symbol"] = clean_text(
            row, "symbol", source_row.get("SYMBOL"), result, identifier=True
        )
        row["old_name"] = clean_text(
            row, "old_name", source_row.get("OLD NAME OF THE COMPANY"), result
        )
        row["new_name"] = clean_text(
            row, "new_name", source_row.get("NEW NAME OF THE COMPANY"), result
        )
        row["effective_date"] = date_text(
            row, "effective_date", source_row.get("EFFECTIVE DATE"), result
        )
        if not row["symbol"]:
            add_flag(row, "missing_symbol")
        row["source_file"] = source_file
        row["source_line"] = str(source_row.number)
        raw_signature = tuple(source_row.get(column) or "" for column in NAME_CHANGE_COLUMNS)
        records.append((row, raw_signature))
        result.input_records += 1

    by_symbol_date: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    by_shared_event: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(
        list
    )
    for row, _ in records:
        by_symbol_date[(row["symbol"], row["effective_date"])].append(row)
        by_shared_event[
            (
                row["old_name"].casefold(),
                row["new_name"].casefold(),
                row["effective_date"],
            )
        ].append(row)

    overlapping_groups: list[dict[str, Any]] = []
    for (symbol, effective_date), rows in sorted(by_symbol_date.items()):
        variants = {
            (row["old_name"].casefold(), row["new_name"].casefold()) for row in rows
        }
        if len(variants) > 1:
            for row in rows:
                add_flag(row, "overlapping_variant")
            overlapping_groups.append(
                {
                    "symbol": symbol,
                    "effective_date": effective_date,
                    "records": [
                        {
                            "source_line": row["source_line"],
                            "old_name": row["old_name"],
                            "new_name": row["new_name"],
                        }
                        for row in rows
                    ],
                    "decision": "retain_all_conflicting_variants",
                }
            )

    shared_event_groups: list[dict[str, Any]] = []
    for key, rows in sorted(by_shared_event.items()):
        symbols = {row["symbol"] for row in rows if row["symbol"]}
        if len(symbols) > 1:
            for row in rows:
                add_flag(row, "shared_event_across_symbols")
            shared_event_groups.append(
                {
                    "old_name": key[0],
                    "new_name": key[1],
                    "effective_date": key[2],
                    "symbols": sorted(symbols),
                    "decision": "retain_shared_event_records",
                }
            )

    grouped: dict[tuple[str, str, str, str], list[tuple[dict[str, str], tuple[str, ...]]]] = defaultdict(list)
    for record in records:
        row, _ = record
        key = (
            row["symbol"],
            row["old_name"],
            row["new_name"],
            row["effective_date"],
        )
        grouped[key].append(record)

    duplicate_groups: list[dict[str, Any]] = []
    for key, group in grouped.items():
        rows = [row for row, _ in group]
        representative = dict(rows[0])
        source_lines = [row["source_line"] for row in rows]
        representative["source_record_count"] = str(len(rows))
        representative["source_lines"] = ";".join(source_lines)
        representative["source_line"] = source_lines[0]
        representative["review_status"] = (
            "collapsed_exact_duplicates" if len(rows) > 1 else "unique"
        )
        flags = sorted({flag for row in rows for flag in split_flags(row["review_flags"])})
        representative["review_flags"] = "|".join(flags)

        if len(rows) > 1:
            raw_exact = len({signature for _, signature in group}) == 1
            duplicate_groups.append(
                {
                    "key": {
                        "symbol": key[0],
                        "old_name": key[1],
                        "new_name": key[2],
                        "effective_date": key[3],
                    },
                    "source_record_count": len(rows),
                    "source_lines": [int(line) for line in source_lines],
                    "raw_exact_across_all_columns": raw_exact,
                    "decision": "collapse_exact_duplicate_copies",
                }
            )
        result.rows.append(representative)

    result.details.update(
        {
            "duplicate_groups": duplicate_groups,
            "exact_duplicate_group_count": len(duplicate_groups),
            "exact_duplicate_extra_records": sum(
                group["source_record_count"] - 1 for group in duplicate_groups
            ),
            "overlapping_variant_groups": overlapping_groups,
            "shared_event_groups": shared_event_groups,
            "decisions": [
                "Exact copies are represented once in the event dataset.",
                "Every collapsed source line is recorded in source_lines.",
                "Overlapping spellings are retained and flagged, not resolved.",
                "Same-event records under different symbols are retained and flagged.",
            ],
        }
    )
    result.counts["collapsed_duplicate_groups"] = len(duplicate_groups)
    result.counts["collapsed_duplicate_records"] = sum(
        group["source_record_count"] - 1 for group in duplicate_groups
    )
    return result


def prepare_symbol_changes(data_root: Path) -> TransformResult:
    """Normalize symbol changes and flag ambiguous change relationships."""

    path = data_root / "reference/listing_history/symbolchange.csv"
    table = load_csv(path)
    result = TransformResult(
        name="symbol_changes",
        filename="symbol_changes.csv",
        headers=DERIVED_HEADERS["derived_symbol_changes"],
        rows=[],
        sources=[path],
        column_map=build_column_map(
            table,
            {
                "company_name": "NAME OF THE COMPANY",
                "old_symbol": "OLD SYMBOL",
                "new_symbol": "NEW SYMBOL",
                "effective_date": "EFFECTIVE DATE",
            },
        ),
        rules=[
            "Read the complete symbol-change history.",
            "Trim identifiers and normalize effective dates to ISO 8601.",
            "Keep every source row; no symbol-change records are removed.",
            "Flag no-op changes, shared new symbols, and repeated company/date records.",
            "Do not infer a canonical symbol or assume a symbol is permanent.",
        ],
    )
    source_file = _relative(path, data_root)

    for source_row in table.rows:
        row = {"review_flags": ""}
        row["company_name"] = clean_text(
            row, "company_name", source_row.get("NAME OF THE COMPANY"), result
        )
        row["old_symbol"] = clean_text(
            row, "old_symbol", source_row.get("OLD SYMBOL"), result, identifier=True
        )
        row["new_symbol"] = clean_text(
            row, "new_symbol", source_row.get("NEW SYMBOL"), result, identifier=True
        )
        row["effective_date"] = date_text(
            row, "effective_date", source_row.get("EFFECTIVE DATE"), result
        )
        if not row["old_symbol"]:
            add_flag(row, "missing_symbol")
        if not row["company_name"]:
            add_flag(row, "missing_company_name")
        if row["old_symbol"] and row["old_symbol"] == row["new_symbol"]:
            add_flag(row, "noop_symbol_change")
        row["source_file"] = source_file
        row["source_line"] = str(source_row.number)
        result.rows.append(row)
        result.input_records += 1

    by_company_date: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    old_by_new: dict[str, set[str]] = defaultdict(set)
    for row in result.rows:
        by_company_date[(row["company_name"], row["effective_date"])].append(row)
        if row["new_symbol"]:
            old_by_new[row["new_symbol"]].add(row["old_symbol"])

    repeated_company_date = []
    for (company, effective_date), rows in sorted(by_company_date.items()):
        if len(rows) > 1:
            for row in rows:
                add_flag(row, "same_company_date_multiple_records")
            repeated_company_date.append(
                {
                    "company_name": company,
                    "effective_date": effective_date,
                    "source_lines": [row["source_line"] for row in rows],
                }
            )

    shared_new_symbols = {
        symbol: sorted(values)
        for symbol, values in old_by_new.items()
        if len({value for value in values if value}) > 1
    }
    for row in result.rows:
        if row["new_symbol"] in shared_new_symbols:
            add_flag(row, "shared_new_symbol")

    result.details.update(
        {
            "repeated_company_date_groups": repeated_company_date,
            "shared_new_symbols": shared_new_symbols,
            "noop_changes": sum(
                1
                for row in result.rows
                if "noop_symbol_change" in split_flags(row["review_flags"])
            ),
            "decision": (
                "All source rows are retained; ambiguous relationships are "
                "flagged for review rather than resolved."
            ),
        }
    )
    return result


def _sheet_records(sheet: Sheet) -> tuple[list[str], list[tuple[int, dict[str, str]]]]:
    if not sheet.rows:
        return [], []
    headers = [clean(value) for value in sheet.rows[0]]
    records: list[tuple[int, dict[str, str]]] = []
    for row_number, values in enumerate(sheet.rows[1:], start=2):
        padded = list(values) + [""] * (len(headers) - len(values))
        records.append((row_number, dict(zip(headers, padded))))
    return headers, records


def _sheet_date(value: str | None):
    serial = parse_excel_serial(value)
    if serial is not None:
        return serial
    return parse_date(value)


def prepare_delistings(data_root: Path) -> TransformResult:
    """Normalize the workbook's primary full-history delisting sheet."""

    path = data_root / "reference/listing_history" / next(
        data_root.joinpath("reference/listing_history").glob(
            "Copy_of_List_of_delisted_Companies_*.xlsx"
        )
    ).name
    workbook = read_xlsx(path)
    primary = workbook.sheet("delisted")
    if primary is None:
        raise ValueError("The delisting workbook has no 'delisted' sheet.")

    result = TransformResult(
        name="delistings",
        filename="delistings.csv",
        headers=DERIVED_HEADERS["derived_delistings"],
        rows=[],
        sources=[path],
        rules=[
            "Read the workbook without modifying it.",
            "Use the primary 'delisted' sheet as the event list; do not merge auxiliary sheets.",
            "Convert Excel 1900-system serial dates to ISO 8601.",
            "Trim surrounding whitespace in identifiers and classifications.",
            "Preserve malformed identifiers and flag them; do not repair them.",
            "Flag dates that conflict with the auxiliary compulsory-delisting sheet.",
            "Record source_file, source_sheet, and the physical worksheet row.",
        ],
    )
    headers, records = _sheet_records(primary)
    result.column_map = {
        "symbol": "Symbol",
        "isin": "ISIN",
        "company_name": "Company Name",
        "board": "Board",
        "delisted_date": "Delisted Date",
        "delisting_type": "Type of Delisting",
    }
    source_file = _relative(path, data_root)

    for sheet_row, source in records:
        row = {"review_flags": ""}
        row["symbol"] = clean_text(
            row, "symbol", source.get("Symbol"), result, identifier=True
        )
        row["isin"] = clean_text(
            row, "isin", source.get("ISIN"), result, identifier=True
        )
        row["company_name"] = clean_text(
            row, "company_name", source.get("Company Name"), result
        )
        row["board"] = clean_text(row, "board", source.get("Board"), result)
        row["delisted_date"] = excel_date_text(
            row, "delisted_date", source.get("Delisted Date"), result
        )
        row["delisting_type"] = clean_text(
            row, "delisting_type", source.get("Type of Delisting"), result
        )
        if not row["symbol"]:
            add_flag(row, "missing_symbol")
        if not row["company_name"]:
            add_flag(row, "missing_company_name")
        if not row["isin"]:
            add_flag(row, "missing_isin")
        elif not ISIN_PATTERN.fullmatch(row["isin"]):
            add_flag(row, "malformed_isin")
        row["source_file"] = source_file
        row["source_sheet"] = primary.name
        row["source_row"] = str(sheet_row)
        result.rows.append(row)
        result.input_records += 1

    auxiliary = _audit_auxiliary_sheets(workbook, result)
    result.details.update(auxiliary)
    result.details["sheet_headers"] = headers
    result.details["workbook_properties"] = workbook.properties
    return result


def _audit_auxiliary_sheets(workbook, result: TransformResult) -> dict[str, Any]:
    """Compare auxiliary sheets with the primary list without merging them."""

    primary = result.rows
    by_symbol_date = {
        (row["symbol"], row["delisted_date"]): row for row in primary
    }
    by_symbol: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in primary:
        by_symbol[row["symbol"]].append(row)

    details: dict[str, Any] = {"auxiliary_sheets": []}
    for sheet_name in ("Add Data-Comp. Delisted", "Exit Provided"):
        sheet = workbook.sheet(sheet_name)
        if sheet is None:
            continue
        headers, records = _sheet_records(sheet)
        matching = 0
        conflicts: list[dict[str, Any]] = []
        additional: list[dict[str, Any]] = []
        note_rows = 0
        for sheet_row, source in records:
            symbol = clean(source.get("Symbol"))
            if not symbol or symbol.casefold().startswith("notes"):
                note_rows += 1
                continue
            delisted_date = _sheet_date(source.get("Delisted Date"))
            date_text_value = delisted_date.isoformat() if delisted_date else ""
            if not date_text_value:
                continue
            key = (symbol, date_text_value)
            primary_row = by_symbol_date.get(key)
            if primary_row is not None:
                matching += 1
                continue
            same_symbol = by_symbol.get(symbol)
            if same_symbol:
                conflicts.append(
                    {
                        "symbol": symbol,
                        "auxiliary_sheet": sheet_name,
                        "auxiliary_row": sheet_row,
                        "auxiliary_date": date_text_value,
                        "primary_dates": [
                            row["delisted_date"] for row in same_symbol
                        ],
                        "decision": "retain_primary_and_flag_conflict",
                    }
                )
                for row in same_symbol:
                    add_flag(row, "auxiliary_sheet_conflict")
            else:
                additional.append(
                    {
                        "symbol": symbol,
                        "auxiliary_sheet": sheet_name,
                        "auxiliary_row": sheet_row,
                        "delisted_date": date_text_value,
                        "decision": "not_merged_requires_review",
                    }
                )
        details["auxiliary_sheets"].append(
            {
                "sheet": sheet_name,
                "headers": headers,
                "data_rows": len(records),
                "note_rows": note_rows,
                "matching_symbol_date_rows": matching,
                "conflict_rows": conflicts,
                "additional_event_rows": additional,
                "decision": (
                    "Audited for overlap only; no auxiliary-sheet row is merged "
                    "into the primary event dataset."
                ),
            }
        )
        result.counts[f"auxiliary_{sheet_name}_matching_rows"] = matching
        result.counts[f"auxiliary_{sheet_name}_conflict_rows"] = len(conflicts)
        result.counts[f"auxiliary_{sheet_name}_additional_rows"] = len(additional)
    return details
