"""Validation of normalized, derived datasets.

These checks are intentionally independent of the raw-source validators. They
verify the invariants the preparation step promises, so a regression in the
transformation code is caught even when the raw files are unchanged.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date

from ..csv_io import Row, Table
from ..derived_schema import (
    DERIVED_DATE_COLUMNS,
    DERIVED_ENTITY_COLUMNS,
    DERIVED_HEADERS,
    DERIVED_IDENTIFIER_COLUMNS,
    DERIVED_ISIN_COLUMNS,
    DERIVED_KEY_COLUMNS,
    DERIVED_REQUIRED_DATE_COLUMNS,
    DERIVED_REQUIRED_TIMESTAMP_COLUMNS,
    DERIVED_TIMESTAMP_COLUMNS,
    REVIEW_FLAG_MESSAGES,
)
from ..models import DatasetResult
from ..parsing import (
    clean,
    format_timestamp,
    is_blank,
    parse_date,
    parse_number,
    parse_timestamp,
)
from .common import add_duplicate_issues, check_schema, date_coverage

ISIN_PATTERN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")
PRICE_FIELDS = ("open", "high", "low", "close")
TOLERANCE = 1e-6


def validate(table: Table, result: DatasetResult, kind: str) -> None:
    """Validate one derived dataset identified by its schema key."""

    expected = DERIVED_HEADERS[kind]
    missing = check_schema(table, result, required=expected, known=expected)
    result.row_count = len(table.rows)
    if missing or not table.headers_ok or not table.rows:
        return

    parsed_dates: dict[str, list[date]] = defaultdict(list)
    duplicate_keys: dict[tuple[str, ...], list[Row]] = defaultdict(list)
    flag_counts: dict[str, int] = defaultdict(int)
    unknown_flags: dict[str, list[int]] = defaultdict(list)

    date_columns = DERIVED_DATE_COLUMNS.get(kind, ())
    required_dates = set(DERIVED_REQUIRED_DATE_COLUMNS.get(kind, ()))
    timestamp_columns = DERIVED_TIMESTAMP_COLUMNS.get(kind, ())
    required_timestamps = set(DERIVED_REQUIRED_TIMESTAMP_COLUMNS.get(kind, ()))
    identifier_columns = DERIVED_IDENTIFIER_COLUMNS.get(kind, ())
    isin_columns = DERIVED_ISIN_COLUMNS.get(kind, ())
    key_columns = DERIVED_KEY_COLUMNS.get(kind, ())

    for row in table.rows:
        for column in identifier_columns:
            value = row.get(column)
            if is_blank(value):
                result.add_error(
                    "derived.identifier_missing",
                    f"{column} is blank.",
                    row=row.number,
                    column=column,
                )
            elif value != value.strip():
                result.add_warning(
                    "derived.identifier_whitespace",
                    f"{column} has surrounding whitespace: {value!r}.",
                    row=row.number,
                    column=column,
                )
        for column in isin_columns:
            value = clean(row.get(column))
            if value and not ISIN_PATTERN.fullmatch(value):
                result.add_warning(
                    "derived.isin_malformed",
                    f"{column} is not a well-formed 12-character ISIN: {value!r}.",
                    row=row.number,
                    column=column,
                )

        for column in date_columns:
            raw = row.get(column)
            if is_blank(raw):
                if column in required_dates:
                    result.add_error(
                        "derived.required_date_missing",
                        f"Required date {column} is blank.",
                        row=row.number,
                        column=column,
                    )
                continue
            parsed = parse_date(raw)
            if parsed is None:
                result.add_error(
                    "derived.date_invalid",
                    f"{column} is not a valid date: {raw!r}.",
                    row=row.number,
                    column=column,
                )
            else:
                if raw != parsed.isoformat():
                    result.add_error(
                        "derived.date_not_iso",
                        f"{column} is not ISO 8601: {raw!r}.",
                        row=row.number,
                        column=column,
                    )
                parsed_dates[column].append(parsed)

        for column in timestamp_columns:
            raw = row.get(column)
            if is_blank(raw):
                if column in required_timestamps:
                    result.add_error(
                        "derived.required_timestamp_missing",
                        f"Required timestamp {column} is blank.",
                        row=row.number,
                        column=column,
                    )
                continue
            parsed = parse_timestamp(raw)
            if parsed is None:
                result.add_error(
                    "derived.timestamp_invalid",
                    f"{column} is not a valid timestamp: {raw!r}.",
                    row=row.number,
                    column=column,
                )
            elif raw != format_timestamp(parsed):
                result.add_error(
                    "derived.timestamp_not_iso",
                    f"{column} is not ISO 8601: {raw!r}.",
                    row=row.number,
                    column=column,
                )

        flags = [flag for flag in row.get("review_flags").split("|") if flag]
        for flag in flags:
            flag_counts[flag] += 1
            if flag not in REVIEW_FLAG_MESSAGES:
                unknown_flags[flag].append(row.number)

        if key_columns and all(clean(row.get(column)) for column in key_columns):
            duplicate_keys[
                tuple(clean(row.get(column)) for column in key_columns)
            ].append(row)

        _validate_row(row, result, kind)

    duplicate_extra_rows = add_duplicate_issues(
        result,
        duplicate_keys,
        code="derived.duplicate_key",
        label=f"{kind} key",
        preview=lambda key: "/".join(key),
    )

    for flag, lines in sorted(unknown_flags.items()):
        sample = ", ".join(str(line) for line in lines[:5])
        result.add_warning(
            "derived.unknown_review_flag",
            (
                f"Review flag {flag!r} has no documented meaning "
                f"(rows {sample})."
            ),
        )

    if flag_counts:
        summary = ", ".join(
            f"{flag}={count}" for flag, count in sorted(flag_counts.items())
        )
        result.add_warning(
            "derived.review_flags_present",
            f"Derived rows carry review flags: {summary}.",
        )

    primary_date_column = (
        DERIVED_REQUIRED_DATE_COLUMNS[kind][0] if required_dates else None
    )
    if primary_date_column:
        result.coverage = date_coverage(
            parsed_dates.get(primary_date_column, []),
            primary_date_column,
        )

    entity_column = DERIVED_ENTITY_COLUMNS.get(kind)
    entities = (
        {
            clean(row.get(entity_column))
            for row in table.rows
            if clean(row.get(entity_column))
        }
        if entity_column
        else set()
    )

    result.metrics.update(
        {
            "scope": "derived_normalized",
            "kind": kind,
            "duplicate_extra_records": duplicate_extra_rows,
            "review_flag_counts": dict(sorted(flag_counts.items())),
            "distinct_entities": len(entities),
        }
    )


def _validate_row(row: Row, result: DatasetResult, kind: str) -> None:
    if kind == "derived_prices":
        _validate_prices_row(row, result)
    elif kind == "derived_financials_legacy":
        _validate_lag_row(row, result, "period_end_date")
    elif kind == "derived_financials_integrated":
        _validate_lag_row(row, result, "quarter_end_date")
    elif kind == "derived_name_changes":
        _validate_name_change_row(row, result)
    elif kind == "derived_symbol_changes":
        old = clean(row.get("old_symbol"))
        new = clean(row.get("new_symbol"))
        if old and old == new:
            result.add_warning(
                "derived.symbol_change_noop",
                f"Old and new symbols are identical: {old!r}.",
                row=row.number,
            )


def _validate_prices_row(row: Row, result: DatasetResult) -> None:
    values: dict[str, float] = {}
    for field in PRICE_FIELDS:
        parsed = parse_number(row.get(field))
        if parsed is None:
            result.add_warning(
                "derived.price_invalid",
                f"{field} is blank or not a number: {row.get(field)!r}.",
                row=row.number,
                column=field,
            )
        else:
            values[field] = parsed

    if len(values) != len(PRICE_FIELDS):
        return

    reason = None
    if values["high"] + TOLERANCE < values["low"]:
        reason = "high is below low"
    elif values["high"] + TOLERANCE < max(values["open"], values["close"]):
        reason = "high is below open or close"
    elif values["low"] - TOLERANCE > min(values["open"], values["close"]):
        reason = "low is above open or close"
    if reason is None:
        return

    if row.get("series").upper() == "EQ":
        result.add_error(
            "derived.ohlc_primary_anomaly",
            f"Primary EQ row has an OHLC anomaly: {reason}.",
            row=row.number,
        )
    else:
        result.add_warning(
            "derived.ohlc_auxiliary_anomaly",
            f"Auxiliary series row has an OHLC anomaly: {reason}.",
            row=row.number,
        )


def _validate_lag_row(
    row: Row,
    result: DatasetResult,
    period_column: str,
) -> None:
    period = parse_date(row.get(period_column))
    disseminated = parse_timestamp(row.get("exchange_dissemination_time"))
    raw_lag = clean(row.get("publication_lag_days"))

    if period is None or disseminated is None:
        if raw_lag:
            result.add_error(
                "derived.publication_lag_unexpected",
                "Publication lag is populated without a parseable period and dissemination time.",
                row=row.number,
            )
        return

    if disseminated.date() < period:
        if raw_lag:
            result.add_error(
                "derived.publication_lag_unexpected",
                "Publication lag is populated even though dissemination precedes the period end.",
                row=row.number,
            )
        return

    expected = (disseminated.date() - period).days
    if not raw_lag:
        result.add_error(
            "derived.publication_lag_missing",
            f"Publication lag should be {expected} days but is blank.",
            row=row.number,
        )
        return
    try:
        actual = int(raw_lag)
    except ValueError:
        result.add_error(
            "derived.publication_lag_invalid",
            f"Publication lag is not an integer: {raw_lag!r}.",
            row=row.number,
        )
        return
    if actual != expected:
        result.add_error(
            "derived.publication_lag_mismatch",
            f"Publication lag is {actual} but the timestamps imply {expected}.",
            row=row.number,
        )


def _validate_name_change_row(row: Row, result: DatasetResult) -> None:
    raw_count = clean(row.get("source_record_count"))
    try:
        count = int(raw_count)
    except ValueError:
        count = 0
    if count < 1:
        result.add_error(
            "derived.source_record_count_invalid",
            f"source_record_count is not a positive integer: {raw_count!r}.",
            row=row.number,
        )
        return

    source_lines = [
        value for value in clean(row.get("source_lines")).split(";") if value
    ]
    if len(source_lines) != count:
        result.add_error(
            "derived.source_lines_mismatch",
            (
                f"source_record_count is {count} but source_lines lists "
                f"{len(source_lines)} line(s)."
            ),
            row=row.number,
        )
    if clean(row.get("source_line")) not in source_lines:
        result.add_error(
            "derived.source_line_missing",
            "source_line is not included in source_lines.",
            row=row.number,
        )
    status = clean(row.get("review_status"))
    if status not in {"unique", "collapsed_exact_duplicates"}:
        result.add_warning(
            "derived.review_status_unknown",
            f"Unexpected review_status: {status!r}.",
            row=row.number,
        )
