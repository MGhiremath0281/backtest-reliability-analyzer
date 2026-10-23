"""Temporal-ordering evidence computations.

These helpers turn parsed rows into the evidence the checks reason about:
when a financial result plausibly became public, when a revision was
relatively published, which corporate-action periods have surrounding prices,
and which dated membership snapshots were collected. Every function is pure
and deterministic: the same inputs always produce the same structures, and no
value is ever inferred from a period, ex, record, or effective date alone.
"""

from __future__ import annotations

import itertools
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Any

from ...parsing import format_date, format_timestamp
from .core import (
    FINANCIAL_KINDS,
    MAX_EXAMPLES,
    CorporateActionRecord,
    FinancialRecord,
    PriceRecord,
)

ANNOUNCEMENT_NOTE = (
    "Corporate-action exports record EX-DATE and RECORD DATE only; they "
    "contain no announcement, board-approval, or publication timestamp, so "
    "the moment at which an action (or its per-share amount) became public "
    "cannot be verified."
)

PRICE_NOTE = (
    "Price rows carry trade dates only; the collected exports contain no "
    "timestamp for when a quote became available, so intraday price "
    "availability cannot be verified."
)

SNAPSHOT_NOTE = (
    "Dated membership snapshots verify membership only on their own dates; "
    "membership on every other date is unverified and is never interpolated."
)

REQUIRED_ANNOUNCEMENT_SOURCE = (
    "Corporate-action announcement timestamps (a public-availability moment "
    "per event, as delivered by the exchange)."
)

REQUIRED_PRICE_SOURCE = (
    "Quote-availability timestamps, or the backtest's feature-computation "
    "timestamps, to date when price information entered the analysis."
)


def publication_time(record: FinancialRecord) -> datetime | None:
    """Return the earliest recorded availability of one result.

    The availability is the minimum of the recorded broadcast and exchange
    dissemination timestamps. Using the earliest recorded value keeps the
    check conservative: a decision made after that moment could not rely on
    the result only if even this time had not elapsed.
    """

    candidates = [
        moment
        for moment in (record.broadcast, record.dissemination)
        if moment is not None
    ]
    return min(candidates) if candidates else None


def _entry(record: FinancialRecord, **extra: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "symbol": record.symbol,
        "company": record.company,
        "kind": record.kind,
        "source": record.source,
        "row": record.row,
    }
    entry.update(extra)
    return entry


def publication_metrics(records: Sequence[FinancialRecord]) -> dict[str, Any]:
    """Measure publication timing across financial rows.

    ``before_period`` collects records whose earliest availability timestamp
    precedes the end of the period they report on. Such a timestamp is
    physically impossible and is reported as a confirmed temporal violation:
    any consumer that trusted it would appear to have used a result before
    the period it reports even existed.
    """

    kind_counts: Counter[str] = Counter(record.kind for record in records)
    with_period = [record for record in records if record.period_end is not None]
    published = [
        (record, publication_time(record))
        for record in records
        if publication_time(record) is not None
    ]

    before_period: list[dict[str, Any]] = []
    dissemination_before_receipt: list[dict[str, Any]] = []
    lags: list[int] = []
    missing: list[FinancialRecord] = []
    for record in sorted(records, key=lambda item: (item.source, item.row)):
        moment = publication_time(record)
        if moment is None:
            missing.append(record)
            continue
        if record.period_end is not None and moment.date() < record.period_end:
            before_period.append(
                _entry(
                    record,
                    period_end=format_date(record.period_end),
                    publication=format_timestamp(moment),
                )
            )
        elif record.period_end is not None:
            lags.append((moment.date() - record.period_end).days)
        secondary = record.receipt
        if (
            record.dissemination is not None
            and secondary is not None
            and record.dissemination < secondary
        ):
            dissemination_before_receipt.append(
                _entry(
                    record,
                    broadcast=format_timestamp(secondary),
                    dissemination=format_timestamp(record.dissemination),
                )
            )

    lags.sort()
    lag_stats: dict[str, Any] | None
    if lags:
        lags_count = len(lags)
        lag_stats = {
            "count": lags_count,
            "minimum": lags[0],
            "median": round(float(lags[lags_count // 2]), 1)
            if lags_count % 2
            else round((lags[lags_count // 2 - 1] + lags[lags_count // 2]) / 2, 1),
            "maximum": lags[-1],
            "unit": "days from period end to earliest recorded availability",
        }
    else:
        lag_stats = None

    return {
        "records": len(records),
        "kind_counts": {
            kind: count
            for kind, count in sorted(kind_counts.items())
            if count and kind in FINANCIAL_KINDS
        },
        "with_period_end": len(with_period),
        "period_end_missing": len(records) - len(with_period),
        "with_publication": len(published),
        "publication_missing": len(records) - len(published),
        "missing_examples": [_entry(record) for record in missing[:MAX_EXAMPLES]],
        "before_period": before_period,
        "before_period_examples": before_period[:MAX_EXAMPLES],
        "before_period_count": len(before_period),
        "dissemination_before_receipt": dissemination_before_receipt,
        "dissemination_before_receipt_examples": dissemination_before_receipt[
            :MAX_EXAMPLES
        ],
        "dissemination_before_receipt_count": len(dissemination_before_receipt),
        "lag_days": lag_stats,
        "availability_note": (
            "A result is treated as potentially public only from its earliest "
            "recorded broadcast or exchange dissemination timestamp."
        ),
    }


def revision_metrics(records: Sequence[FinancialRecord]) -> dict[str, Any]:
    """Compare revision events with the publication of original figures.

    A revision whose recorded availability precedes the period's original
    publication is a confirmed violation: the corrected figures could not
    have existed before the figures they correct were public. A revision
    published later creates a restatement window; a decision taken inside
    that window could have consumed either version, which is reported as a
    suspicious pattern, not a violation.
    """

    grouped: dict[tuple[str, str, str], list[FinancialRecord]] = defaultdict(list)
    for record in records:
        key = (
            record.symbol,
            format_date(record.period_end) or "",
            record.company,
        )
        grouped[key].append(record)

    submissions: Counter[str] = Counter(
        record.submission for record in records if record.submission
    )
    revision_rows: list[FinancialRecord] = [
        record
        for record in sorted(records, key=lambda item: (item.source, item.row))
        if record.revision_present
    ]

    before_publication: list[dict[str, Any]] = []
    restatement_windows: list[dict[str, Any]] = []
    revised_periods: list[dict[str, Any]] = []
    for key in sorted(grouped):
        rows = grouped[key]
        originals = [row for row in rows if row.submission.casefold() != "revised"]
        # Without any original submission there is no publication that a
        # revision could precede; no ordering is asserted for that period.
        original_publication = (
            min(
                (
                    moment
                    for moment in (publication_time(row) for row in originals)
                    if moment is not None
                ),
                default=None,
            )
            if originals
            else None
        )
        for row in [
            item
            for item in rows
            if item.revision_present and item.submission.casefold() == "revised"
        ]:
            revision_at = min(
                (
                    moment
                    for moment in (row.revised, row.dissemination)
                    if moment is not None
                ),
                default=None,
            )
            if revision_at is None:
                continue
            summary = {
                "symbol": key[0],
                "period_end": key[1],
                "original_publication": (
                    format_timestamp(original_publication)
                    if original_publication is not None
                    else None
                ),
                "revision_published": format_timestamp(revision_at),
                "source": row.source,
                "row": row.row,
            }
            revised_periods.append(summary)
            if original_publication is not None and revision_at < original_publication:
                before_publication.append(summary)
            elif original_publication is not None:
                restatement_windows.append(
                    {
                        **summary,
                        "window": {
                            "start": format_timestamp(original_publication),
                            "end": format_timestamp(revision_at),
                        },
                    }
                )

    return {
        "records": len(records),
        "submission_counts": {
            value: count for value, count in sorted(submissions.items()) if value
        },
        "revision_rows": len(revision_rows),
        "revised_period_count": len(revised_periods),
        "revised_periods": revised_periods[:MAX_EXAMPLES],
        "revision_before_publication": before_publication,
        "revision_before_publication_examples": before_publication[:MAX_EXAMPLES],
        "revision_before_publication_count": len(before_publication),
        "restatement_windows": restatement_windows,
        "restatement_window_examples": restatement_windows[:MAX_EXAMPLES],
        "restatement_window_count": len(restatement_windows),
        "scope_note": (
            "Revision evidence exists only in the integrated-filing schemas "
            "(submission type and revised timestamp); the legacy quarterly "
            "exports carry no revision columns."
        ),
    }


def corporate_action_metrics(
    actions: Sequence[CorporateActionRecord],
) -> dict[str, Any]:
    """Summarize the entitlement dates and their ordering anomalies."""

    with_ex = [record for record in actions if record.ex_date is not None]
    record_before_ex: list[dict[str, Any]] = []
    for record in sorted(actions, key=lambda item: (item.source, item.row)):
        if (
            record.record_date is not None
            and record.ex_date is not None
            and record.record_date < record.ex_date
        ):
            record_before_ex.append(
                {
                    "symbol": record.symbol,
                    "purpose": record.purpose,
                    "ex_date": format_date(record.ex_date),
                    "record_date": format_date(record.record_date),
                    "source": record.source,
                    "row": record.row,
                }
            )
    same_day = sum(
        1
        for record in actions
        if record.ex_date is not None
        and record.record_date is not None
        and record.record_date == record.ex_date
    )
    return {
        "records": len(actions),
        "with_ex_date": len(with_ex),
        "ex_date_missing": len(actions) - len(with_ex),
        "record_date_missing": sum(
            1 for record in actions if record.record_date is None and record.symbol
        ),
        "same_day_ex_and_record": same_day,
        "record_before_ex": record_before_ex,
        "record_before_ex_examples": record_before_ex[:MAX_EXAMPLES],
        "record_before_ex_count": len(record_before_ex),
        "announcement_unavailable_note": ANNOUNCEMENT_NOTE,
        "required_additional_source": REQUIRED_ANNOUNCEMENT_SOURCE,
        "purpose_kinds": sorted(
            {record.purpose for record in actions if record.purpose}
        )[:MAX_EXAMPLES],
    }


def event_price_coverage(
    actions: Sequence[CorporateActionRecord],
    price_dates: Mapping[str, set[date]],
) -> dict[str, Any]:
    """Measure price coverage around every corporate action.

    Pre-event prices are the raw material for event-window features; missing
    pre-event prices prevent the availability checks from being exhaustive
    and are reported as coverage limitations rather than violations.
    """

    pre_present = pre_missing = 0
    missing_examples: list[dict[str, Any]] = []
    unpriced_symbols: set[str] = set()
    for record in sorted(actions, key=lambda item: (item.source, item.row)):
        if record.ex_date is None or not record.symbol:
            continue
        dates = price_dates.get(record.symbol)
        if not dates:
            unpriced_symbols.add(record.symbol)
            continue
        if any(price_date < record.ex_date for price_date in dates):
            pre_present += 1
        else:
            pre_missing += 1
            missing_examples.append(
                {
                    "symbol": record.symbol,
                    "purpose": record.purpose,
                    "ex_date": format_date(record.ex_date),
                    "source": record.source,
                    "row": record.row,
                }
            )
    return {
        "evaluable_actions": pre_present + pre_missing,
        "pre_event_prices_present": pre_present,
        "pre_event_prices_missing": pre_missing,
        "missing_examples": missing_examples[:MAX_EXAMPLES],
        "symbols_without_prices": sorted(unpriced_symbols)[:MAX_EXAMPLES],
        "symbols_without_price_count": len(unpriced_symbols),
        "availability_note": PRICE_NOTE,
    }


def price_availability_metrics(prices: Sequence[PriceRecord]) -> dict[str, Any]:
    """Describe the collected price evidence and its availability limit."""

    dates = [record.trade_date for record in prices]
    return {
        "rows": len(prices),
        "symbols": sorted({record.symbol for record in prices if record.symbol}),
        "date_range": (
            {
                "start": format_date(min(dates)),
                "end": format_date(max(dates)),
            }
            if dates
            else None
        ),
        "availability_note": PRICE_NOTE,
        "required_additional_source": REQUIRED_PRICE_SOURCE,
    }


def snapshot_summary(
    snapshots: Sequence[Any],
) -> dict[str, Any]:
    """Summarize the dated membership snapshots as point-in-time evidence.

    ``snapshots`` are the survivorship analyzer's parsed snapshot rows; the
    summary mirrors their structure without re-deriving membership: group
    counts, dates, symbol counts, and the unverified gaps between snapshots.
    """

    grouped: Counter[tuple[str, str]] = Counter()
    symbols: set[str] = set()
    for snapshot in snapshots:
        day = format_date(snapshot.snapshot_date)
        if day is None:
            continue
        grouped[(snapshot.index_name, day)] += 1
        if snapshot.symbol:
            symbols.add(snapshot.symbol)
    days = sorted(day for _, day in grouped)
    indexes = sorted({index for index, _ in grouped})
    gaps = [
        {
            "after_snapshot": before,
            "before_snapshot": after,
            "days": (date.fromisoformat(after) - date.fromisoformat(before)).days,
        }
        for before, after in itertools.pairwise(days)
    ]
    owner_by_date: dict[str, list[str]] = defaultdict(list)
    for index, day in grouped:
        owner_by_date[day].append(index)
    return {
        "point_in_time_snapshots_present": bool(grouped),
        "snapshot_count": len(grouped),
        "snapshot_dates": [
            {
                "date": day,
                "indexes": sorted(owner_by_date[day]),
                "rows": grouped[(index, day)],
            }
            for day in days
            for index in sorted(owner_by_date[day])
        ]
        if grouped
        else [],
        "indexes": indexes,
        "distinct_symbols": len(symbols),
        "date_range": {"start": days[0], "end": days[-1]} if days else None,
        "gaps": gaps,
        "membership_between_snapshots": "unverified" if days else "unavailable",
        "interpolation_performed": False,
        "snapshot_note": SNAPSHOT_NOTE,
    }
