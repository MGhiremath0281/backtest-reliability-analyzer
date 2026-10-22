"""Financial-results validation tests."""

from __future__ import annotations

from bra.csv_io import read_csv
from bra.models import Status
from bra.validators import financials

from .support import (
    INTEGRATED_FINANCIAL_HEADERS,
    LEGACY_FINANCIAL_HEADERS,
    integrated_financial_row,
    issue_codes,
    legacy_financial_row,
    make_result,
)


def run(path, expected_symbol: str | None = None):
    table = read_csv(path)
    result = make_result("financials:INFY")
    result.issues.extend(table.issues)
    financials.validate(table, result, expected_symbol)
    return result


def test_valid_legacy_result_passes_and_keeps_period_separate(make_csv):
    path = make_csv(
        "legacy.csv",
        LEGACY_FINANCIAL_HEADERS,
        [legacy_financial_row()],
    )

    result = run(path, expected_symbol="INFY")

    assert result.status is Status.PASS
    assert result.coverage == {
        "date_column": "PERIOD ENDED",
        "start": "2024-12-31",
        "end": "2024-12-31",
    }
    assert result.metrics["reporting_period_coverage"]["end"] == "2024-12-31"
    assert result.metrics["dissemination_coverage"]["end"] == "2025-01-16"
    assert result.metrics["publication_lag_days"] == {"min": 16, "max": 16}


def test_missing_and_invalid_period_fail(make_csv):
    path = make_csv(
        "bad-period.csv",
        LEGACY_FINANCIAL_HEADERS,
        [
            legacy_financial_row(period=""),
            legacy_financial_row(period="31-Xxx-2024"),
        ],
    )

    result = run(path)

    codes = issue_codes(result)
    assert "financials.period_missing" in codes
    assert "financials.period_invalid" in codes


def test_missing_dissemination_timestamp_fails(make_csv):
    path = make_csv(
        "missing-dissemination.csv",
        LEGACY_FINANCIAL_HEADERS,
        [legacy_financial_row(disseminated="")],
    )

    result = run(path)

    assert "financials.dissemination_missing" in issue_codes(result)
    assert result.status is Status.FAIL


def test_invalid_dissemination_timestamp_fails(make_csv):
    path = make_csv(
        "invalid-dissemination.csv",
        LEGACY_FINANCIAL_HEADERS,
        [legacy_financial_row(disseminated="16/01/2025 19:42")],
    )

    result = run(path)

    assert "financials.dissemination_invalid" in issue_codes(result)


def test_dissemination_before_reporting_period_end_fails(make_csv):
    path = make_csv(
        "look-ahead.csv",
        LEGACY_FINANCIAL_HEADERS,
        [
            legacy_financial_row(
                period="31-Dec-2024",
                received="01-Dec-2024 10:00:00",
                disseminated="02-Dec-2024 10:00:00",
            )
        ],
    )

    result = run(path)

    assert "financials.disseminated_before_period" in issue_codes(result)
    assert result.status is Status.FAIL


def test_received_after_dissemination_warns(make_csv):
    path = make_csv(
        "timestamp-order.csv",
        LEGACY_FINANCIAL_HEADERS,
        [
            legacy_financial_row(
                received="16-Jan-2025 20:00:00",
                disseminated="16-Jan-2025 19:42:44",
            )
        ],
    )

    result = run(path)

    assert "financials.dissemination_before_secondary_timestamp" in issue_codes(result)
    assert result.status is Status.WARN


def test_duplicate_result_fails(make_csv):
    path = make_csv(
        "duplicate-results.csv",
        LEGACY_FINANCIAL_HEADERS,
        [legacy_financial_row(), legacy_financial_row()],
    )

    result = run(path)

    assert "financials.duplicate_record" in issue_codes(result)
    assert result.metrics["duplicate_records"] == 1


def test_consolidated_and_standalone_results_are_not_duplicates(make_csv):
    path = make_csv(
        "consolidation.csv",
        LEGACY_FINANCIAL_HEADERS,
        [
            legacy_financial_row(consolidation="Consolidated"),
            legacy_financial_row(consolidation="Non-Consolidated"),
        ],
    )

    result = run(path)

    assert "financials.duplicate_record" not in issue_codes(result)


def test_integrated_schema_with_newline_headers_and_symbol_mismatch(make_csv):
    path = make_csv(
        "integrated.csv",
        INTEGRATED_FINANCIAL_HEADERS,
        [integrated_financial_row(symbol="TCS")],
    )

    result = run(path, expected_symbol="INFY")

    codes = issue_codes(result)
    assert "csv.header_whitespace" in codes
    assert "financials.symbol_mismatch" in codes
    assert result.metrics["schema"] == "integrated_financials"


def test_integrated_dissemination_before_broadcast_warns(make_csv):
    path = make_csv(
        "integrated-order.csv",
        INTEGRATED_FINANCIAL_HEADERS,
        [
            integrated_financial_row(
                broadcast="16-Jan-2025 19:43:00",
                disseminated="16-Jan-2025 19:42:44",
            )
        ],
    )

    result = run(path)

    assert "financials.dissemination_before_secondary_timestamp" in issue_codes(result)
    assert result.status is Status.WARN


def test_missing_important_field_warns(make_csv):
    path = make_csv(
        "important-field.csv",
        INTEGRATED_FINANCIAL_HEADERS,
        [integrated_financial_row(consolidation="")],
    )

    result = run(path)

    assert "financials.important_field_missing" in issue_codes(result)
    assert result.status is Status.WARN
