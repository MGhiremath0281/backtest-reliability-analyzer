"""Validation for NSE corporate-action exports.

No action type is inferred or corrected. ``PURPOSE`` is reported as supplied so
dividends, buybacks, meetings, demergers, and any other action remain distinct.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
from typing import Any

from ..csv_io import Row, Table
from ..models import DatasetResult
from ..parsing import (
    clean,
    format_date,
    is_blank,
    is_not_applicable,
    parse_date,
)
from .common import (
    add_duplicate_issues,
    check_schema,
    count_pairs,
    count_values,
    date_coverage,
)

CORPORATE_ACTION_COLUMNS = [
    "SYMBOL",
    "COMPANY NAME",
    "SERIES",
    "PURPOSE",
    "FACE VALUE",
    "EX-DATE",
    "RECORD DATE",
    "BOOK CLOSURE START DATE",
    "BOOK CLOSURE END DATE",
]

REQUIRED_COLUMNS = ["SYMBOL", "COMPANY NAME", "PURPOSE", "EX-DATE"]
OPTIONAL_DATE_COLUMNS = (
    "RECORD DATE",
    "BOOK CLOSURE START DATE",
    "BOOK CLOSURE END DATE",
)


def _symbol_summary(
    rows: list[Row],
    parsed_ex_dates: dict[str, list[date]],
) -> dict[str, Any]:
    counts = Counter(clean(row.get("SYMBOL")) for row in rows)
    counts.pop("", None)
    summary: dict[str, Any] = {}
    for symbol in sorted(counts):
        dates = parsed_ex_dates.get(symbol, [])
        summary[symbol] = {
            "actions": counts[symbol],
            "start": format_date(min(dates)) if dates else None,
            "end": format_date(max(dates)) if dates else None,
        }
    return summary


def validate(
    table: Table,
    result: DatasetResult,
    expected_symbol: str | None = None,
) -> None:
    """Validate a parsed corporate-actions table."""

    check_schema(
        table,
        result,
        required=REQUIRED_COLUMNS,
        known=CORPORATE_ACTION_COLUMNS,
    )
    result.row_count = len(table.rows)
    if not table.headers_ok or not table.rows:
        return

    expected = expected_symbol.upper() if expected_symbol else None
    parsed_dates: list[date] = []
    parsed_ex_dates: dict[str, list[date]] = defaultdict(list)
    duplicate_keys: dict[tuple[str, str, str], list[Row]] = defaultdict(list)

    for row in table.rows:
        symbol = clean(row.get("SYMBOL"))
        company = clean(row.get("COMPANY NAME"))
        purpose = clean(row.get("PURPOSE"))
        ex_date_text = row.get("EX-DATE")

        if not symbol:
            result.add_error(
                "corporate_actions.symbol_missing",
                "Row has no symbol.",
                row=row.number,
                column="SYMBOL",
            )
        elif expected and symbol.upper() != expected:
            result.add_error(
                "corporate_actions.symbol_mismatch",
                (
                    f"Symbol {symbol!r} does not match the expected symbol "
                    f"{expected!r} from the filename."
                ),
                row=row.number,
                column="SYMBOL",
            )

        if not company:
            result.add_warning(
                "corporate_actions.company_missing",
                "Row has no company name.",
                row=row.number,
                column="COMPANY NAME",
            )

        if not purpose:
            result.add_error(
                "corporate_actions.purpose_missing",
                "Row has no corporate-action purpose.",
                row=row.number,
                column="PURPOSE",
            )

        ex_date: date | None = None
        if is_blank(ex_date_text) or is_not_applicable(ex_date_text):
            result.add_error(
                "corporate_actions.ex_date_missing",
                "Ex-date is missing.",
                row=row.number,
                column="EX-DATE",
            )
        else:
            ex_date = parse_date(ex_date_text)
            if ex_date is None:
                result.add_error(
                    "corporate_actions.ex_date_invalid",
                    f"Unparseable ex-date: {ex_date_text!r}.",
                    row=row.number,
                    column="EX-DATE",
                )
            else:
                parsed_dates.append(ex_date)
                if symbol:
                    parsed_ex_dates[symbol].append(ex_date)

        for column in OPTIONAL_DATE_COLUMNS:
            value = row.get(column)
            if is_blank(value) or is_not_applicable(value):
                continue
            if parse_date(value) is None:
                result.add_error(
                    "corporate_actions.date_invalid",
                    f"{column} is not a valid date: {value!r}.",
                    row=row.number,
                    column=column,
                )

        closure_start = parse_date(row.get("BOOK CLOSURE START DATE"))
        closure_end = parse_date(row.get("BOOK CLOSURE END DATE"))
        if closure_start and closure_end and closure_start > closure_end:
            result.add_error(
                "corporate_actions.closure_range_invalid",
                (
                    "Book-closure start date is after its end date: "
                    f"{closure_start.isoformat()} > {closure_end.isoformat()}."
                ),
                row=row.number,
            )

        record_value = row.get("RECORD DATE")
        has_closure = any(
            not is_blank(row.get(column)) and not is_not_applicable(row.get(column))
            for column in ("BOOK CLOSURE START DATE", "BOOK CLOSURE END DATE")
        )
        if (
            is_blank(record_value) or is_not_applicable(record_value)
        ) and not has_closure:
            result.add_warning(
                "corporate_actions.record_date_missing",
                (
                    "Neither a record date nor book-closure dates are present; "
                    "the entitlement date may be incomplete."
                ),
                row=row.number,
                column="RECORD DATE",
            )

        if symbol and ex_date and purpose:
            key = (symbol, ex_date.isoformat(), purpose)
            duplicate_keys[key].append(row)

    duplicate_extra_rows = add_duplicate_issues(
        result,
        duplicate_keys,
        code="corporate_actions.duplicate_record",
        label="corporate action",
        preview=lambda key: f"{key[0]} on {key[1]} ({key[2]})",
    )

    result.coverage = date_coverage(parsed_dates, "EX-DATE")
    result.metrics.update(
        {
            "by_symbol": _symbol_summary(table.rows, parsed_ex_dates),
            "by_purpose": count_values(table.rows, "PURPOSE"),
            "by_series": count_values(table.rows, "SERIES"),
            "by_symbol_purpose": count_pairs(table.rows, "SYMBOL", "PURPOSE"),
            "duplicate_records": duplicate_extra_rows,
        }
    )
