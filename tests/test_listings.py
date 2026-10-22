"""Listing, name/symbol change, and delisting validation tests."""

from __future__ import annotations

from bra.csv_io import read_csv
from bra.models import Status
from bra.validators import listings

from .support import (
    CURRENT_LISTING_HEADERS,
    DELISTING_HEADERS,
    NAME_CHANGE_HEADERS,
    SYMBOL_CHANGE_HEADERS,
    current_listing_row,
    delisting_row,
    issue_codes,
    make_result,
    name_change_row,
    symbol_change_row,
)


def run_current(path):
    table = read_csv(path)
    result = make_result("current_listing")
    result.issues.extend(table.issues)
    listings.validate_current_listing(table, result)
    return result


def run_names(path):
    table = read_csv(path)
    result = make_result("name_changes")
    result.issues.extend(table.issues)
    listings.validate_name_changes(table, result)
    return result


def run_symbols(path):
    table = read_csv(path)
    result = make_result("symbol_changes")
    result.issues.extend(table.issues)
    listings.validate_symbol_changes(table, result)
    return result


def run_delistings(path, scope="all_board_delistings_2021_2026"):
    table = read_csv(path)
    result = make_result("delistings")
    result.issues.extend(table.issues)
    listings.validate_delistings(table, result, scope=scope)
    return result


def test_valid_current_listing_passes(make_csv):
    path = make_csv(
        "listing.csv",
        CURRENT_LISTING_HEADERS,
        [current_listing_row()],
    )

    result = run_current(path)

    assert result.status is Status.PASS
    assert result.coverage == {
        "date_column": "DATE OF LISTING",
        "start": "2008-10-06",
        "end": "2008-10-06",
    }
    assert result.metrics["scope"] == "current_listing_reference"


def test_duplicate_symbol_and_series_fails(make_csv):
    path = make_csv(
        "duplicate-listing.csv",
        CURRENT_LISTING_HEADERS,
        [current_listing_row(), current_listing_row()],
    )

    result = run_current(path)

    assert "listings.duplicate_record" in issue_codes(result)
    assert result.metrics["duplicate_records"] == 1


def test_same_isin_with_different_series_is_allowed(make_csv):
    path = make_csv(
        "multi-series-listing.csv",
        CURRENT_LISTING_HEADERS,
        [
            current_listing_row(series="EQ"),
            current_listing_row(series="BE"),
        ],
    )

    result = run_current(path)

    assert "listings.duplicate_record" not in issue_codes(result)


def test_invalid_listing_date_and_missing_isin_fail(make_csv):
    path = make_csv(
        "bad-listing.csv",
        CURRENT_LISTING_HEADERS,
        [current_listing_row(listing_date="not-a-date", isin="")],
    )

    result = run_current(path)

    codes = issue_codes(result)
    assert "listings.listing_date_invalid" in codes
    assert "listings.isin_missing" in codes


def test_invalid_isin_format_warns(make_csv):
    path = make_csv(
        "bad-isin.csv",
        CURRENT_LISTING_HEADERS,
        [current_listing_row(isin="INVALID")],
    )

    result = run_current(path)

    assert "listings.isin_format_invalid" in issue_codes(result)
    assert result.status is Status.WARN


def test_valid_name_change_passes(make_csv):
    path = make_csv(
        "namechange.csv",
        NAME_CHANGE_HEADERS,
        [name_change_row()],
    )

    result = run_names(path)

    assert result.status is Status.PASS
    assert result.metrics["by_symbol"]["INFY"]["records"] == 1


def test_duplicate_name_change_fails(make_csv):
    path = make_csv(
        "duplicate-namechange.csv",
        NAME_CHANGE_HEADERS,
        [name_change_row(), name_change_row()],
    )

    result = run_names(path)

    assert "listings.duplicate_record" in issue_codes(result)
    assert result.metrics["duplicate_records"] == 1


def test_bad_effective_date_fails(make_csv):
    path = make_csv(
        "bad-effective-date.csv",
        NAME_CHANGE_HEADERS,
        [name_change_row(effective_date="31-Feb-2024")],
    )

    result = run_names(path)

    assert "listings.effective_date_invalid" in issue_codes(result)


def test_valid_symbol_change_passes(make_csv):
    path = make_csv(
        "symbolchange.csv",
        SYMBOL_CHANGE_HEADERS,
        [symbol_change_row()],
    )

    result = run_symbols(path)

    assert result.status is Status.PASS
    assert result.metrics["by_new_symbol"]["INFY"]["records"] == 1


def test_missing_company_name_warns_but_missing_symbol_fails(make_csv):
    path = make_csv(
        "symbolchange-missing.csv",
        SYMBOL_CHANGE_HEADERS,
        [
            symbol_change_row(name=""),
            symbol_change_row(old_symbol="", new_symbol=""),
        ],
    )

    result = run_symbols(path)

    codes = issue_codes(result)
    assert "listings.company_name_missing" in codes
    assert "listings.old_symbol_missing" in codes
    assert "listings.new_symbol_missing" in codes
    assert result.status is Status.FAIL


def test_identical_old_and_new_symbol_warns(make_csv):
    path = make_csv(
        "noop-symbolchange.csv",
        SYMBOL_CHANGE_HEADERS,
        [symbol_change_row(old_symbol="INFY", new_symbol="INFY")],
    )

    result = run_symbols(path)

    assert "listings.symbol_change_noop" in issue_codes(result)
    assert result.status is Status.WARN


def test_valid_delisting_passes_and_reports_scope(make_csv):
    path = make_csv(
        "delistings.csv",
        DELISTING_HEADERS,
        [delisting_row()],
    )

    result = run_delistings(path, scope="main_board_delistings_2021_2026")

    assert result.status is Status.PASS
    assert result.coverage == {
        "date_column": "Delisted Date",
        "start": "2024-01-15",
        "end": "2024-01-15",
    }
    assert result.metrics["scope"] == "main_board_delistings_2021_2026"
    assert result.metrics["by_board"] == {"Main Board": 1}
    assert result.metrics["by_type"] == {"Voluntary Delisting": 1}


def test_duplicate_delisting_fails(make_csv):
    path = make_csv(
        "duplicate-delistings.csv",
        DELISTING_HEADERS,
        [delisting_row(), delisting_row()],
    )

    result = run_delistings(path)

    assert "delistings.duplicate_record" in issue_codes(result)
    assert result.metrics["duplicate_records"] == 1


def test_invalid_delisting_date_and_missing_identifiers_fail(make_csv):
    path = make_csv(
        "bad-delistings.csv",
        DELISTING_HEADERS,
        [
            delisting_row(
                symbol="",
                isin="",
                name="",
                board="",
                delisted_date="not-a-date",
                delisting_type="",
            )
        ],
    )

    result = run_delistings(path)

    codes = issue_codes(result)
    assert "delistings.symbol_missing" in codes
    assert "delistings.isin_missing" in codes
    assert "delistings.company_name_missing" in codes
    assert "delistings.board_missing" in codes
    assert "delistings.date_invalid" in codes
    assert "delistings.type_missing" in codes


def test_delisting_identifier_whitespace_and_isin_format_warn(make_csv):
    path = make_csv(
        "messy-delistings.csv",
        DELISTING_HEADERS,
        [
            delisting_row(symbol="OLDTECH ", isin="INE123A01018 *"),
            delisting_row(symbol="OTHER", isin="INE456A01019", board="Main Board "),
        ],
    )

    result = run_delistings(path)

    codes = issue_codes(result)
    assert "delistings.identifier_whitespace" in codes
    assert "listings.isin_format_invalid" in codes
    assert result.status is Status.WARN
