"""Historical price validation tests."""

from __future__ import annotations

import pytest

from bra.csv_io import read_csv
from bra.models import Status
from bra.validators import prices

from .support import PRICE_HEADERS, issue_codes, make_result, price_row


def run(path, expected_symbol: str = "INFY"):
    table = read_csv(path)
    result = make_result("prices:INFY")
    result.issues.extend(table.issues)
    prices.validate(table, result, expected_symbol)
    return result


def test_valid_price_data_passes(make_csv):
    path = make_csv(
        "valid-prices.csv",
        PRICE_HEADERS,
        [
            price_row("22-Oct-2026"),
            price_row("21-Oct-2026"),
        ],
    )

    result = run(path)

    assert result.status is Status.PASS
    assert result.row_count == 2
    assert result.coverage == {
        "date_column": "Date",
        "start": "2026-10-21",
        "end": "2026-10-22",
    }


def test_duplicate_dates_within_same_series_fail(make_csv):
    path = make_csv(
        "duplicate-dates.csv",
        PRICE_HEADERS,
        [
            price_row("22-Oct-2021"),
            price_row("22-Oct-2021"),
        ],
    )

    result = run(path)

    assert result.status is Status.FAIL
    assert "prices.duplicate_date" in issue_codes(result)
    assert result.metrics["duplicate_date_rows"] == 1


def test_same_date_in_different_series_is_not_a_duplicate(make_csv):
    path = make_csv(
        "different-series.csv",
        PRICE_HEADERS,
        [
            price_row("22-Oct-2021", series="EQ"),
            price_row("22-Oct-2021", series="BL"),
        ],
    )

    result = run(path)

    assert result.status is Status.PASS
    assert result.metrics["duplicate_date_rows"] == 0
    assert result.metrics["dates_with_multiple_series"] == 1


def test_missing_price_value_fails(make_csv):
    path = make_csv(
        "missing-price.csv",
        PRICE_HEADERS,
        [price_row("22-Oct-2021", close="")],
    )

    result = run(path)

    assert "prices.value_missing" in issue_codes(result)
    assert result.status is Status.FAIL


@pytest.mark.parametrize("bad_value", ["not-a-number", "1,2,3x"])
def test_invalid_price_number_fails(make_csv, bad_value):
    path = make_csv(
        "invalid-price.csv",
        PRICE_HEADERS,
        [price_row("22-Oct-2021", open_price=bad_value)],
    )

    result = run(path)

    assert "prices.value_invalid" in issue_codes(result)


def test_non_positive_price_fails(make_csv):
    path = make_csv(
        "zero-price.csv",
        PRICE_HEADERS,
        [price_row("22-Oct-2021", low="0")],
    )

    result = run(path)

    assert "prices.price_non_positive" in issue_codes(result)


def test_invalid_ohlc_relationship_on_primary_series_fails(make_csv):
    path = make_csv(
        "bad-ohlc.csv",
        PRICE_HEADERS,
        [
            price_row(
                "22-Oct-2021",
                open_price="100",
                high="101",
                low="99",
                close="105",
            )
        ],
    )

    result = run(path)

    assert "prices.ohlc_invalid" in issue_codes(result)
    assert result.status is Status.FAIL


def test_invalid_ohlc_on_auxiliary_series_warns_only(make_csv):
    path = make_csv(
        "bad-ohlc-aux.csv",
        PRICE_HEADERS,
        [
            price_row("22-Oct-2021", series="EQ"),
            price_row(
                "21-Oct-2021",
                series="T0",
                open_price="100",
                high="101",
                low="99",
                close="105",
            ),
        ],
    )

    result = run(path)

    assert "prices.ohlc_invalid_auxiliary" in issue_codes(result)
    assert "prices.ohlc_invalid" not in issue_codes(result)
    assert result.status is Status.WARN


def test_unordered_dates_fail(make_csv):
    path = make_csv(
        "unordered.csv",
        PRICE_HEADERS,
        [
            price_row("22-Oct-2021"),
            price_row("24-Oct-2021"),
            price_row("23-Oct-2021"),
        ],
    )

    result = run(path)

    assert "prices.date_order" in issue_codes(result)
    assert result.metrics["series_date_order"]["EQ"] == "unordered"


def test_large_calendar_gap_warns_without_claiming_missing_sessions(make_csv):
    path = make_csv(
        "gap.csv",
        PRICE_HEADERS,
        [
            price_row("22-Oct-2021"),
            price_row("15-Nov-2021"),
        ],
    )

    result = run(path)

    assert result.status is Status.WARN
    assert "prices.large_calendar_gap" in issue_codes(result)
    gap_issue = next(
        issue for issue in result.issues if issue.code == "prices.large_calendar_gap"
    )
    assert "not classified as a missing trading session" in gap_issue.message


def test_missing_required_column_fails(make_csv):
    headers = [column for column in PRICE_HEADERS if column != "Open Price"]
    row = [
        value
        for column, value in zip(PRICE_HEADERS, price_row("22-Oct-2021"))
        if column != "Open Price"
    ]
    path = make_csv("missing-column.csv", headers, [row])

    result = run(path)

    assert "columns.missing" in issue_codes(result)
    assert result.status is Status.FAIL


def test_unexpected_column_warns(make_csv):
    path = make_csv(
        "unexpected-column.csv",
        [*PRICE_HEADERS, "Surprise"],
        [[*price_row("22-Oct-2021"), "x"]],
    )

    result = run(path)

    assert "columns.unexpected" in issue_codes(result)
    assert result.status is Status.WARN


def test_symbol_mismatch_fails(make_csv):
    path = make_csv(
        "symbol-mismatch.csv",
        PRICE_HEADERS,
        [price_row("22-Oct-2021", symbol="TCS")],
    )

    result = run(path, expected_symbol="INFY")

    assert "prices.symbol_mismatch" in issue_codes(result)


def test_per_symbol_record_counts_and_ranges(make_csv):
    path = make_csv(
        "two-symbols.csv",
        PRICE_HEADERS,
        [
            price_row("22-Oct-2021", symbol="INFY"),
            price_row("21-Oct-2021", symbol="INFY"),
            price_row("22-Oct-2021", symbol="TCS"),
        ],
    )

    result = run(path, expected_symbol=None)

    assert result.metrics["by_symbol"]["INFY"]["rows"] == 2
    assert result.metrics["by_symbol"]["INFY"]["start"] == "2021-10-21"
    assert result.metrics["by_symbol"]["TCS"]["rows"] == 1
    assert result.metrics["series_counts"] == {"EQ": 3}
