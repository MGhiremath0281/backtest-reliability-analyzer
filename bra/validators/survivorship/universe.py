"""Historical universe reconstruction from dated index-constituent snapshots.

The only accepted evidence of historical index membership is a dated,
authoritative constituent snapshot. Membership is reported per exact snapshot
date; it is never interpolated between snapshots and never inferred from
present-day listings, delisting records, or a symbol's price history.
"""

from __future__ import annotations

import itertools
from collections import defaultdict
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Any

from ...parsing import format_date
from .core import (
    INDEX_COVERAGE_START,
    IndexSnapshot,
    relative,
)

GAP_DOC_NAME = "docs/historical-universe-gap.md"

COVERAGE_START_BASIS = (
    "The project's NSE Indices monthly constituent archive begins in "
    "September 2013; the immediately preceding months are not available "
    "from that source."
)

REQUIRED_ADDITIONAL_SOURCE = (
    "A dated point-in-time index-constituent membership series (one row per "
    "constituent per membership/effective date, with index name, snapshot "
    "date, symbol, and a stable identifier such as the ISIN) covering the "
    "full backtest period."
)


def locate_gap_document(root: Path) -> Path | None:
    """Find the historical-universe gap investigation document."""

    candidates = [
        root / GAP_DOC_NAME,
        root.parent / GAP_DOC_NAME,
        Path(__file__).resolve().parents[3] / GAP_DOC_NAME,
    ]
    return next((path for path in candidates if path.is_file()), None)


def _document_reference(document: Path | None, root: Path) -> str | None:
    """Return a traceable path for the gap document.

    The document usually lives at the repository root while the data root is
    ``data/``, so the parent directory is also tried before falling back to
    the file name.
    """

    if document is None:
        return None
    for base in (root, root.parent):
        try:
            return document.relative_to(base).as_posix()
        except ValueError:
            continue
    return document.name


def _sample_artifacts(root: Path) -> list[str]:
    directory = root / "reference/index_constituents"
    if not directory.is_dir():
        directory = root / "data/reference/index_constituents"
    if not directory.is_dir():
        return []
    artifacts: list[str] = []
    for pattern in ("extracted_csv/*.csv", "snapshots_pdfs/*.pdf", "*.zip"):
        artifacts.extend(
            relative(path, root) for path in sorted(directory.glob(pattern))
        )
    return artifacts


def snapshot_groups(
    snapshots: Sequence[IndexSnapshot],
) -> list[dict[str, Any]]:
    """Group snapshot rows into dated membership records, deterministically.

    Each group is one authoritative membership observation: every member was
    listed in ``index_name`` on ``snapshot_date`` exactly as recorded.
    """

    grouped: dict[tuple[str, date], list[IndexSnapshot]] = defaultdict(list)
    for snapshot in snapshots:
        if snapshot.snapshot_date is None:
            continue
        grouped[(snapshot.index_name, snapshot.snapshot_date)].append(snapshot)

    groups: list[dict[str, Any]] = []
    for (index_name, snapshot_date), rows in sorted(grouped.items()):
        symbols = sorted({row.symbol for row in rows})
        source_files = sorted({row.source_file for row in rows})
        source_pdfs = sorted({row.source_pdf for row in rows if row.source_pdf})
        groups.append(
            {
                "index_name": index_name,
                "snapshot_date": format_date(snapshot_date),
                "_date": snapshot_date,
                "symbol_count": len(symbols),
                "symbols": symbols,
                "source_files": source_files,
                "source_pdfs": source_pdfs,
            }
        )
    return groups


def universe_symbols(snapshots: Sequence[IndexSnapshot]) -> set[str]:
    """Return every symbol observed in any dated membership snapshot."""

    return {
        snapshot.symbol
        for snapshot in snapshots
        if snapshot.snapshot_date is not None and snapshot.symbol
    }


def _index_gaps(groups: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Report every interval between consecutive snapshots of one index.

    Membership inside a gap is unverified; the gap is reported rather than
    bridged, because no source semantics justify interpolation.
    """

    by_index: dict[str, list[date]] = defaultdict(list)
    for group in groups:
        by_index[group["index_name"]].append(group["_date"])

    gaps: list[dict[str, Any]] = []
    for index_name in sorted(by_index):
        dates = sorted(by_index[index_name])
        for before, after in itertools.pairwise(dates):
            gaps.append(
                {
                    "index_name": index_name,
                    "after_snapshot": format_date(before),
                    "before_snapshot": format_date(after),
                    "days": (after - before).days,
                }
            )
    gaps.sort(
        key=lambda gap: (
            gap["index_name"],
            gap["after_snapshot"] or "",
            gap["before_snapshot"] or "",
        )
    )
    return gaps


def pooled_gaps(dates: Sequence[date]) -> list[dict[str, Any]]:
    """Gaps between consecutive snapshot dates across every collected index.

    These are the periods in which no membership evidence of any kind exists
    in the collected data. The gaps are reported, never bridged.
    """

    return [
        {
            "after_snapshot": format_date(before),
            "before_snapshot": format_date(after),
            "days": (after - before).days,
        }
        for before, after in itertools.pairwise(sorted(set(dates)))
    ]


def membership_metrics(
    snapshots: Sequence[IndexSnapshot],
    root: Path,
    excluded_rows: int = 0,
) -> dict[str, Any]:
    """Build the ``index_membership`` metrics block.

    Preserves the documented September 2013 archive floor and adds the actual
    dated-snapshot evidence that was collected.
    """

    document = locate_gap_document(root)
    groups = snapshot_groups(snapshots)
    dated = [snapshot for snapshot in snapshots if snapshot.snapshot_date is not None]

    dates = sorted({group["_date"] for group in groups})
    symbols = universe_symbols(snapshots)
    gaps = _index_gaps(groups)

    indexes: dict[str, dict[str, Any]] = {}
    for group in groups:
        entry = indexes.setdefault(
            group["index_name"],
            {"snapshot_count": 0, "snapshot_dates": [], "distinct_symbols": set()},
        )
        entry["snapshot_count"] += 1
        entry["snapshot_dates"].append(group["snapshot_date"])
        entry["distinct_symbols"].update(group["symbols"])
    index_summary = {
        index_name: {
            "snapshot_count": entry["snapshot_count"],
            "snapshot_dates": sorted(entry["snapshot_dates"]),
            "distinct_symbols": len(entry["distinct_symbols"]),
        }
        for index_name, entry in sorted(indexes.items())
    }

    snapshot_records = [
        {
            "index_name": group["index_name"],
            "snapshot_date": group["snapshot_date"],
            "symbol_count": group["symbol_count"],
            "source_files": group["source_files"],
            "source_pdfs": group["source_pdfs"],
        }
        for group in groups
    ]

    return {
        "coverage_start": "2013-09",
        "coverage_start_date": format_date(INDEX_COVERAGE_START),
        "coverage_start_basis": COVERAGE_START_BASIS,
        "documented_in": _document_reference(document, root),
        "sample_artifacts": _sample_artifacts(root),
        "point_in_time_membership_dataset_present": bool(dated),
        "inferred_from_current_listings_or_delistings": False,
        "snapshot_source": "reference/index_constituents/extracted_csv",
        "snapshot_count": len(groups),
        "constituent_rows": len(dated),
        "excluded_snapshot_rows": excluded_rows,
        "snapshots": snapshot_records,
        "indexes": index_summary,
        "date_range": (
            {"start": format_date(dates[0]), "end": format_date(dates[-1])}
            if dates
            else None
        ),
        "distinct_symbols": len(symbols),
        "membership_between_snapshots": "unverified" if dated else "unavailable",
        "interpolation_performed": False,
        "gaps": gaps,
        "coverage_gaps": pooled_gaps(dates),
        "required_additional_source": REQUIRED_ADDITIONAL_SOURCE,
    }
