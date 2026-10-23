"""Backtest-specific look-ahead assessment.

``LookaheadConfig`` describes one backtest from the availability angle: the
interval it covers, the dates on which it decides, the figures and universe
membership it claims to rely on, and how long its feature windows reach back.
The general data-coverage audit still runs without a configuration;
decision-specific conclusions are then reported as ``unavailable`` rather
than substituted with whatever the datasets happen to contain.

Every check reports ``ok``, ``confirmed``, ``suspicious``, ``unavailable``
(with the reason), ``not_applicable`` (nothing to run), or ``invalid``
(configuration errors). No timing is inferred from a period, ex, record, or
effective date alone, and no availability timestamp is invented.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from ...parsing import clean, format_date, format_timestamp, parse_date
from .core import (
    CHECK_DECISIONS,
    CHECK_DERIVED,
    CHECK_PRICE_ACTION,
    CHECK_PUBLICATION_TIMING,
    CHECK_REVISIONS,
    CHECK_UNIVERSE,
    MAX_EXAMPLES,
    STATUS_CONFIRMED,
    STATUS_INVALID,
    STATUS_NOT_APPLICABLE,
    STATUS_OK,
    STATUS_SUSPICIOUS,
    STATUS_UNAVAILABLE,
    CorporateActionRecord,
    FinancialRecord,
)
from .timing import publication_time

UNIVERSE_NOT_SUBSTITUTED = (
    "No target index or universe symbols were supplied; the symbols present "
    "in the collected datasets are not substituted for the requested universe."
)

NO_SNAPSHOT_EVIDENCE = (
    "No dated point-in-time membership snapshot is present in the collected "
    "data, so membership on the requested dates cannot be verified."
)

MEMBERSHIP_SOURCE_REQUIRED = (
    "A dated index-constituent membership series covering the backtest "
    "interval (index name, snapshot/effective date, symbol, ISIN)."
)

MISSING_INPUT_DECISIONS = (
    "decision dates with clock times (the collected data has none)"
)
MISSING_INPUT_WINDOW = "feature definitions and their computation windows"
MISSING_INPUT_ANNOUNCEMENTS = "announcement timestamps for corporate actions"


@dataclass(frozen=True)
class LookaheadConfig:
    """Inputs for a backtest-specific look-ahead assessment.

    ``target_index`` and ``universe_symbols`` mirror the survivorship
    configuration so both analyzers assess the same backtest.
    ``start_date``/``end_date`` define the backtest interval (inclusive).
    ``decision_dates`` are the dates on which the backtest makes decisions;
    they are interpreted as end-of-day boundaries. ``membership_snapshot_dates``
    are the authoritative membership snapshots the run relies on; without
    them, membership reliance is only ever a suspicious pattern.
    ``lookback_days`` is the assumed feature look-back window (in calendar
    days) that ends on each decision date.
    """

    target_index: str | None = None
    universe_symbols: tuple[str, ...] = ()
    start_date: date | None = None
    end_date: date | None = None
    decision_dates: tuple[date, ...] = ()
    membership_snapshot_dates: tuple[date, ...] = ()
    lookback_days: int | None = None


def _parse_config_date(value: Any, label: str, errors: list[str]) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    parsed = parse_date(str(value))
    if parsed is None:
        errors.append(f"{label} could not be parsed as a date: {value!r}")
    return parsed


def _normalise_dates(
    values: Sequence[Any], label: str, errors: list[str]
) -> tuple[date, ...]:
    parsed = tuple(
        parsed
        for parsed in (_parse_config_date(value, label, errors) for value in values)
        if parsed is not None
    )
    # Duplicates are collapsed deterministically instead of counting twice.
    return tuple(sorted(set(parsed)))


def build_lookahead_config(
    *,
    target_index: str | None = None,
    start_date: date | str | None = None,
    end_date: date | str | None = None,
    universe_symbols: Sequence[str] = (),
    decision_dates: Sequence[date | str] = (),
    membership_snapshot_dates: Sequence[date | str] = (),
    lookback_days: int | None = None,
) -> tuple[LookaheadConfig | None, list[str]]:
    """Build a config from raw values, returning every input problem found."""

    errors: list[str] = []
    start = _parse_config_date(start_date, "backtest start date", errors)
    end = _parse_config_date(end_date, "backtest end date", errors)
    decisions = _normalise_dates(decision_dates, "decision date", errors)
    membership = _normalise_dates(
        membership_snapshot_dates, "membership snapshot date", errors
    )
    if lookback_days is not None and (
        isinstance(lookback_days, bool) or not isinstance(lookback_days, int)
    ):
        errors.append(
            f"lookback_days must be a whole number of days, got {lookback_days!r}"
        )
        lookback_days = None
    config = LookaheadConfig(
        target_index=clean(target_index) or None,
        universe_symbols=tuple(
            cleaned
            for cleaned in (clean(symbol).upper() for symbol in universe_symbols)
            if cleaned
        ),
        start_date=start,
        end_date=end,
        decision_dates=decisions,
        membership_snapshot_dates=membership,
        lookback_days=lookback_days,
    )
    # Structural validation runs even when parsing already failed, so the
    # caller sees every input problem in one report.
    errors.extend(validate_config(config))
    return (None, errors) if errors else (config, [])


def validate_config(config: LookaheadConfig) -> list[str]:
    """Return structural configuration errors (an empty list means valid)."""

    errors: list[str] = []
    if (config.start_date is None) != (config.end_date is None):
        errors.append(
            "backtest start and end dates must both be provided (got only one of them)"
        )
    elif (
        config.start_date is not None
        and config.end_date is not None
        and config.start_date > config.end_date
    ):
        errors.append(
            f"backtest start {format_date(config.start_date)} is after "
            f"backtest end {format_date(config.end_date)}"
        )

    if config.lookback_days is not None and config.lookback_days < 0:
        errors.append(
            f"lookback_days must not be negative, got {config.lookback_days!r}"
        )

    for label, values in (
        ("decision", config.decision_dates),
        ("membership snapshot", config.membership_snapshot_dates),
    ):
        if config.start_date is None or config.end_date is None:
            continue
        outside = [
            value
            for value in values
            if value < config.start_date or value > config.end_date
        ]
        if outside:
            errors.append(
                f"{label} date(s) fall outside the backtest interval: "
                + ", ".join(
                    format_date(day) or ""
                    for day in sorted(set(outside))[:MAX_EXAMPLES]
                )
            )
    return errors


def config_summary(config: LookaheadConfig) -> dict[str, Any]:
    """Normalised, JSON-safe view of the supplied configuration."""

    interval_days = (
        (config.end_date - config.start_date).days
        if config.start_date is not None and config.end_date is not None
        else None
    )
    return {
        "target_index": config.target_index,
        "universe_symbol_count": len(config.universe_symbols),
        "start": format_date(config.start_date),
        "end": format_date(config.end_date),
        "interval_days": interval_days,
        "decision_dates": [format_date(day) for day in config.decision_dates],
        "membership_snapshot_dates": [
            format_date(day) for day in config.membership_snapshot_dates
        ],
        "lookback_days": config.lookback_days,
    }


def _check(
    name: str,
    status: str,
    reason: str | None = None,
    evidence: Any = None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {"check": name, "status": status}
    if reason:
        entry["reason"] = reason
    if evidence is not None:
        entry["evidence"] = evidence
    return entry


def _decision_profiles(
    decisions: Sequence[date],
    financials: Sequence[FinancialRecord],
) -> list[dict[str, Any]]:
    """For every decision date, describe which figure reports were available.

    Periods that end before a decision are the periods a model would rely
    on; the profile records whether their results were already published,
    published later, or carry no availability evidence at all. Using a
    not-yet-published result would be a temporal violation, but the
    collected evidence cannot show which figures a decision actually
    consumed, so the profile is reported rather than judged.
    """

    profiles: list[dict[str, Any]] = []
    for decision in decisions:
        relied = [
            record
            for record in financials
            if record.period_end is not None and record.period_end <= decision
        ]
        published_by: list[FinancialRecord] = []
        published_after: list[FinancialRecord] = []
        evidence_missing: list[FinancialRecord] = []
        for record in sorted(relied, key=lambda item: (item.source, item.row)):
            moment = publication_time(record)
            if moment is None:
                evidence_missing.append(record)
            elif moment.date() <= decision:
                published_by.append(record)
            else:
                published_after.append(record)
        profiles.append(
            {
                "decision": format_date(decision),
                "relying_records": len(relied),
                "published_by_decision": len(published_by),
                "published_after_decision": len(published_after),
                "publication_evidence_missing": len(evidence_missing),
                "published_after_examples": [
                    {
                        "symbol": record.symbol,
                        "period_end": format_date(record.period_end),
                        "publication": format_timestamp(publication_time(record)),
                    }
                    for record in published_after[:MAX_EXAMPLES]
                ],
                "evidence_missing_symbols": sorted(
                    {record.symbol for record in evidence_missing if record.symbol}
                )[:MAX_EXAMPLES],
            }
        )
    return profiles


def _restatement_overlaps(
    windows: Sequence[Mapping[str, Any]],
    decisions: Sequence[date],
) -> list[dict[str, Any]]:
    """Restatement windows that contain at least one decision date."""

    overlaps: list[dict[str, Any]] = []
    for window in windows:
        scope = window.get("window") or {}
        start_text = scope.get("start")
        end_text = scope.get("end")
        if not start_text or not end_text:
            continue
        start_day = date.fromisoformat(start_text[:10])
        end_day = date.fromisoformat(end_text[:10])
        for decision in decisions:
            if start_day < decision < end_day:
                overlaps.append(
                    {
                        "symbol": window.get("symbol"),
                        "period_end": window.get("period_end"),
                        "window": {"start": start_text, "end": end_text},
                        "decision": format_date(decision),
                    }
                )
    return overlaps


def _universe_origin(
    config: LookaheadConfig,
    groups: Sequence[Mapping[str, Any]],
    listing_symbols: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Classify universe symbols whose membership no snapshot can date.

    Returns (suspicious entries, evidence counts). A symbol that a snapshot
    dated on or before the earliest decision contains is verifiable; the
    remaining symbols either appear only in later snapshots (membership
    evidence postdates the decision) or occur nowhere except the present-day
    listing snapshot, which is not a point-in-time universe.
    """

    provided = set(config.universe_symbols)
    earliest = min(config.decision_dates) if config.decision_dates else None
    confirmed_symbols: set[str] = set()
    later_symbols: set[str] = set()
    for group in groups:
        day: date | None = group.get("_date")
        symbols = set(group.get("symbols") or ())
        if day is None:
            continue
        if earliest is not None and day <= earliest:
            confirmed_symbols |= symbols
        else:
            later_symbols |= symbols
    undated = sorted(provided - confirmed_symbols)
    entries: list[dict[str, Any]] = []
    if not provided or earliest is None:
        return entries, [{"universe_symbols": len(provided)}]
    later_only = [symbol for symbol in undated if symbol in later_symbols]
    listing_only = [
        symbol
        for symbol in undated
        if symbol not in later_symbols and symbol in listing_symbols
    ]
    untraceable = [
        symbol
        for symbol in undated
        if symbol not in set(later_only) | set(listing_only)
    ]
    if later_only:
        entries.append(
            {
                "reason": "membership evidence exists only in snapshots dated after the decision dates",
                "symbols": later_only[:MAX_EXAMPLES],
                "count": len(later_only),
            }
        )
    if listing_only:
        entries.append(
            {
                "reason": (
                    "the only collected source containing these symbols is "
                    "the present-day listing snapshot, which is not a "
                    "point-in-time universe"
                ),
                "symbols": listing_only[:MAX_EXAMPLES],
                "count": len(listing_only),
            }
        )
    if untraceable:
        entries.append(
            {
                "reason": (
                    "no collected dataset contains this symbol; its origin "
                    "cannot be verified"
                ),
                "symbols": untraceable[:MAX_EXAMPLES],
                "count": len(untraceable),
            }
        )
    return entries, [
        {
            "universe_symbols": len(provided),
            "confirmed_by_earlier_snapshots": len(provided & confirmed_symbols),
            "undated_symbols": len(undated),
        }
    ]


def assess_backtest(
    config: LookaheadConfig,
    *,
    financials: Sequence[FinancialRecord],
    action_records: Sequence[CorporateActionRecord],
    publication: Mapping[str, Any],
    revisions: Mapping[str, Any],
    actions: Mapping[str, Any],
    event_prices: Mapping[str, Any],
    groups: Sequence[Mapping[str, Any]],
    listing_symbols: set[str],
    price_dates: Mapping[str, set[date]],
    observed_dates: Sequence[date],
    derived_inputs: Mapping[str, bool],
) -> dict[str, Any]:
    """Run every backtest-specific check that the evidence permits."""

    summary = config_summary(config)
    errors = validate_config(config)
    impact = {
        "status": "unavailable",
        "reason": (
            "Quantifying look-ahead bias requires the backtest's decision "
            "timestamps with clock times, its exact feature definitions and "
            "computation windows, and announcement timings for every "
            "corporate action and index change. None of these inputs are "
            "part of this analysis, and no methodology can estimate impact "
            "from coverage data alone."
        ),
        "missing_inputs": [
            MISSING_INPUT_DECISIONS,
            MISSING_INPUT_WINDOW,
            MISSING_INPUT_ANNOUNCEMENTS,
        ],
    }

    if errors:
        reason = "; ".join(errors)
        return {
            "status": "invalid",
            "config": summary,
            "errors": errors,
            "checks": [_check("config_validation", STATUS_INVALID, reason)],
            "bias_impact": impact,
        }

    checks: list[dict[str, Any]] = [
        _check("config_validation", STATUS_OK, evidence={"errors": []})
    ]
    decisions = list(config.decision_dates)
    start = config.start_date
    end = config.end_date
    has_interval = start is not None and end is not None
    confirmed_count = 0
    suspicious_count = 0
    insufficient_notes: list[str] = []

    # ------------------------------------------------ publication timing
    before_period = list(publication.get("before_period") or ())
    if start is not None and end is not None:
        before_period = [
            entry
            for entry in before_period
            if entry.get("period_end")
            and start <= date.fromisoformat(entry["period_end"]) <= end
        ]
    profiles = _decision_profiles(decisions, financials) if decisions else []
    unconfirmed_decisions = [
        profile
        for profile in profiles
        if profile["publication_evidence_missing"]
        or profile["published_after_decision"]
    ]
    if before_period:
        confirmed_count += len(before_period)
        checks.append(
            _check(
                CHECK_PUBLICATION_TIMING,
                STATUS_CONFIRMED,
                evidence={
                    "confirmed_violation_count": len(before_period),
                    "examples": before_period[:MAX_EXAMPLES],
                    "decision_profiles": profiles,
                },
            )
        )
    elif not decisions and not has_interval:
        checks.append(
            _check(
                CHECK_PUBLICATION_TIMING,
                STATUS_NOT_APPLICABLE,
                "no decision dates and no backtest interval were supplied; "
                "the check reports the general publication-timing evidence "
                "only",
            )
        )
    elif not financials and decisions:
        checks.append(
            _check(
                CHECK_PUBLICATION_TIMING,
                STATUS_UNAVAILABLE,
                "no financial results were available, so the figures a "
                "decision could rely on cannot be timed",
            )
        )
    else:
        checks.append(
            _check(
                CHECK_PUBLICATION_TIMING,
                STATUS_OK,
                evidence={
                    "before_period_count": publication.get("before_period_count", 0),
                    "records_without_publication": publication.get(
                        "publication_missing", 0
                    ),
                    "decision_profiles": profiles,
                },
            )
        )
    for profile in unconfirmed_decisions:
        insufficient_notes.append(
            f"decision {profile['decision']}: "
            f"{profile['publication_evidence_missing']} relying record(s) "
            "have no availability timestamp and "
            f"{profile['published_after_decision']} were published after "
            "the decision; which figures the decision consumed cannot be "
            "verified"
        )

    # ------------------------------------------------------- revised figures
    revision_violations = list(revisions.get("revision_before_publication") or ())
    overlaps = _restatement_overlaps(
        list(revisions.get("restatement_windows") or ()), decisions
    )
    if revision_violations:
        confirmed_count += len(revision_violations)
        checks.append(
            _check(
                CHECK_REVISIONS,
                STATUS_CONFIRMED,
                evidence={
                    "confirmed_violation_count": len(revision_violations),
                    "examples": revision_violations[:MAX_EXAMPLES],
                    "restatement_overlaps": overlaps[:MAX_EXAMPLES],
                },
            )
        )
    elif not any(revisions.get("submission_counts") or {}):
        checks.append(
            _check(
                CHECK_REVISIONS,
                STATUS_NOT_APPLICABLE,
                "no financial-row submissions were available, so a revision "
                "timeline cannot be compared with original publications",
            )
        )
    else:
        status = STATUS_SUSPICIOUS if overlaps else STATUS_OK
        suspicious_count += len(overlaps)
        checks.append(
            _check(
                CHECK_REVISIONS,
                status,
                evidence={
                    "revised_period_count": revisions.get("revised_period_count", 0),
                    "restatement_window_count": revisions.get(
                        "restatement_window_count", 0
                    ),
                    "restatement_overlaps": overlaps[:MAX_EXAMPLES],
                },
            )
        )
    for overlap in overlaps[:MAX_EXAMPLES]:
        insufficient_notes.append(
            f"decision {overlap['decision']} falls inside the restatement "
            f"window for {overlap['symbol'] or 'the period'} "
            f"({overlap['window']['start']} to {overlap['window']['end']}); "
            "either the original or the revised figures could have been "
            "consumed"
        )

    # ------------------------------------------------- point-in-time universe
    if not groups:
        if not decisions and not has_interval:
            checks.append(
                _check(
                    CHECK_UNIVERSE,
                    STATUS_NOT_APPLICABLE,
                    "no decision dates and no interval were supplied",
                )
            )
        elif config.universe_symbols and any(
            symbol not in listing_symbols for symbol in config.universe_symbols
        ):
            # Some universe symbols are not present in the current listing,
            # so membership cannot be verified for those symbols → suspicious.
            entries, counts = _universe_origin(config, groups, listing_symbols)
            if entries:
                suspicious_count += len(entries)
                checks.append(
                    _check(
                        CHECK_UNIVERSE,
                        STATUS_SUSPICIOUS,
                        evidence={"entries": entries, "counts": counts},
                    )
                )
            else:
                # All universe symbols are in the listing but no dated snapshot exists.
                checks.append(
                    _check(
                        CHECK_UNIVERSE,
                        STATUS_UNAVAILABLE,
                        NO_SNAPSHOT_EVIDENCE,
                        evidence={"required_source": MEMBERSHIP_SOURCE_REQUIRED},
                    )
                )
        else:
            # No dated snapshots exist and all universe symbols (if any) are
            # present in the current listing → unavailable.
            checks.append(
                _check(
                    CHECK_UNIVERSE,
                    STATUS_UNAVAILABLE,
                    NO_SNAPSHOT_EVIDENCE,
                    evidence={"required_source": MEMBERSHIP_SOURCE_REQUIRED},
                )
            )
    elif config.membership_snapshot_dates:
        unavailable_dates = sorted(
            day
            for day in config.membership_snapshot_dates
            if day not in {group["_date"] for group in groups}
        )
        # A snapshot the backtest claims to rely on cannot supply membership
        # to a decision that precedes it; that reliance is a confirmed
        # violation of the temporal ordering of the configuration itself.
        future_pairs: list[dict[str, Any]] = []
        universe_confirmed = 0
        for decision in decisions:
            for relied in sorted(set(config.membership_snapshot_dates)):
                if decision < relied:
                    universe_confirmed += 1
                    future_pairs.append(
                        {
                            "decision": format_date(decision),
                            "relied_snapshot": format_date(relied),
                        }
                    )
        confirmed_count += universe_confirmed
        if unavailable_dates:
            checks.append(
                _check(
                    CHECK_UNIVERSE,
                    STATUS_UNAVAILABLE,
                    (
                        "membership snapshot(s) missing for: "
                        + ", ".join(format_date(day) or "" for day in unavailable_dates)
                    ),
                    evidence={
                        "requested": [
                            format_date(day) for day in config.membership_snapshot_dates
                        ],
                        "missing": [format_date(day) for day in unavailable_dates],
                        "required_source": MEMBERSHIP_SOURCE_REQUIRED,
                        "future_reliance": future_pairs[:MAX_EXAMPLES],
                        "future_reliance_count": universe_confirmed,
                    },
                )
            )
        elif universe_confirmed:
            checks.append(
                _check(
                    CHECK_UNIVERSE,
                    STATUS_CONFIRMED,
                    evidence={
                        "future_reliance": future_pairs[:MAX_EXAMPLES],
                        "future_reliance_count": universe_confirmed,
                    },
                )
            )
        else:
            checks.append(
                _check(
                    CHECK_UNIVERSE,
                    STATUS_OK,
                    evidence={
                        "relied_snapshots": [
                            format_date(day)
                            for day in sorted(set(config.membership_snapshot_dates))
                        ]
                    },
                )
            )
    elif decisions:
        entries, counts = _universe_origin(config, groups, listing_symbols)
        if entries:
            suspicious_count += len(entries)
            checks.append(
                _check(
                    CHECK_UNIVERSE,
                    STATUS_SUSPICIOUS,
                    evidence={"entries": entries, "counts": counts},
                )
            )
        else:
            checks.append(
                _check(CHECK_UNIVERSE, STATUS_OK, evidence={"counts": counts})
            )
    elif has_interval:
        in_interval = sorted(
            group["_date"] for group in groups if start <= group["_date"] <= end
        )
        if in_interval:
            checks.append(
                _check(
                    CHECK_UNIVERSE,
                    STATUS_OK,
                    evidence={
                        "snapshot_dates_in_interval": [
                            format_date(day) for day in in_interval
                        ],
                        "membership_between_snapshots": "unverified",
                    },
                )
            )
        else:
            checks.append(
                _check(
                    CHECK_UNIVERSE,
                    STATUS_UNAVAILABLE,
                    (
                        "membership snapshots exist but none fall inside the "
                        "requested interval; collected snapshot dates: "
                        + ", ".join(
                            format_date(group["_date"]) or "" for group in groups
                        )
                    ),
                    evidence={"required_source": MEMBERSHIP_SOURCE_REQUIRED},
                )
            )
    else:
        checks.append(
            _check(
                CHECK_UNIVERSE,
                STATUS_NOT_APPLICABLE,
                "no decision dates and no interval were supplied",
            )
        )

    # ------------------------------------------------------ price/action timing
    if not action_records and not price_dates:
        checks.append(
            _check(
                CHECK_PRICE_ACTION,
                STATUS_UNAVAILABLE,
                "no corporate-action events and no priced trading days were "
                "available, so event timing around decisions cannot be "
                "measured",
            )
        )
    else:
        insufficient_events: list[dict[str, Any]] = []
        future_price_rows: list[dict[str, Any]] = []
        if decisions:
            scope_end = end
            last_decision = decisions[-1]
            for decision in decisions:
                boundary = scope_end or decision
                for record in sorted(
                    action_records, key=lambda item: (item.source, item.row)
                ):
                    if (
                        record.ex_date is not None
                        and decision < record.ex_date <= boundary
                    ):
                        insufficient_events.append(
                            {
                                "decision": format_date(decision),
                                "symbol": record.symbol,
                                "purpose": record.purpose,
                                "ex_date": format_date(record.ex_date),
                                "source": record.source,
                                "row": record.row,
                            }
                        )
            if scope_end is not None and last_decision < scope_end:
                after = sorted(
                    day for day in observed_dates if last_decision < day <= scope_end
                )
                rows_after = sum(
                    len(price_dates.get(symbol, set()) & set(after))
                    for symbol in sorted(price_dates)
                )
                if rows_after:
                    suspicious_count += 1
                    future_price_rows.append(
                        {
                            "last_decision": format_date(last_decision),
                            "interval_end": format_date(scope_end),
                            "priced_days_after_decision": len(after),
                            "price_rows_after_decision": rows_after,
                            "dated_examples": [
                                format_date(day) for day in after[:MAX_EXAMPLES]
                            ],
                        }
                    )
            if insufficient_events:
                insufficient_notes.append(
                    f"{len(insufficient_events)} corporate-action event(s) "
                    "carry an ex/record date on or after a decision date; "
                    "announcement timestamps required to time them are "
                    "unavailable"
                )
        if not decisions and not has_interval:
            checks.append(
                _check(
                    CHECK_PRICE_ACTION,
                    STATUS_NOT_APPLICABLE,
                    "no decision dates and no interval were supplied",
                )
            )
        else:
            checks.append(
                _check(
                    CHECK_PRICE_ACTION,
                    STATUS_SUSPICIOUS if future_price_rows else STATUS_OK,
                    evidence={
                        "announce_unknown_events": insufficient_events[:MAX_EXAMPLES],
                        "announce_unknown_event_count": len(insufficient_events),
                        "future_price_rows": future_price_rows,
                        "pre_event_prices_missing": event_prices.get(
                            "pre_event_prices_missing", 0
                        ),
                    },
                )
            )
        if not action_records:
            insufficient_notes.append(
                "no corporate-action events were available; event-timing "
                "checks ran against the price series only"
            )

    # -------------------------------------------------- derived feature timing
    derived_kinds = tuple(
        record.kind for record in financials if record.kind.startswith("derived_")
    )
    derived_violations = [
        entry
        for entry in before_period
        if str(entry.get("kind", "")).startswith("derived_")
    ]
    if not any(derived_inputs.values()) and not derived_kinds:
        checks.append(
            _check(
                CHECK_DERIVED,
                STATUS_NOT_APPLICABLE,
                "no derived datasets were present in the analysis scope",
            )
        )
    elif derived_inputs.get("prices") or derived_inputs.get("corporate_actions"):
        note = (
            "derived price and corporate-action rows carry no availability "
            "timestamps, so forward-facing feature timing cannot be verified "
            "from them"
        )
        insufficient_notes.append(note)
        if derived_violations:
            confirmed_count += len(derived_violations)
            checks.append(
                _check(
                    CHECK_DERIVED,
                    STATUS_CONFIRMED,
                    evidence={
                        "confirmed_violation_count": len(derived_violations),
                        "examples": derived_violations[:MAX_EXAMPLES],
                        "limitations": [note],
                    },
                )
            )
        else:
            checks.append(
                _check(
                    CHECK_DERIVED,
                    STATUS_OK,
                    evidence={"limitations": [note]},
                )
            )
    elif derived_violations:
        confirmed_count += len(derived_violations)
        checks.append(
            _check(
                CHECK_DERIVED,
                STATUS_CONFIRMED,
                evidence={
                    "confirmed_violation_count": len(derived_violations),
                    "examples": derived_violations[:MAX_EXAMPLES],
                },
            )
        )
    else:
        checks.append(
            _check(
                CHECK_DERIVED,
                STATUS_OK,
                evidence={
                    "derived_financial_rows": len(
                        [kind for kind in derived_kinds if kind]
                    )
                },
            )
        )

    # ------------------------------------------------- decision timestamp coverage
    if not decisions:
        checks.append(
            _check(
                CHECK_DECISIONS,
                STATUS_NOT_APPLICABLE,
                "no decision dates were supplied; decision-specific temporal "
                "checks did not run",
            )
        )
    else:
        missing_evidence = sum(
            profile["publication_evidence_missing"] for profile in profiles
        )
        checks.append(
            _check(
                CHECK_DECISIONS,
                STATUS_OK,
                evidence={
                    "decision_count": len(decisions),
                    "decision_dates": [format_date(day) for day in decisions],
                    "boundary_note": (
                        "decision dates are treated as end-of-day "
                        "boundaries; publication timestamps are intraday, so "
                        "sub-day ordering cannot be verified"
                    ),
                    "evidence_missing_records": missing_evidence,
                },
            )
        )
        if missing_evidence:
            insufficient_notes.append(
                f"{missing_evidence} relying record(s) across the decision "
                "dates carry no availability timestamp; their use cannot be "
                "timed"
            )

    unavailable_count = sum(
        1 for check in checks if check["status"] == STATUS_UNAVAILABLE
    )
    if any(check["status"] == STATUS_CONFIRMED for check in checks):
        status = "confirmed"
    elif any(check["status"] == STATUS_SUSPICIOUS for check in checks):
        status = "suspicious"
    elif unavailable_count:
        status = "partial"
    else:
        status = "ok"

    return {
        "status": status,
        "config": summary,
        "checks": checks,
        "bias_impact": impact,
        "unavailable_check_count": unavailable_count,
        "confirmed_count": confirmed_count,
        "suspicious_count": suspicious_count,
        "insufficient_notes": insufficient_notes,
    }


def unavailable_assessment(reason: str) -> dict[str, Any]:
    """The backtest section reported when no configuration was supplied."""

    return {
        "status": STATUS_UNAVAILABLE,
        "reason": reason,
        "checks": [],
        "bias_impact": {
            "status": STATUS_UNAVAILABLE,
            "reason": (
                "No backtest configuration was supplied, so no "
                "decision-availability assessment or impact estimate can be "
                "produced. The general temporal-evidence audit does not "
                "quantify impact."
            ),
        },
    }


__all__ = [
    "LookaheadConfig",
    "assess_backtest",
    "build_lookahead_config",
    "config_summary",
    "unavailable_assessment",
    "validate_config",
]
