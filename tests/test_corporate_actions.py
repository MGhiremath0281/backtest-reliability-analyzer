"""Corporate-action validation tests."""

from __future__ import annotations

from bra.csv_io import read_csv
from bra.models import Status
from bra.validators import corporate_actions

from .support import CA_HEADERS, ca_row, issue_codes, make_result


def run(path, expected_symbol: str | None = "INFY"):
    table = read_csv(path)
    result = make_result("corporate_actions:INFY")
    result.issues.extend(table.issues)
    corporate_actions.validate(table, result, expected_symbol)
    return result


def test_valid_action_with_book_closure_passes(make_csv):
    path = make_csv(
        "actions.csv",
        CA_HEADERS,
        [
            ca_row(
                purpose="Annual General Meeting",
                record_date="-",
                closure_start="18-Jul-2022",
                closure_end="19-Jul-2022",
            )
        ],
    )

    result = run(path)

    assert result.status is Status.PASS
    assert result.coverage == {
        "date_column": "EX-DATE",
        "start": "2024-06-15",
        "end": "2024-06-15",
    }
    assert result.metrics["by_purpose"]["Annual General Meeting"] == 1


def test_missing_identifiers_and_purpose_fail(make_csv):
    path = make_csv(
        "missing-fields.csv",
        CA_HEADERS,
        [
            ca_row(symbol="", company="", purpose="", ex_date=""),
        ],
    )

    result = run(path, expected_symbol=None)

    codes = issue_codes(result)
    assert "corporate_actions.symbol_missing" in codes
    assert "corporate_actions.company_missing" in codes
    assert "corporate_actions.purpose_missing" in codes
    assert "corporate_actions.ex_date_missing" in codes
    assert result.status is Status.FAIL


def test_invalid_action_dates_fail(make_csv):
    path = make_csv(
        "invalid-dates.csv",
        CA_HEADERS,
        [
            ca_row(
                ex_date="not-a-date",
                record_date="32-Jan-2024",
                closure_start="bad",
                closure_end="also-bad",
            )
        ],
    )

    result = run(path)

    codes = issue_codes(result)
    assert "corporate_actions.ex_date_invalid" in codes
    assert codes.count("corporate_actions.date_invalid") == 3


def test_invalid_book_closure_range_fails(make_csv):
    path = make_csv(
        "closure-range.csv",
        CA_HEADERS,
        [
            ca_row(
                purpose="Annual General Meeting",
                record_date="-",
                closure_start="20-Jul-2024",
                closure_end="19-Jul-2024",
            )
        ],
    )

    result = run(path)

    assert "corporate_actions.closure_range_invalid" in issue_codes(result)


def test_record_date_and_book_closure_both_missing_warns(make_csv):
    path = make_csv(
        "missing-entitlement-date.csv",
        CA_HEADERS,
        [ca_row(record_date="-")],
    )

    result = run(path)

    assert "corporate_actions.record_date_missing" in issue_codes(result)
    assert result.status is Status.WARN


def test_duplicate_corporate_action_fails(make_csv):
    path = make_csv(
        "duplicate-actions.csv",
        CA_HEADERS,
        [ca_row(), ca_row()],
    )

    result = run(path)

    assert "corporate_actions.duplicate_record" in issue_codes(result)
    assert result.metrics["duplicate_records"] == 1


def test_symbol_mismatch_fails(make_csv):
    path = make_csv(
        "symbol-mismatch.csv",
        CA_HEADERS,
        [ca_row(symbol="TCS")],
    )

    result = run(path)

    assert "corporate_actions.symbol_mismatch" in issue_codes(result)


def test_purposes_are_counted_without_type_inference(make_csv):
    path = make_csv(
        "purposes.csv",
        CA_HEADERS,
        [
            ca_row(purpose="Bonus 1:1", ex_date="01-Jan-2024"),
            ca_row(purpose="Buyback", ex_date="02-Jan-2024"),
            ca_row(purpose="Demerger", ex_date="03-Jan-2024"),
        ],
    )

    result = run(path)

    assert result.metrics["by_purpose"] == {
        "Bonus 1:1": 1,
        "Buyback": 1,
        "Demerger": 1,
    }
    assert result.metrics["by_symbol"]["INFY"]["actions"] == 3
    assert result.metrics["by_symbol"]["INFY"]["start"] == "2024-01-01"
