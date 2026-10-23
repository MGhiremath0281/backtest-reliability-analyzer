"""Shared data structures, constants, and read-only input parsing.

Everything in this module only reads source files. Malformed rows are reported
as warnings on the supplied ``DatasetResult`` and excluded from coverage; they
are never repaired or rewritten in the source file.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

from ...csv_io import Row, Table, read_csv
from ...discovery import discover_datasets
from ...models import DatasetResult, Severity
from ...parsing import clean, parse_date

ANALYSIS_DATASET_ID = "survivorship:analysis"
ANALYSIS_CATEGORY = "survivorship_bias"
ANALYSIS_LABEL = "Survivorship-bias coverage analysis"

RELEVANT_KINDS = frozenset(
    {
        "prices",
        "derived_prices",
        "current_listing",
        "derived_current_listings",
        "delistings",
        "derived_delistings",
        "symbol_changes",
        "derived_symbol_changes",
        "name_changes",
        "derived_name_changes",
        "index_snapshot",
    }
)

PRICE_FILE_RE = re.compile(
    r"TO-\d{2}-\d{2}-\d{4}-(?P<symbol>.+)-ALL-N\.csv$",
)

# The project's NSE Indices monthly constituent archive begins in September
# 2013 (see docs/historical-universe-gap.md). This is a source-coverage floor
# and is independent of any dated snapshot that was actually collected.
INDEX_COVERAGE_START = date(2013, 9, 1)

MAX_EXAMPLES = 8

# Match classes for delisted-security price reconciliation.
MATCH_CONFIRMED = "confirmed"
MATCH_CANDIDATE = "candidate"
MATCH_AMBIGUOUS = "ambiguous"
MATCH_UNMATCHED = "unmatched"
MATCH_CLASSES = (
    MATCH_CONFIRMED,
    MATCH_CANDIDATE,
    MATCH_AMBIGUOUS,
    MATCH_UNMATCHED,
)

# Price-coverage classes for an eligible security.
COVERAGE_COMPLETE = "complete"
COVERAGE_PARTIAL = "partial"
COVERAGE_MISSING = "missing"
COVERAGE_AMBIGUOUS = "ambiguous"
COVERAGE_CLASSES = (
    COVERAGE_COMPLETE,
    COVERAGE_PARTIAL,
    COVERAGE_MISSING,
    COVERAGE_AMBIGUOUS,
)

INDEX_SNAPSHOT_DIRNAME = Path("reference/index_constituents")
INDEX_SNAPSHOT_GLOB = "extracted_csv/*.csv"
INDEX_SNAPSHOT_SOURCE = "reference/index_constituents/extracted_csv"

# Finding kinds used to separate evidence classes in the report.
KIND_FACT = "confirmed_data_fact"
KIND_RISK = "potential_survivorship_risk"
KIND_LIMITATION = "coverage_limitation"
KIND_CHECK = "check_passed"
KIND_UNVERIFIABLE = "unverifiable_conclusion"
KIND_BACKTEST = "backtest_specific_result"


@dataclass(frozen=True)
class CurrentListing:
    """One row of the current listing snapshot."""

    symbol: str
    name: str
    series: str
    listing_date: date | None
    isin: str
    row: int
    source: str


@dataclass(frozen=True)
class Delisting:
    """One row of a delisting-history dataset."""

    symbol: str
    isin: str
    name: str
    board: str
    delisted_date: date | None
    row: int
    source: str


@dataclass(frozen=True)
class PriceRecord:
    """One dated price row."""

    symbol: str
    trade_date: date
    row: int
    source: str


@dataclass(frozen=True)
class SymbolChange:
    """One effective-dated symbol-change record."""

    old_symbol: str
    new_symbol: str
    company_name: str
    effective_date: date | None
    row: int
    source: str


@dataclass(frozen=True)
class NameChange:
    """One effective-dated company-name-change record."""

    symbol: str
    old_name: str
    new_name: str
    effective_date: date | None
    row: int
    source: str


@dataclass(frozen=True)
class IndexSnapshot:
    """One constituent row of a dated index-membership snapshot."""

    symbol: str
    security_name: str
    index_name: str
    snapshot_date: date | None
    source_file: str
    source_pdf: str
    row: int


def text(row: Row, *columns: str) -> str:
    """Return the first non-blank value among ``columns``."""

    for column in columns:
        value = clean(row.get(column))
        if value:
            return value
    return ""


def relative(path: Path, root: Path) -> str:
    """Return ``path`` relative to ``root`` for traceable report references."""

    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def security_key(record: Delisting) -> tuple[str, str]:
    """Group delisting rows into securities by the strongest available identifier.

    A valid ISIN identifies one security line; a symbol or a case-folded name is
    only a fallback when the source row carries no ISIN. Symbol equality alone
    is never treated as company identity.
    """

    if record.isin:
        return ("isin", record.isin)
    if record.symbol:
        return ("symbol", record.symbol)
    if record.name:
        return ("name", record.name.casefold())
    return ("row", str(record.row))


def load_relevant_tables(data_root: Path) -> dict[str, list[Table]]:
    """Read only the discovered datasets needed by the cross-dataset analysis."""

    tables: dict[str, list[Table]] = defaultdict(list)
    if not data_root.exists():
        return {}
    for spec in discover_datasets(data_root):
        if spec.kind not in RELEVANT_KINDS:
            continue
        if spec.path is None or not spec.path.is_file():
            continue
        tables[spec.kind].append(read_csv(spec.path))
    return dict(tables)


def index_snapshot_dir(root: Path) -> Path | None:
    """Locate the collected index-constituent snapshot directory, if present."""

    candidates = [
        root / INDEX_SNAPSHOT_DIRNAME,
        root / "data" / INDEX_SNAPSHOT_DIRNAME,
    ]
    return next((path for path in candidates if path.is_dir()), None)


def load_index_snapshot_tables(root: Path) -> list[Table]:
    """Read every dated index-constituent snapshot CSV under ``root``.

    Snapshot files are reference inputs rather than discovered validation
    datasets, so they are read here. The files are opened read-only.
    """

    directory = index_snapshot_dir(root)
    if directory is None:
        return []
    return [
        read_csv(path)
        for path in sorted(directory.glob(INDEX_SNAPSHOT_GLOB))
        if path.is_file()
    ]


def snapshot_tables(
    tables: Mapping[str, Sequence[Table]] | None,
    root: Path,
) -> list[Table]:
    """Return index-snapshot tables from explicit inputs or the data root.

    Tests can inject snapshot tables under the ``index_snapshot`` kind.
    Otherwise the snapshots are loaded from the data root so the validation
    runner sees them without a discovery change.
    """

    if tables is not None and "index_snapshot" in tables:
        return list(tables.get("index_snapshot", ()))
    return load_index_snapshot_tables(root)


def select_table(
    tables: Mapping[str, Sequence[Table]],
    kinds: Sequence[str],
) -> Table | None:
    """Return the first readable table among ``kinds``, in priority order."""

    for kind in kinds:
        readable = [table for table in tables.get(kind, ()) if table.readable]
        if readable:
            return readable[0]
    return None


def delisting_table(tables: Mapping[str, Sequence[Table]]) -> Table | None:
    """Prefer the normalized delistings file, else the largest raw history."""

    derived = select_table(tables, ("derived_delistings",))
    if derived is not None:
        return derived
    readable = [table for table in tables.get("delistings", ()) if table.readable]
    if not readable:
        return None
    # Prefer the all-board file over its main-board subset. The row count is a
    # data-derived tie-breaker; the path keeps the result deterministic.
    return min(readable, key=lambda table: (-len(table.rows), table.path.as_posix()))


def price_tables(tables: Mapping[str, Sequence[Table]]) -> list[Table]:
    """Return readable price tables, preferring the normalized dataset."""

    derived = [table for table in tables.get("derived_prices", ()) if table.readable]
    if derived:
        return derived
    return [table for table in tables.get("prices", ()) if table.readable]


def attach_table_issues(
    result: DatasetResult,
    tables: Sequence[Table],
    root: Path,
) -> None:
    """Attach structural CSV findings for non-discovered inputs.

    Snapshot files are reference inputs rather than validated datasets of
    their own, so their loader findings (encoding, structure) are reported on
    the analysis result with the source path prefixed for traceability.
    Structural loader errors are downgraded to warnings: a broken reference
    input is a coverage limitation of this analysis and must not fail the
    validation run on its own. The original issue code is preserved so the
    underlying problem stays visible.
    """

    for table in tables:
        source = relative(table.path, root)
        for issue in table.issues:
            severity = (
                Severity.WARNING if issue.severity is Severity.ERROR else issue.severity
            )
            result.add(
                replace(
                    issue,
                    message=f"{source}: {issue.message}",
                    severity=severity,
                )
            )


def parse_current_listings(
    table: Table,
    result: DatasetResult,
    source: str,
) -> tuple[list[CurrentListing], list[date]]:
    """Parse the current listing snapshot; malformed dates become warnings."""

    records: list[CurrentListing] = []
    dates: list[date] = []
    invalid_dates: list[tuple[int, str]] = []

    for row in table.rows:
        symbol = text(row, "SYMBOL", "symbol")
        name = text(row, "NAME OF COMPANY", "company_name")
        series = text(row, "SERIES", "series")
        isin = text(row, "ISIN NUMBER", "isin")
        date_text = text(row, "DATE OF LISTING", "listing_date")
        listing_date = parse_date(date_text) if date_text else None
        if date_text and listing_date is None:
            invalid_dates.append((row.number, date_text))
        if listing_date is not None:
            dates.append(listing_date)
        records.append(
            CurrentListing(
                symbol=symbol,
                name=name,
                series=series,
                listing_date=listing_date,
                isin=isin,
                row=row.number,
                source=source,
            )
        )

    if invalid_dates:
        examples = ", ".join(
            f"line {line}: {value!r}" for line, value in invalid_dates[:MAX_EXAMPLES]
        )
        result.add_warning(
            "survivorship.current_listing_date_invalid",
            (
                f"{len(invalid_dates)} current-listing date(s) could not be parsed "
                f"({examples}). They were excluded from date coverage only."
            ),
        )
    return records, dates


def parse_delistings(
    table: Table,
    result: DatasetResult,
    source: str,
) -> tuple[list[Delisting], list[date]]:
    """Parse a delisting-history dataset; malformed dates become warnings."""

    records: list[Delisting] = []
    dates: list[date] = []
    invalid_dates: list[tuple[int, str]] = []

    for row in table.rows:
        date_text = text(row, "Delisted Date", "delisted_date")
        delisted_date = parse_date(date_text) if date_text else None
        if date_text and delisted_date is None:
            invalid_dates.append((row.number, date_text))
        if delisted_date is not None:
            dates.append(delisted_date)
        records.append(
            Delisting(
                symbol=text(row, "Symbol", "symbol"),
                isin=text(row, "ISIN", "isin"),
                name=text(row, "Company Name", "company_name"),
                board=text(row, "Board", "board"),
                delisted_date=delisted_date,
                row=row.number,
                source=source,
            )
        )

    if invalid_dates:
        examples = ", ".join(
            f"line {line}: {value!r}" for line, value in invalid_dates[:MAX_EXAMPLES]
        )
        result.add_warning(
            "survivorship.delisting_date_invalid",
            (
                f"{len(invalid_dates)} delisting date(s) could not be parsed "
                f"({examples}). They were excluded from date coverage only."
            ),
        )
    return records, dates


def parse_prices(
    tables: Sequence[Table],
    root: Path,
    result: DatasetResult,
) -> tuple[list[PriceRecord], list[date]]:
    """Parse price rows; rows without a symbol or date are excluded and warned."""

    records: list[PriceRecord] = []
    dates: list[date] = []
    invalid_dates: list[tuple[str, int, str]] = []
    missing_symbols: list[tuple[str, int]] = []

    for table in tables:
        source = relative(table.path, root)
        fallback_match = PRICE_FILE_RE.search(table.path.name)
        fallback_symbol = (
            fallback_match.group("symbol").upper() if fallback_match else ""
        )
        for row in table.rows:
            symbol = text(row, "Symbol", "symbol") or fallback_symbol
            date_text = text(row, "Date", "trade_date")
            trade_date = parse_date(date_text) if date_text else None
            if not symbol:
                missing_symbols.append((source, row.number))
                continue
            if trade_date is None:
                invalid_dates.append((source, row.number, date_text))
                continue
            records.append(
                PriceRecord(
                    symbol=symbol,
                    trade_date=trade_date,
                    row=row.number,
                    source=source,
                )
            )
            dates.append(trade_date)

    if invalid_dates:
        examples = ", ".join(
            f"{source} line {line}: {value!r}"
            for source, line, value in invalid_dates[:MAX_EXAMPLES]
        )
        result.add_warning(
            "survivorship.price_date_invalid",
            (
                f"{len(invalid_dates)} price row(s) have missing or malformed "
                f"dates ({examples}). They were not counted as price coverage."
            ),
        )
    if missing_symbols:
        examples = ", ".join(
            f"{source} line {line}" for source, line in missing_symbols[:MAX_EXAMPLES]
        )
        result.add_warning(
            "survivorship.price_symbol_missing",
            (
                f"{len(missing_symbols)} price row(s) have no symbol "
                f"({examples}). They were not counted as symbol coverage."
            ),
        )
    return records, dates


def parse_symbol_changes(
    table: Table,
    result: DatasetResult,
    source: str,
) -> list[SymbolChange]:
    """Parse effective-dated symbol changes; malformed dates become warnings."""

    records: list[SymbolChange] = []
    invalid_dates: list[tuple[int, str]] = []
    for row in table.rows:
        date_text = text(row, "EFFECTIVE DATE", "effective_date")
        effective_date = parse_date(date_text) if date_text else None
        if date_text and effective_date is None:
            invalid_dates.append((row.number, date_text))
        records.append(
            SymbolChange(
                old_symbol=text(row, "OLD SYMBOL", "old_symbol"),
                new_symbol=text(row, "NEW SYMBOL", "new_symbol"),
                company_name=text(row, "NAME OF THE COMPANY", "company_name"),
                effective_date=effective_date,
                row=row.number,
                source=source,
            )
        )
    if invalid_dates:
        examples = ", ".join(
            f"line {line}: {value!r}" for line, value in invalid_dates[:MAX_EXAMPLES]
        )
        result.add_warning(
            "survivorship.symbol_change_date_invalid",
            (
                f"{len(invalid_dates)} symbol-change effective date(s) could not "
                f"be parsed ({examples}). The relationships were retained but are "
                "not date-bounded."
            ),
        )
    return records


def parse_name_changes(
    table: Table,
    result: DatasetResult,
    source: str,
) -> list[NameChange]:
    """Parse effective-dated name changes; malformed dates become warnings."""

    records: list[NameChange] = []
    invalid_dates: list[tuple[int, str]] = []
    for row in table.rows:
        date_text = text(row, "EFFECTIVE DATE", "effective_date")
        effective_date = parse_date(date_text) if date_text else None
        if date_text and effective_date is None:
            invalid_dates.append((row.number, date_text))
        records.append(
            NameChange(
                symbol=text(row, "SYMBOL", "symbol"),
                old_name=text(row, "OLD NAME OF THE COMPANY", "old_name"),
                new_name=text(row, "NEW NAME OF THE COMPANY", "new_name"),
                effective_date=effective_date,
                row=row.number,
                source=source,
            )
        )
    if invalid_dates:
        examples = ", ".join(
            f"line {line}: {value!r}" for line, value in invalid_dates[:MAX_EXAMPLES]
        )
        result.add_warning(
            "survivorship.name_change_date_invalid",
            (
                f"{len(invalid_dates)} name-change effective date(s) could not be "
                f"parsed ({examples}). The records were retained as continuity "
                "evidence only."
            ),
        )
    return records


def parse_index_snapshots(
    tables: Sequence[Table],
    root: Path,
    result: DatasetResult,
) -> tuple[list[IndexSnapshot], list[date], int]:
    """Parse dated index-constituent snapshots.

    Returns the dated rows, their dates, and the number of rows excluded
    because they have no symbol or no parsable ``snapshot_date``. An undated
    row cannot be placed on a timeline, so it is excluded from membership and
    reported as a warning; no date is ever inferred for it.
    """

    records: list[IndexSnapshot] = []
    snapshot_dates: list[date] = []
    invalid_dates: list[tuple[str, int, str]] = []
    missing_symbols: list[tuple[str, int]] = []

    for table in tables:
        source = relative(table.path, root)
        for row in table.rows:
            symbol = text(row, "symbol", "Symbol", "SYMBOL")
            date_text = text(row, "snapshot_date", "Snapshot Date")
            snapshot_date = parse_date(date_text) if date_text else None
            if not symbol:
                missing_symbols.append((source, row.number))
                continue
            if snapshot_date is None:
                invalid_dates.append((source, row.number, date_text))
                continue
            records.append(
                IndexSnapshot(
                    symbol=symbol,
                    security_name=text(row, "security_name", "Security Name"),
                    index_name=text(row, "index_name", "Index Name") or "unknown",
                    snapshot_date=snapshot_date,
                    source_file=source,
                    source_pdf=text(row, "source_pdf", "Source PDF"),
                    row=row.number,
                )
            )
            snapshot_dates.append(snapshot_date)

    if invalid_dates:
        examples = ", ".join(
            f"{source} line {line}: {value!r}"
            for source, line, value in invalid_dates[:MAX_EXAMPLES]
        )
        result.add_warning(
            "survivorship.index_snapshot_date_invalid",
            (
                f"{len(invalid_dates)} index-snapshot row(s) have a missing or "
                f"malformed snapshot date ({examples}). They were excluded from "
                "membership because no date can be assigned to them."
            ),
        )
    if missing_symbols:
        examples = ", ".join(
            f"{source} line {line}" for source, line in missing_symbols[:MAX_EXAMPLES]
        )
        result.add_warning(
            "survivorship.index_snapshot_symbol_missing",
            (
                f"{len(missing_symbols)} index-snapshot row(s) have no symbol "
                f"({examples}). They were excluded from membership."
            ),
        )
    return records, snapshot_dates, len(invalid_dates) + len(missing_symbols)
