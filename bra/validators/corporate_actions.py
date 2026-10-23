"""Validation for NSE corporate-action exports.

No action type is inferred or corrected. ``PURPOSE`` is reported as supplied so
dividends, buybacks, meetings, demergers, and any other action remain distinct.

Additional validation:
  - Record date / ex-date ordering (when both are present and valid).
  - Price-coverage matching (pre-event / post-event price availability).
  - Suspicious price discontinuities around split / bonus events.
  - Classification of findings as confirmed, suspicious, or insufficient evidence.
"""

from __future__ import annotations

import re
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

# ---------------------------------------------------------------------------
# New issue codes for corporate-actions validation.
# ---------------------------------------------------------------------------
CODE_RECORD_BEFORE_EX = "corporate_actions.record_before_ex"
CODE_PRICE_COVERAGE = "corporate_actions.price_coverage"
CODE_SUSPICIOUS_DISCONTINUITY = "corporate_actions.suspicious_discontinuity"
CODE_CONFIRMED_INCONSISTENCY = "corporate_actions.confirmed_inconsistency"
CODE_SUSPICIOUS_ADJUSTMENT = "corporate_actions.suspicious_adjustment"
CODE_INSUFFICIENT_EVIDENCE = "corporate_actions.insufficient_evidence"


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


def _parse_purpose_ratio(purpose: str) -> float | None:
    """Extract a bonus/split ratio from the PURPOSE string.

    Returns the expected post-event / pre-event price ratio, or None when
    the purpose does not convey a interpretable ratio.
    """
    if not purpose:
        return None
    m = re.search(r"Bonus\s+(\d+):(\d+)", purpose, re.IGNORECASE)
    if m:
        big = int(m.group(1))
        small = int(m.group(2))
        if big > 0 and small > 0:
            return small / (big + small)  # e.g. 1:1 → 0.5, 1:2 → 0.667
    m = re.search(r"Split\s+(\d+):(\d+)", purpose, re.IGNORECASE)
    if m:
        big = int(m.group(1))
        small = int(m.group(2))
        if big > 0 and small > 0:
            return small / (big + small)
    # Also handle "1:1" style standalone ratios (less common in PURPOSE)
    m = re.search(r"(?<!\d):(?!\d)", purpose)  # just checking format, not extracting
    return None


def _expected_ratio_for_purpose(purpose: str) -> float | None:
    """Return the expected price-ratio for a known action purpose, or None."""

    if not purpose:
        return None
    # Bonus X:Y → holders get X new shares for Y owned; price ~ Y/(X+Y)
    m = re.search(r"Bonus\s+(\d+):(\d+)", purpose, re.IGNORECASE)
    if m:
        big = int(m.group(1))
        small = int(m.group(2))
        if big > 0 and small > 0:
            return small / (big + small)
    # Split X:Y
    m = re.search(r"Split\s+(\d+):(\d+)", purpose, re.IGNORECASE)
    if m:
        big = int(m.group(1))
        small = int(m.group(2))
        if big > 0 and small > 0:
            return small / (big + small)
    # Dividend: no fixed ratio; price typically drops by the dividend amount,
    # which is unpredictable without the cash amount, so return None.
    if "Dividend" in purpose:
        return None
    # Buyback: no fixed ratio
    if "Buyback" in purpose or "buyback" in purpose:
        return None
    return None


def _find_price_date(
    rows_by_symbol: dict[str, list[Row]], symbol: str, target_date: date, direction: str
) -> date | None:
    """Find the nearest price date for *symbol* in the given *direction*.

    *direction* is "pre" (latest date <= target) or "post" (earliest date >= target).
    Returns None when no matching row exists.
    """
    rows = rows_by_symbol.get(symbol, [])
    matching = [
        r
        for r in rows
        if r.get(
            "Series",
        ).upper()
        == "EQ"
    ]
    if not matching:
        return None
    prices: list[tuple[date, Row]] = []
    for row in matching:
        d = parse_date(row.get("Date"))
        if d is not None:
            prices.append((d, row))
    if direction == "pre":
        # latest date strictly before target
        before = [p for p, _ in prices if p < target_date]
        if before:
            return max(before)
    elif direction == "post":
        # earliest date on or after target
        on_or_after = [p for p, _ in prices if p >= target_date]
        if on_or_after:
            return min(on_or_after)
    return None


def _get_price(row: Row, column: str = "Close Price") -> float | None:
    """Parse a close-price field from a price row, returning None on failure."""
    value = row.get(column)
    if value is None:
        return None
    try:
        return float(value.replace(",", "").strip())
    except ValueError:
        return None


def _classify_severity(
    discrepancy_ratio: float | None, expected_ratio: float | None, purpose: str
) -> str:
    """Classify a price discontinuity finding.

    Returns one of: "confirmed_inconsistency", "suspicious_adjustment",
    "insufficient_evidence".
    """
    if expected_ratio is None:
        return "insufficient_evidence"
    if discrepancy_ratio is None:
        return "insufficient_evidence"
    # If the actual ratio is within a tolerant band of the expected ratio, it's
    # not suspicious.  A 20% tolerance is used for bonus/split events.
    tolerance = 0.20
    if (
        expected_ratio * (1 - tolerance)
        <= discrepancy_ratio
        <= expected_ratio * (1 + tolerance)
    ):
        return "insufficient_evidence"
    # If the discrepancy is extreme (e.g. > 2x the expected move), flag it.
    # Otherwise treat it as a suspicious adjustment pattern.
    ratio_of_ratios = abs(discrepancy_ratio / expected_ratio)
    if ratio_of_ratios > 2.0:
        return "suspicious_adjustment"
    return "suspicious_adjustment"


def validate(
    table: Table,
    result: DatasetResult,
    expected_symbol: str | None = None,
    price_table: Any = None,
) -> None:
    """Validate a parsed corporate-actions table.

    ``price_table`` is optional. When provided it should be a ``Table`` object
    containing price data (Symbol, Series, Date, Close Price columns) for the
    same symbol, enabling price-coverage and discontinuity checks.
    """

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

    # --- Build price lookup if a price table is supplied ---
    rows_by_symbol: dict[str, list[Row]] = defaultdict(list)
    if price_table is not None and price_table.rows:
        for row in price_table.rows:
            sym = clean(row.get("Symbol"))
            if sym:
                rows_by_symbol[sym.upper()].append(row)

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

        # --- Check: record date before ex-date ---
        # When both ex_date and record_date are present and valid, flag if
        # the record date precedes the ex-date (which is anomalous under
        # standard corporate-action semantics).
        record_date: date | None = None
        if not is_blank(record_value) and not is_not_applicable(record_value):
            record_date = parse_date(record_value)
            if (
                record_date is not None
                and ex_date is not None
                and record_date < ex_date
            ):
                result.add_error(
                    CODE_CONFIRMED_INCONSISTENCY,
                    (
                        f"Record date {format_date(record_date)} precedes "
                        f"ex-date {format_date(ex_date)}; under standard "
                        f"semantics the ex-date should come before the "
                        f"record date."
                    ),
                    row=row.number,
                    column="RECORD DATE",
                )

        # --- Price-coverage and discontinuity checks (if price data available) ---
        if symbol and ex_date and price_table is not None and price_table.rows:
            # Determine pre-event and post-event price dates
            pre_price_date = _find_price_date(
                rows_by_symbol, symbol.upper(), ex_date, "pre"
            )
            post_price_date = _find_price_date(
                rows_by_symbol, symbol.upper(), ex_date, "post"
            )

            # Report missing pre/post coverage
            pre_covered = pre_price_date is not None
            post_covered = post_price_date is not None

            if not pre_covered:
                result.add_warning(
                    CODE_PRICE_COVERAGE,
                    (
                        f"No price data found before ex-date "
                        f"{format_date(ex_date)} for {symbol}; pre-event coverage "
                        f"is a data limitation."
                    ),
                    row=row.number,
                    column="EX-DATE",
                )
            if not post_covered:
                result.add_warning(
                    CODE_PRICE_COVERAGE,
                    (
                        f"No price data found after ex-date "
                        f"{format_date(ex_date)} for {symbol}; post-event coverage "
                        f"is a data limitation."
                    ),
                    row=row.number,
                    column="EX-DATE",
                )

            # Suspicious discontinuity check for split/bonus events
            if not pre_covered or not post_covered:
                # Cannot assess discontinuity without both price points
                pass
            else:
                pre_price_row = None
                for r in rows_by_symbol[symbol.upper()]:
                    if parse_date(r.get("Date")) == pre_price_date:
                        pre_price_row = r
                        break
                post_price_row = None
                for r in rows_by_symbol[symbol.upper()]:
                    if parse_date(r.get("Date")) == post_price_date:
                        post_price_row = r
                        break

                if pre_price_row is not None and post_price_row is not None:
                    pre_close = _get_price(pre_price_row)
                    post_close = _get_price(post_price_row)
                    if (
                        pre_close is not None
                        and post_close is not None
                        and pre_close > 0
                    ):
                        discrepancy_ratio = post_close / pre_close
                        purpose = clean(row.get("PURPOSE"))
                        expected_ratio = _expected_ratio_for_purpose(purpose)

                        classification = _classify_severity(
                            discrepancy_ratio, expected_ratio, purpose
                        )

                        if classification == "suspicious_adjustment":
                            result.add_warning(
                                CODE_SUSPICIOUS_DISCONTINUITY,
                                (
                                    f"Suspicious price discontinuity around "
                                    f"corporate action on {format_date(ex_date)} for "
                                    f"{symbol}: pre-close {pre_close}, post-close "
                                    f"{post_close}, ratio {discrepancy_ratio:.3f}. "
                                    f"Purpose: {purpose!r}. "
                                    f"Price move may not be consistent with the "
                                    f"action's expected effect; investigation required."
                                ),
                                row=row.number,
                                column="EX-DATE",
                            )
                        elif classification == "confirmed_inconsistency":
                            result.add_error(
                                CODE_SUSPICIOUS_DISCONTINUITY,
                                (
                                    f"Price discontinuity confirmed around "
                                    f"corporate action on {format_date(ex_date)} for "
                                    f"{symbol}: pre-close {pre_close}, post-close "
                                    f"{post_close}, ratio {discrepancy_ratio:.3f}. "
                                    f"Purpose: {purpose!r}. The price move is "
                                    f"inconsistent with the expected effect of the "
                                    f"corporate action."
                                ),
                                row=row.number,
                                column="EX-DATE",
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
