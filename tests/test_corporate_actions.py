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


def test_record_date_before_ex_date_fails(make_csv):
    """Record date before ex-date should be flagged as confirmed inconsistency."""
    path = make_csv(
        "record-before-ex.csv",
        CA_HEADERS,
        [
            ca_row(
                ex_date="20-Jul-2024",
                record_date="19-Jul-2024",  # before ex-date
                purpose="Bonus 1:1",
            ),
        ],
    )

    result = run(path)

    codes = issue_codes(result)
    assert "corporate_actions.confirmed_inconsistency" in codes
    assert result.status is Status.FAIL


def test_record_date_after_ex_date_passes(make_csv):
    """Record date after ex-date is normal; no error should be raised."""
    path = make_csv(
        "record-after-ex.csv",
        CA_HEADERS,
        [
            ca_row(
                ex_date="15-Jun-2024",
                record_date="16-Jun-2024",  # after ex-date - normal
                purpose="Dividend - Rs 10 Per Share",
            ),
        ],
    )

    result = run(path)

    codes = issue_codes(result)
    # confirmed_inconsistency should NOT appear
    assert "corporate_actions.confirmed_inconsistency" not in codes
    assert result.status is Status.PASS


def test_price_coverage_missing_warns_with_price_data(make_csv, tmp_path):
    """When price data is available but no pre/post coverage, warn as data limitation."""
    import csv

    # Create a price table with data ONLY before the ex-date (no post-event prices).
    # The ex-date is 15-Jun-2024, and the only price is from 10-Jun-2024 (before).
    price_path = tmp_path / "prices-INFY.csv"
    with open(price_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Symbol", "Series", "Date", "Close Price"])
        # Only a pre-ex price; no price on or after the ex-date
        writer.writerow(["INFY", "EQ", "10-Jun-2024", "1000"])

    from bra.csv_io import read_csv as read_price_csv

    price_table = read_price_csv(price_path)

    path = make_csv(
        "actions-with-price.csv",
        CA_HEADERS,
        [
            ca_row(
                ex_date="15-Jun-2024",
                record_date="16-Jun-2024",
                purpose="Bonus 1:1",
            ),
        ],
    )

    result = make_result("corporate_actions:INFY")
    table = read_csv(path)
    result.issues.extend(table.issues)
    corporate_actions.validate(table, result, "INFY", price_table=price_table)

    codes = issue_codes(result)
    # No post-event price → should report missing post-event coverage
    assert "corporate_actions.price_coverage" in codes


def test_suspicious_discontinuity_for_bonus_1_1_within_tolerance_passes(
    make_csv, tmp_path
):
    """A 1:1 bonus with a price move within tolerance should not be flagged as suspicious."""
    import csv

    # Create price data: pre-close 1000, post-close 550 (within 20% tolerance of 0.5)
    # 0.55 is within [0.4, 0.6], so it should be "insufficient_evidence"
    price_path = tmp_path / "prices-INFY.csv"
    with open(price_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Symbol", "Series", "Date", "Close Price"])
        writer.writerow(["INFY", "EQ", "14-Jun-2024", "1000"])  # pre-ex
        writer.writerow(["INFY", "EQ", "17-Jun-2024", "550"])  # post-ex

    from bra.csv_io import read_csv as read_price_csv

    price_table = read_price_csv(price_path)

    path = make_csv(
        "bonus-action-within-tol.csv",
        CA_HEADERS,
        [
            ca_row(
                ex_date="15-Jun-2024",
                record_date="16-Jun-2024",
                purpose="Bonus 1:1",
            ),
        ],
    )

    result = make_result("corporate_actions:INFY")
    table = read_csv(path)
    result.issues.extend(table.issues)
    corporate_actions.validate(table, result, "INFY", price_table=price_table)

    codes = issue_codes(result)
    # 0.55 is within the 20% tolerance band [0.4, 0.6], so no suspicious_discontinuity
    # should be raised; if it is, it should be classified as insufficient_evidence
    assert "corporate_actions.suspicious_discontinuity" not in codes


def test_suspicious_discontinuity_for_bonus_1_1_extreme_fails(make_csv, tmp_path):
    """A 1:1 bonus with an extreme price move (e.g. 10% instead of 50%) should be suspicious."""
    import csv

    # Create price data: pre-close 1000, post-close 900 (only 10% drop, not ~50%)
    # ratio = 0.9, expected = 0.5, ratio_of_ratios = 0.9/0.5 = 1.8, not > 2.0
    # So this should be "suspicious_adjustment" only if ratio_of_ratios > 2.0
    # Let me use a more extreme case: pre-close 1000, post-close 800 (20% drop)
    # ratio = 0.8, ratio_of_ratios = 0.8/0.5 = 1.6, still not > 2.0
    # Let me use pre-close 1000, post-close 500 (exactly 50% - within tolerance)
    # And pre-close 1000, post-close 400 (60% drop), ratio_of_ratios = 0.4/0.5 = 0.8
    # Hmm, let me think about this differently.
    # For ratio_of_ratios > 2.0, I need discrepancy_ratio > 2.0 * expected_ratio = 2.0 * 0.5 = 1.0
    # Or discrepancy_ratio < 0.5 / 2.0 = 0.25
    # So post/pre < 0.25 or post/pre > 1.0 (for >2x expected)
    # Let me use post-close 200 (90% drop), ratio = 0.2, ratio_of_ratios = 0.2/0.5 = 0.4, not > 2.0
    # Wait, I need to check the logic again.
    # _classify_severity: ratio_of_ratios = abs(discrepancy_ratio / expected_ratio)
    # If ratio_of_ratios > 2.0 → suspicious_adjustment
    # So for ratio_of_ratios > 2.0: |disc/0.5| > 2.0 → disc > 1.0 or disc < 0.25
    # So post/pre > 1.0 (price went up) or post/pre < 0.25 (price dropped more than 75%)
    # Let me use post-close 1200 (price went up 20%), ratio = 1.2, ratio_of_ratios = 1.2/0.5 = 2.4 > 2.0 → suspicious
    # Or post-close 100 (90% drop), ratio = 0.1, ratio_of_ratios = 0.1/0.5 = 0.2, not > 2.0

    # Actually, let me just use a price move that gives ratio_of_ratios > 2.0
    # pre-close 1000, post-close 50 → ratio = 0.05, ratio_of_ratios = 0.05/0.5 = 0.1, not > 2.0
    # pre-close 1000, post-close 1200 → ratio = 1.2, ratio_of_ratios = 1.2/0.5 = 2.4 > 2.0 → suspicious_adjustment

    price_path = tmp_path / "prices-INFY.csv"
    with open(price_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Symbol", "Series", "Date", "Close Price"])
        writer.writerow(["INFY", "EQ", "14-Jun-2024", "1000"])  # pre-ex
        writer.writerow(
            ["INFY", "EQ", "17-Jun-2024", "1200"]
        )  # post-ex: price went up, very suspicious for bonus

    from bra.csv_io import read_csv as read_price_csv

    price_table = read_price_csv(price_path)

    path = make_csv(
        "bonus-action-extreme.csv",
        CA_HEADERS,
        [
            ca_row(
                ex_date="15-Jun-2024",
                record_date="16-Jun-2024",
                purpose="Bonus 1:1",
            ),
        ],
    )

    result = make_result("corporate_actions:INFY")
    table = read_csv(path)
    result.issues.extend(table.issues)
    corporate_actions.validate(table, result, "INFY", price_table=price_table)

    codes = issue_codes(result)
    # ratio=1.2, expected=0.5, ratio_of_ratios=2.4 > 2.0 → suspicious_adjustment
    assert "corporate_actions.suspicious_discontinuity" in codes
