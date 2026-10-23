"""Tests for the Survivorship-Bias Analyzer.

All fixtures are built in-memory or under ``tmp_path``. The collected source
datasets under ``data/`` are never read or modified.
"""

from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

import pytest

from bra import cli
from bra.csv_io import Row, Table
from bra.discovery import DatasetSpec
from bra.models import Status
from bra.runner import run_validation
from bra.validators import survivorship

from .support import create_valid_data_root


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


CURRENT_LISTING_HEADERS = [
    "SYMBOL",
    "NAME OF COMPANY",
    "SERIES",
    "DATE OF LISTING",
    "PAID UP VALUE",
    "MARKET LOT",
    "ISIN NUMBER",
    "FACE VALUE",
]

DELISTING_HEADERS = [
    "Symbol",
    "ISIN",
    "Company Name",
    "Board",
    "Delisted Date",
    "Type of Delisting",
]

PRICE_HEADERS = ["symbol", "series", "trade_date", "close"]

SYMBOL_CHANGE_HEADERS = [
    "NAME OF THE COMPANY",
    "OLD SYMBOL",
    "NEW SYMBOL",
    "EFFECTIVE DATE",
]

NAME_CHANGE_HEADERS = [
    "SYMBOL",
    "OLD NAME OF THE COMPANY",
    "NEW NAME OF THE COMPANY",
    "EFFECTIVE DATE",
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


def tables_for(**tables: Table) -> dict[str, list[Table]]:
    return {kind: [table] for kind, table in tables.items()}


def issue_codes(result) -> list[str]:
    return [issue.code for issue in result.issues]


def snapshot_row(
    symbol: str,
    snapshot_date: str,
    index_name: str = "NIFTY 50",
    **extra: str,
) -> list[str]:
    """One dated index-constituent row for fixture snapshots."""

    values = {
        "security_name": f"{symbol} Limited",
        "industry": "General",
        "close_price": "100",
        "index_mcap_cr": "1000",
        "weightage_pct": "1.0",
        "source_pdf": f"{index_name.replace(' ', '_')}.pdf",
    }
    values.update(extra)
    return [
        symbol,
        values["security_name"],
        values["industry"],
        values["close_price"],
        values["index_mcap_cr"],
        values["weightage_pct"],
        snapshot_date,
        index_name,
        values["source_pdf"],
    ]


def write_snapshot(
    root: Path,
    filename: str,
    rows: list[list[str]],
    *,
    raw: str | None = None,
) -> Path:
    """Write a dated membership snapshot under the data root (fixture only)."""

    path = root / "reference/index_constituents/extracted_csv" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    if raw is not None:
        path.write_text(raw, encoding="utf-8")
        return path
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(INDEX_SNAPSHOT_HEADERS)
        writer.writerows(rows)
    return path


def test_current_listing_snapshot_reported_as_not_point_in_time():
    current = make_table(
        "current_listing",
        CURRENT_LISTING_HEADERS,
        [
            [
                "INFY",
                "Infosys Limited",
                "EQ",
                "06-Oct-2008",
                "5",
                "1",
                "INE009A01021",
                "5",
            ],
            [
                "RELIANCE",
                "Reliance Industries Limited",
                "EQ",
                "06-Oct-2008",
                "10",
                "1",
                "INE002A01018",
                "10",
            ],
        ],
    )
    result = survivorship.analyze(
        Path("/tmp/root"), tables_for(current_listing=current)
    )
    codes = issue_codes(result)
    assert "survivorship.current_listing_snapshot_not_point_in_time" in codes
    assert (
        result.metrics["current_listing_snapshot"]["is_point_in_time_universe"] is False
    )
    assert result.metrics["current_listing_snapshot"]["rows"] == 2
    assert result.metrics["current_listing_snapshot"]["distinct_symbols"] == 2


def test_index_membership_coverage_gap_reported():
    current = make_table(
        "current_listing",
        CURRENT_LISTING_HEADERS,
        [
            [
                "INFY",
                "Infosys Limited",
                "EQ",
                "06-Oct-2008",
                "5",
                "1",
                "INE009A01021",
                "5",
            ]
        ],
    )
    result = survivorship.analyze(
        Path("/tmp/root"), tables_for(current_listing=current)
    )
    codes = issue_codes(result)
    assert "survivorship.index_membership_coverage_gap" in codes
    index = result.metrics["index_membership"]
    assert index["point_in_time_membership_dataset_present"] is False
    assert index["coverage_start_date"] == "2013-09-01"
    assert index["inferred_from_current_listings_or_delistings"] is False


def test_delisted_with_price_coverage_matched():
    current = make_table(
        "current_listing",
        CURRENT_LISTING_HEADERS,
        [
            [
                "INFY",
                "Infosys Limited",
                "EQ",
                "06-Oct-2008",
                "5",
                "1",
                "INE009A01021",
                "5",
            ]
        ],
    )
    delistings = make_table(
        "delistings",
        DELISTING_HEADERS,
        [
            [
                "INFY",
                "INE009A01021",
                "Infosys Limited",
                "Main Board",
                "2024-01-15",
                "Voluntary Delisting",
            ]
        ],
    )
    prices = make_table(
        "prices",
        PRICE_HEADERS,
        [
            ["INFY", "EQ", "2024-01-10", "100"],
            ["INFY", "EQ", "2024-01-11", "101"],
        ],
    )
    result = survivorship.analyze(
        Path("/tmp/root"),
        tables_for(current_listing=current, delistings=delistings, prices=prices),
    )
    coverage = result.metrics["delisted_price_coverage"]
    assert coverage["delisted_securities"] == 1
    assert coverage["matched_to_price_history"] == 1
    assert coverage["direct_symbol_matches"] == 1
    assert coverage["unmatched"] == 0
    assert coverage["matched_examples"][0]["match_type"] == "direct_symbol"
    assert "survivorship.delisted_price_coverage_gap" not in issue_codes(result)


def test_delisted_without_price_coverage_unmatched():
    delistings = make_table(
        "delistings",
        DELISTING_HEADERS,
        [
            [
                "NOPE",
                "INE999Z01099",
                "Nope Limited",
                "Main Board",
                "2024-01-15",
                "Voluntary Delisting",
            ]
        ],
    )
    prices = make_table("prices", PRICE_HEADERS, [["INFY", "EQ", "2024-01-10", "100"]])
    result = survivorship.analyze(
        Path("/tmp/root"), tables_for(delistings=delistings, prices=prices)
    )
    coverage = result.metrics["delisted_price_coverage"]
    assert coverage["delisted_securities"] == 1
    assert coverage["matched_to_price_history"] == 0
    assert coverage["unmatched"] == 1
    assert coverage["unmatched_examples"][0]["symbol"] == "NOPE"
    codes = issue_codes(result)
    assert "survivorship.delisted_price_coverage_gap" in codes
    message = next(
        issue.message
        for issue in result.issues
        if issue.code == "survivorship.delisted_price_coverage_gap"
    )
    assert "coverage limitation" in message
    assert "not evidence that a backtest excluded" in message


def test_price_symbols_and_date_range_from_data():
    prices = make_table(
        "prices",
        PRICE_HEADERS,
        [
            ["INFY", "EQ", "2024-01-10", "100"],
            ["INFY", "EQ", "2024-01-12", "102"],
            ["RELIANCE", "EQ", "2024-01-10", "2000"],
            ["RELIANCE", "EQ", "2024-02-01", "2010"],
            ["TCS", "EQ", "2024-01-15", "3000"],
        ],
    )
    result = survivorship.analyze(Path("/tmp/root"), tables_for(prices=prices))
    price = result.metrics["price_coverage"]
    assert price["symbol_count"] == 3
    assert price["symbols"]["INFY"]["rows"] == 2
    assert price["symbols"]["INFY"]["start"] == "2024-01-10"
    assert price["symbols"]["INFY"]["end"] == "2024-01-12"
    assert price["symbols"]["RELIANCE"]["start"] == "2024-01-10"
    assert price["symbols"]["RELIANCE"]["end"] == "2024-02-01"
    assert price["date_range"] == {"start": "2024-01-10", "end": "2024-02-01"}
    assert result.metrics["data_facts"]["price_symbols"] == ["INFY", "RELIANCE", "TCS"]


def test_symbol_change_candidate_matching():
    delistings = make_table(
        "delistings",
        DELISTING_HEADERS,
        [
            [
                "OLDTECH",
                "INE111A01011",
                "Old Tech Limited",
                "Main Board",
                "2024-01-15",
                "Voluntary Delisting",
            ]
        ],
    )
    prices = make_table(
        "prices", PRICE_HEADERS, [["NEWTECH", "EQ", "2024-01-10", "100"]]
    )
    symbol_changes = make_table(
        "symbol_changes",
        SYMBOL_CHANGE_HEADERS,
        [["Old Tech Limited", "OLDTECH", "NEWTECH", "2023-06-01"]],
    )
    result = survivorship.analyze(
        Path("/tmp/root"),
        tables_for(delistings=delistings, prices=prices, symbol_changes=symbol_changes),
    )
    coverage = result.metrics["delisted_price_coverage"]
    assert coverage["matched_to_price_history"] == 1
    assert coverage["symbol_change_candidate_matches"] == 1
    example = coverage["matched_examples"][0]
    assert example["match_type"] == "symbol_change_candidate"
    assert example["matched_symbol"] == "NEWTECH"
    assert example["identity_confirmed"] is False


def test_relisted_or_reused_identifier_evidence():
    current = make_table(
        "current_listing",
        CURRENT_LISTING_HEADERS,
        [
            [
                "OLDTECH",
                "Old Tech Limited",
                "EQ",
                "2024-02-01",
                "5",
                "1",
                "INE111A01011",
                "5",
            ]
        ],
    )
    delistings = make_table(
        "delistings",
        DELISTING_HEADERS,
        [
            [
                "OLDTECH",
                "INE111A01011",
                "Old Tech Limited",
                "Main Board",
                "2023-01-15",
                "Voluntary Delisting",
            ]
        ],
    )
    result = survivorship.analyze(
        Path("/tmp/root"),
        tables_for(current_listing=current, delistings=delistings),
    )
    reuse = result.metrics["identifier_reuse"]
    assert reuse["overlap_count"] == 1
    assert reuse["symbol_and_isin_overlaps"] == 1
    codes = issue_codes(result)
    assert "survivorship.relisted_or_reused_identifier" in codes
    message = next(
        issue.message
        for issue in result.issues
        if issue.code == "survivorship.relisted_or_reused_identifier"
    )
    assert "not proof" in message or "not assumed" in message


def test_reused_delisting_symbol_is_not_company_identity():
    delistings = make_table(
        "delistings",
        DELISTING_HEADERS,
        [
            [
                "VIKASH",
                "INE111A01011",
                "Vikas Metal Limited",
                "Main Board",
                "2023-01-15",
                "Voluntary Delisting",
            ],
            [
                "VIKASH",
                "INE222B01022",
                "Vikas Industries Limited",
                "SME",
                "2023-03-01",
                "Compulsory Delisting",
            ],
        ],
    )
    result = survivorship.analyze(Path("/tmp/root"), tables_for(delistings=delistings))
    reuse = result.metrics["delisting_symbol_reuse"]
    assert reuse["reused_symbol_count"] == 1
    assert "VIKASH" in reuse["reused_symbols"]
    codes = issue_codes(result)
    assert "survivorship.reused_symbol_in_delisting_history" in codes
    message = next(
        issue.message
        for issue in result.issues
        if issue.code == "survivorship.reused_symbol_in_delisting_history"
    )
    assert "Symbol equality alone" in message


def test_continuity_evidence_surfaces_symbol_and_name_changes():
    current = make_table(
        "current_listing",
        CURRENT_LISTING_HEADERS,
        [
            [
                "NEWTECH",
                "New Tech Limited",
                "EQ",
                "2024-02-01",
                "5",
                "1",
                "INE111A01011",
                "5",
            ]
        ],
    )
    delistings = make_table(
        "delistings",
        DELISTING_HEADERS,
        [
            [
                "OLDTECH",
                "INE111A01011",
                "Old Tech Limited",
                "Main Board",
                "2023-01-15",
                "Voluntary Delisting",
            ]
        ],
    )
    symbol_changes = make_table(
        "symbol_changes",
        SYMBOL_CHANGE_HEADERS,
        [["Old Tech Limited", "OLDTECH", "NEWTECH", "2023-06-01"]],
    )
    name_changes = make_table(
        "name_changes",
        NAME_CHANGE_HEADERS,
        [["OLDTECH", "Old Name Limited", "Old Tech Limited", "2022-01-01"]],
    )
    result = survivorship.analyze(
        Path("/tmp/root"),
        tables_for(
            current_listing=current,
            delistings=delistings,
            symbol_changes=symbol_changes,
            name_changes=name_changes,
        ),
    )
    continuity = result.metrics["continuity_evidence"]
    assert len(continuity) == 1
    assert continuity[0]["current_identifier_overlap"] is True
    assert continuity[0]["symbol_changes"][0]["old_symbol"] == "OLDTECH"
    assert continuity[0]["symbol_changes"][0]["new_symbol"] == "NEWTECH"
    assert continuity[0]["name_changes"][0]["old_name"] == "Old Name Limited"


def test_empty_or_missing_inputs():
    result = survivorship.analyze(Path("/tmp/root"), {})
    codes = issue_codes(result)
    assert "survivorship.current_listing_missing" in codes
    assert "survivorship.delistings_missing" in codes
    assert "survivorship.prices_missing" in codes
    assert result.metrics["delisted_price_coverage"]["unmatched"] == 0
    assert result.metrics["price_coverage"]["symbol_count"] == 0


def test_malformed_dates_reported():
    current = make_table(
        "current_listing",
        CURRENT_LISTING_HEADERS,
        [
            [
                "INFY",
                "Infosys Limited",
                "EQ",
                "not-a-date",
                "5",
                "1",
                "INE009A01021",
                "5",
            ]
        ],
    )
    delistings = make_table(
        "delistings",
        DELISTING_HEADERS,
        [
            [
                "OLDTECH",
                "INE111A01011",
                "Old Tech Limited",
                "Main Board",
                "31-Feb-2024",
                "Voluntary Delisting",
            ]
        ],
    )
    prices = make_table("prices", PRICE_HEADERS, [["INFY", "EQ", "not-a-date", "100"]])
    result = survivorship.analyze(
        Path("/tmp/root"),
        tables_for(current_listing=current, delistings=delistings, prices=prices),
    )
    codes = issue_codes(result)
    assert "survivorship.current_listing_date_invalid" in codes
    assert "survivorship.delisting_date_invalid" in codes
    assert "survivorship.price_date_invalid" in codes
    # Malformed rows are excluded from coverage, not counted as facts.
    assert result.metrics["data_facts"]["price_rows"] == 0


def test_deterministic_output():
    current = make_table(
        "current_listing",
        CURRENT_LISTING_HEADERS,
        [
            [
                "INFY",
                "Infosys Limited",
                "EQ",
                "06-Oct-2008",
                "5",
                "1",
                "INE009A01021",
                "5",
            ]
        ],
    )
    delistings = make_table(
        "delistings",
        DELISTING_HEADERS,
        [
            [
                "OLDTECH",
                "INE111A01011",
                "Old Tech Limited",
                "Main Board",
                "2024-01-15",
                "Voluntary Delisting",
            ]
        ],
    )
    prices = make_table("prices", PRICE_HEADERS, [["INFY", "EQ", "2024-01-10", "100"]])
    tables = tables_for(current_listing=current, delistings=delistings, prices=prices)

    first = survivorship.analyze(Path("/tmp/root"), tables)
    second = survivorship.analyze(Path("/tmp/root"), tables)

    assert first.metrics == second.metrics
    assert issue_codes(first) == issue_codes(second)
    assert [
        (issue.code, issue.severity.value, issue.message) for issue in first.issues
    ] == [(issue.code, issue.severity.value, issue.message) for issue in second.issues]


def test_integration_with_run_validation(tmp_path: Path):
    data_root = tmp_path / "data"
    price_path = data_root / "raw/22-10-2021-TO-22-10-2026-INFY-ALL-N.csv"
    price_path.parent.mkdir(parents=True)
    price_path.write_text(
        "Symbol,Series,Date,Prev Close,Open,High,Low,Last,Close\n"
        "INFY,EQ,10-Jan-2024,100,100,101,99,100,100\n",
        encoding="utf-8",
    )
    eq_path = data_root / "reference/listing_history/EQUITY_L.csv"
    eq_path.parent.mkdir(parents=True)
    eq_path.write_text(
        "SYMBOL,NAME OF COMPANY,SERIES,DATE OF LISTING,ISIN NUMBER\n"
        "INFY,Infosys Limited,EQ,06-Oct-2008,INE009A01021\n",
        encoding="utf-8",
    )
    del_path = data_root / "processed/delisted_companies_2021-2026.csv"
    del_path.parent.mkdir(parents=True)
    del_path.write_text(
        "Symbol,ISIN,Company Name,Board,Delisted Date,Type of Delisting\n"
        "NOPE,INE999Z01099,Nope Limited,Main Board,2024-01-15,Voluntary Delisting\n",
        encoding="utf-8",
    )

    specs = [
        DatasetSpec(
            dataset_id="prices:INFY",
            category="historical_prices",
            kind="prices",
            label="Historical prices - INFY",
            path=price_path,
            relative_path="raw/22-10-2021-TO-22-10-2026-INFY-ALL-N.csv",
            expected_symbol="INFY",
        ),
        DatasetSpec(
            dataset_id="current_listing:EQUITY_L",
            category="listing_reference",
            kind="current_listing",
            label="Current listing reference",
            path=eq_path,
            relative_path="reference/listing_history/EQUITY_L.csv",
            expected_symbol=None,
        ),
        DatasetSpec(
            dataset_id="delistings:delisted_companies_2021-2026",
            category="historical_delistings",
            kind="delistings",
            label="Delistings - all boards (2021-2026)",
            path=del_path,
            relative_path="processed/delisted_companies_2021-2026.csv",
            expected_symbol=None,
        ),
    ]

    report = run_validation(data_root, specs=specs)
    by_id = {dataset.dataset_id: dataset for dataset in report.datasets}
    assert "survivorship:analysis" in by_id
    analysis = by_id["survivorship:analysis"]
    assert analysis.category == "survivorship_bias"
    assert analysis.label == "Survivorship-bias coverage analysis"
    codes = issue_codes(analysis)
    assert "survivorship.current_listing_snapshot_not_point_in_time" in codes
    assert "survivorship.index_membership_coverage_gap" in codes
    assert "survivorship.delisted_price_coverage_gap" in codes
    # Warnings from coverage findings do not fail the validation run by
    # themselves; the run only fails on critical errors.
    assert analysis.status is Status.WARN


def test_source_datasets_not_modified(tmp_path: Path):
    data_root = tmp_path / "data"
    del_path = data_root / "processed/delisted_companies_2021-2026.csv"
    del_path.parent.mkdir(parents=True)
    original = (
        "Symbol,ISIN,Company Name,Board,Delisted Date,Type of Delisting\n"
        "NOPE,INE999Z01099,Nope Limited,Main Board,2024-01-15,Voluntary Delisting\n"
    )
    del_path.write_text(original, encoding="utf-8")
    before = del_path.read_bytes()

    from bra.csv_io import read_csv

    parsed = read_csv(del_path)
    result = survivorship.analyze(data_root, tables_for(delistings=parsed))

    assert del_path.read_bytes() == before
    # The analyzer only reads; it reports NOPE as unmatched without altering data.
    assert result.metrics["delisted_price_coverage"]["unmatched"] == 1
    assert result.metrics["data_facts"]["delisting_records"] == 1


def test_confirmed_facts_risks_limitations_and_checks_separated():
    delistings = make_table(
        "delistings",
        DELISTING_HEADERS,
        [
            [
                "NOPE",
                "INE999Z01099",
                "Nope Limited",
                "Main Board",
                "2024-01-15",
                "Voluntary Delisting",
            ]
        ],
    )
    prices = make_table("prices", PRICE_HEADERS, [["INFY", "EQ", "2024-01-10", "100"]])
    result = survivorship.analyze(
        Path("/tmp/root"), tables_for(delistings=delistings, prices=prices)
    )
    findings = result.metrics["findings"]
    assert "confirmed_data_facts" in findings
    assert "potential_survivorship_risks" in findings
    assert "coverage_limitations" in findings
    assert "checks_passed" in findings
    assert findings["confirmed_data_facts"]["delisted_securities"] == 1
    assert any(
        "no matching price symbol" in limitation
        for limitation in findings["coverage_limitations"]
    )
    assert any(
        "current_listings_not_used_as_historical_index_membership" in check
        for check in findings["checks_passed"]
    )
    assert any(
        "delisting_records_not_used_as_historical_index_membership" in check
        for check in findings["checks_passed"]
    )


def test_coverage_describes_delisting_dates_not_price_dates():
    # Delisting dates span a different range than price dates; the analysis
    # coverage must describe the delisting inputs (consistent with row_count),
    # not the price date range.
    delistings = make_table(
        "delistings",
        DELISTING_HEADERS,
        [
            [
                "OLDTECH",
                "INE111A01011",
                "Old Tech Limited",
                "Main Board",
                "2023-01-15",
                "Voluntary Delisting",
            ],
            [
                "NOPE",
                "INE999Z01099",
                "Nope Limited",
                "SME",
                "2023-02-01",
                "Compulsory Delisting",
            ],
        ],
    )
    prices = make_table(
        "prices",
        PRICE_HEADERS,
        [
            ["INFY", "EQ", "2024-01-10", "100"],
            ["INFY", "EQ", "2024-02-01", "102"],
            ["RELIANCE", "EQ", "2024-01-10", "2000"],
        ],
    )
    result = survivorship.analyze(
        Path("/tmp/root"), tables_for(delistings=delistings, prices=prices)
    )

    # row_count describes the delisting input records.
    assert result.row_count == 2
    # coverage describes delisting dates, not the price date range.
    assert result.coverage == {
        "date_column": "Delisted Date",
        "start": "2023-01-15",
        "end": "2023-02-01",
    }
    # The price date range is still reported separately in metrics, but it is
    # not the overall analysis coverage.
    assert result.metrics["data_facts"]["price_date_range"] == {
        "start": "2024-01-10",
        "end": "2024-02-01",
    }
    assert result.coverage != result.metrics["data_facts"]["price_date_range"]


def test_no_delistings_yields_no_overall_coverage():
    # With no delisting input, there is nothing for row_count/coverage to
    # describe; coverage is None rather than a price-derived range.
    prices = make_table("prices", PRICE_HEADERS, [["INFY", "EQ", "2024-01-10", "100"]])
    result = survivorship.analyze(Path("/tmp/root"), tables_for(prices=prices))

    assert result.row_count == 0
    assert result.coverage is None
    assert result.metrics["data_facts"]["price_date_range"] == {
        "start": "2024-01-10",
        "end": "2024-01-10",
    }


# ---------------------------------------------------------------------------
# Historical universe reconstruction from dated membership snapshots
# ---------------------------------------------------------------------------


def test_universe_reconstructed_from_dated_snapshots(tmp_path: Path):
    root = tmp_path / "data"
    write_snapshot(
        root,
        "NIFTY_50_Mar2022.csv",
        [
            snapshot_row("INFY", "2022-03-31"),
            snapshot_row("TCS", "2022-03-31"),
        ],
    )
    write_snapshot(
        root,
        "NIFTY_50_Sep2026.csv",
        [
            snapshot_row("INFY", "2026-09-30"),
            snapshot_row("WIPRO", "2026-09-30"),
        ],
    )

    result = survivorship.analyze(root)
    membership = result.metrics["index_membership"]

    assert membership["point_in_time_membership_dataset_present"] is True
    assert membership["inferred_from_current_listings_or_delistings"] is False
    assert membership["snapshot_count"] == 2
    assert membership["constituent_rows"] == 4
    assert membership["distinct_symbols"] == 3
    assert membership["date_range"] == {"start": "2022-03-31", "end": "2026-09-30"}
    assert membership["membership_between_snapshots"] == "unverified"
    assert membership["interpolation_performed"] is False
    assert [entry["snapshot_date"] for entry in membership["snapshots"]] == [
        "2022-03-31",
        "2026-09-30",
    ]
    assert membership["indexes"]["NIFTY 50"] == {
        "snapshot_count": 2,
        "snapshot_dates": ["2022-03-31", "2026-09-30"],
        "distinct_symbols": 3,
    }
    # The period without any membership evidence is reported, never bridged.
    assert membership["coverage_gaps"] == [
        {
            "after_snapshot": "2022-03-31",
            "before_snapshot": "2026-09-30",
            "days": 1644,
        }
    ]
    assert "survivorship.index_membership_coverage_gap" in issue_codes(result)
    assert result.metrics["data_facts"]["membership_snapshot_dates"] == [
        "2022-03-31",
        "2026-09-30",
    ]
    assert result.metrics["data_facts"]["membership_symbol_count"] == 3


def test_sparse_snapshots_report_gaps_without_interpolation(tmp_path: Path):
    root = tmp_path / "data"
    write_snapshot(root, "old.csv", [snapshot_row("INFY", "2013-09-30")])
    write_snapshot(root, "new.csv", [snapshot_row("INFY", "2016-09-30")])

    result = survivorship.analyze(root)
    membership = result.metrics["index_membership"]

    assert membership["gaps"] == [
        {
            "index_name": "NIFTY 50",
            "after_snapshot": "2013-09-30",
            "before_snapshot": "2016-09-30",
            "days": 1096,
        }
    ]
    assert membership["membership_between_snapshots"] == "unverified"
    assert membership["interpolation_performed"] is False
    assert (
        "membership_not_interpolated_between_snapshots"
        in result.metrics["findings"]["checks_passed"]
    )
    # A symbol seen in one snapshot is not claimed for the years between them.
    assert membership["distinct_symbols"] == 1


def test_snapshot_rows_without_usable_date_are_excluded(tmp_path: Path):
    root = tmp_path / "data"
    write_snapshot(
        root,
        "mixed.csv",
        [
            snapshot_row("INFY", "2022-03-31"),
            snapshot_row("TCS", "not-a-date"),
            snapshot_row("", "2022-03-31"),
        ],
    )

    result = survivorship.analyze(root)
    codes = issue_codes(result)
    assert "survivorship.index_snapshot_date_invalid" in codes
    assert "survivorship.index_snapshot_symbol_missing" in codes

    membership = result.metrics["index_membership"]
    assert membership["snapshot_count"] == 1
    assert membership["constituent_rows"] == 1
    assert membership["excluded_snapshot_rows"] == 2
    assert membership["distinct_symbols"] == 1
    assert result.error_count == 0
    assert result.status is Status.WARN


def test_missing_snapshot_directory_and_empty_file(tmp_path: Path):
    root = tmp_path / "data"
    (root / "reference/index_constituents/extracted_csv").mkdir(parents=True)
    write_snapshot(root, "empty.csv", [], raw="")

    result = survivorship.analyze(root)
    codes = issue_codes(result)
    assert "survivorship.index_membership_coverage_gap" in codes
    message = next(
        issue.message
        for issue in result.issues
        if issue.code == "survivorship.index_membership_coverage_gap"
    )
    assert "no dated membership snapshot" in message

    membership = result.metrics["index_membership"]
    assert membership["snapshot_count"] == 0
    assert membership["point_in_time_membership_dataset_present"] is False
    # A broken reference input is a coverage limitation, never a fatal error.
    assert result.error_count == 0
    assert result.status is Status.WARN
    loader_issue = next(issue for issue in result.issues if issue.code == "csv.empty")
    assert "empty.csv" in loader_issue.message
    assert loader_issue.severity.value == "warning"


def test_duplicate_snapshot_rows_do_not_invent_members(tmp_path: Path):
    root = tmp_path / "data"
    write_snapshot(
        root,
        "dup.csv",
        [
            snapshot_row("INFY", "2022-03-31"),
            snapshot_row("INFY", "2022-03-31"),
        ],
    )

    result = survivorship.analyze(root)
    membership = result.metrics["index_membership"]
    assert membership["snapshot_count"] == 1
    assert membership["constituent_rows"] == 2
    assert membership["indexes"]["NIFTY 50"]["distinct_symbols"] == 1
    assert [entry["symbol_count"] for entry in membership["snapshots"]] == [1]


def test_index_gap_issue_stays_explicit_when_snapshots_exist(tmp_path: Path):
    root = tmp_path / "data"
    write_snapshot(root, "one.csv", [snapshot_row("INFY", "2022-03-31")])

    result = survivorship.analyze(root)
    message = next(
        issue.message
        for issue in result.issues
        if issue.code == "survivorship.index_membership_coverage_gap"
    )
    assert "sparse" in message
    assert "never interpolated" in message
    assert "September 2013" in message

    membership = result.metrics["index_membership"]
    assert membership["coverage_start_date"] == "2013-09-01"
    assert membership["documented_in"].endswith("historical-universe-gap.md")
    assert membership["required_additional_source"]


def test_snapshot_source_files_are_not_modified(tmp_path: Path):
    root = tmp_path / "data"
    path = write_snapshot(root, "one.csv", [snapshot_row("INFY", "2022-03-31")])
    before = path.read_bytes()

    survivorship.analyze(root)

    assert path.read_bytes() == before


# ---------------------------------------------------------------------------
# Backtest-specific assessment
# ---------------------------------------------------------------------------


def test_backtest_config_builder_parses_and_normalises_inputs():
    config, errors = survivorship.build_backtest_config(
        target_index="  NIFTY 50  ",
        start_date="2024-01-01",
        end_date="2024-12-31",
        universe_symbols=[" infy ", "", "tcs"],
        membership_snapshot_dates=["2024-03-31"],
        rebalance_dates=["2024-06-30"],
        min_price_coverage=0.5,
    )

    assert errors == []
    assert config is not None
    assert config.target_index == "NIFTY 50"
    assert config.universe_symbols == ("INFY", "TCS")
    assert config.start_date == date(2024, 1, 1)
    assert config.end_date == date(2024, 12, 31)
    assert config.membership_snapshot_dates == (date(2024, 3, 31),)
    assert config.rebalance_dates == (date(2024, 6, 30),)
    assert config.min_price_coverage == 0.5

    summary = survivorship.config_summary(config)
    assert summary["interval_days"] == 366
    assert summary["membership_snapshot_dates"] == ["2024-03-31"]
    assert summary["identifier_mapping_count"] == 0

    invalid, errors = survivorship.build_backtest_config(
        start_date="31-Feb-2024",
        end_date="2024-12-31",
    )
    assert invalid is None
    assert any(
        "start date" in error and "could not be parsed" in error for error in errors
    )


def test_backtest_config_validation_reports_every_problem():
    missing_interval = survivorship.validate_config(
        survivorship.BacktestConfig(target_index="NIFTY 50")
    )
    assert any(
        "start and end dates are required" in error for error in missing_interval
    )

    half_interval = survivorship.validate_config(
        survivorship.BacktestConfig(start_date=date(2024, 1, 1))
    )
    assert any("both be provided" in error for error in half_interval)

    reversed_interval = survivorship.validate_config(
        survivorship.BacktestConfig(
            start_date=date(2024, 12, 31), end_date=date(2024, 1, 1)
        )
    )
    assert any("is after" in error for error in reversed_interval)

    bad_threshold = survivorship.validate_config(
        survivorship.BacktestConfig(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            min_price_coverage=1.5,
        )
    )
    assert any("between 0 and 1" in error for error in bad_threshold)

    outside_dates = survivorship.validate_config(
        survivorship.BacktestConfig(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            membership_snapshot_dates=(date(2023, 12, 31),),
            rebalance_dates=(date(2025, 1, 1),),
        )
    )
    assert any("outside the backtest interval" in error for error in outside_dates)

    bad_mapping = survivorship.validate_config(
        survivorship.BacktestConfig(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            identifier_mappings=(
                survivorship.IdentifierMapping(old_symbol="", new_symbol="NEW"),
            ),
        )
    )
    assert any("missing its old or new symbol" in error for error in bad_mapping)


def test_general_audit_reports_backtest_results_as_unavailable():
    prices = make_table("prices", PRICE_HEADERS, [["INFY", "EQ", "2024-01-10", "100"]])

    result = survivorship.analyze(Path("/tmp/root"), tables_for(prices=prices))

    assessment = result.metrics["backtest_assessment"]
    assert assessment["status"] == "unavailable"
    assert "No backtest configuration was supplied" in assessment["reason"]
    assert (
        result.metrics["findings"]["backtest_specific_results"]["status"]
        == "unavailable"
    )
    assert result.metrics["analysis"]["mode"] == "general_data_coverage_audit"


def test_backtest_without_interval_is_invalid_not_an_exception():
    prices = make_table("prices", PRICE_HEADERS, [["INFY", "EQ", "2024-01-10", "100"]])

    # This used to raise AssertionError inside the assessment and surface as a
    # runner.validator_exception. It must be a reported configuration warning.
    result = survivorship.analyze(
        Path("/tmp/root"),
        tables_for(prices=prices),
        backtest=survivorship.BacktestConfig(target_index="NIFTY 50"),
    )

    assert result.error_count == 0
    assert result.status is Status.WARN
    codes = issue_codes(result)
    assert "survivorship.backtest_config_invalid" in codes
    assert "runner.validator_exception" not in codes
    assessment = result.metrics["backtest_assessment"]
    assert assessment["status"] == "invalid"
    assert any("required" in error for error in assessment["errors"])
    assert assessment["bias_impact"]["status"] == "unavailable"


def test_backtest_uses_dated_membership_and_reports_coverage(tmp_path: Path):
    root = tmp_path / "data"
    write_snapshot(
        root,
        "NIFTY_50_Mar2024.csv",
        [
            snapshot_row("INFY", "2024-03-31"),
            snapshot_row("TCS", "2024-03-31"),
        ],
    )
    prices = make_table(
        "prices",
        PRICE_HEADERS,
        [
            ["INFY", "EQ", "2024-01-02", "100"],
            ["INFY", "EQ", "2024-03-31", "101"],
            ["TCS", "EQ", "2024-01-02", "3000"],
        ],
    )
    config = survivorship.BacktestConfig(
        target_index="NIFTY 50",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        membership_snapshot_dates=(date(2024, 3, 31),),
        rebalance_dates=(date(2024, 3, 31), date(2024, 6, 30)),
        min_price_coverage=1.0,
    )

    result = survivorship.analyze(
        root,
        tables_for(prices=prices),
        backtest=config,
    )
    assessment = result.metrics["backtest_assessment"]

    assert result.metrics["analysis"]["mode"] == "backtest_specific_assessment"
    assert assessment["status"] == "partial"
    assert assessment["config"]["target_index"] == "NIFTY 50"
    assert assessment["universe"]["source"] == "membership_snapshots_in_interval"
    assert assessment["universe"]["universe_symbol_count"] == 2

    membership = assessment["membership_coverage"]
    assert membership["status"] == "ok"
    assert membership["snapshot_dates_in_interval"] == ["2024-03-31"]
    assert membership["days_with_membership_snapshot"] == 1
    assert membership["denominator"] == 366
    assert membership["interpolation_performed"] is False
    assert membership["largest_unverified_gap"] == {
        "start": "2024-04-01",
        "end": "2024-12-31",
        "days": 275,
    }

    coverage = assessment["price_coverage"]
    assert coverage["status"] == "ok"
    assert coverage["denominator"] == 2
    assert coverage["observed_trading_days"] == 2
    assert coverage["counts"] == {
        "complete": 1,
        "partial": 1,
        "missing": 0,
        "ambiguous": 0,
    }
    assert coverage["below_threshold_count"] == 1
    assert coverage["below_threshold_examples"] == [
        {"symbol": "TCS", "coverage_ratio": 0.5}
    ]

    rebalancing = assessment["rebalance_membership"]
    assert rebalancing["status"] == "partial"
    assert rebalancing["verified_count"] == 1
    assert rebalancing["unverified_dates"] == ["2024-06-30"]
    checks = {check["check"]: check for check in assessment["checks"]}
    assert checks["membership_snapshots_in_interval"]["status"] == "ok"
    assert checks["requested_membership_snapshot_dates"]["status"] == "ok"
    assert checks["rebalance_membership_dates"]["status"] == "unavailable"
    assert checks["bias_impact_quantification"]["status"] == "unavailable"
    assert assessment["bias_impact"]["missing_inputs"]


def test_backtest_reports_missing_requested_snapshot_dates(tmp_path: Path):
    root = tmp_path / "data"
    write_snapshot(root, "one.csv", [snapshot_row("INFY", "2024-03-31")])
    prices = make_table("prices", PRICE_HEADERS, [["INFY", "EQ", "2024-03-31", "100"]])
    config = survivorship.BacktestConfig(
        target_index="NIFTY 50",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        membership_snapshot_dates=(date(2024, 3, 31), date(2024, 6, 30)),
    )

    result = survivorship.analyze(root, tables_for(prices=prices), backtest=config)
    assessment = result.metrics["backtest_assessment"]
    check = next(
        item
        for item in assessment["checks"]
        if item["check"] == "requested_membership_snapshot_dates"
    )

    assert check["status"] == "unavailable"
    assert check["evidence"]["missing"] == ["2024-06-30"]
    assert check["evidence"]["requested"] == ["2024-03-31", "2024-06-30"]


def test_backtest_explicit_universe_confirms_only_snapshot_members(tmp_path: Path):
    root = tmp_path / "data"
    write_snapshot(root, "one.csv", [snapshot_row("INFY", "2024-03-31")])
    prices = make_table(
        "prices",
        PRICE_HEADERS,
        [
            ["INFY", "EQ", "2024-03-31", "100"],
            ["TCS", "EQ", "2024-03-31", "3000"],
        ],
    )
    config = survivorship.BacktestConfig(
        universe_symbols=("INFY", "TCS"),
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
    )

    result = survivorship.analyze(root, tables_for(prices=prices), backtest=config)
    universe = result.metrics["backtest_assessment"]["universe"]

    assert universe["status"] == "ok"
    assert universe["source"] == "supplied_universe_symbols_with_membership_snapshots"
    assert universe["universe_symbol_count"] == 2
    assert universe["membership_confirmed_count"] == 1
    assert universe["membership_unconfirmed_examples"] == ["TCS"]


def test_backtest_does_not_substitute_price_symbols_for_universe():
    prices = make_table("prices", PRICE_HEADERS, [["INFY", "EQ", "2024-01-10", "100"]])
    config = survivorship.BacktestConfig(
        target_index="NIFTY 50",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
    )

    result = survivorship.analyze(
        Path("/tmp/root"), tables_for(prices=prices), backtest=config
    )
    assessment = result.metrics["backtest_assessment"]

    assert assessment["universe"]["status"] == "unavailable"
    assert (
        "No dated point-in-time membership snapshot" in assessment["universe"]["reason"]
    )
    assert assessment["price_coverage"]["status"] == "unavailable"
    check = next(
        item for item in assessment["checks"] if item["check"] == "universe_resolution"
    )
    assert check["status"] == "unavailable"
    # The priced symbol INFY never becomes the requested universe.
    assert "INFY" not in assessment["universe"].get("universe_symbols", [])


def test_backtest_delisted_securities_limited_to_interval():
    delistings = make_table(
        "delistings",
        DELISTING_HEADERS,
        [
            [
                "OLDTECH",
                "INE111A01011",
                "Old Tech Limited",
                "Main Board",
                "2024-06-15",
                "Voluntary Delisting",
            ],
            [
                "NOPE",
                "INE999Z01099",
                "Nope Limited",
                "SME",
                "2025-01-15",
                "Compulsory Delisting",
            ],
        ],
    )
    prices = make_table(
        "prices", PRICE_HEADERS, [["NEWTECH", "EQ", "2024-06-10", "100"]]
    )
    symbol_changes = make_table(
        "symbol_changes",
        SYMBOL_CHANGE_HEADERS,
        [["Old Tech Limited", "OLDTECH", "NEWTECH", "2023-06-01"]],
    )
    config = survivorship.BacktestConfig(
        universe_symbols=("NEWTECH",),
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
    )

    result = survivorship.analyze(
        Path("/tmp/root"),
        tables_for(
            delistings=delistings,
            prices=prices,
            symbol_changes=symbol_changes,
        ),
        backtest=config,
    )
    interval = result.metrics["backtest_assessment"]["delisted_in_interval"]

    assert interval["status"] == "ok"
    assert interval["denominator"] == 1
    assert interval["match_classes"]["candidate"] == 1
    assert interval["with_price_history"] == 1
    assert interval["examples"][0]["symbol"] == "OLDTECH"
    assert interval["examples"][0]["match_class"] == "candidate"


def test_backtest_cli_writes_deterministic_json(tmp_path: Path):
    root = create_valid_data_root(tmp_path / "data")
    write_snapshot(root, "NIFTY_50_Jun2026.csv", [snapshot_row("INFY", "2026-06-30")])
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    args = [
        "--data-root",
        str(root),
        "--backtest-index",
        "NIFTY 50",
        "--backtest-start",
        "2026-01-01",
        "--backtest-end",
        "2026-12-31",
        "--backtest-min-price-coverage",
        "1.0",
    ]

    assert cli.main([*args, "--json-report", str(first)]) == 0
    assert cli.main([*args, "--json-report", str(second)]) == 0
    assert first.read_bytes() == second.read_bytes()

    payload = json.loads(first.read_text(encoding="utf-8"))
    analysis = next(
        dataset
        for dataset in payload["datasets"]
        if dataset["id"] == "survivorship:analysis"
    )
    assessment = analysis["metrics"]["backtest_assessment"]

    assert payload["overall_status"] == "WARN"
    assert analysis["metrics"]["analysis"]["mode"] == "backtest_specific_assessment"
    assert assessment["status"] == "partial"  # impact quantification is unavailable
    assert assessment["config"]["min_price_coverage"] == 1.0
    assert assessment["universe"]["universe_symbol_count"] == 1
    assert assessment["price_coverage"]["below_threshold_count"] == 0
    assert not any(
        issue["code"] == "runner.validator_exception" for issue in analysis["issues"]
    )


def test_backtest_cli_without_interval_reports_config_warning(tmp_path: Path, capsys):
    root = create_valid_data_root(tmp_path / "data")
    report_path = tmp_path / "report.json"

    exit_code = cli.main(
        [
            "--data-root",
            str(root),
            "--json-report",
            str(report_path),
            "--backtest-index",
            "NIFTY 50",
        ]
    )

    assert exit_code == 0
    assert "Overall status: WARN" in capsys.readouterr().out
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    analysis = next(
        dataset
        for dataset in payload["datasets"]
        if dataset["id"] == "survivorship:analysis"
    )
    codes = [issue["code"] for issue in analysis["issues"]]
    assert "survivorship.backtest_config_invalid" in codes
    assert "runner.validator_exception" not in codes
    assert analysis["metrics"]["backtest_assessment"]["status"] == "invalid"


def test_cli_unparseable_backtest_date_is_a_usage_error(tmp_path: Path):
    with pytest.raises(SystemExit) as excinfo:
        cli.main(
            [
                "--data-root",
                str(tmp_path / "data"),
                "--json-report",
                str(tmp_path / "report.json"),
                "--backtest-start",
                "31-Feb-2024",
            ]
        )

    assert excinfo.value.code == 2
    assert not (tmp_path / "report.json").exists()
