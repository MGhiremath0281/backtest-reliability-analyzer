"""Derived-dataset validator tests, independent of the preparation code."""

from __future__ import annotations

from pathlib import Path

from bra.csv_io import read_csv
from bra.derived_schema import DERIVED_HEADERS
from bra.models import Status
from bra.prepare import prepare_all
from bra.runner import run_validation
from bra.validators import derived

from .support import create_prepare_data_root, issue_codes, make_result, write_csv


def _table(tmp_path: Path, kind: str, rows: list[list[str]]):
    path = write_csv(
        tmp_path / f"{kind}.csv",
        list(DERIVED_HEADERS[kind]),
        rows,
    )
    return read_csv(path)


def _fill(kind: str, **values: str) -> list[str]:
    return [values.get(column, "") for column in DERIVED_HEADERS[kind]]


def _price_row(**values: str) -> list[str]:
    defaults = {
        "symbol": "INFY",
        "series": "EQ",
        "trade_date": "2026-10-22",
        "prev_close": "100",
        "open": "100",
        "high": "110",
        "low": "90",
        "last": "105",
        "close": "105",
        "average": "101",
        "volume": "1000",
        "turnover": "100000",
        "trades": "10",
        "deliverable_qty": "100",
        "delivery_pct": "10",
        "source_file": "raw/example.csv",
        "source_line": "2",
    }
    defaults.update(values)
    return _fill("derived_prices", **defaults)


def test_valid_derived_prices_pass(tmp_path: Path):
    table = _table(tmp_path, "derived_prices", [_price_row()])
    result = make_result()

    derived.validate(table, result, "derived_prices")

    assert result.status is Status.PASS
    assert result.row_count == 1


def test_missing_column_fails(tmp_path: Path):
    headers = [
        column
        for column in DERIVED_HEADERS["derived_prices"]
        if column != "close"
    ]
    path = write_csv(tmp_path / "broken.csv", headers, [["x"] * len(headers)])
    result = make_result()

    derived.validate(read_csv(path), result, "derived_prices")

    assert result.status is Status.FAIL
    assert "columns.missing" in issue_codes(result)


def test_duplicate_key_fails(tmp_path: Path):
    table = _table(
        tmp_path,
        "derived_prices",
        [_price_row(), _price_row(source_line="3")],
    )
    result = make_result()

    derived.validate(table, result, "derived_prices")

    assert result.status is Status.FAIL
    assert "derived.duplicate_key" in issue_codes(result)


def test_non_iso_date_fails(tmp_path: Path):
    table = _table(
        tmp_path,
        "derived_prices",
        [_price_row(trade_date="22-Oct-2026")],
    )
    result = make_result()

    derived.validate(table, result, "derived_prices")

    assert result.status is Status.FAIL
    assert "derived.date_not_iso" in issue_codes(result)


def test_review_flags_are_preserved_as_warning(tmp_path: Path):
    table = _table(
        tmp_path,
        "derived_prices",
        [_price_row(review_flags="ohlc_anomaly_primary")],
    )
    result = make_result()

    derived.validate(table, result, "derived_prices")

    assert result.status is Status.WARN
    assert result.metrics["review_flag_counts"] == {"ohlc_anomaly_primary": 1}


def test_publication_lag_mismatch_fails(tmp_path: Path):
    row = _fill(
        "derived_financials_legacy",
        symbol="INFY",
        symbol_source="filename",
        company_name="Infosys Limited",
        period_end_date="2024-12-31",
        exchange_dissemination_time="2025-01-16 19:42:44",
        publication_lag_days="10",
        source_file="reference/example.csv",
        source_line="2",
    )
    table = _table(tmp_path, "derived_financials_legacy", [row])
    result = make_result()

    derived.validate(table, result, "derived_financials_legacy")

    assert result.status is Status.FAIL
    assert "derived.publication_lag_mismatch" in issue_codes(result)


def test_name_change_source_line_count_must_match(tmp_path: Path):
    row = _fill(
        "derived_name_changes",
        symbol="INFY",
        old_name="Old",
        new_name="New",
        effective_date="2024-01-01",
        source_record_count="2",
        source_lines="2",
        source_line="2",
        source_file="reference/namechange.csv",
        review_status="collapsed_exact_duplicates",
    )
    table = _table(tmp_path, "derived_name_changes", [row])
    result = make_result()

    derived.validate(table, result, "derived_name_changes")

    assert result.status is Status.FAIL
    assert "derived.source_lines_mismatch" in issue_codes(result)


def test_validation_run_includes_prepared_datasets(tmp_path: Path):
    root = create_prepare_data_root(tmp_path / "data")
    prepare_all(
        root,
        output_dir=root / "processed" / "normalized",
        audit_json=tmp_path / "audit.json",
        audit_doc=tmp_path / "audit.md",
    )

    report = run_validation(root)
    by_id = {dataset.dataset_id: dataset for dataset in report.datasets}

    assert "derived_prices:prices" in by_id
    assert "derived_delistings:delistings" in by_id
    assert by_id["derived_prices:prices"].row_count == 2
    assert by_id["derived_delistings:delistings"].row_count == 1
