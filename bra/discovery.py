"""Dataset discovery for the collected NSE data tree.

Discovery is deliberately read-only. Missing expected files or empty dataset
groups become explicit failing dataset results rather than being skipped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

PRICE_PATTERN = "raw/*-ALL-N.csv"
CORPORATE_ACTION_PATTERN = "reference/corporate_actions/CF-CA-equities-*.csv"
FINANCIAL_PATTERN = "reference/financial_results/CF-FR-equities-*.csv"
INTEGRATED_FINANCIAL_PATTERN = (
    "reference/financial_results/additional/CF-Integrated-Filing-*Financials-*.csv"
)

PRICE_SYMBOL_RE = re.compile(r"TO-\d{2}-\d{2}-\d{4}-(?P<symbol>.+)-ALL-N\.csv$")
CORPORATE_ACTION_SYMBOL_RE = re.compile(
    r"^CF-CA-equities-(?P<symbol>.+?)-\d{2}-\d{2}-\d{4}-to-"
    r"\d{2}-\d{2}-\d{4}\.csv$"
)
FINANCIAL_SYMBOL_RE = re.compile(
    r"^CF-FR-equities-(?P<symbol>.+?)-\d{2}-\d{2}-\d{4}-to-"
    r"\d{2}-\d{2}-\d{4}\.csv$"
)
INTEGRATED_SYMBOL_RE = re.compile(
    r"Financials-(?P<symbol>.+?)-\d{2}-\d{2}-\d{4}-to-"
    r"\d{2}-\d{2}-\d{4}\.csv$"
)

KIND_ORDER = {
    "prices": 0,
    "corporate_actions": 1,
    "financials": 2,
    "integrated_financials": 3,
    "current_listing": 4,
    "name_changes": 5,
    "symbol_changes": 6,
    "delistings": 7,
}


@dataclass(frozen=True)
class DatasetSpec:
    """A discovered dataset or an explicit missing-dataset marker."""

    dataset_id: str
    category: str
    kind: str
    label: str
    path: Path | None
    relative_path: str
    expected_symbol: str | None = None
    missing: bool = False
    missing_message: str | None = None


def _extract_symbol(filename: str, pattern: re.Pattern[str]) -> str | None:
    match = pattern.search(filename)
    return match.group("symbol").upper() if match else None


def _relative(path: Path, data_root: Path) -> str:
    try:
        return path.relative_to(data_root).as_posix()
    except ValueError:
        return path.name


def _glob_specs(
    data_root: Path,
    pattern: str,
    *,
    kind: str,
    category: str,
    label_prefix: str,
    symbol_pattern: re.Pattern[str],
) -> list[DatasetSpec]:
    matches = sorted(data_root.glob(pattern))
    specs: list[DatasetSpec] = []
    for path in matches:
        if not path.is_file():
            continue
        filename = path.name
        symbol = _extract_symbol(filename, symbol_pattern)
        identifier = symbol or path.stem
        specs.append(
            DatasetSpec(
                dataset_id=f"{kind}:{identifier}",
                category=category,
                kind=kind,
                label=f"{label_prefix} - {identifier}",
                path=path,
                relative_path=_relative(path, data_root),
                expected_symbol=symbol,
            )
        )

    if not specs:
        specs.append(
            DatasetSpec(
                dataset_id=kind,
                category=category,
                kind=kind,
                label=f"{label_prefix} (missing)",
                path=None,
                relative_path=pattern.split("*")[0].rstrip("/") + "/",
                missing=True,
                missing_message=(
                    f"No files matching {pattern!r} were found under the data root."
                ),
            )
        )
    return specs


def discover_datasets(data_root: Path) -> list[DatasetSpec]:
    """Discover all supported datasets under ``data_root`` in stable order."""

    specs: list[DatasetSpec] = []

    specs.extend(
        _glob_specs(
            data_root,
            PRICE_PATTERN,
            kind="prices",
            category="historical_prices",
            label_prefix="Historical prices",
            symbol_pattern=PRICE_SYMBOL_RE,
        )
    )
    specs.extend(
        _glob_specs(
            data_root,
            CORPORATE_ACTION_PATTERN,
            kind="corporate_actions",
            category="corporate_actions",
            label_prefix="Corporate actions",
            symbol_pattern=CORPORATE_ACTION_SYMBOL_RE,
        )
    )
    specs.extend(
        _glob_specs(
            data_root,
            FINANCIAL_PATTERN,
            kind="financials",
            category="financial_results",
            label_prefix="Financial results",
            symbol_pattern=FINANCIAL_SYMBOL_RE,
        )
    )
    specs.extend(
        _glob_specs(
            data_root,
            INTEGRATED_FINANCIAL_PATTERN,
            kind="integrated_financials",
            category="financial_results",
            label_prefix="Integrated financial filings",
            symbol_pattern=INTEGRATED_SYMBOL_RE,
        )
    )

    fixed = [
        (
            "reference/listing_history/EQUITY_L.csv",
            "current_listing",
            "listing_reference",
            "Current listing reference",
        ),
        (
            "reference/listing_history/namechange.csv",
            "name_changes",
            "listing_reference",
            "Company name changes",
        ),
        (
            "reference/listing_history/symbolchange.csv",
            "symbol_changes",
            "listing_reference",
            "Symbol changes",
        ),
        (
            "processed/delisted_companies_2021-2026.csv",
            "delistings",
            "historical_delistings",
            "Delistings - all boards (2021-2026)",
        ),
        (
            "processed/main_board_delistings_2021-2026.csv",
            "delistings",
            "historical_delistings",
            "Delistings - main board (2021-2026)",
        ),
    ]

    for relative, kind, category, label in fixed:
        path = data_root / relative
        identifier = path.stem
        specs.append(
            DatasetSpec(
                dataset_id=f"{kind}:{identifier}",
                category=category,
                kind=kind,
                label=label,
                path=path,
                relative_path=relative,
                expected_symbol=None,
                missing=not path.is_file(),
                missing_message=None,
            )
        )

    return sorted(
        specs,
        key=lambda spec: (KIND_ORDER[spec.kind], spec.dataset_id),
    )
