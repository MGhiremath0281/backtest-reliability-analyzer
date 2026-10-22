"""Validation orchestration."""

from __future__ import annotations

from pathlib import Path

from .csv_io import read_csv
from .discovery import DatasetSpec, discover_datasets
from .models import DatasetResult, Report
from .validators import corporate_actions, financials, listings, prices


def _validate_table(spec: DatasetSpec, table, result: DatasetResult) -> None:
    if spec.kind == "prices":
        prices.validate(table, result, spec.expected_symbol)
    elif spec.kind == "corporate_actions":
        corporate_actions.validate(table, result, spec.expected_symbol)
    elif spec.kind in {"financials", "integrated_financials"}:
        financials.validate(table, result, spec.expected_symbol)
    elif spec.kind == "current_listing":
        listings.validate_current_listing(table, result)
    elif spec.kind == "name_changes":
        listings.validate_name_changes(table, result)
    elif spec.kind == "symbol_changes":
        listings.validate_symbol_changes(table, result)
    elif spec.kind == "delistings":
        scope = (
            "main_board_delistings_2021_2026"
            if "main_board" in spec.relative_path
            else "all_board_delistings_2021_2026"
        )
        listings.validate_delistings(table, result, scope=scope)
    else:
        result.add_error(
            "runner.unknown_dataset_kind",
            f"No validator is registered for dataset kind {spec.kind!r}.",
        )


def run_validation(
    data_root: str | Path,
    specs: list[DatasetSpec] | None = None,
) -> Report:
    """Discover and validate every supported dataset under ``data_root``."""

    root = Path(data_root)
    dataset_specs = specs if specs is not None else discover_datasets(root)
    report = Report(data_root=str(data_root))

    for spec in dataset_specs:
        result = DatasetResult(
            dataset_id=spec.dataset_id,
            category=spec.category,
            label=spec.label,
            path=spec.relative_path,
        )

        if spec.path is None:
            result.add_error(
                "discovery.dataset_missing",
                spec.missing_message or "Dataset was not found.",
            )
            report.datasets.append(result)
            continue

        table = read_csv(spec.path)
        for issue in table.issues:
            result.add(issue)
        result.row_count = len(table.rows)

        if not table.readable:
            report.datasets.append(result)
            continue

        try:
            _validate_table(spec, table, result)
        except Exception as exc:  # noqa: BLE001 - report, do not hide, a broken dataset.
            result.add_error(
                "runner.validator_exception",
                f"{type(exc).__name__}: {exc}",
            )

        report.datasets.append(result)

    return report
