"""Backtest-specific survivorship assessment.

``BacktestConfig`` is the documented interface for assessing one backtest:
target index or explicit universe, backtest interval, authoritative membership
snapshots the run relies on, rebalancing/membership dates, identifier
mappings, and a price-coverage threshold. The general data-coverage audit
still runs without a configuration; backtest-specific conclusions are then
reported as ``unavailable`` rather than substituted with whatever symbols
happen to have price data.

Every check reports ``ok``, ``unavailable`` (with the reason and the data that
would be required), ``not_applicable``, or ``invalid`` (configuration errors).
No membership, coverage percentage, or impact figure is ever invented.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from ...parsing import clean, format_date, parse_date
from .core import (
    COVERAGE_AMBIGUOUS,
    COVERAGE_CLASSES,
    MATCH_CLASSES,
    MAX_EXAMPLES,
    IndexSnapshot,
)
from .matching import coverage_summary
from .universe import snapshot_groups

UNIVERSE_NOT_SUBSTITUTED = (
    "No target index or universe symbols were supplied; the symbols present "
    "in the price dataset are not substituted for the requested universe."
)

NO_MEMBERSHIP_SNAPSHOTS = (
    "No dated point-in-time membership snapshot is present in the collected "
    "data, so membership on the requested dates cannot be verified."
)

MEMBERSHIP_SOURCE_REQUIRED = (
    "A dated index-constituent membership series covering the backtest "
    "interval (index name, snapshot/effective date, symbol, ISIN)."
)


@dataclass(frozen=True)
class IdentifierMapping:
    """A user-supplied identifier mapping used alongside collected records."""

    old_symbol: str = ""
    new_symbol: str = ""
    isin: str = ""
    effective_date: date | None = None


@dataclass(frozen=True)
class BacktestConfig:
    """Inputs for a backtest-specific survivorship assessment.

    ``target_index`` selects an index whose dated snapshots define membership;
    ``universe_symbols`` supplies an explicit universe selection instead of,
    or in addition to, an index. Symbols are compared case-insensitively.
    ``start_date``/``end_date`` define the backtest interval (inclusive).
    ``membership_snapshot_dates`` are the authoritative snapshots the backtest
    relies on; missing ones are reported. ``rebalance_dates`` are checked for
    membership evidence. ``identifier_mappings`` supplement the collected
    symbol-change records. ``min_price_coverage`` is a required coverage ratio
    in ``[0, 1]`` applied per universe member against the observed trading
    days inside the interval.
    """

    target_index: str | None = None
    universe_symbols: tuple[str, ...] = ()
    start_date: date | None = None
    end_date: date | None = None
    membership_snapshot_dates: tuple[date, ...] = ()
    rebalance_dates: tuple[date, ...] = ()
    identifier_mappings: tuple[IdentifierMapping, ...] = ()
    min_price_coverage: float | None = None


def _parse_config_date(value: Any, label: str, errors: list[str]) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    parsed = parse_date(str(value))
    if parsed is None:
        errors.append(f"{label} could not be parsed as a date: {value!r}")
    return parsed


def build_backtest_config(
    *,
    target_index: str | None = None,
    start_date: date | str | None = None,
    end_date: date | str | None = None,
    universe_symbols: Sequence[str] = (),
    membership_snapshot_dates: Sequence[date | str] = (),
    rebalance_dates: Sequence[date | str] = (),
    identifier_mappings: Sequence[IdentifierMapping] = (),
    min_price_coverage: float | None = None,
) -> tuple[BacktestConfig | None, list[str]]:
    """Build a config from raw values, returning every input problem found.

    Returns ``(None, errors)`` when a date could not be parsed, otherwise a
    config plus any structural validation errors (the caller reports those).
    """

    errors: list[str] = []
    start = _parse_config_date(start_date, "backtest start date", errors)
    end = _parse_config_date(end_date, "backtest end date", errors)
    snapshot_dates = tuple(
        parsed
        for parsed in (
            _parse_config_date(value, "membership snapshot date", errors)
            for value in membership_snapshot_dates
        )
        if parsed is not None
    )
    rebalancing = tuple(
        parsed
        for parsed in (
            _parse_config_date(value, "rebalancing date", errors)
            for value in rebalance_dates
        )
        if parsed is not None
    )
    if errors:
        return None, errors

    config = BacktestConfig(
        target_index=clean(target_index) or None,
        universe_symbols=tuple(
            cleaned
            for cleaned in (clean(symbol).upper() for symbol in universe_symbols)
            if cleaned
        ),
        start_date=start,
        end_date=end,
        membership_snapshot_dates=snapshot_dates,
        rebalance_dates=rebalancing,
        identifier_mappings=tuple(identifier_mappings),
        min_price_coverage=min_price_coverage,
    )
    return config, validate_config(config)


def validate_config(config: BacktestConfig) -> list[str]:
    """Return structural configuration errors (an empty list means valid)."""

    errors: list[str] = []
    if config.start_date is None and config.end_date is None:
        errors.append(
            "backtest start and end dates are required for a backtest-specific "
            "assessment (both were omitted)"
        )
    elif (config.start_date is None) != (config.end_date is None):
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

    if config.min_price_coverage is not None and not (
        0.0 <= config.min_price_coverage <= 1.0
    ):
        errors.append(
            "min_price_coverage must be between 0 and 1, got "
            f"{config.min_price_coverage!r}"
        )

    if config.start_date is not None and config.end_date is not None:
        outside = sorted(
            format_date(day) or ""
            for day in (
                *config.membership_snapshot_dates,
                *config.rebalance_dates,
            )
            if day < config.start_date or day > config.end_date
        )
        if outside:
            errors.append(
                "membership/rebalancing dates fall outside the backtest "
                f"interval: {', '.join(outside[:MAX_EXAMPLES])}"
            )

    for mapping in config.identifier_mappings:
        if not clean(mapping.old_symbol) or not clean(mapping.new_symbol):
            errors.append(
                "an identifier mapping is missing its old or new symbol "
                f"({mapping.old_symbol!r} -> {mapping.new_symbol!r})"
            )
    return errors


def config_summary(config: BacktestConfig) -> dict[str, Any]:
    """Normalised, JSON-safe view of the supplied configuration."""

    interval_days = (
        (config.end_date - config.start_date).days + 1
        if config.start_date is not None and config.end_date is not None
        else None
    )
    return {
        "target_index": config.target_index,
        "universe_symbol_count": len(config.universe_symbols),
        "start": format_date(config.start_date),
        "end": format_date(config.end_date),
        "interval_days": interval_days,
        "membership_snapshot_dates": [
            format_date(day) for day in config.membership_snapshot_dates
        ],
        "rebalance_dates": [format_date(day) for day in config.rebalance_dates],
        "identifier_mapping_count": len(config.identifier_mappings),
        "min_price_coverage": config.min_price_coverage,
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


def _largest_unverified_gap(
    start: date,
    end: date,
    verified: Sequence[date],
) -> dict[str, Any] | None:
    """Longest run of interval days with no membership snapshot on any day."""

    runs: list[tuple[date, date]] = []
    cursor = start
    for day in sorted({day for day in verified if start <= day <= end}):
        if cursor < day:
            runs.append((cursor, day - timedelta(days=1)))
        cursor = day + timedelta(days=1)
    if cursor <= end:
        runs.append((cursor, end))
    if not runs:
        return None
    gap_start, gap_end = max(runs, key=lambda run: ((run[1] - run[0]).days, run[0]))
    return {
        "start": format_date(gap_start),
        "end": format_date(gap_end),
        "days": (gap_end - gap_start).days + 1,
    }


def _resolve_index(
    target_index: str | None,
    groups: Sequence[dict[str, Any]],
) -> tuple[list[dict[str, Any]], str | None, str | None]:
    """Resolve the requested index against collected snapshots."""

    if not target_index:
        return list(groups), None, None
    wanted = " ".join(target_index.split()).casefold()
    available = sorted({group["index_name"] for group in groups})
    matched = [
        group
        for group in groups
        if " ".join(group["index_name"].split()).casefold() == wanted
    ]
    if not matched:
        return (
            [],
            None,
            (
                f"no collected membership snapshot covers index "
                f"{target_index!r}; available indexes: "
                f"{', '.join(available) or 'none'}"
            ),
        )
    return matched, matched[0]["index_name"], None


def assess_backtest(
    config: BacktestConfig,
    *,
    snapshots: Sequence[IndexSnapshot],
    price_dates: Mapping[str, set[date]],
    observed_dates: Sequence[date],
    ambiguous_symbols: Mapping[str, Sequence[str]],
    securities: Sequence[dict[str, Any]],
    classifications: Mapping[tuple[str, str], dict[str, Any]],
    delistings_available: bool,
) -> dict[str, Any]:
    """Run every backtest-specific check that the evidence permits.

    Each check either computes its metric from actual data (with explicit
    denominators) or reports ``unavailable`` with the reason and the source
    that would be required. Nothing is inferred from current listings.
    """

    summary = config_summary(config)
    errors = validate_config(config)
    impact = {
        "status": "unavailable",
        "reason": (
            "Quantifying the return impact of survivorship bias requires the "
            "backtest's own return or trade series, portfolio weights and "
            "rebalancing allocations, a point-in-time membership timeline for "
            "the full interval, and delisted-security price histories. None "
            "of these inputs are part of this analysis, and no methodology "
            "for estimating impact can be applied to coverage data alone."
        ),
        "missing_inputs": [
            "backtest return or trade series with portfolio weights",
            "point-in-time membership timeline for the whole interval",
            "price history for delisted and unlisted securities in the interval",
        ],
    }

    if errors:
        reason = "; ".join(errors)
        return {
            "status": "invalid",
            "config": summary,
            "errors": errors,
            "checks": [_check("config_validation", "invalid", reason)],
            "bias_impact": impact,
        }

    checks: list[dict[str, Any]] = [
        _check("config_validation", "ok", evidence={"errors": []})
    ]
    groups = snapshot_groups(snapshots)
    relevant_groups, resolved_index, index_error = _resolve_index(
        config.target_index, groups
    )
    start = config.start_date
    end = config.end_date
    if start is None or end is None:
        # Defensive: validate_config() reports this, so this branch is only
        # reached if a caller bypasses validation in a future change.
        missing_reason = (
            "backtest start and end dates are required for a backtest-specific "
            "assessment"
        )
        return {
            "status": "invalid",
            "config": summary,
            "errors": [missing_reason],
            "checks": [_check("config_validation", "invalid", missing_reason)],
            "bias_impact": impact,
        }

    # --- membership snapshots inside the interval -------------------------
    if index_error:
        checks.append(
            _check("membership_snapshots_in_interval", "unavailable", index_error)
        )
        in_interval: list[dict[str, Any]] = []
    elif not relevant_groups:
        checks.append(
            _check(
                "membership_snapshots_in_interval",
                "unavailable",
                NO_MEMBERSHIP_SNAPSHOTS,
                evidence={"required_source": MEMBERSHIP_SOURCE_REQUIRED},
            )
        )
        in_interval = []
    else:
        in_interval = [
            group for group in relevant_groups if start <= group["_date"] <= end
        ]
        if in_interval:
            checks.append(
                _check(
                    "membership_snapshots_in_interval",
                    "ok",
                    evidence={
                        "snapshot_dates": [
                            group["snapshot_date"] for group in in_interval
                        ],
                        "index": resolved_index or "all collected indexes",
                    },
                )
            )
        else:
            outside = sorted(group["snapshot_date"] for group in relevant_groups)
            checks.append(
                _check(
                    "membership_snapshots_in_interval",
                    "unavailable",
                    (
                        "membership snapshots exist for the requested index "
                        "but none fall inside the requested interval; "
                        f"collected snapshot dates: {', '.join(outside)}"
                    ),
                    evidence={
                        "collected_snapshot_dates": outside,
                        "required_source": MEMBERSHIP_SOURCE_REQUIRED,
                    },
                )
            )

    # --- requested authoritative snapshot dates ---------------------------
    if not config.membership_snapshot_dates:
        checks.append(
            _check(
                "requested_membership_snapshot_dates",
                "not_applicable",
                "no authoritative membership snapshot dates were supplied",
            )
        )
    else:
        available_dates = {group["_date"] for group in relevant_groups}
        missing_dates = sorted(
            day
            for day in config.membership_snapshot_dates
            if day not in available_dates
        )
        if missing_dates:
            checks.append(
                _check(
                    "requested_membership_snapshot_dates",
                    "unavailable",
                    (
                        "membership snapshot(s) missing for: "
                        + ", ".join(format_date(day) or "" for day in missing_dates)
                    ),
                    evidence={
                        "requested": [
                            format_date(day) for day in config.membership_snapshot_dates
                        ],
                        "missing": [format_date(day) for day in missing_dates],
                        "required_source": MEMBERSHIP_SOURCE_REQUIRED,
                    },
                )
            )
        else:
            checks.append(
                _check(
                    "requested_membership_snapshot_dates",
                    "ok",
                    evidence={
                        "requested": [
                            format_date(day) for day in config.membership_snapshot_dates
                        ]
                    },
                )
            )

    # --- universe resolution ---------------------------------------------
    user_symbols = set(config.universe_symbols)
    snapshot_symbols = {
        group_symbol for group in in_interval for group_symbol in group["symbols"]
    }
    universe: dict[str, Any]
    universe_symbols: set[str] = set()
    if user_symbols and in_interval:
        universe_symbols = set(user_symbols)
        confirmed = sorted(user_symbols & snapshot_symbols)
        universe = {
            "status": "ok",
            "source": "supplied_universe_symbols_with_membership_snapshots",
            "universe_symbol_count": len(user_symbols),
            "membership_confirmed_count": len(confirmed),
            "membership_unconfirmed_examples": sorted(user_symbols - snapshot_symbols)[
                :MAX_EXAMPLES
            ],
            "denominator": len(user_symbols),
            "note": (
                "Supplied universe symbols are the evaluated universe; the "
                "in-interval membership snapshots provide confirmation for "
                "the symbols they contain."
            ),
        }
        checks.append(
            _check(
                "universe_resolution",
                "ok",
                evidence={
                    "universe_symbol_count": len(user_symbols),
                    "membership_confirmed_count": len(confirmed),
                },
            )
        )
    elif user_symbols:
        universe_symbols = set(user_symbols)
        universe = {
            "status": "ok",
            "source": "supplied_universe_symbols",
            "universe_symbol_count": len(user_symbols),
            "membership_confirmed_count": 0,
            "denominator": len(user_symbols),
            "note": (
                "Membership of the supplied symbols is unverified because no "
                "membership snapshot falls inside the interval."
            ),
        }
        checks.append(
            _check(
                "universe_resolution",
                "ok",
                evidence={"universe_symbol_count": len(user_symbols)},
            )
        )
    elif resolved_index and snapshot_symbols:
        universe_symbols = set(snapshot_symbols)
        universe = {
            "status": "ok",
            "source": "membership_snapshots_in_interval",
            "index": resolved_index,
            "universe_symbol_count": len(universe_symbols),
            "membership_confirmed_count": len(universe_symbols),
            "denominator": len(universe_symbols),
            "snapshot_dates": sorted(group["snapshot_date"] for group in in_interval),
        }
        checks.append(
            _check(
                "universe_resolution",
                "ok",
                evidence={
                    "index": resolved_index,
                    "universe_symbol_count": len(universe_symbols),
                },
            )
        )
    else:
        reason = index_error or UNIVERSE_NOT_SUBSTITUTED
        if not relevant_groups:
            reason = NO_MEMBERSHIP_SNAPSHOTS
        elif config.target_index and not in_interval:
            reason = (
                f"no membership snapshot for index {config.target_index!r} "
                "falls inside the requested interval, and no explicit "
                "universe symbols were supplied; membership is not inferred "
                "from current listings or price history"
            )
        universe = {
            "status": "unavailable",
            "reason": reason,
            "required_source": MEMBERSHIP_SOURCE_REQUIRED,
        }
        checks.append(
            _check("universe_resolution", "unavailable", reason, evidence=universe)
        )

    # --- membership coverage over the interval ----------------------------
    interval_days = (end - start).days + 1
    verified_days = sorted(
        {group["_date"] for group in relevant_groups if start <= group["_date"] <= end}
    )
    if verified_days:
        membership_coverage: dict[str, Any] = {
            "status": "ok",
            "interval": {
                "start": format_date(start),
                "end": format_date(end),
                "days": interval_days,
            },
            "snapshot_dates_in_interval": [format_date(day) for day in verified_days],
            "days_with_membership_snapshot": len(verified_days),
            "denominator": interval_days,
            "verified_day_percentage": round(
                100.0 * len(verified_days) / interval_days, 1
            ),
            "interpolation_performed": False,
            "granularity_note": (
                "A snapshot verifies membership only on its own date. "
                "Membership on the remaining interval days is unverified; no "
                "interpolation between snapshots is performed."
            ),
            "largest_unverified_gap": _largest_unverified_gap(
                start, end, verified_days
            ),
        }
    else:
        membership_coverage = {
            "status": "unavailable",
            "interval": {
                "start": format_date(start),
                "end": format_date(end),
                "days": interval_days,
            },
            "snapshot_dates_in_interval": [],
            "days_with_membership_snapshot": 0,
            "denominator": interval_days,
            "verified_day_percentage": None,
            "interpolation_performed": False,
            "reason": (
                "no membership snapshot falls inside the requested interval"
                if relevant_groups
                else NO_MEMBERSHIP_SNAPSHOTS
            ),
            "required_source": MEMBERSHIP_SOURCE_REQUIRED,
        }

    # --- price coverage inside the interval -------------------------------
    observed_in_interval = sorted(
        day for day in set(observed_dates) if start <= day <= end
    )
    price_coverage: dict[str, Any]
    if not observed_in_interval:
        price_coverage = {
            "status": "unavailable",
            "reason": (
                "no priced trading days fall inside the requested interval, "
                "so price coverage cannot be measured"
            ),
            "interval": {
                "start": format_date(start),
                "end": format_date(end),
                "days": interval_days,
            },
            "observed_trading_days": 0,
        }
        checks.append(
            _check(
                "universe_price_coverage",
                "unavailable",
                price_coverage["reason"],
                evidence={"observed_trading_days": 0},
            )
        )
    elif not universe_symbols:
        reason = universe.get(
            "reason", "the universe could not be resolved for this interval"
        )
        price_coverage = {
            "status": "unavailable",
            "reason": reason,
            "interval": {
                "start": format_date(start),
                "end": format_date(end),
                "days": interval_days,
            },
            "observed_trading_days": len(observed_in_interval),
        }
        checks.append(_check("universe_price_coverage", "unavailable", reason))
    else:
        price_coverage = coverage_summary(
            sorted(universe_symbols),
            price_dates,
            observed_in_interval,
            ambiguous_symbols,
        )
        price_coverage["interval"] = {
            "start": format_date(start),
            "end": format_date(end),
            "days": interval_days,
        }
        price_coverage["reference_basis"] = (
            "distinct priced trading days inside the backtest interval"
        )
        if config.min_price_coverage is not None:
            threshold = config.min_price_coverage
            below: list[dict[str, Any]] = []
            observed_days = price_coverage["observed_trading_days"]
            for symbol in sorted(universe_symbols):
                covered = len(
                    price_dates.get(symbol, set()) & set(observed_in_interval)
                )
                ratio = round(covered / observed_days, 4) if observed_days else 0.0
                if ratio < threshold:
                    below.append({"symbol": symbol, "coverage_ratio": ratio})
            price_coverage["required_min_price_coverage"] = threshold
            price_coverage["below_threshold_count"] = len(below)
            price_coverage["below_threshold_examples"] = below[:MAX_EXAMPLES]
        checks.append(
            _check(
                "universe_price_coverage",
                "ok",
                evidence={
                    "denominator": price_coverage["denominator"],
                    "counts": price_coverage["counts"],
                    "observed_trading_days": price_coverage["observed_trading_days"],
                },
            )
        )

    # --- delisted securities inside the interval --------------------------
    if not delistings_available or not securities:
        delisted_in_interval: dict[str, Any] = {
            "status": "unavailable",
            "reason": (
                "no delisting history was available for this analysis"
                if not delistings_available
                else "the delisting history contains no securities"
            ),
        }
        checks.append(
            _check(
                "delisted_securities_in_interval",
                "unavailable",
                delisted_in_interval["reason"],
            )
        )
    else:
        in_window: list[dict[str, Any]] = []
        for security in securities:
            hit_dates = sorted(
                day_text
                for day_text in security["delisted_dates"]
                if start <= date.fromisoformat(day_text) <= end
            )
            if not hit_dates:
                continue
            key = (str(security["key"][0]), str(security["key"][1]))
            info = classifications.get(key, {})
            in_window.append(
                {
                    "symbol": security["first"].symbol,
                    "delisted_dates": hit_dates,
                    "match_class": info.get("match_class", "unmatched"),
                }
            )
        in_window.sort(key=lambda item: (item["symbol"], item["delisted_dates"]))
        class_counts = {
            class_name: sum(
                1 for item in in_window if item["match_class"] == class_name
            )
            for class_name in MATCH_CLASSES
        }
        denominator = len(in_window)
        delisted_in_interval = {
            "status": "ok",
            "interval": {
                "start": format_date(start),
                "end": format_date(end),
                "days": interval_days,
            },
            "count": denominator,
            "denominator": denominator,
            "match_classes": class_counts,
            "with_price_history": denominator - class_counts["unmatched"],
            "percentages": (
                {
                    class_name: round(100.0 * class_counts[class_name] / denominator, 1)
                    for class_name in MATCH_CLASSES
                }
                if denominator
                else None
            ),
            "examples": in_window[:MAX_EXAMPLES],
        }
        checks.append(
            _check(
                "delisted_securities_in_interval",
                "ok",
                evidence={
                    "count": denominator,
                    "match_classes": class_counts,
                },
            )
        )

    # --- rebalancing / membership dates -----------------------------------
    if not config.rebalance_dates:
        rebalance_membership: dict[str, Any] = {
            "status": "not_applicable",
            "reason": "no rebalancing or membership dates were supplied",
        }
        checks.append(
            _check(
                "rebalance_membership_dates",
                "not_applicable",
                rebalance_membership["reason"],
            )
        )
    else:
        verified_set = set(verified_days)
        entries = [
            {
                "date": format_date(day),
                "membership_snapshot_on_date": day in verified_set,
            }
            for day in sorted(config.rebalance_dates)
        ]
        unverified = [
            entry["date"]
            for entry in entries
            if not entry["membership_snapshot_on_date"]
        ]
        rebalance_membership = {
            "status": "ok" if not unverified else "partial",
            "denominator": len(entries),
            "verified_count": len(entries) - len(unverified),
            "unverified_dates": unverified[:MAX_EXAMPLES],
            "dates": entries,
        }
        checks.append(
            _check(
                "rebalance_membership_dates",
                "ok" if not unverified else "unavailable",
                (
                    None
                    if not unverified
                    else "no membership snapshot exists for rebalancing "
                    f"date(s): {', '.join(unverified[:MAX_EXAMPLES])}"
                ),
                evidence={
                    "verified_count": rebalance_membership["verified_count"],
                    "denominator": len(entries),
                },
            )
        )

    checks.append(_check("bias_impact_quantification", "unavailable", impact["reason"]))

    unavailable_count = sum(1 for check in checks if check["status"] == "unavailable")
    status = "partial" if unavailable_count else "ok"

    return {
        "status": status,
        "config": summary,
        "checks": checks,
        "universe": universe,
        "membership_coverage": membership_coverage,
        "price_coverage": price_coverage,
        "delisted_in_interval": delisted_in_interval,
        "rebalance_membership": rebalance_membership,
        "bias_impact": impact,
        "unavailable_check_count": unavailable_count,
    }


def unavailable_assessment(reason: str) -> dict[str, Any]:
    """The backtest section reported when no configuration was supplied."""

    return {
        "status": "unavailable",
        "reason": reason,
        "checks": [],
        "bias_impact": {
            "status": "unavailable",
            "reason": (
                "No backtest configuration was supplied, so no backtest-specific "
                "assessment or impact estimate can be produced. The general "
                "data-coverage audit does not quantify return impact."
            ),
        },
    }


# Re-exported for callers that classify coverage with the same denominators.
__all__ = [
    "COVERAGE_AMBIGUOUS",
    "COVERAGE_CLASSES",
    "BacktestConfig",
    "IdentifierMapping",
    "assess_backtest",
    "build_backtest_config",
    "config_summary",
    "unavailable_assessment",
    "validate_config",
]
