"""Validation orchestration."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from .csv_io import Table, read_csv
from .derived_schema import DERIVED_HEADERS
from .discovery import DatasetSpec, discover_datasets
from .models import DatasetResult, Report
from .validators import (
    corporate_actions,
    derived,
    financials,
    listings,
    lookahead,
    prices,
    survivorship,
)


def _validate_table(
    spec: DatasetSpec,
    table,
    result: DatasetResult,
    tables_by_kind: dict[str, list] | None = None,
) -> None:
    if spec.kind == "prices":
        prices.validate(table, result, spec.expected_symbol)
    elif spec.kind == "corporate_actions":
        price_table = None
        if tables_by_kind is not None and "prices" in tables_by_kind:
            price_table = (
                tables_by_kind["prices"][0] if tables_by_kind["prices"] else None
            )
        corporate_actions.validate(
            table, result, spec.expected_symbol, price_table=price_table
        )
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
    elif spec.kind in DERIVED_HEADERS:
        derived.validate(table, result, spec.kind)
    else:
        result.add_error(
            "runner.unknown_dataset_kind",
            f"No validator is registered for dataset kind {spec.kind!r}.",
        )


def run_validation(
    data_root: str | Path,
    specs: list[DatasetSpec] | None = None,
    backtest: survivorship.BacktestConfig | None = None,
    lookahead_config: lookahead.LookaheadConfig | None = None,
) -> Report:
    """Discover and validate every supported dataset under ``data_root``.

    ``backtest`` optionally enables the backtest-specific survivorship
    assessment; ``lookahead_config`` optionally enables the backtest-specific
    look-ahead assessment. When omitted, the respective analyzer runs only
    the general data-coverage audit and backtest-specific results are
    reported as unavailable.
    """

    root = Path(data_root)
    dataset_specs = specs if specs is not None else discover_datasets(root)
    report = Report(data_root=str(data_root))
    tables_by_kind: dict[str, list[Table]] = defaultdict(list)

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

        tables_by_kind[spec.kind].append(table)

        try:
            _validate_table(spec, table, result, tables_by_kind=tables_by_kind)
        except Exception as exc:  # noqa: BLE001 - report, do not hide, a broken dataset.
            result.add_error(
                "runner.validator_exception",
                f"{type(exc).__name__}: {exc}",
            )

        report.datasets.append(result)

    if any(kind in tables_by_kind for kind in survivorship.RELEVANT_KINDS):
        try:
            report.datasets.append(
                survivorship.analyze(root, tables_by_kind, backtest=backtest)
            )
        except Exception as exc:  # noqa: BLE001 - keep analysis failures visible.
            analysis = DatasetResult(
                dataset_id=survivorship.ANALYSIS_DATASET_ID,
                category=survivorship.ANALYSIS_CATEGORY,
                label=survivorship.ANALYSIS_LABEL,
                path="survivorship",
            )
            analysis.add_error(
                "runner.validator_exception",
                f"{type(exc).__name__}: {exc}",
            )
            report.datasets.append(analysis)

    if any(kind in tables_by_kind for kind in lookahead.LOOKAHEAD_RELEVANT_KINDS):
        try:
            report.datasets.append(
                lookahead.analyze(root, tables_by_kind, config=lookahead_config)
            )
        except Exception as exc:  # noqa: BLE001 - keep analysis failures visible.
            analysis = DatasetResult(
                dataset_id=lookahead.LOOKAHEAD_DATASET_ID,
                category=lookahead.LOOKAHEAD_CATEGORY,
                label=lookahead.LOOKAHEAD_LABEL,
                path="lookahead",
            )
            analysis.add_error(
                "runner.validator_exception",
                f"{type(exc).__name__}: {exc}",
            )
            report.datasets.append(analysis)

    return report
