"""Survivorship-bias coverage analysis.

The analysis is deliberately descriptive. It measures what the collected data
can and cannot cover, and it never treats a current listing snapshot, a
delisting event, or symbol equality as proof of historical universe membership
or security identity.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from ..csv_io import Row, Table, read_csv
from ..discovery import discover_datasets
from ..models import DatasetResult
from ..parsing import clean, format_date, parse_date
from .common import date_coverage

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
    }
)

PRICE_FILE_RE = re.compile(
    r"TO-\d{2}-\d{2}-\d{4}-(?P<symbol>.+)-ALL-N\.csv$",
)
INDEX_COVERAGE_START = date(2013, 9, 1)
MAX_EXAMPLES = 8


@dataclass(frozen=True)
class _CurrentListing:
    symbol: str
    name: str
    series: str
    listing_date: date | None
    isin: str
    row: int
    source: str


@dataclass(frozen=True)
class _Delisting:
    symbol: str
    isin: str
    name: str
    board: str
    delisted_date: date | None
    row: int
    source: str


@dataclass(frozen=True)
class _PriceRecord:
    symbol: str
    trade_date: date
    row: int
    source: str


@dataclass(frozen=True)
class _SymbolChange:
    old_symbol: str
    new_symbol: str
    company_name: str
    effective_date: date | None
    row: int
    source: str


@dataclass(frozen=True)
class _NameChange:
    symbol: str
    old_name: str
    new_name: str
    effective_date: date | None
    row: int
    source: str


def _text(row: Row, *columns: str) -> str:
    for column in columns:
        value = clean(row.get(column))
        if value:
            return value
    return ""


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def _load_relevant_tables(data_root: Path) -> dict[str, list[Table]]:
    """Read only the datasets needed by the cross-dataset analysis."""

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


def _select(
    tables: Mapping[str, Sequence[Table]],
    kinds: Sequence[str],
) -> Table | None:
    for kind in kinds:
        readable = [table for table in tables.get(kind, ()) if table.readable]
        if readable:
            return readable[0]
    return None


def _delisting_table(tables: Mapping[str, Sequence[Table]]) -> Table | None:
    derived = _select(tables, ("derived_delistings",))
    if derived is not None:
        return derived
    readable = [table for table in tables.get("delistings", ()) if table.readable]
    if not readable:
        return None
    # Prefer the all-board file over its main-board subset. The row count is a
    # data-derived tie-breaker; the path keeps the result deterministic.
    return min(readable, key=lambda table: (-len(table.rows), table.path.as_posix()))


def _price_tables(tables: Mapping[str, Sequence[Table]]) -> list[Table]:
    derived = [table for table in tables.get("derived_prices", ()) if table.readable]
    if derived:
        return derived
    return [table for table in tables.get("prices", ()) if table.readable]


def _security_key(record: _Delisting) -> tuple[str, str]:
    if record.isin:
        return ("isin", record.isin)
    if record.symbol:
        return ("symbol", record.symbol)
    if record.name:
        return ("name", record.name.casefold())
    return ("row", str(record.row))


def _parse_current_listings(
    table: Table,
    result: DatasetResult,
    source: str,
) -> tuple[list[_CurrentListing], list[date]]:
    records: list[_CurrentListing] = []
    dates: list[date] = []
    invalid_dates: list[tuple[int, str]] = []

    for row in table.rows:
        symbol = _text(row, "SYMBOL", "symbol")
        name = _text(row, "NAME OF COMPANY", "company_name")
        series = _text(row, "SERIES", "series")
        isin = _text(row, "ISIN NUMBER", "isin")
        date_text = _text(row, "DATE OF LISTING", "listing_date")
        listing_date = parse_date(date_text) if date_text else None
        if date_text and listing_date is None:
            invalid_dates.append((row.number, date_text))
        if listing_date is not None:
            dates.append(listing_date)
        records.append(
            _CurrentListing(
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


def _parse_delistings(
    table: Table,
    result: DatasetResult,
    source: str,
) -> tuple[list[_Delisting], list[date]]:
    records: list[_Delisting] = []
    dates: list[date] = []
    invalid_dates: list[tuple[int, str]] = []

    for row in table.rows:
        date_text = _text(row, "Delisted Date", "delisted_date")
        delisted_date = parse_date(date_text) if date_text else None
        if date_text and delisted_date is None:
            invalid_dates.append((row.number, date_text))
        if delisted_date is not None:
            dates.append(delisted_date)
        records.append(
            _Delisting(
                symbol=_text(row, "Symbol", "symbol"),
                isin=_text(row, "ISIN", "isin"),
                name=_text(row, "Company Name", "company_name"),
                board=_text(row, "Board", "board"),
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


def _parse_prices(
    tables: Sequence[Table],
    root: Path,
    result: DatasetResult,
) -> tuple[list[_PriceRecord], list[date]]:
    records: list[_PriceRecord] = []
    dates: list[date] = []
    invalid_dates: list[tuple[str, int, str]] = []
    missing_symbols: list[tuple[str, int]] = []

    for table in tables:
        source = _relative(table.path, root)
        fallback_match = PRICE_FILE_RE.search(table.path.name)
        fallback_symbol = (
            fallback_match.group("symbol").upper() if fallback_match else ""
        )
        for row in table.rows:
            symbol = _text(row, "Symbol", "symbol") or fallback_symbol
            date_text = _text(row, "Date", "trade_date")
            trade_date = parse_date(date_text) if date_text else None
            if not symbol:
                missing_symbols.append((source, row.number))
                continue
            if trade_date is None:
                invalid_dates.append((source, row.number, date_text))
                continue
            records.append(
                _PriceRecord(
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


def _parse_symbol_changes(
    table: Table,
    result: DatasetResult,
    source: str,
) -> list[_SymbolChange]:
    records: list[_SymbolChange] = []
    invalid_dates: list[tuple[int, str]] = []
    for row in table.rows:
        date_text = _text(row, "EFFECTIVE DATE", "effective_date")
        effective_date = parse_date(date_text) if date_text else None
        if date_text and effective_date is None:
            invalid_dates.append((row.number, date_text))
        records.append(
            _SymbolChange(
                old_symbol=_text(row, "OLD SYMBOL", "old_symbol"),
                new_symbol=_text(row, "NEW SYMBOL", "new_symbol"),
                company_name=_text(row, "NAME OF THE COMPANY", "company_name"),
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


def _parse_name_changes(
    table: Table,
    result: DatasetResult,
    source: str,
) -> list[_NameChange]:
    records: list[_NameChange] = []
    invalid_dates: list[tuple[int, str]] = []
    for row in table.rows:
        date_text = _text(row, "EFFECTIVE DATE", "effective_date")
        effective_date = parse_date(date_text) if date_text else None
        if date_text and effective_date is None:
            invalid_dates.append((row.number, date_text))
        records.append(
            _NameChange(
                symbol=_text(row, "SYMBOL", "symbol"),
                old_name=_text(row, "OLD NAME OF THE COMPANY", "old_name"),
                new_name=_text(row, "NEW NAME OF THE COMPANY", "new_name"),
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


def _price_metrics(
    prices: Sequence[_PriceRecord],
    dates: Sequence[date],
) -> dict[str, Any]:
    by_symbol: dict[str, dict[str, Any]] = {}
    for record in prices:
        entry = by_symbol.setdefault(
            record.symbol,
            {"rows": 0, "start": record.trade_date, "end": record.trade_date},
        )
        entry["rows"] += 1
        entry["start"] = min(entry["start"], record.trade_date)
        entry["end"] = max(entry["end"], record.trade_date)

    symbols = {
        symbol: {
            "rows": entry["rows"],
            "start": format_date(entry["start"]),
            "end": format_date(entry["end"]),
        }
        for symbol, entry in sorted(by_symbol.items())
    }
    start = min(dates) if dates else None
    end = max(dates) if dates else None
    return {
        "rows": len(prices),
        "symbol_count": len(symbols),
        "symbols": symbols,
        "date_range": (
            {"start": format_date(start), "end": format_date(end)} if dates else None
        ),
    }


def _symbol_alias_candidates(
    symbols: Sequence[str],
    delisted_date: date | None,
    changes: Sequence[_SymbolChange],
) -> dict[str, list[str]]:
    """Return cautious alias candidates reachable through symbol changes.

    The result is not an identity proof. It only says that a symbol-change
    record links the delisted symbol to another symbol that has price data.
    """

    forward: dict[str, list[_SymbolChange]] = defaultdict(list)
    reverse: dict[str, list[_SymbolChange]] = defaultdict(list)
    for change in changes:
        if not change.old_symbol or not change.new_symbol:
            continue
        forward[change.old_symbol].append(change)
        reverse[change.new_symbol].append(change)

    def allowed(change: _SymbolChange) -> bool:
        if delisted_date is None or change.effective_date is None:
            return True
        return change.effective_date <= delisted_date

    candidates: dict[str, list[str]] = {}

    def remember(symbol: str, path: list[str]) -> None:
        existing = candidates.get(symbol)
        if existing is None or (len(path), path) < (len(existing), existing):
            candidates[symbol] = path

    for start in sorted(set(symbols)):
        queue: list[tuple[str, list[str]]] = [(start, [])]
        visited = {start}
        while queue:
            current, path = queue.pop(0)
            next_changes = [
                (change.new_symbol, change, "forward")
                for change in forward.get(current, ())
                if allowed(change)
            ] + [
                (change.old_symbol, change, "reverse")
                for change in reverse.get(current, ())
                if allowed(change)
            ]
            for candidate, change, direction in sorted(
                next_changes,
                key=lambda item: (
                    item[0],
                    item[1].effective_date or date.min,
                    item[1].row,
                ),
            ):
                if not candidate or candidate in visited:
                    continue
                visited.add(candidate)
                step = (
                    f"{change.old_symbol}->{change.new_symbol}"
                    f"@{format_date(change.effective_date) or 'unknown'}"
                    f" ({direction})"
                )
                new_path = [*path, step]
                if candidate not in set(symbols):
                    remember(candidate, new_path)
                queue.append((candidate, new_path))
    return dict(sorted(candidates.items()))


def _current_index_membership_evidence(root: Path) -> dict[str, Any]:
    doc_candidates = [
        root / "docs/historical-universe-gap.md",
        root.parent / "docs/historical-universe-gap.md",
        Path(__file__).resolve().parents[2] / "docs/historical-universe-gap.md",
    ]
    document = next((path for path in doc_candidates if path.is_file()), None)

    index_candidates = [
        root / "reference/index_constituents",
        root / "data/reference/index_constituents",
    ]
    index_dir = next((path for path in index_candidates if path.is_dir()), None)
    sample_artifacts: list[str] = []
    if index_dir is not None:
        for pattern in ("extracted_csv/*.csv", "snapshots_pdfs/*.pdf", "*.zip"):
            sample_artifacts.extend(
                _relative(path, root) for path in sorted(index_dir.glob(pattern))
            )

    return {
        "coverage_start": "2013-09",
        "coverage_start_date": format_date(INDEX_COVERAGE_START),
        "coverage_start_basis": (
            "The project's NSE Indices monthly constituent archive begins in "
            "September 2013; the immediately preceding months are not available "
            "from that source."
        ),
        "documented_in": _relative(document, root) if document is not None else None,
        "sample_artifacts": sample_artifacts,
        "point_in_time_membership_dataset_present": False,
        "inferred_from_current_listings_or_delistings": False,
    }


def _security_groups(
    delistings: Sequence[_Delisting],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[_Delisting]] = defaultdict(list)
    for record in delistings:
        grouped[_security_key(record)].append(record)

    securities: list[dict[str, Any]] = []
    for key, records in sorted(grouped.items()):
        ordered = sorted(
            records,
            key=lambda record: (
                record.delisted_date or date.min,
                record.row,
            ),
        )
        first = ordered[0]
        dates = sorted(
            {
                record.delisted_date.isoformat()
                for record in records
                if record.delisted_date is not None
            }
        )
        securities.append(
            {
                "key": list(key),
                "symbols": sorted(
                    {record.symbol for record in records if record.symbol}
                ),
                "isins": sorted({record.isin for record in records if record.isin}),
                "names": sorted({record.name for record in records if record.name}),
                "boards": sorted({record.board for record in records if record.board}),
                "delisted_dates": dates,
                "record_count": len(records),
                "first": first,
            }
        )
    return securities


def _example(security: dict[str, Any], **extra: Any) -> dict[str, Any]:
    first: _Delisting = security["first"]
    data = {
        "symbol": first.symbol
        or (security["symbols"][0] if security["symbols"] else ""),
        "symbols": security["symbols"],
        "isin": first.isin or (security["isins"][0] if security["isins"] else ""),
        "company_name": first.name
        or (security["names"][0] if security["names"] else ""),
        "delisted_date": (
            security["delisted_dates"][0] if security["delisted_dates"] else None
        ),
    }
    data.update(extra)
    return data


def _find_delisted_price_coverage(
    securities: Sequence[dict[str, Any]],
    price_symbols: set[str],
    changes: Sequence[_SymbolChange],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    matched: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    direct_matches = 0
    alias_matches = 0

    for security in securities:
        symbols = security["symbols"]
        direct = sorted(set(symbols) & price_symbols)
        if direct:
            direct_matches += 1
            matched.append(
                _example(
                    security,
                    match_type="direct_symbol",
                    matched_symbol=direct[0],
                    identity_confirmed=False,
                )
            )
            continue

        latest_date = (
            date.fromisoformat(security["delisted_dates"][-1])
            if security["delisted_dates"]
            else None
        )
        aliases = _symbol_alias_candidates(symbols, latest_date, changes)
        alias_hits = sorted(set(aliases) & price_symbols)
        if alias_hits:
            alias_matches += 1
            symbol = alias_hits[0]
            matched.append(
                _example(
                    security,
                    match_type="symbol_change_candidate",
                    matched_symbol=symbol,
                    via_symbol_change=aliases[symbol],
                    identity_confirmed=False,
                )
            )
            continue

        unmatched.append(_example(security))

    metrics = {
        "delisting_records": sum(security["record_count"] for security in securities),
        "delisted_securities": len(securities),
        "matched_to_price_history": len(matched),
        "direct_symbol_matches": direct_matches,
        "symbol_change_candidate_matches": alias_matches,
        "unmatched": len(unmatched),
        "identity_confirmation": ("not_possible_from_symbol_and_delisting_data_alone"),
        "symbol_equality_is_not_identity": True,
        "matched_examples": matched[:MAX_EXAMPLES],
        "unmatched_examples": unmatched[:MAX_EXAMPLES],
    }
    return metrics, matched


def _identifier_reuse_evidence(
    securities: Sequence[dict[str, Any]],
    current: Sequence[_CurrentListing],
) -> dict[str, Any]:
    current_by_symbol: dict[str, list[_CurrentListing]] = defaultdict(list)
    current_by_isin: dict[str, list[_CurrentListing]] = defaultdict(list)
    for record in current:
        if record.symbol:
            current_by_symbol[record.symbol].append(record)
        if record.isin:
            current_by_isin[record.isin].append(record)

    both = 0
    symbol_only = 0
    isin_only = 0
    examples: list[dict[str, Any]] = []

    for security in securities:
        symbol_hits: list[_CurrentListing] = []
        for symbol in security["symbols"]:
            symbol_hits.extend(current_by_symbol.get(symbol, []))
        isin_hits: list[_CurrentListing] = []
        for isin in security["isins"]:
            isin_hits.extend(current_by_isin.get(isin, []))

        if not symbol_hits and not isin_hits:
            continue

        same_record = any(
            record.symbol in security["symbols"] and record.isin in security["isins"]
            for record in current
        )
        if same_record:
            kind = "symbol_and_isin"
            both += 1
        elif symbol_hits:
            kind = "symbol_only"
            symbol_only += 1
        else:
            kind = "isin_only"
            isin_only += 1

        current_hits = sorted(
            {
                (
                    record.symbol,
                    record.isin,
                    record.name,
                    format_date(record.listing_date) or "",
                )
                for record in [*symbol_hits, *isin_hits]
            }
        )
        examples.append(
            _example(
                security,
                match_type=kind,
                current_listings=[
                    {
                        "symbol": symbol,
                        "isin": isin,
                        "company_name": name,
                        "listing_date": listing_date or None,
                    }
                    for symbol, isin, name, listing_date in current_hits[:MAX_EXAMPLES]
                ],
            )
        )

    examples.sort(key=lambda item: (item["symbol"], item["isin"], item["match_type"]))
    return {
        "overlap_count": len(examples),
        "symbol_and_isin_overlaps": both,
        "symbol_only_overlaps": symbol_only,
        "isin_only_overlaps": isin_only,
        "examples": examples[:MAX_EXAMPLES],
        "identity_note": (
            "An overlap is evidence of a relisting or an identifier reuse. It is "
            "not proof that the current and delisted securities are the same "
            "company."
        ),
    }


def _reused_symbols_in_delistings(
    securities: Sequence[dict[str, Any]],
) -> dict[str, int]:
    keys_by_symbol: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for security in securities:
        key_value = security["key"]
        key = (str(key_value[0]), str(key_value[1]))
        for symbol in security["symbols"]:
            keys_by_symbol[symbol].add(key)
    return {
        symbol: len(keys)
        for symbol, keys in sorted(keys_by_symbol.items())
        if len(keys) > 1
    }


def _symbol_change_metrics(
    changes: Sequence[_SymbolChange],
) -> tuple[dict[str, Any], dict[str, list[str]]]:
    old_by_new: dict[str, set[str]] = defaultdict(set)
    noop = 0
    for change in changes:
        if not change.old_symbol or not change.new_symbol:
            continue
        if change.old_symbol == change.new_symbol:
            noop += 1
            continue
        old_by_new[change.new_symbol].add(change.old_symbol)
    shared = {
        new_symbol: sorted(old_symbols)
        for new_symbol, old_symbols in sorted(old_by_new.items())
        if len(old_symbols) > 1
    }
    return (
        {
            "records": len(changes),
            "noop_changes": noop,
            "shared_new_symbols": shared,
        },
        shared,
    )


def _continuity_examples(
    securities: Sequence[dict[str, Any]],
    current: Sequence[_CurrentListing],
    symbol_changes: Sequence[_SymbolChange],
    name_changes: Sequence[_NameChange],
) -> list[dict[str, Any]]:
    current_symbols = {record.symbol for record in current if record.symbol}
    current_isins = {record.isin for record in current if record.isin}
    changes_by_symbol: dict[str, list[_SymbolChange]] = defaultdict(list)
    names_by_symbol: dict[str, list[_NameChange]] = defaultdict(list)
    for change in symbol_changes:
        changes_by_symbol[change.old_symbol].append(change)
        changes_by_symbol[change.new_symbol].append(change)
    for change in name_changes:
        names_by_symbol[change.symbol].append(change)

    examples: list[dict[str, Any]] = []
    for security in securities:
        overlaps_current = any(
            symbol in current_symbols for symbol in security["symbols"]
        ) or any(isin in current_isins for isin in security["isins"])
        related: set[str] = set(security["symbols"])
        for symbol in security["symbols"]:
            for change in changes_by_symbol.get(symbol, ()):
                related.update(
                    value for value in (change.old_symbol, change.new_symbol) if value
                )
        if not related:
            continue
        relevant_symbol_changes = sorted(
            {
                (
                    change.old_symbol,
                    change.new_symbol,
                    format_date(change.effective_date) or "",
                    change.company_name,
                )
                for symbol in related
                for change in changes_by_symbol.get(symbol, ())
            }
        )
        relevant_name_changes = sorted(
            {
                (
                    change.symbol,
                    change.old_name,
                    change.new_name,
                    format_date(change.effective_date) or "",
                )
                for symbol in related
                for change in names_by_symbol.get(symbol, ())
            }
        )
        if not relevant_symbol_changes and not relevant_name_changes:
            continue
        if not overlaps_current and not relevant_symbol_changes:
            continue
        examples.append(
            _example(
                security,
                current_identifier_overlap=overlaps_current,
                symbol_changes=[
                    {
                        "old_symbol": old,
                        "new_symbol": new,
                        "effective_date": effective_date or None,
                        "company_name": company,
                    }
                    for old, new, effective_date, company in relevant_symbol_changes[
                        :MAX_EXAMPLES
                    ]
                ],
                name_changes=[
                    {
                        "symbol": symbol,
                        "old_name": old,
                        "new_name": new,
                        "effective_date": effective_date or None,
                    }
                    for symbol, old, new, effective_date in relevant_name_changes[
                        :MAX_EXAMPLES
                    ]
                ],
            )
        )
    examples.sort(key=lambda item: (item["symbol"], item["isin"]))
    return examples[:MAX_EXAMPLES]


def analyze(
    data_root: str | Path,
    tables: Mapping[str, Sequence[Table]] | None = None,
) -> DatasetResult:
    """Analyze survivorship-bias coverage without modifying any source file."""

    root = Path(data_root)
    if tables is None:
        tables = _load_relevant_tables(root)

    current_table = _select(
        tables,
        ("derived_current_listings", "current_listing"),
    )
    delisting_table = _delisting_table(tables)
    price_tables = _price_tables(tables)
    symbol_change_table = _select(
        tables,
        ("derived_symbol_changes", "symbol_changes"),
    )
    name_change_table = _select(
        tables,
        ("derived_name_changes", "name_changes"),
    )

    selected_tables = [
        table
        for table in (
            current_table,
            delisting_table,
            *price_tables,
            symbol_change_table,
            name_change_table,
        )
        if table is not None
    ]
    primary_path = (
        _relative(selected_tables[0].path, root) if selected_tables else "survivorship"
    )
    result = DatasetResult(
        dataset_id=ANALYSIS_DATASET_ID,
        category=ANALYSIS_CATEGORY,
        label=ANALYSIS_LABEL,
        path=primary_path,
    )

    current: list[_CurrentListing] = []
    current_dates: list[date] = []
    delistings: list[_Delisting] = []
    delisting_dates: list[date] = []
    prices: list[_PriceRecord] = []
    price_dates: list[date] = []
    symbol_changes: list[_SymbolChange] = []
    name_changes: list[_NameChange] = []

    if current_table is not None:
        current, current_dates = _parse_current_listings(
            current_table,
            result,
            _relative(current_table.path, root),
        )
    else:
        result.add_warning(
            "survivorship.current_listing_missing",
            (
                "No current listing reference was available. The current-snapshot "
                "check and relisting evidence are therefore incomplete."
            ),
        )

    if delisting_table is not None:
        delistings, delisting_dates = _parse_delistings(
            delisting_table,
            result,
            _relative(delisting_table.path, root),
        )
    else:
        result.add_warning(
            "survivorship.delistings_missing",
            (
                "No delisting history was available. Delisted-security price "
                "coverage cannot be calculated."
            ),
        )

    if price_tables:
        prices, price_dates = _parse_prices(price_tables, root, result)
    else:
        result.add_warning(
            "survivorship.prices_missing",
            (
                "No price history was available. Price symbol coverage and "
                "delisted-security matching cannot be calculated."
            ),
        )

    if symbol_change_table is not None:
        symbol_changes = _parse_symbol_changes(
            symbol_change_table,
            result,
            _relative(symbol_change_table.path, root),
        )
    if name_change_table is not None:
        name_changes = _parse_name_changes(
            name_change_table,
            result,
            _relative(name_change_table.path, root),
        )

    result.row_count = len(delistings)
    result.coverage = date_coverage(delisting_dates, "Delisted Date")

    current_date_range = (
        {
            "start": format_date(min(current_dates)),
            "end": format_date(max(current_dates)),
        }
        if current_dates
        else None
    )
    delisting_date_range = (
        {
            "start": format_date(min(delisting_dates)),
            "end": format_date(max(delisting_dates)),
        }
        if delisting_dates
        else None
    )
    price_metrics = _price_metrics(prices, price_dates)
    securities = _security_groups(delistings)
    delisted_coverage, _ = _find_delisted_price_coverage(
        securities,
        set(price_metrics["symbols"]),
        symbol_changes,
    )
    identifier_reuse = _identifier_reuse_evidence(securities, current)
    reused_symbols = _reused_symbols_in_delistings(securities)
    symbol_metrics, shared_new_symbols = _symbol_change_metrics(symbol_changes)
    continuity = _continuity_examples(
        securities,
        current,
        symbol_changes,
        name_changes,
    )
    index_evidence = _current_index_membership_evidence(root)

    result.metrics["analysis"] = {
        "dataset_id": ANALYSIS_DATASET_ID,
        "conclusion": (
            "This analysis measures coverage and identifier risks; it does not "
            "measure the magnitude of survivorship bias. The absence of a "
            "reported problem would not prove that survivorship bias is absent."
        ),
        "inputs": sorted(
            {
                _relative(table.path, root)
                for table in selected_tables
                if table is not None
            }
        ),
    }
    result.metrics["current_listing_snapshot"] = {
        "is_point_in_time_universe": False,
        "rows": len(current),
        "distinct_symbols": len({record.symbol for record in current if record.symbol}),
        "distinct_isins": len({record.isin for record in current if record.isin}),
        "date_range": current_date_range,
        "identity_note": (
            "A current listing reference contains only securities listed at "
            "extraction time. It does not record which securities belonged to a "
            "historical universe or an index on a past date."
        ),
    }
    result.metrics["price_coverage"] = price_metrics
    result.metrics["delisted_price_coverage"] = delisted_coverage
    result.metrics["index_membership"] = index_evidence
    result.metrics["identifier_reuse"] = identifier_reuse
    result.metrics["delisting_symbol_reuse"] = {
        "reused_symbols": reused_symbols,
        "reused_symbol_count": len(reused_symbols),
    }
    result.metrics["symbol_changes"] = symbol_metrics
    result.metrics["name_changes"] = {
        "records": len(name_changes),
        "symbols": len({change.symbol for change in name_changes if change.symbol}),
    }
    result.metrics["continuity_evidence"] = continuity
    result.metrics["data_facts"] = {
        "current_listing_rows": len(current),
        "current_listing_date_range": current_date_range,
        "delisting_records": len(delistings),
        "delisted_securities": len(securities),
        "delisting_date_range": delisting_date_range,
        "price_rows": len(prices),
        "price_symbols": sorted(price_metrics["symbols"]),
        "price_date_range": price_metrics["date_range"],
        "symbol_change_records": len(symbol_changes),
        "name_change_records": len(name_changes),
    }

    risks: list[str] = []
    limitations: list[str] = [
        (
            "The current listing reference is a present-day snapshot, not a "
            "point-in-time historical universe."
        ),
        (
            "Historical index-membership coverage begins in September 2013; "
            "earlier membership is unavailable from the project's archive."
        ),
    ]
    checks: list[str] = [
        "current_listings_not_used_as_historical_index_membership",
        "delisting_records_not_used_as_historical_index_membership",
    ]

    if current_table is not None:
        result.add_warning(
            "survivorship.current_listing_snapshot_not_point_in_time",
            (
                "The current listing reference is a present-day snapshot: "
                f"{len(current)} row(s), "
                f"{len({record.symbol for record in current if record.symbol})} "
                "distinct symbol(s). It records listing dates but not historical "
                "universe or index membership, so it is not used as a point-in-time "
                "universe."
            ),
        )

    result.add_warning(
        "survivorship.index_membership_coverage_gap",
        (
            "Point-in-time index-membership coverage is limited: the project's "
            "NSE Indices monthly archive begins in September 2013, and no "
            "historical membership timeline is present in the supplied data. "
            "Current listings and delisting records are not treated as index "
            "membership."
        ),
    )

    if delisting_table is not None and delisted_coverage["unmatched"]:
        limitations.append(
            f"{delisted_coverage['unmatched']} of "
            f"{delisted_coverage['delisted_securities']} delisted security(ies) "
            "have no matching price symbol. This is a coverage limitation, not "
            "proof that a backtest excluded those securities."
        )
        result.add_warning(
            "survivorship.delisted_price_coverage_gap",
            (
                f"{delisted_coverage['unmatched']} of "
                f"{delisted_coverage['delisted_securities']} delisted "
                "security(ies) have no direct or symbol-change price match. "
                "Missing delisted price history is a coverage limitation; it is "
                "not evidence that a backtest excluded those stocks."
            ),
        )

    if identifier_reuse["overlap_count"]:
        risks.append(
            f"{identifier_reuse['overlap_count']} delisted identifier(s) also "
            "appear in the current listing snapshot."
        )
        result.add_warning(
            "survivorship.relisted_or_reused_identifier",
            (
                f"{identifier_reuse['overlap_count']} delisted identifier(s) also "
                "appear in the current listing snapshot "
                f"(symbol and ISIN: {identifier_reuse['symbol_and_isin_overlaps']}, "
                f"symbol only: {identifier_reuse['symbol_only_overlaps']}, "
                f"ISIN only: {identifier_reuse['isin_only_overlaps']}). "
                "This is relisting or identifier-reuse evidence only; the "
                "identifiers are not assumed to prove the same company."
            ),
        )

    if reused_symbols:
        risks.append(
            f"{len(reused_symbols)} delisting symbol(s) occur in more than one "
            "security identity."
        )
        result.add_warning(
            "survivorship.reused_symbol_in_delisting_history",
            (
                f"{len(reused_symbols)} delisting symbol(s) are associated with "
                "more than one security identity (for example, different ISINs). "
                "Symbol equality alone is not treated as company identity."
            ),
        )

    if shared_new_symbols:
        risks.append(
            f"{len(shared_new_symbols)} new symbol(s) are shared by multiple old "
            "symbols in the change history."
        )
        result.add_warning(
            "survivorship.ambiguous_symbol_change",
            (
                f"{len(shared_new_symbols)} new symbol(s) are targets of multiple "
                "old symbols in the symbol-change history. Symbol-change chains "
                "are used only as coverage candidates, not identity proof."
            ),
        )

    if continuity:
        risks.append(
            f"{len(continuity)} identifier(s) have symbol/name continuity "
            "evidence that requires review."
        )

    if not result.issues or all(
        issue.severity.value == "warning" for issue in result.issues
    ):
        checks.append("all_checked_inputs_were_read_without_validation_errors")

    result.metrics["findings"] = {
        "confirmed_data_facts": result.metrics["data_facts"],
        "potential_survivorship_risks": risks,
        "coverage_limitations": limitations,
        "checks_passed": checks,
    }
    return result
