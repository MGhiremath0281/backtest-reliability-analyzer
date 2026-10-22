"""Dataset discovery and orchestration tests."""

from __future__ import annotations

from pathlib import Path

from bra.discovery import discover_datasets
from bra.models import Status
from bra.runner import run_validation

from .support import (
    create_valid_data_root,
    write_csv,
)


def test_discovers_expected_files_and_symbols(tmp_path: Path):
    root = create_valid_data_root(tmp_path / "data")
    write_csv(
        root / "reference/listing_history/ignored.xlsx",
        ["not", "a", "csv"],
        [],
    )

    specs = discover_datasets(root)
    by_id = {spec.dataset_id: spec for spec in specs}

    assert "prices:INFY" in by_id
    assert by_id["prices:INFY"].expected_symbol == "INFY"
    assert "corporate_actions:INFY" in by_id
    assert "financials:INFY" in by_id
    assert "integrated_financials:INFY" in by_id
    assert "current_listing:EQUITY_L" in by_id
    assert "name_changes:namechange" in by_id
    assert "symbol_changes:symbolchange" in by_id
    assert "delistings:delisted_companies_2021-2026" in by_id
    assert "delistings:main_board_delistings_2021-2026" in by_id
    assert all("ignored" not in spec.dataset_id for spec in specs)


def test_missing_data_root_produces_explicit_missing_datasets(tmp_path: Path):
    root = tmp_path / "missing"

    specs = discover_datasets(root)

    assert any(spec.kind == "prices" and spec.missing for spec in specs)
    assert any(spec.kind == "corporate_actions" and spec.missing for spec in specs)
    assert any(spec.kind == "current_listing" and spec.missing for spec in specs)

    report = run_validation(root)

    assert report.overall_status is Status.FAIL
    assert len(report.datasets) == len(specs)
    assert all(dataset.status is Status.FAIL for dataset in report.datasets)
    assert all(
        any("missing" in issue.code for issue in dataset.issues)
        for dataset in report.datasets
    )


def test_run_validation_on_complete_fixture_passes(tmp_path: Path):
    root = create_valid_data_root(tmp_path / "data")

    report = run_validation(root)

    assert report.overall_status is Status.PASS
    assert report.summary()["pass"] == len(report.datasets)
    assert report.error_count == 0
    assert report.warning_count == 0


def test_discovery_is_stable_and_relative(tmp_path: Path):
    root = create_valid_data_root(tmp_path / "data")

    first = [spec.dataset_id for spec in discover_datasets(root)]
    second = [spec.dataset_id for spec in discover_datasets(root)]

    assert first == second
    assert all(
        not Path(spec.relative_path).is_absolute() for spec in discover_datasets(root)
    )


def test_empty_group_creates_one_missing_marker(tmp_path: Path):
    root = tmp_path / "data"
    (root / "raw").mkdir(parents=True)

    specs = discover_datasets(root)
    price_specs = [spec for spec in specs if spec.kind == "prices"]

    assert len(price_specs) == 1
    assert price_specs[0].missing
    assert price_specs[0].path is None
