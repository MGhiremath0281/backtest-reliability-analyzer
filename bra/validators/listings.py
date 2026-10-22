"""Validation for listing references, name/symbol changes, and delistings."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import date
from typing import Any

from ..csv_io import Row, Table
from ..models import DatasetResult
from ..parsing import clean, format_date, is_blank, parse_date, parse_number
from .common import (
    add_duplicate_issues,
    check_schema,
    count_values,
    date_coverage,
)

ISIN_PATTERN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")

CURRENT_LISTING_COLUMNS = [
    "SYMBOL",
    "NAME OF COMPANY",
    "SERIES",
    "DATE OF LISTING",
    "PAID UP VALUE",
    "MARKET LOT",
    "ISIN NUMBER",
    "FACE VALUE",
]
CURRENT_LISTING_REQUIRED = [
    "SYMBOL",
    "NAME OF COMPANY",
    "SERIES",
    "DATE OF LISTING",
    "ISIN NUMBER",
]

NAME_CHANGE_COLUMNS = [
    "SYMBOL",
    "OLD NAME OF THE COMPANY",
    "NEW NAME OF THE COMPANY",
    "EFFECTIVE DATE",
]
NAME_CHANGE_REQUIRED = list(NAME_CHANGE_COLUMNS)

SYMBOL_CHANGE_COLUMNS = [
    "NAME OF THE COMPANY",
    "OLD SYMBOL",
    "NEW SYMBOL",
    "EFFECTIVE DATE",
]
SYMBOL_CHANGE_REQUIRED = ["OLD SYMBOL", "NEW SYMBOL", "EFFECTIVE DATE"]

DELISTING_COLUMNS = [
    "Symbol",
    "ISIN",
    "Company Name",
    "Board",
    "Delisted Date",
    "Type of Delisting",
]
DELISTING_REQUIRED = [
    "Symbol",
    "ISIN",
    "Company Name",
    "Delisted Date",
    "Type of Delisting",
]


def _key(row: Row, columns: Iterable[str]) -> tuple[str, ...]:
    return tuple(clean(row.get(column)) for column in columns)


def _check_identifier_whitespace(
    result: DatasetResult,
    row: Row,
    columns: Iterable[str],
    code: str = "listings.identifier_whitespace",
) -> None:
    for column in columns:
        value = row.get(column)
        if value and value != value.strip():
            result.add_warning(
                code,
                (
                    f"{column} has leading/trailing whitespace: {value!r}; "
                    "comparisons use the trimmed value."
                ),
                row=row.number,
                column=column,
            )


def _check_isin(result: DatasetResult, row: Row, column: str) -> None:
    value = clean(row.get(column))
    if value and not ISIN_PATTERN.fullmatch(value):
        result.add_warning(
            "listings.isin_format_invalid",
            f"{column} does not look like a 12-character ISIN: {value!r}.",
            row=row.number,
            column=column,
        )


def _symbol_ranges(
    rows: list[Row],
    symbol_column: str,
    parsed_dates: dict[str, list[date]],
) -> dict[str, Any]:
    counts = Counter(clean(row.get(symbol_column)) for row in rows)
    counts.pop("", None)
    summary: dict[str, Any] = {}
    for symbol in sorted(counts):
        values = parsed_dates.get(symbol, [])
        summary[symbol] = {
            "records": counts[symbol],
            "start": format_date(min(values)) if values else None,
            "end": format_date(max(values)) if values else None,
        }
    return summary


def validate_current_listing(table: Table, result: DatasetResult) -> None:
    """Validate the current NSE equity listing reference."""

    check_schema(
        table,
        result,
        required=CURRENT_LISTING_REQUIRED,
        known=CURRENT_LISTING_COLUMNS,
    )
    result.row_count = len(table.rows)
    if not table.headers_ok or not table.rows:
        return

    parsed_dates: list[date] = []
    duplicate_keys: dict[tuple[str, str], list[Row]] = defaultdict(list)

    for row in table.rows:
        symbol = clean(row.get("SYMBOL"))
        name = clean(row.get("NAME OF COMPANY"))
        series = clean(row.get("SERIES"))
        listing_date_text = row.get("DATE OF LISTING")
        isin = clean(row.get("ISIN NUMBER"))

        if not symbol:
            result.add_error(
                "listings.symbol_missing",
                "Row has no symbol.",
                row=row.number,
                column="SYMBOL",
            )
        if not name:
            result.add_error(
                "listings.company_name_missing",
                "Row has no company name.",
                row=row.number,
                column="NAME OF COMPANY",
            )
        if not series:
            result.add_warning(
                "listings.series_missing",
                "Row has no series.",
                row=row.number,
                column="SERIES",
            )
        if not isin:
            result.add_error(
                "listings.isin_missing",
                "Row has no ISIN.",
                row=row.number,
                column="ISIN NUMBER",
            )
        else:
            _check_isin(result, row, "ISIN NUMBER")

        listing_date: date | None = None
        if is_blank(listing_date_text):
            result.add_error(
                "listings.listing_date_missing",
                "Listing date is missing.",
                row=row.number,
                column="DATE OF LISTING",
            )
        else:
            listing_date = parse_date(listing_date_text)
            if listing_date is None:
                result.add_error(
                    "listings.listing_date_invalid",
                    f"Unparseable listing date: {listing_date_text!r}.",
                    row=row.number,
                    column="DATE OF LISTING",
                )
            else:
                parsed_dates.append(listing_date)

        for column in ("PAID UP VALUE", "MARKET LOT", "FACE VALUE"):
            value = row.get(column)
            if is_blank(value):
                continue
            if parse_number(value) is None:
                result.add_warning(
                    "listings.numeric_value_invalid",
                    f"{column} is not a valid number: {value!r}.",
                    row=row.number,
                    column=column,
                )

        _check_identifier_whitespace(result, row, ("SYMBOL", "ISIN NUMBER", "SERIES"))

        if symbol and series:
            duplicate_keys[(symbol, series)].append(row)

    duplicate_extra_rows = add_duplicate_issues(
        result,
        duplicate_keys,
        code="listings.duplicate_record",
        label="current-listing record for symbol/series",
        preview=lambda key: f"{key[0]}/{key[1]}",
    )

    result.coverage = date_coverage(parsed_dates, "DATE OF LISTING")
    result.metrics.update(
        {
            "scope": "current_listing_reference",
            "series_counts": count_values(table.rows, "SERIES"),
            "duplicate_records": duplicate_extra_rows,
        }
    )


def validate_name_changes(table: Table, result: DatasetResult) -> None:
    """Validate the historical company-name change reference."""

    check_schema(
        table,
        result,
        required=NAME_CHANGE_REQUIRED,
        known=NAME_CHANGE_COLUMNS,
    )
    result.row_count = len(table.rows)
    if not table.headers_ok or not table.rows:
        return

    parsed_dates: list[date] = []
    parsed_by_symbol: dict[str, list[date]] = defaultdict(list)
    duplicate_keys: dict[tuple[str, ...], list[Row]] = defaultdict(list)

    for row in table.rows:
        symbol = clean(row.get("SYMBOL"))
        old_name = clean(row.get("OLD NAME OF THE COMPANY"))
        new_name = clean(row.get("NEW NAME OF THE COMPANY"))
        effective_text = row.get("EFFECTIVE DATE")

        if not symbol:
            result.add_error(
                "listings.symbol_missing",
                "Row has no symbol.",
                row=row.number,
                column="SYMBOL",
            )
        if not old_name:
            result.add_warning(
                "listings.old_name_missing",
                "Row has no old company name.",
                row=row.number,
                column="OLD NAME OF THE COMPANY",
            )
        if not new_name:
            result.add_warning(
                "listings.new_name_missing",
                "Row has no new company name.",
                row=row.number,
                column="NEW NAME OF THE COMPANY",
            )

        effective_date: date | None = None
        if is_blank(effective_text):
            result.add_error(
                "listings.effective_date_missing",
                "Effective date is missing.",
                row=row.number,
                column="EFFECTIVE DATE",
            )
        else:
            effective_date = parse_date(effective_text)
            if effective_date is None:
                result.add_error(
                    "listings.effective_date_invalid",
                    f"Unparseable effective date: {effective_text!r}.",
                    row=row.number,
                    column="EFFECTIVE DATE",
                )
            else:
                parsed_dates.append(effective_date)
                if symbol:
                    parsed_by_symbol[symbol].append(effective_date)

        if symbol and effective_date:
            duplicate_keys[
                (symbol, old_name, new_name, effective_date.isoformat())
            ].append(row)

    duplicate_extra_rows = add_duplicate_issues(
        result,
        duplicate_keys,
        code="listings.duplicate_record",
        label="name-change record",
        preview=lambda key: f"{key[0]} effective {key[3]}: {key[1]!r} -> {key[2]!r}",
    )

    result.coverage = date_coverage(parsed_dates, "EFFECTIVE DATE")
    result.metrics.update(
        {
            "scope": "historical_name_changes",
            "by_symbol": _symbol_ranges(table.rows, "SYMBOL", parsed_by_symbol),
            "duplicate_records": duplicate_extra_rows,
        }
    )


def validate_symbol_changes(table: Table, result: DatasetResult) -> None:
    """Validate the historical symbol change reference."""

    check_schema(
        table,
        result,
        required=SYMBOL_CHANGE_REQUIRED,
        known=SYMBOL_CHANGE_COLUMNS,
    )
    result.row_count = len(table.rows)
    if not table.headers_ok or not table.rows:
        return

    parsed_dates: list[date] = []
    parsed_by_new_symbol: dict[str, list[date]] = defaultdict(list)
    duplicate_keys: dict[tuple[str, ...], list[Row]] = defaultdict(list)

    for row in table.rows:
        name = clean(row.get("NAME OF THE COMPANY"))
        old_symbol = clean(row.get("OLD SYMBOL"))
        new_symbol = clean(row.get("NEW SYMBOL"))
        effective_text = row.get("EFFECTIVE DATE")

        if not name:
            result.add_warning(
                "listings.company_name_missing",
                "Row has no company name.",
                row=row.number,
                column="NAME OF THE COMPANY",
            )
        if not old_symbol:
            result.add_error(
                "listings.old_symbol_missing",
                "Row has no old symbol.",
                row=row.number,
                column="OLD SYMBOL",
            )
        if not new_symbol:
            result.add_error(
                "listings.new_symbol_missing",
                "Row has no new symbol.",
                row=row.number,
                column="NEW SYMBOL",
            )
        if old_symbol and new_symbol and old_symbol == new_symbol:
            result.add_warning(
                "listings.symbol_change_noop",
                f"Old and new symbols are identical: {old_symbol!r}.",
                row=row.number,
            )

        effective_date: date | None = None
        if is_blank(effective_text):
            result.add_error(
                "listings.effective_date_missing",
                "Effective date is missing.",
                row=row.number,
                column="EFFECTIVE DATE",
            )
        else:
            effective_date = parse_date(effective_text)
            if effective_date is None:
                result.add_error(
                    "listings.effective_date_invalid",
                    f"Unparseable effective date: {effective_text!r}.",
                    row=row.number,
                    column="EFFECTIVE DATE",
                )
            else:
                parsed_dates.append(effective_date)
                if new_symbol:
                    parsed_by_new_symbol[new_symbol].append(effective_date)

        if old_symbol and new_symbol and effective_date:
            duplicate_keys[
                (name, old_symbol, new_symbol, effective_date.isoformat())
            ].append(row)

    duplicate_extra_rows = add_duplicate_issues(
        result,
        duplicate_keys,
        code="listings.duplicate_record",
        label="symbol-change record",
        preview=lambda key: f"{key[1]} -> {key[2]} on {key[3]}",
    )

    result.coverage = date_coverage(parsed_dates, "EFFECTIVE DATE")
    result.metrics.update(
        {
            "scope": "historical_symbol_changes",
            "by_new_symbol": _symbol_ranges(
                table.rows,
                "NEW SYMBOL",
                parsed_by_new_symbol,
            ),
            "duplicate_records": duplicate_extra_rows,
        }
    )


def validate_delistings(
    table: Table,
    result: DatasetResult,
    *,
    scope: str,
) -> None:
    """Validate a processed historical delisting dataset."""

    check_schema(
        table,
        result,
        required=DELISTING_REQUIRED,
        known=DELISTING_COLUMNS,
    )
    result.row_count = len(table.rows)
    if not table.headers_ok or not table.rows:
        return

    parsed_dates: list[date] = []
    duplicate_keys: dict[tuple[str, ...], list[Row]] = defaultdict(list)

    for row in table.rows:
        symbol = clean(row.get("Symbol"))
        isin = clean(row.get("ISIN"))
        name = clean(row.get("Company Name"))
        board = clean(row.get("Board"))
        delisted_text = row.get("Delisted Date")
        delisting_type = clean(row.get("Type of Delisting"))

        if not symbol:
            result.add_error(
                "delistings.symbol_missing",
                "Row has no symbol.",
                row=row.number,
                column="Symbol",
            )
        if not isin:
            result.add_error(
                "delistings.isin_missing",
                "Row has no ISIN.",
                row=row.number,
                column="ISIN",
            )
        else:
            _check_isin(result, row, "ISIN")
        if not name:
            result.add_warning(
                "delistings.company_name_missing",
                "Row has no company name.",
                row=row.number,
                column="Company Name",
            )
        if not board:
            result.add_warning(
                "delistings.board_missing",
                "Row has no board classification.",
                row=row.number,
                column="Board",
            )
        if not delisting_type:
            result.add_error(
                "delistings.type_missing",
                "Row has no delisting type.",
                row=row.number,
                column="Type of Delisting",
            )

        delisted_date: date | None = None
        if is_blank(delisted_text):
            result.add_error(
                "delistings.date_missing",
                "Delisted date is missing.",
                row=row.number,
                column="Delisted Date",
            )
        else:
            delisted_date = parse_date(delisted_text)
            if delisted_date is None:
                result.add_error(
                    "delistings.date_invalid",
                    f"Unparseable delisted date: {delisted_text!r}.",
                    row=row.number,
                    column="Delisted Date",
                )
            else:
                parsed_dates.append(delisted_date)

        _check_identifier_whitespace(
            result,
            row,
            ("Symbol", "ISIN", "Board"),
            code="delistings.identifier_whitespace",
        )

        if symbol and delisted_date:
            duplicate_keys[(symbol, isin, delisted_date.isoformat())].append(row)

    duplicate_extra_rows = add_duplicate_issues(
        result,
        duplicate_keys,
        code="delistings.duplicate_record",
        label="delisting record",
        preview=lambda key: f"{key[0]} on {key[2]}",
    )

    result.coverage = date_coverage(parsed_dates, "Delisted Date")
    result.metrics.update(
        {
            "scope": scope,
            "by_board": count_values(table.rows, "Board"),
            "by_type": count_values(table.rows, "Type of Delisting"),
            "duplicate_records": duplicate_extra_rows,
        }
    )
