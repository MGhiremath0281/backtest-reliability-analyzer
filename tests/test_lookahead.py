"""Tests for the Look-Ahead-Bias Analyzer.

All fixtures are built in-memory or under ``tmp_path``. The collected source
datasets under ``data/`` are never read or modified.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from bra import cli
from bra.csv_io import Row, Table
from bra.models import Status
from bra.runner import run_validation
from bra.validators import lookahead
from bra.validators.lookahead import (
    LookaheadConfig,
    build_lookahead_config,
    validate_config,
)

from .support import (
    CA_HEADERS,
    CURRENT_LISTING_HEADERS,
    LEGACY_FINANCIAL_HEADERS,
    PRICE_HEADERS,
    ca_row,
    create_valid_data_root,
    current_listing_row,
    legacy_financial_row,
    price_row,
    write_csv,
)


def make_table(
    kind: str,
    headers: list[str],
    rows: list[list[str]],
    *,
    filename: str | None = None,
) -> Table:
    """Build an in-memory CSV table for one dataset kind."""

    path = Path(filename or f"{kind}.csv")
    table_rows = [
        Row(index + 2, dict(zip(headers, row))) for index, row in enumerate(rows)
    ]
    return Table(path=path, headers=list(headers), rows=table_rows)


INTEGRATED_FINANCIAL_HEADERS = [
    "SYMBOL",
    "COMPANY NAME",
    "QUARTER END DATE",
    "TYPE OF SUBMISSION",
    "XBRL",
    "BROADCAST DATE/TIME",
    "REVISED DATE/TIME",
    "REVISION REMARKS",
    "EXCHANGE DISSEMINATION TIME",
    "TIME TAKEN",
]

DERIVED_LEGACY_FINANCIAL_HEADERS = [
    "symbol",
    "company_name",
    "period_end_date",
    "exchange_received_time",
    "exchange_dissemination_time",
]

DERIVED_INTEGRATED_FINANCIAL_HEADERS = [
    "symbol",
    "company_name",
    "quarter_end_date",
    "submission_type",
    "broadcast_datetime",
    "revised_datetime",
    "exchange_dissemination_time",
]

DERIVED_PRICE_HEADERS = ["symbol", "series", "trade_date", "close"]

DERIVED_ACTION_HEADERS = [
    "symbol",
    "company_name",
    "series",
    "purpose",
    "face_value",
    "ex_date",
    "record_date",
    "book_closure_start_date",
    "book_closure_end_date",
]

INDEX_SNAPSHOT_HEADERS = [
    "symbol",
    "security_name",
    "industry",
    "close_price",
    "index_mcap_cr",
    "weightage_pct",
    "snapshot_date",
    "index_name",
    "source_pdf",
]


def integrated_financial_row(
    *,
    symbol: str = "INFY",
    company: str = "Infosys Limited",
    period: str = "31-Dec-2024",
    submission: str = "Original",
    broadcast: str = "16-Jan-2025 19:42:00",
    revised: str = "",
    remarks: str = "",
    disseminated: str = "16-Jan-2025 19:42:44",
) -> list[str]:
    return [
        symbol,
        company,
        period,
        submission,
        "https://example.invalid/xbrl.xml",
        broadcast,
        revised,
        remarks,
        disseminated,
        "00:00:44",
    ]


def derived_legacy_row(
    *,
    company: str = "Infosys Limited",
    period: str = "31-Dec-2024",
    received: str = "16-Jan-2025 19:42:10",
    disseminated: str = "16-Jan-2025 19:42:44",
) -> list[str]:
    return [
        "INFY",
        company,
        period,
        received,
        disseminated,
    ]


def derived_integrated_row(
    *,
    symbol: str = "INFY",
    company: str = "Infosys Limited",
    period: str = "31-Dec-2024",
    submission: str = "Original",
    broadcast: str = "16-Jan-2025 19:42:00",
    revised: str = "",
    disseminated: str = "16-Jan-2025 19:42:44",
) -> list[str]:
    return [
        symbol,
        company,
        period,
        submission,
        broadcast,
        revised,
        disseminated,
    ]


def derived_price_row(
    trade_date: str,
    *,
    symbol: str = "INFY",
) -> list[str]:
    return [symbol, "EQ", trade_date, "105"]


def derived_action_row(
    *,
    symbol: str = "INFY",
    ex_date: str = "15-Jun-2024",
    record_date: str = "16-Jun-2024",
    purpose: str = "Dividend - Rs 10 Per Share",
) -> list[str]:
    return [
        symbol,
        "Infosys Limited",
        "EQ",
        purpose,
        "5",
        ex_date,
        record_date,
        "-",
        "-",
    ]


def snapshot_row(symbol: str, snapshot_date: str, index_name: str = "NIFTY 50"):
    return [
        symbol,
        f"{symbol} Limited",
        "General",
        "100",
        "1000",
        "1.0",
        snapshot_date,
        index_name,
        f"{index_name.replace(' ', '_')}.pdf",
    ]


def tables_for(**tables: Table) -> dict[str, list[Table]]:
    return {kind: [table] for kind, table in tables.items()}


def issue_codes(result) -> list[str]:
    return [issue.code for issue in result.issues]


def finding_codes(result) -> list[str]:
    return [entry["code"] for entry in result.metrics["findings"]["detailed_findings"]]


def checks_by_name(result) -> dict[str, dict]:
    return {
        check["check"]: check
        for check in result.metrics["backtest_assessment"]["checks"]
    }


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def test_financial_records_from_legacy_raw_uses_filename_symbol():
    table = make_table(
        "financials",
        LEGACY_FINANCIAL_HEADERS,
        [legacy_financial_row()],
        filename="CF-FR-equities-TCS-22-10-2021-to-22-10-2026.csv",
    )
    records = lookahead.analyze(Path("/tmp/root"), tables_for(financials=table))  # noqa: S108 - inert paths
    assert records.row_count == 1  # noqa: F821


def test_financial_record_symbols_and_kinds():
    legacy = make_table(
        "financials",
        LEGACY_FINANCIAL_HEADERS,
        [legacy_financial_row()],
        filename="CF-FR-equities-TCS-22-10-2021-to-22-10-2026.csv",
    )
    integrated = make_table(
        "integrated_financials",
        INTEGRATED_FINANCIAL_HEADERS,
        [integrated_financial_row()],
    )
    tables = tables_for(financials=legacy, integrated_financials=integrated)
    records = lookahead.core.financial_records(tables)

    assert len(records) == 2
    assert {record.symbol for record in records} == {"TCS", "INFY"}
    assert {record.kind for record in records} == {
        "financials",
        "integrated_financials",
    }
    for record in records:
        assert record.period_end == date(2024, 12, 31)
        assert record.dissemination is not None
        assert not record.revision_present


def test_derived_tables_preferred_over_raw():
    raw = make_table(
        "financials",
        LEGACY_FINANCIAL_HEADERS,
        [legacy_financial_row()],
        filename="CF-FR-equities-INFY-22-10-2021-to-22-10-2026.csv",
    )
    derived = make_table(
        "derived_financials_legacy",
        DERIVED_LEGACY_FINANCIAL_HEADERS,
        [derived_legacy_row(period="31-Mar-2025")],
    )
    tables = tables_for(financials=raw, derived_financials_legacy=derived)
    records = lookahead.core.financial_records(tables)

    assert [record.period_end for record in records] == [date(2025, 3, 31)]
    assert records[0].kind == "derived_financials_legacy"


def test_unparseable_timestamps_reported_and_excluded():
    table = make_table(
        "financials",
        LEGACY_FINANCIAL_HEADERS,
        [
            legacy_financial_row(disseminated="16-Jan-2025 ??"),
        ],
        filename="CF-FR-equities-INFY-22-10-2021-to-22-10-2026.csv",
    )
    result = lookahead.analyze(Path("/tmp/root"), tables_for(financials=table))  # noqa: S108 - inert paths

    codes = issue_codes(result)
    assert "lookahead.timestamp_unparseable" in codes
    assert "lookahead.publication_timestamp_missing" in codes
    assert result.metrics["financial_publication"]["publication_missing"] == 1
    assert result.row_count == 1


def test_sentinel_values_are_skipped_not_used():
    table = make_table(
        "financials",
        LEGACY_FINANCIAL_HEADERS,
        [legacy_financial_row(received="-", disseminated="--")],
        filename="CF-FR-equities-INFY-22-10-2021-to-22-10-2026.csv",
    )
    result = lookahead.analyze(Path("/tmp/root"), tables_for(financials=table))  # noqa: S108 - inert paths

    pub = result.metrics["financial_publication"]
    assert pub["publication_missing"] == 1
    assert "lookahead.timestamp_unparseable" not in issue_codes(result)


def test_price_rows_without_dates_are_excluded():
    table = make_table(
        "derived_prices",
        DERIVED_PRICE_HEADERS,
        [
            derived_price_row("2024-06-28"),
            derived_price_row("not-a-date"),
        ],
    )
    prices, undated = lookahead.core._price_records_with_counts(
        tables_for(derived_prices=table)
    )

    assert len(prices) == 1
    assert undated == 1


# ---------------------------------------------------------------------------
# Confirmed publication/revision violations
# ---------------------------------------------------------------------------


def test_dissemination_before_period_is_confirmed_violation():
    table = make_table(
        "financials",
        LEGACY_FINANCIAL_HEADERS,
        [
            legacy_financial_row(
                period="31-Dec-2024",
                received="13-Jan-2025 10:00:00",
                disseminated="15-Dec-2024 10:00:44",  # before period end
            ),
        ],
        filename="CF-FR-equities-INFY-22-10-2021-to-22-10-2026.csv",
    )
    result = lookahead.analyze(Path("/tmp/root"), tables_for(financials=table))  # noqa: S108 - inert paths

    pub = result.metrics["financial_publication"]
    assert pub["before_period_count"] == 1
    assert pub["before_period"][0]["publication"] == "2024-12-15 10:00:44"
    entry = next(
        item
        for item in result.metrics["findings"]["detailed_findings"]
        if item["code"] == "lookahead.publication_before_period"
    )
    assert entry["kind"] == "confirmed_lookahead_violation"
    assert entry["counts"] == {"violations": 1}
    assert "lookahead.publication_before_period" in issue_codes(result)


def test_dissemination_before_received_is_confirmed_violation():
    table = make_table(
        "financials",
        LEGACY_FINANCIAL_HEADERS,
        [
            legacy_financial_row(
                received="20-Jan-2025 10:00:00",
                disseminated="16-Jan-2025 10:00:44",
            ),
        ],
        filename="CF-FR-equities-INFY-22-10-2021-to-22-10-2026.csv",
    )
    result = lookahead.analyze(Path("/tmp/root"), tables_for(financials=table))  # noqa: S108 - inert paths

    pub = result.metrics["financial_publication"]
    assert pub["dissemination_before_receipt_count"] == 1
    assert "lookahead.dissemination_before_receipt" in issue_codes(result)


def test_revision_before_original_publication_is_confirmed():
    original = integrated_financial_row(
        broadcast="10-Jan-2025 10:00:00",
        disseminated="10-Jan-2025 10:00:30",
    )
    revised = integrated_financial_row(
        submission="Revised",
        revised="05-Jan-2025 09:00:00",
        disseminated="05-Jan-2025 09:00:45",
    )
    table = make_table(
        "integrated_financials",
        INTEGRATED_FINANCIAL_HEADERS,
        [original, revised],
    )
    result = lookahead.analyze(Path("/tmp/root"), tables_for(integrated_financials=table))  # noqa: S108 - inert paths

    rev = result.metrics["financial_revisions"]
    assert rev["revision_rows"] == 1
    assert rev["revision_before_publication_count"] == 1
    assert rev["restatement_window_count"] == 0
    assert "lookahead.revision_used_before_public" in issue_codes(result)
    summary = result.metrics["findings"]["confirmed_lookahead_violations"]
    assert "revisions precede the publication they correct" in summary


def test_revision_after_publication_creates_restatement_window():
    original = integrated_financial_row(
        broadcast="10-Jan-2025 10:00:00",
        disseminated="10-Jan-2025 10:00:30",
    )
    revised = integrated_financial_row(
        submission="Revised",
        revised="01-Mar-2025 09:00:00",
        disseminated="01-Mar-2025 09:00:45",
    )
    table = make_table(
        "integrated_financials",
        INTEGRATED_FINANCIAL_HEADERS,
        [original, revised],
    )
    result = lookahead.analyze(Path("/tmp/root"), tables_for(integrated_financials=table))  # noqa: S108 - inert paths

    rev = result.metrics["financial_revisions"]
    assert rev["revision_before_publication_count"] == 0
    assert rev["restatement_window_count"] == 1
    assert rev["restatement_windows"][0]["window"] == {
        "start": "2025-01-10 10:00:00",
        "end": "2025-03-01 09:00:00",
    }
    assert "lookahead.restatement_window" in issue_codes(result)


def test_revised_only_period_makes_no_ordering_claim():
    revised = integrated_financial_row(
        submission="Revised",
        revised="01-Mar-2025 09:00:00",
        disseminated="01-Mar-2025 09:00:45",
    )
    table = make_table(
        "integrated_financials",
        INTEGRATED_FINANCIAL_HEADERS,
        [revised],
    )
    result = lookahead.analyze(Path("/tmp/root"), tables_for(integrated_financials=table))  # noqa: S108 - inert paths

    rev = result.metrics["financial_revisions"]
    assert rev["revision_rows"] == 1
    assert rev["revision_before_publication_count"] == 0
    assert rev["restatement_window_count"] == 0


# ---------------------------------------------------------------------------
# Corporate actions and price evidence
# ---------------------------------------------------------------------------


def test_record_date_before_ex_date_is_suspicious():
    table = make_table(
        "corporate_actions",
        CA_HEADERS,
        [ca_row(ex_date="16-Jun-2024", record_date="15-Jun-2024")],
    )
    result = lookahead.analyze(Path("/tmp/root"), tables_for(corporate_actions=table))  # noqa: S108 - inert paths

    actions = result.metrics["corporate_action_timing"]
    assert actions["record_before_ex_count"] == 1
    assert "lookahead.record_date_before_ex_date" in issue_codes(result)
    summary = result.metrics["findings"]["potential_lookahead_risks"]
    assert "record dates precede ex dates" in summary


def test_action_without_ex_date_is_insufficient():
    table = make_table(
        "corporate_actions",
        CA_HEADERS,
        [ca_row(ex_date="-", record_date="16-Jun-2024")],
    )
    result = lookahead.analyze(Path("/tmp/root"), tables_for(corporate_actions=table))  # noqa: S108 - inert paths

    assert "lookahead.ex_date_missing" in issue_codes(result)
    assert (
        result.metrics["corporate_action_timing"]["ex_date_missing"] == 1
    )


def test_announcement_unavailable_is_reported_when_actions_exist():
    table = make_table("corporate_actions", CA_HEADERS, [ca_row()])
    result = lookahead.analyze(Path("/tmp/root"), tables_for(corporate_actions=table))  # noqa: S108 - inert paths

    assert "lookahead.announcement_timestamp_unavailable" in issue_codes(result)
    entry = next(
        item
        for item in result.metrics["findings"]["detailed_findings"]
        if item["code"] == "lookahead.announcement_timestamp_unavailable"
    )
    assert entry["kind"] == "insufficient_lookahead_evidence"
    assert "EX-DATE" in actions_note(result)  # noqa: F821


def actions_note(result) -> str:
    return next(
        item["explanation"]
        for item in result.metrics["findings"]["detailed_findings"]
        if item["code"] == "lookahead.announcement_timestamp_unavailable"
    )


def test_pre_event_price_coverage_measured():
    actions = make_table(
        "corporate_actions",
        CA_HEADERS,
        [ca_row(ex_date="15-Jun-2024")],
    )
    prices = make_table(
        "derived_prices",
        DERIVED_PRICE_HEADERS,
        [derived_price_row("10-Jun-2024"), derived_price_row("18-Jun-2024")],
    )
    result = lookahead.analyze(
        Path("/tmp/root"),  # noqa: S108 - inert paths
        tables_for(corporate_actions=actions, derived_prices=prices),
    )
    coverage = result.metrics["corporate_action_timing"]["event_price_coverage"]
    assert coverage == {
        **coverage,
        "evaluable_actions": 1,
        "pre_event_prices_present": 1,
        "pre_event_prices_missing": 0,
    }
    assert (
        "every_action_has_pre_event_price_rows"
        in result.metrics["findings"]["checks_passed"]
    )


def test_missing_pre_event_prices_is_insufficient():
    actions = make_table(
        "corporate_actions",
        CA_HEADERS,
        [ca_row(ex_date="15-Jun-2024", symbol="NEWCO")],
    )
    prices = make_table(
        "derived_prices",
        DERIVED_PRICE_HEADERS,
        [derived_price_row("18-Jun-2024", symbol="NEWCO")],
    )
    result = lookahead.analyze(
        Path("/tmp/root"),  # noqa: S108 - inert paths
        tables_for(corporate_actions=actions, derived_prices=prices),
    )
    coverage = result.metrics["corporate_action_timing"]["event_price_coverage"]
    assert coverage["pre_event_prices_missing"] == 1
    assert "lookahead.pre_event_price_missing" in issue_codes(result)
    assert result.metrics["findings"]["insufficient_lookahead_evidence"]  # nonempty


def test_unpriced_action_symbol_is_listed_without_coverage_class():
    actions = make_table(
        "corporate_actions",
        CA_HEADERS,
        [ca_row(ex_date="15-Jun-2024", symbol="UNPRICED")],
    )
    result = lookahead.analyze(
        Path("/tmp/root"),  # noqa: S108 - inert paths
        tables_for(corporate_actions=actions),
    )
    coverage = result.metrics["corporate_action_timing"]["event_price_coverage"]
    assert coverage["evaluable_actions"] == 0
    assert coverage["symbols_without_price_count"] == 1
    assert coverage["symbols_without_prices"] == ["UNPRICED"]


def test_price_availability_limit_is_reported():
    prices = make_table(
        "derived_prices",
        DERIVED_PRICE_HEADERS,
        [derived_price_row("2024-06-28")],
    )
    result = lookahead.analyze(Path("/tmp/root"), tables_for(derived_prices=prices))  # noqa: S108 - inert paths

    assert "lookahead.price_availability_unknown" in issue_codes(result)
    assert result.metrics["price_availability"]["rows"] == 1
    assert result.metrics["price_availability"]["date_range"] == {
        "start": "2024-06-28",
        "end": "2024-06-28",
    }


# ---------------------------------------------------------------------------
# Membership snapshots and the point-in-time universe
# ---------------------------------------------------------------------------


def test_snapshot_summary_counts_and_dates():
    snapshots = make_table(
        "index_snapshot",
        INDEX_SNAPSHOT_HEADERS,
        [
            snapshot_row("INFY", "2022-03-31"),
            snapshot_row("TCS", "2022-03-31"),
            snapshot_row("INFY", "2026-09-30"),
        ],
    )
    result = lookahead.analyze(Path("/tmp/root"), tables_for(index_snapshot=snapshots))  # noqa: S108 - inert paths

    universe = result.metrics["point_in_time_universe"]
    assert universe["snapshot_count"] == 2
    assert universe["distinct_symbols"] == 2
    assert universe["date_range"] == {"start": "2022-03-31", "end": "2026-09-30"}
    assert universe["interpolation_performed"] is False
    assert (
        "lookahead.point_in_time_universe_missing" not in issue_codes(result)
    )
    assert result.metrics["data_facts"]["membership_snapshot_count"] == 2


def test_no_snapshots_warns_point_in_time_universe_missing():
    result = lookahead.analyze(Path("/tmp/root"), {})
    assert "lookahead.point_in_time_universe_missing" in issue_codes(result)
    entry = next(
        item
        for item in result.metrics["findings"]["detailed_findings"]
        if item["code"] == "lookahead.point_in_time_universe_missing"
    )
    assert entry["remediation"]


def test_missing_current_listing_reference_warns():
    financial = make_table(
        "financials",
        LEGACY_FINANCIAL_HEADERS,
        [legacy_financial_row()],
        filename="CF-FR-equities-INFY-22-10-2021-to-22-10-2026.csv",
    )
    result = lookahead.analyze(Path("/tmp/root"), tables_for(financials=financial))  # noqa: S108 - inert paths

    assert "lookahead.current_listing_missing" in issue_codes(result)


def test_current_listing_rows_are_parsed_without_membership_claims():
    listings = make_table(
        "current_listing",
        CURRENT_LISTING_HEADERS,
        [current_listing_row(), current_listing_row(symbol="TCS")],
    )
    result = lookahead.analyze(Path("/tmp/root"), tables_for(current_listing=listings))  # noqa: S108 - inert paths

    assert result.metrics["data_facts"]["listing_rows"] == 2
    entry = next(
        item
        for item in result.metrics["findings"]["detailed_findings"]
        if item["code"] == "lookahead.point_in_time_universe_missing"
    )
    assert "never treated as historical membership" in entry["explanation"]


# ---------------------------------------------------------------------------
# Configuration building and validation
# ---------------------------------------------------------------------------


def test_build_config_normalizes_input():
    config, errors = build_lookahead_config(
        target_index=" NIFTY 50 ",
        start_date="2024-01-01",
        end_date=date(2024, 12, 31),
        universe_symbols=[" infy ", "", "TCS"],
        decision_dates=["2024-07-01", "2024-01-05", "2024-07-01"],
        lookback_days=20,
    )
    assert errors == []
    assert config.target_index == "NIFTY 50"
    assert config.universe_symbols == ("INFY", "TCS")
    assert config.decision_dates == (date(2024, 1, 5), date(2024, 7, 1))
    assert config.end_date == date(2024, 12, 31)


def test_build_config_reports_all_errors():
    config, errors = build_lookahead_config(
        start_date="2024-06-01",
        end_date=None,
        decision_dates=["2024-13-01"],
        lookback_days=-3,
    )
    assert config is None
    joined = "; ".join(errors)
    assert "backtest start and end dates must both be provided" in joined
    assert "decision date could not be parsed" in joined
    assert "lookback_days must not be negative" in joined


def test_validate_config_reports_interval_and_membership_problems():
    config = LookaheadConfig(
        start_date=date(2024, 1, 1),
        end_date=date(2023, 12, 31),
        decision_dates=(date(2025, 1, 1),),
        membership_snapshot_dates=(date(2020, 1, 1),),
    )
    errors = validate_config(config)
    joined = " | ".join(errors)
    assert "backtest start 2024-01-01 is after backtest end 2023-12-31" in joined
    assert "decision date(s) fall outside the backtest interval" in joined
    assert "membership snapshot date(s) fall outside" in joined


def test_membership_dates_and_decisions_inside_interval_are_valid():
    config = LookaheadConfig(
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        decision_dates=(date(2024, 6, 28),),
        membership_snapshot_dates=(date(2024, 3, 31),),
        lookback_days=90,
    )
    assert validate_config(config) == []


# ---------------------------------------------------------------------------
# Backtest-specific assessment
# ---------------------------------------------------------------------------


def base_tables():
    financial = make_table(
        "financials",
        LEGACY_FINANCIAL_HEADERS,
        [legacy_financial_row(period="31-Dec-2023")],
        filename="CF-FR-equities-INFY-22-10-2021-to-22-10-2026.csv",
    )
    listing = make_table(
        "current_listing",
        CURRENT_LISTING_HEADERS,
        [current_listing_row()],
    )
    return tables_for(financials=financial, current_listing=listing)


def test_without_config_only_the_general_audit_runs():
    result = lookahead.analyze(Path("/tmp/root"), base_tables())  # noqa: S108 - inert paths

    assert result.metrics["analysis"]["mode"] == "general_temporal_evidence_audit"
    assert result.metrics["analysis"]["backtest_config_supplied"] is False
    assert (
        result.metrics["backtest_assessment"]["status"] == "unavailable"
    )
    assert "reason" in result.metrics["backtest_assessment"]
    assert "impact" in result.metrics["findings"]["backtest_specific_results"] or (
        "how_to_enable"
        in result.metrics["findings"]["backtest_specific_results"]
    )


def test_invalid_config_is_reported_as_invalid():
    config = LookaheadConfig(start_date=date(2024, 6, 1), end_date=date(2024, 1, 1))
    result = lookahead.analyze(Path("/tmp/root"), base_tables(), config=config)  # noqa: S108 - inert paths

    assert result.metrics["backtest_assessment"]["status"] == "invalid"
    codes = issue_codes(result)
    assert "lookahead.backtest_config_invalid" in codes
    entry = next(
        item
        for item in result.metrics["findings"]["detailed_findings"]
        if item["code"] == "lookahead.backtest_config_invalid"
    )
    assert "2024-06-01 is after" in "; ".join(entry["evidence"]["errors"])


def test_confirmed_future_membership_reliance():
    snapshots = make_table(
        "index_snapshot",
        INDEX_SNAPSHOT_HEADERS,
        [snapshot_row("INFY", "2023-06-30")],
    )
    config = LookaheadConfig(
        decision_dates=(date(2023, 1, 1), date(2024, 1, 1)),
        membership_snapshot_dates=(date(2023, 6, 30),),
        universe_symbols=("INFY",),
    )
    result = lookahead.analyze(
        Path("/tmp/root"),  # noqa: S108 - inert paths
        {**base_tables(), "index_snapshot": [snapshots]},
        config=config,
    )
    check = checks_by_name(result)["point_in_time_universe"]
    assert check["status"] == "confirmed"
    assert check["evidence"]["future_reliance_count"] == 1
    assert check["evidence"]["future_reliance"] == [
        {"decision": "2023-01-01", "relied_snapshot": "2023-06-30"}
    ]
    assert result.metrics["backtest_assessment"]["status"] == "confirmed"


def test_membership_relied_snapshot_older_than_decision_is_ok():
    snapshots = make_table(
        "index_snapshot",
        INDEX_SNAPSHOT_HEADERS,
        [snapshot_row("INFY", "2023-06-30")],
    )
    config = LookaheadConfig(
        decision_dates=(date(2023, 12, 1),),
        membership_snapshot_dates=(date(2023, 6, 30),),
    )
    result = lookahead.analyze(
        Path("/tmp/root"),  # noqa: S108 - inert paths
        {**base_tables(), "index_snapshot": [snapshots]},
        config=config,
    )
    check = checks_by_name(result)["point_in_time_universe"]
    assert check["status"] == "ok"
    assert check["evidence"]["relied_snapshots"] == ["2023-06-30"]


def test_membership_snapshot_missing_is_unavailable():
    snapshots = make_table(
        "index_snapshot",
        INDEX_SNAPSHOT_HEADERS,
        [snapshot_row("INFY", "2023-06-30")],
    )
    config = LookaheadConfig(
        decision_dates=(date(2023, 12, 1),),
        membership_snapshot_dates=(date(2022, 6, 30),),
    )
    result = lookahead.analyze(
        Path("/tmp/root"),  # noqa: S108 - inert paths
        {**base_tables(), "index_snapshot": [snapshots]},
        config=config,
    )
    check = checks_by_name(result)["point_in_time_universe"]
    assert check["status"] == "unavailable"
    assert check["evidence"]["missing"] == ["2022-06-30"]
    assert "lookahead.backtest_checks_unavailable" in issue_codes(result)


def test_universe_symbols_from_present_day_listing_only_is_suspicious():
    config = LookaheadConfig(
        decision_dates=(date(2023, 1, 1),),
        universe_symbols=("INFY", "NEVERSEEN"),
    )
    result = lookahead.analyze(Path("/tmp/root"), base_tables(), config=config)  # noqa: S108 - inert paths
    check = checks_by_name(result)["point_in_time_universe"]
    assert check["status"] == "suspicious"
    reasons = [entry["reason"] for entry in check["evidence"]["entries"]]
    assert any("present-day listing snapshot" in reason for reason in reasons)
    assert any("cannot be verified" in reason for reason in reasons)
    assert result.metrics["backtest_assessment"]["status"] == "suspicious"


def test_no_snapshots_at_all_makes_universe_check_unavailable():
    config = LookaheadConfig(decision_dates=(date(2024, 1, 1),), universe_symbols=("INFY",))
    result = lookahead.analyze(Path("/tmp/root"), base_tables(), config=config)  # noqa: S108 - inert paths
    check = checks_by_name(result)["point_in_time_universe"]
    assert check["status"] == "unavailable"
    assert check["reason"] == (
        "No dated point-in-time membership snapshot is present in the collected "
        "data, so membership on the requested dates cannot be verified."
    )


def test_decision_profile_counts_published_and_unpublished_figures():
    config = LookaheadConfig(
        decision_dates=(date(2024, 1, 2),),
    )
    result = lookahead.analyze(Path("/tmp/root"), base_tables(), config=config)  # noqa: S108 - inert paths
    check = checks_by_name(result)["publication_timing"]
    profile = check["evidence"]["decision_profiles"][0]
    assert profile["decision"] == "2024-01-02"
    assert profile["relying_records"] == 1
    assert profile["published_by_decision"] == 0
    assert profile["published_after_decision"] == 1
    assert profile["published_after_examples"][0]["publication"] == (
        "2025-01-16 19:42:44"
    )
    entry = next(
        note
        for note in result.metrics["backtest_assessment"]["insufficient_notes"]
        if "decision 2024-01-02" in note
    )
    assert "which figures the decision consumed cannot be verified" in entry


def test_decision_before_any_relying_period_is_available_profiles_only():
    config = LookaheadConfig(decision_dates=(date(2023, 1, 1),))
    result = lookahead.analyze(Path("/tmp/root"), base_tables(), config=config)  # noqa: S108 - inert paths
    check = checks_by_name(result)["publication_timing"]
    assert check["status"] == "ok"
    assert check["evidence"]["decision_profiles"][0]["relying_records"] == 0


def test_future_price_rows_within_interval_are_suspicious():
    prices = make_table(
        "derived_prices",
        DERIVED_PRICE_HEADERS,
        [
            derived_price_row("2023-12-01"),
            derived_price_row("2024-01-10"),
        ],
    )
    config = LookaheadConfig(
        start_date=date(2023, 1, 1),
        end_date=date(2024, 6, 30),
        decision_dates=(date(2023, 12, 1),),
    )
    result = lookahead.analyze(
        Path("/tmp/root"),  # noqa: S108 - inert paths
        {**base_tables(), "derived_prices": [prices]},
        config=config,
    )
    check = checks_by_name(result)["price_action_timing"]
    assert check["status"] == "suspicious"
    assert check["evidence"]["future_price_rows"][0][
        "price_rows_after_decision"
    ] == 1


def test_events_after_decision_are_reported_as_insufficient():
    actions = make_table(
        "corporate_actions",
        CA_HEADERS,
        [ca_row(ex_date="15-Jan-2024")],
    )
    config = LookaheadConfig(
        start_date=date(2023, 12, 1),
        end_date=date(2024, 3, 31),
        decision_dates=(date(2024, 1, 1),),
    )
    result = lookahead.analyze(
        Path("/tmp/root"),  # noqa: S108 - inert paths
        {**base_tables(), "corporate_actions": [actions]},
        config=config,
    )
    check = checks_by_name(result)["price_action_timing"]
    assert check["evidence"]["announce_unknown_event_count"] == 1
    assert check["evidence"]["announce_unknown_events"][0]["ex_date"] == "2024-01-15"
    notes = result.metrics["backtest_assessment"]["insufficient_notes"]
    assert any("announcement timestamps required" in note for note in notes)


def test_restatement_window_overlapping_decision_is_reported():
    original = integrated_financial_row(
        broadcast="05-Jan-2025 10:00:00",
        disseminated="05-Jan-2025 10:00:30",
    )
    revised = integrated_financial_row(
        submission="Revised",
        revised="20-Jun-2025 09:00:00",
        disseminated="20-Jun-2025 09:00:45",
    )
    integrated = make_table(
        "integrated_financials",
        INTEGRATED_FINANCIAL_HEADERS,
        [original, revised],
    )
    config = LookaheadConfig(decision_dates=(date(2025, 3, 1),))
    result = lookahead.analyze(
        Path("/tmp/root"),  # noqa: S108 - inert paths
        tables_for(integrated_financials=integrated),
        config=config,
    )
    check = checks_by_name(result)["financial_revisions"]
    assert check["status"] == "suspicious"
    overlap = check["evidence"]["restatement_overlaps"][0]
    assert overlap["decision"] == "2025-03-01"
    assert overlap["window"] == {
        "start": "2025-01-05 10:00:00",
        "end": "2025-06-20 09:00:00",
    }


def test_derived_financial_violations_attributed_to_derived_feature_check():
    table = make_table(
        "derived_financials_legacy",
        DERIVED_LEGACY_FINANCIAL_HEADERS,
        [derived_legacy_row(period="31-Dec-2023", disseminated="2023-12-20 10:00:00")],
    )
    config = LookaheadConfig(
        start_date=date(2023, 6, 1),
        end_date=date(2024, 6, 30),
        decision_dates=(date(2024, 1, 1),),
    )
    result = lookahead.analyze(
        Path("/tmp/root"),  # noqa: S108 - inert paths
        {**base_tables(), "derived_financials_legacy": [table]},
        config=config,
    )
    check = checks_by_name(result)["derived_feature_timing"]
    assert check["status"] == "confirmed"
    assert check["evidence"]["confirmed_violation_count"] == 1
    assert check["evidence"]["examples"][0]["kind"] == "derived_financials_legacy"


def test_decision_timestamp_coverage_reports_boundary_limitation():
    config = LookaheadConfig(decision_dates=(date(2024, 1, 2), date(2024, 7, 1)))
    result = lookahead.analyze(Path("/tmp/root"), base_tables(), config=config)  # noqa: S108 - inert paths
    check = checks_by_name(result)["decision_timestamp_coverage"]
    assert check["status"] == "ok"
    assert check["evidence"]["decision_count"] == 2
    assert "end-of-day" in check["evidence"]["boundary_note"]


def test_no_decisions_and_no_interval_marks_checks_not_applicable():
    config = LookaheadConfig(universe_symbols=("INFY",))
    result = lookahead.analyze(Path("/tmp/root"), base_tables(), config=config)  # noqa: S108 - inert paths
    by_name = checks_by_name(result)
    assert by_name["publication_timing"]["status"] == "not_applicable"
    assert by_name["decision_timestamp_coverage"]["status"] == "not_applicable"
    assert by_name["point_in_time_universe"]["status"] == "not_applicable"


# ---------------------------------------------------------------------------
# Determinism, immutability, and runner/CLI integration
# ---------------------------------------------------------------------------


def test_analysis_is_deterministic():
    tables = base_tables()
    first = lookahead.analyze(Path("/tmp/root"), tables)  # noqa: S108 - inert paths
    second = lookahead.analyze(Path("/tmp/root"), tables)

    assert first.metrics == second.metrics
    assert issue_codes(first) == issue_codes(second)
    assert [i.message for i in first.issues] == [i.message for i in second.issues]


def test_analyze_never_modifies_source_files(tmp_path: Path):
    root = create_valid_data_root(tmp_path / "data")
    originals = {
        path: path.read_bytes()
        for path in sorted(root.rglob("*.csv"))
    }

    result = lookahead.analyze(root)

    assert {"status": result.status}
    assert {path: path.read_bytes() for path in sorted(root.rglob("*.csv"))} == originals


def test_run_validation_includes_lookahead_dataset(tmp_path: Path):
    root = create_valid_data_root(tmp_path / "data")
    config = LookaheadConfig(
        start_date=date(2024, 1, 1),
        end_date=date(2025, 12, 31),
        decision_dates=(date(2024, 7, 1),),
    )
    report = run_validation(root, lookahead_config=config)

    analysis = next(
        dataset for dataset in report.datasets if dataset.dataset_id == "lookahead:analysis"
    )
    assert analysis.metrics["analysis"]["mode"] == "backtest_specific_assessment"
    assert analysis.metrics["analysis"]["backtest_config_supplied"] is True
    assessment = analysis.metrics["backtest_assessment"]
    assert assessment["status"] in {"ok", "partial", "suspicious", "confirmed"}
    assert assessment["config"]["interval_days"] == 730


def test_run_validation_report_json_serializes(tmp_path: Path):
    root = create_valid_data_root(tmp_path / "data")
    config = LookaheadConfig(decision_dates=(date(2026, 1, 4),))
    report = run_validation(root, lookahead_config=config)

    payload = json.dumps(
        {
            "datasets": [
                {
                    "id": dataset.dataset_id,
                    "status": dataset.status.value,
                    "metrics": dataset.metrics,
                    "issues": [issue.to_dict() for issue in dataset.issues],
                }
                for dataset in report.datasets
            ]
        },
        ensure_ascii=False,
        sort_keys=False,
    )
    data = json.loads(payload)
    analysis = next(
        d for d in data["datasets"] if d["id"] == "lookahead:analysis"
    )
    assert analysis["status"] in {"PASS", "WARN"}
    assert analysis["metrics"]["findings"]["detailed_findings"]


def test_cli_decision_flags_write_deterministic_json(tmp_path: Path):
    root = create_valid_data_root(tmp_path / "data")
    write_snapshot_file = tmp_path / "unused"
    del write_snapshot_file  # snapshots are optional; none are supplied here
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    args = [
        "--data-root",
        str(root),
        "--decision-date",
        "2025-01-05",
        "--backtest-start",
        "2024-01-01",
        "--backtest-end",
        "2026-12-31",
        "--feature-lookback-days",
        "30",
    ]

    assert cli.main([*args, "--json-report", str(first)]) == 0
    assert cli.main([*args, "--json-report", str(second)]) == 0
    assert first.read_bytes() == second.read_bytes()

    payload = json.loads(first.read_text(encoding="utf-8"))
    analysis = next(
        d for d in payload["datasets"] if d["id"] == "lookahead:analysis"
    )
    assert analysis["metrics"]["analysis"]["mode"] == "backtest_specific_assessment"
    assessment = analysis["metrics"]["backtest_assessment"]
    assert assessment["config"]["decision_dates"] == ["2025-01-05"]
    assert assessment["config"]["lookback_days"] == 30
    assert assessment["status"] in {"ok", "partial", "suspicious", "confirmed"}


def test_cli_unparseable_decision_date_exits_two():
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["--decision-date", "not-a-date"])
    assert excinfo.value.code == 2


def test_cli_without_flags_runs_general_audit_only(tmp_path: Path):
    root = create_valid_data_root(tmp_path / "data")
    report_path = tmp_path / "report.json"

    exit_code = cli.main(["--data-root", str(root), "--json-report", str(report_path)])

    assert exit_code == 0
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    analysis = next(
        d for d in payload["datasets"] if d["id"] == "lookahead:analysis"
    )
    assert analysis["metrics"]["analysis"]["mode"] == "general_temporal_evidence_audit"
    assert (
        analysis["metrics"]["backtest_assessment"]["status"] == "unavailable"
    )


def test_real_data_guard_real_input_never_claimed() -> None:
    """The analyzer must not claim 'ok' when it parsed no evidence at all."""

    result = lookahead.analyze(Path("/tmp/nonexistent-root-xyz"), {})
    assert result.metrics["data_facts"]["financial_records_analyzed"] == 0
    entry = next(
        item
        for item in result.metrics["findings"]["detailed_findings"]
        if item["code"] == "lookahead.point_in_time_universe_missing"
    )
    assert entry["kind"] == "insufficient_lookahead_evidence"


def test_dataset_status_is_never_fail_on_the_analysis_dataset(tmp_path: Path):
    """Findings are warnings; per-dataset validation fails its own files."""

    root = create_valid_data_root(tmp_path / "data")
    report = run_validation(root)
    analysis = next(
        dataset
        for dataset in report.datasets
        if dataset.dataset_id == "lookahead:analysis"
    )
    assert analysis.status is not Status.FAIL
    assert all(issue.severity.value != "error" for issue in analysis.issues)
