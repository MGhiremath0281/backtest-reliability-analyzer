"""Validation for historical OHLC price exports.

NSE price files can contain multiple market series for the same date (for
example ``EQ``, ``BL``, and ``T0``). Duplicate dates are therefore checked per
symbol and series, not across the whole file. Standard OHLC checks are strict
for the primary ``EQ`` series and advisory for auxiliary series, whose auction
or special-session prices can break normal intraday relationships.
"""

from __future__ import annotations

import itertools
from collections import Counter, defaultdict
from datetime import date
from typing import Any

from ..csv_io import Row, Table
from ..models import DatasetResult
from ..parsing import clean, format_date, is_blank, parse_date, parse_number
from .common import (
    add_duplicate_issues,
    check_schema,
    date_coverage,
)

PRICE_COLUMNS = [
    "Symbol",
    "Series",
    "Date",
    "Prev Close",
    "Open Price",
    "High Price",
    "Low Price",
    "Last Price",
    "Close Price",
    "Average Price",
    "Total Traded Quantity",
    "Turnover ₹",
    "No. of Trades",
    "Deliverable Qty",
    "% Dly Qt to Traded Qty",
]

REQUIRED_COLUMNS = [
    "Symbol",
    "Series",
    "Date",
    "Open Price",
    "High Price",
    "Low Price",
    "Close Price",
]

OHLC_COLUMNS = ("Open Price", "High Price", "Low Price", "Close Price")
OPTIONAL_NUMERIC_COLUMNS = (
    "Prev Close",
    "Last Price",
    "Average Price",
    "Total Traded Quantity",
    "Turnover ₹",
    "No. of Trades",
    "Deliverable Qty",
    "% Dly Qt to Traded Qty",
)

PRIMARY_SERIES = "EQ"
LARGE_GAP_DAYS = 10
TOLERANCE = 1e-6


def _is_monotonic(values: list[date], *, descending: bool) -> bool:
    pairs = itertools.pairwise(values)
    if descending:
        return all(left >= right for left, right in pairs)
    return all(left <= right for left, right in pairs)


def _symbol_summary(
    dates_by_symbol: dict[str, list[date]],
    series_by_symbol: dict[str, Counter[str]],
    rows_by_symbol: Counter[str],
) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for symbol in sorted(dates_by_symbol):
        dates = dates_by_symbol[symbol]
        summary[symbol] = {
            "rows": rows_by_symbol[symbol],
            "start": format_date(min(dates)) if dates else None,
            "end": format_date(max(dates)) if dates else None,
            "series": dict(sorted(series_by_symbol[symbol].items())),
        }
    return summary


def validate(
    table: Table,
    result: DatasetResult,
    expected_symbol: str | None = None,
) -> None:
    """Validate a parsed historical-prices table."""

    check_schema(
        table,
        result,
        required=REQUIRED_COLUMNS,
        known=PRICE_COLUMNS,
    )
    result.row_count = len(table.rows)
    if not table.headers_ok or not table.rows:
        return

    expected = expected_symbol.upper() if expected_symbol else None

    parsed_dates: list[date] = []
    dates_by_series: dict[str, list[date]] = defaultdict(list)
    dates_by_symbol: dict[str, list[date]] = defaultdict(list)
    series_by_symbol: dict[str, Counter[str]] = defaultdict(Counter)
    rows_by_symbol: Counter[str] = Counter()
    series_counts: Counter[str] = Counter()
    series_sets_by_date: dict[date, set[str]] = defaultdict(set)

    duplicate_keys: dict[tuple[str, str, date], list[Row]] = defaultdict(list)

    has_primary_series = False

    for row in table.rows:
        symbol = clean(row.get("Symbol"))
        series = clean(row.get("Series"))

        if not symbol:
            result.add_error(
                "prices.symbol_missing",
                "Row has no symbol.",
                row=row.number,
                column="Symbol",
            )
        else:
            rows_by_symbol[symbol] += 1
            if expected and symbol.upper() != expected:
                result.add_error(
                    "prices.symbol_mismatch",
                    (
                        f"Symbol {symbol!r} does not match the expected symbol "
                        f"{expected!r} from the filename."
                    ),
                    row=row.number,
                    column="Symbol",
                )

        if not series:
            result.add_error(
                "prices.series_missing",
                "Row has no market series.",
                row=row.number,
                column="Series",
            )
        else:
            series_counts[series] += 1
            if symbol:
                series_by_symbol[symbol][series] += 1
            if series.upper() == PRIMARY_SERIES:
                has_primary_series = True

        parsed_date = parse_date(row.get("Date"))
        if is_blank(row.get("Date")):
            result.add_error(
                "prices.date_missing",
                "Trading date is missing.",
                row=row.number,
                column="Date",
            )
        elif parsed_date is None:
            result.add_error(
                "prices.date_invalid",
                f"Unparseable trading date: {row.get('Date')!r}.",
                row=row.number,
                column="Date",
            )
        else:
            parsed_dates.append(parsed_date)
            if symbol:
                dates_by_symbol[symbol].append(parsed_date)
            if series:
                dates_by_series[series].append(parsed_date)
                series_sets_by_date[parsed_date].add(series)
            if symbol and series:
                duplicate_keys[(symbol, series, parsed_date)].append(row)

        prices: dict[str, float] = {}
        for column in OHLC_COLUMNS:
            value = row.get(column)
            if is_blank(value):
                result.add_error(
                    "prices.value_missing",
                    f"{column} is missing.",
                    row=row.number,
                    column=column,
                )
                continue
            number = parse_number(value)
            if number is None:
                result.add_error(
                    "prices.value_invalid",
                    f"{column} is not a valid number: {value!r}.",
                    row=row.number,
                    column=column,
                )
                continue
            if number <= 0:
                result.add_error(
                    "prices.price_non_positive",
                    f"{column} must be positive, got {number}.",
                    row=row.number,
                    column=column,
                )
                continue
            prices[column] = number

        if len(prices) == len(OHLC_COLUMNS):
            open_price = prices["Open Price"]
            high = prices["High Price"]
            low = prices["Low Price"]
            close = prices["Close Price"]
            invalid_reason: str | None = None
            if high + TOLERANCE < low:
                invalid_reason = "high price is below low price"
            elif high + TOLERANCE < max(open_price, close):
                invalid_reason = "high price is below open or close"
            elif low - TOLERANCE > min(open_price, close):
                invalid_reason = "low price is above open or close"
            if invalid_reason:
                is_primary = series.upper() == PRIMARY_SERIES
                message = (
                    f"Invalid OHLC relationship ({invalid_reason}): "
                    f"open={open_price}, high={high}, low={low}, close={close}."
                )
                if is_primary:
                    result.add_error(
                        "prices.ohlc_invalid",
                        message,
                        row=row.number,
                    )
                else:
                    result.add_warning(
                        "prices.ohlc_invalid_auxiliary",
                        f"{message} Series={series or 'unknown'}.",
                        row=row.number,
                    )

        for column in OPTIONAL_NUMERIC_COLUMNS:
            value = row.get(column)
            if is_blank(value) or value.strip() in {"-", "--"}:
                continue
            if parse_number(value) is None:
                result.add_warning(
                    "prices.optional_value_invalid",
                    f"{column} is not a valid number: {value!r}.",
                    row=row.number,
                    column=column,
                )

    if not has_primary_series:
        result.add_warning(
            "prices.primary_series_missing",
            f"No rows found for the primary {PRIMARY_SERIES!r} series.",
        )

    duplicate_extra_rows = add_duplicate_issues(
        result,
        duplicate_keys,
        code="prices.duplicate_date",
        label="trading date within symbol/series",
        preview=lambda key: f"{key[0]}/{key[1]} on {key[2].isoformat()}",
    )

    order_by_series: dict[str, str] = {}
    for series in sorted(dates_by_series):
        values = dates_by_series[series]
        descending = _is_monotonic(values, descending=True)
        ascending = _is_monotonic(values, descending=False)
        if descending and ascending:
            order_by_series[series] = "flat"
        elif descending:
            order_by_series[series] = "descending"
        elif ascending:
            order_by_series[series] = "ascending"
        else:
            order_by_series[series] = "unordered"
            result.add_error(
                "prices.date_order",
                (f"Dates in series {series!r} are not monotonic in either direction."),
                column="Date",
            )

    gaps: list[dict[str, Any]] = []
    primary_dates = sorted(set(dates_by_series.get(PRIMARY_SERIES, [])))
    for previous, current in itertools.pairwise(primary_dates):
        gap_days = (current - previous).days
        if gap_days > LARGE_GAP_DAYS:
            gaps.append(
                {
                    "start": previous.isoformat(),
                    "end": current.isoformat(),
                    "days": gap_days,
                }
            )
            result.add_warning(
                "prices.large_calendar_gap",
                (
                    f"{gap_days}-day calendar gap in {PRIMARY_SERIES} series "
                    f"between {previous.isoformat()} and {current.isoformat()}. "
                    "This is not classified as a missing trading session because "
                    "no authoritative exchange calendar is available."
                ),
                column="Date",
            )

    multiple_series_dates = sum(
        1 for series in series_sets_by_date.values() if len(series) > 1
    )

    result.coverage = date_coverage(parsed_dates, "Date")
    result.metrics.update(
        {
            "primary_series": PRIMARY_SERIES,
            "series_counts": dict(sorted(series_counts.items())),
            "series_date_order": order_by_series,
            "by_symbol": _symbol_summary(
                dates_by_symbol,
                series_by_symbol,
                rows_by_symbol,
            ),
            "primary_series_coverage": date_coverage(
                dates_by_series.get(PRIMARY_SERIES, []), "Date"
            ),
            "duplicate_date_rows": duplicate_extra_rows,
            "dates_with_multiple_series": multiple_series_dates,
            "max_calendar_gap_days": (
                max(
                    (
                        (current - previous).days
                        for previous, current in itertools.pairwise(primary_dates)
                    ),
                    default=0,
                )
            ),
            "large_calendar_gaps": gaps,
        }
    )
