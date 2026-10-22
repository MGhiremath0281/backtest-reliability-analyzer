"""Preparation pipeline, normalization, and reproducibility tests."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from bra.discovery import discover_datasets
from bra.parsing import parse_date
from bra.prepare import prepare_all

from .support import (
    DELISTING_HEADERS,
    NAME_CHANGE_HEADERS,
    PRICE_HEADERS,
    create_prepare_data_root,
    excel_serial,
    name_change_row,
    price_row,
    write_csv,
    write_xlsx,
)


def _hash_tree(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _run(root: Path, tmp_path: Path):
    return prepare_all(
        root,
        output_dir=root / "processed" / "normalized",
        audit_json=tmp_path / "audit.json",
        audit_doc=tmp_path / "audit.md",
    )


def test_prepare_writes_all_normalized_outputs(tmp_path: Path):
    root = create_prepare_data_root(tmp_path / "data")

    run = _run(root, tmp_path)

    expected_rows = {
        "prices": 2,
        "corporate_actions": 1,
        "financial_results_legacy": 1,
        "financial_results_integrated": 1,
        "current_listings": 1,
        "name_changes": 1,
        "symbol_changes": 1,
        "delistings": 1,
    }
    assert {
        transform.name: len(transform.rows) for transform in run.transforms
    } == expected_rows
    for filename in (
        "prices.csv",
        "corporate_actions.csv",
        "financial_results_legacy.csv",
        "financial_results_integrated.csv",
        "current_listings.csv",
        "name_changes.csv",
        "symbol_changes.csv",
        "delistings.csv",
    ):
        assert (root / "processed" / "normalized" / filename).is_file()
    assert run.audit_json.is_file()
    assert run.audit_doc.is_file()


def test_prepare_normalizes_dates_and_numbers(tmp_path: Path):
    root = create_prepare_data_root(tmp_path / "data")

    run = _run(root, tmp_path)
    prices = {item.name: item for item in run.transforms}["prices"]

    assert [row["trade_date"] for row in prices.rows] == [
        "2026-10-22",
        "2026-10-21",
    ]
    assert prices.rows[0]["volume"] == "1000"
    assert prices.rows[0]["turnover"] == "100000"
    assert prices.rows[0]["source_file"].startswith("raw/")


def test_prepare_normalizes_timestamps_and_publication_lag(tmp_path: Path):
    root = create_prepare_data_root(tmp_path / "data")

    run = _run(root, tmp_path)
    legacy = {item.name: item for item in run.transforms}[
        "financial_results_legacy"
    ]

    assert legacy.rows[0]["exchange_received_time"] == "2025-01-16 19:42:10"
    assert (
        legacy.rows[0]["exchange_dissemination_time"] == "2025-01-16 19:42:44"
    )
    assert legacy.rows[0]["publication_lag_days"] == "16"


def test_prepare_trims_identifier_whitespace_and_flags_it(tmp_path: Path):
    root = create_prepare_data_root(tmp_path / "data")
    write_csv(
        root / "raw/22-10-2021-TO-22-10-2026-INFY-ALL-N.csv",
        PRICE_HEADERS,
        [price_row("22-Oct-2026", symbol=" INFY ", series=" EQ ")],
    )

    run = _run(root, tmp_path)
    prices = {item.name: item for item in run.transforms}["prices"]

    assert prices.rows[0]["symbol"] == "INFY"
    assert prices.rows[0]["series"] == "EQ"
    assert "identifier_whitespace_trimmed" in prices.rows[0]["review_flags"]


def test_prepare_preserves_malformed_delisting_isin(tmp_path: Path):
    root = create_prepare_data_root(tmp_path / "data")
    workbook = next((root / "reference/listing_history").glob("*.xlsx"))
    write_xlsx(
        workbook,
        {
            "delisted": [
                DELISTING_HEADERS,
                [
                    "OLDTECH",
                    "Not Available",
                    "Old Tech Limited",
                    "Main Board",
                    excel_serial(date(2024, 1, 15)),
                    "Voluntary Delisting",
                ],
            ]
        },
    )

    run = _run(root, tmp_path)
    delistings = {item.name: item for item in run.transforms}["delistings"]

    assert delistings.rows[0]["isin"] == "Not Available"
    assert "malformed_isin" in delistings.rows[0]["review_flags"]


def test_prepare_flags_current_listing_that_matches_delisting_history(
    tmp_path: Path,
):
    root = create_prepare_data_root(tmp_path / "data")
    write_csv(
        root / "reference/listing_history/EQUITY_L.csv",
        [
            "SYMBOL",
            "NAME OF COMPANY",
            "SERIES",
            "DATE OF LISTING",
            "PAID UP VALUE",
            "MARKET LOT",
            "ISIN NUMBER",
            "FACE VALUE",
        ],
        [
            [
                "OLDTECH",
                "Old Tech Limited",
                "EQ",
                "15-JAN-2024",
                "5",
                "1",
                "INE123A01018",
                "5",
            ]
        ],
    )

    run = _run(root, tmp_path)
    current = {item.name: item for item in run.transforms}["current_listings"]

    assert "relisted_or_reused_identifier" in current.rows[0]["review_flags"]
    assert current.details["delisting_cross_references"][0][
        "matched_delistings"
    ][0]["delisted_date"] == "2024-01-15"



def test_prepare_corporate_action_sentinels_become_blank(tmp_path: Path):
    root = create_prepare_data_root(tmp_path / "data")

    run = _run(root, tmp_path)
    corporate_actions = {item.name: item for item in run.transforms}[
        "corporate_actions"
    ]

    assert corporate_actions.rows[0]["book_closure_start_date"] == ""
    assert corporate_actions.rows[0]["book_closure_end_date"] == ""
    assert corporate_actions.rows[0]["source_line"] == "2"


def test_prepare_invalid_date_is_left_blank_and_flagged(tmp_path: Path):
    root = create_prepare_data_root(tmp_path / "data")
    write_csv(
        root / "raw/22-10-2021-TO-22-10-2026-INFY-ALL-N.csv",
        PRICE_HEADERS,
        [price_row("not-a-date")],
    )

    run = _run(root, tmp_path)
    prices = {item.name: item for item in run.transforms}["prices"]

    assert prices.rows[0]["trade_date"] == ""
    assert "invalid_date" in prices.rows[0]["review_flags"]
    assert prices.rows[0]["source_line"] == "2"


def test_prepare_integrated_symbol_falls_back_to_filename(tmp_path: Path):
    root = create_prepare_data_root(tmp_path / "data")
    path = (
        root
        / "reference/financial_results/additional/"
        "CF-Integrated-Filing-equities-Integrated Filing- Financials-INFY-"
        "01-01-2025-to-22-10-2026.csv"
    )
    write_csv(
        path,
        [
            "SYMBOL",
            "COMPANY NAME",
            "QUARTER END DATE",
            "TYPE OF SUBMISSION",
            "AUDITED / UNAUDITED",
            "CONSOLIDATED / STANDALONE",
            "DETAILS",
            "XBRL",
            "BROADCAST DATE/TIME",
            "REVISED DATE/TIME",
            "REVISION REMARKS",
            "EXCHANGE DISSEMINATION TIME",
            "TIME TAKEN",
        ],
        [
            [
                "",
                "Infosys Limited",
                "31-Dec-2024",
                "Original",
                "Audited",
                "Consolidated",
                "https://example.invalid/details",
                "https://example.invalid/xbrl",
                "16-Jan-2025 19:42:00",
                "",
                "",
                "16-Jan-2025 19:42:44",
                "00:00:44",
            ]
        ],
    )

    run = _run(root, tmp_path)
    integrated = {item.name: item for item in run.transforms}[
        "financial_results_integrated"
    ]

    assert integrated.rows[0]["symbol"] == "INFY"
    assert integrated.rows[0]["symbol_source"] == "filename_fallback"
    assert "missing_symbol" in integrated.rows[0]["review_flags"]


def test_prepare_collapses_only_exact_name_change_duplicates(tmp_path: Path):
    root = create_prepare_data_root(tmp_path / "data")
    write_csv(
        root / "reference/listing_history/namechange.csv",
        NAME_CHANGE_HEADERS,
        [
            name_change_row(),
            name_change_row(),
            name_change_row(),
            name_change_row(old_name="Old Infosys Ltd"),
            name_change_row(symbol="TCS"),
        ],
    )

    run = _run(root, tmp_path)
    name_changes = {item.name: item for item in run.transforms}["name_changes"]

    assert len(name_changes.rows) == 3
    collapsed = next(
        row for row in name_changes.rows if row["source_record_count"] == "3"
    )
    assert collapsed["review_status"] == "collapsed_exact_duplicates"
    assert collapsed["source_lines"].count(";") == 2
    assert "overlapping_variant" in collapsed["review_flags"]
    shared = next(row for row in name_changes.rows if row["symbol"] == "TCS")
    assert "shared_event_across_symbols" in shared["review_flags"]
    assert name_changes.details["exact_duplicate_group_count"] == 1
    assert name_changes.details["exact_duplicate_extra_records"] == 2


def test_prepare_uses_primary_delisting_sheet_and_flags_conflicts(tmp_path: Path):
    root = create_prepare_data_root(tmp_path / "data")
    workbook = next(
        (root / "reference/listing_history").glob("*.xlsx")
    )
    write_xlsx(
        workbook,
        {
            "delisted": [
                DELISTING_HEADERS,
                [
                    "OLDTECH",
                    "INE123A01018",
                    "Old Tech Limited",
                    "Main Board",
                    excel_serial(date(2024, 1, 15)),
                    "Voluntary Delisting",
                ],
            ],
            "Add Data-Comp. Delisted": [
                DELISTING_HEADERS,
                [
                    "OLDTECH",
                    "INE123A01018",
                    "Old Tech Limited",
                    "Main Board",
                    excel_serial(date(2024, 1, 16)),
                    "Compulsory Delisting",
                ],
            ],
        },
    )

    run = _run(root, tmp_path)
    delistings = {item.name: item for item in run.transforms}["delistings"]

    assert delistings.rows[0]["delisted_date"] == "2024-01-15"
    assert delistings.rows[0]["delisting_type"] == "Voluntary Delisting"
    assert "auxiliary_sheet_conflict" in delistings.rows[0]["review_flags"]
    assert delistings.details["auxiliary_sheets"][0]["conflict_rows"]


def test_prepare_never_modifies_sources_and_is_deterministic(tmp_path: Path):
    root = create_prepare_data_root(tmp_path / "data")
    before = _hash_tree(root)

    first = _run(root, tmp_path)
    first_outputs = {
        name: path.read_bytes() for name, path in first.output_paths.items()
    }
    first_audit = first.audit_json.read_bytes()
    first_doc = first.audit_doc.read_bytes()

    after = _hash_tree(root)
    for relative, content in before.items():
        assert after[relative] == content, f"source changed: {relative}"

    second = _run(root, tmp_path)
    assert {
        name: path.read_bytes() for name, path in second.output_paths.items()
    } == first_outputs
    assert second.audit_json.read_bytes() == first_audit
    assert second.audit_doc.read_bytes() == first_doc


def test_audit_records_coverage_and_assessments(tmp_path: Path):
    root = create_prepare_data_root(tmp_path / "data")

    run = _run(root, tmp_path)
    audit = run.audit

    assert audit["source_inventory"]["file_count"] >= 10
    assert audit["transformations"]["delistings"]["input_records"] == 1
    assert audit["cross_dataset"]["price_symbols"] == ["INFY"]
    assert "not_supported" in audit["assessments"]["A_survivorship_bias"]["verdict"]
    assert "partially_supported" in audit["assessments"]["B_look_ahead_bias"]["verdict"]
    assert "not_verifiable" in audit["assessments"]["C_corporate_actions"]["verdict"]
    assert any(
        item["path"].endswith("namechange.csv")
        for item in audit["source_inventory"]["files"]
    )


def test_discovery_only_adds_derived_datasets_after_preparation(tmp_path: Path):
    root = create_prepare_data_root(tmp_path / "data")

    before = {spec.dataset_id for spec in discover_datasets(root)}
    assert not any(dataset_id.startswith("derived_") for dataset_id in before)

    _run(root, tmp_path)
    after = {spec.dataset_id for spec in discover_datasets(root)}

    assert after - before == {
        "derived_prices:prices",
        "derived_corporate_actions:corporate_actions",
        "derived_financials_legacy:financial_results_legacy",
        "derived_financials_integrated:financial_results_integrated",
        "derived_current_listings:current_listings",
        "derived_name_changes:name_changes",
        "derived_symbol_changes:symbol_changes",
        "derived_delistings:delistings",
    }


def test_normalized_dates_are_iso(tmp_path: Path):
    root = create_prepare_data_root(tmp_path / "data")

    run = _run(root, tmp_path)
    for transform in run.transforms:
        for row in transform.rows:
            for column in ("trade_date", "ex_date", "effective_date", "delisted_date"):
                value = row.get(column)
                if value:
                    assert parse_date(value) is not None
                    assert parse_date(value).isoformat() == value
