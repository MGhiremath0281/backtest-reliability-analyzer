"""Tests for the Survivorship-Bias Analyzer.

All fixtures are built in-memory or under ``tmp_path``. The collected source
datasets under ``data/`` are never read or modified.
"""

from __future__ import annotations

from pathlib import Path

from bra.csv_io import Row, Table
from bra.discovery import DatasetSpec
from bra.models import Status
from bra.runner import run_validation
from bra.validators import survivorship


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


def tables_for(**tables: Table) -> dict[str, list[Table]]:
    return {kind: [table] for kind, table in tables.items()}


def issue_codes(result) -> list[str]:
    return [issue.code for issue in result.issues]


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
