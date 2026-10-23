"""Orchestration of the look-ahead-bias analysis.

The analysis separates three evidence classes and never blurs them:

- **Confirmed temporal violations** are reproducible ordering defects in the
  collected data itself: a result disseminated before its reporting period
  ended, a dissemination timestamp that precedes the exchange receipt or
  broadcast it should follow, or a revision recorded before the figures it
  corrects were public. Trusting such timestamps would let a backtest appear
  to use information before it existed.
- **Suspicious patterns** need knowledge of what a decision consumed before
  they can be called violations: restatement windows that contain decision
  dates, membership evidence that only postdates the decision dates, or the
  present-day listing snapshot standing in for a historical universe.
- **Insufficient evidence** marks statements the collected schemas cannot
  decide: announcement timestamps for corporate actions, quote-availability
  timestamps for prices, and the figures a decision actually consumed.

Which figures a decision consumed, and how harmful that consumption was, are
never asserted. The analyzer reuses the survivorship analyzer's dated
membership-snapshot reader so both assessments see the same evidence.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

from ...csv_io import Table
from ...models import DatasetResult
from ...parsing import format_date
from ..common import date_coverage
from ..survivorship.core import (
    parse_current_listings,
    parse_index_snapshots,
    snapshot_tables,
)
from ..survivorship.universe import snapshot_groups
from .backtest import (
    LookaheadConfig,
    assess_backtest,
    unavailable_assessment,
)
from .core import (
    CHECK_DERIVED,
    FINDING_CONFIRMED_CODE,
    FINDING_INSUFFICIENT_CODE,
    FINDING_SUSPICIOUS_CODE,
    ISSUE_ANNOUNCEMENT_UNAVAILABLE,
    ISSUE_CURRENT_LISTING_MISSING,
    ISSUE_DERIVED_FORWARD,
    ISSUE_DISSEMINATION_BEFORE_RECEIPT,
    ISSUE_EX_DATE_MISSING,
    ISSUE_PERIOD_MISSING,
    ISSUE_PRE_EVENT_PRICE_MISSING,
    ISSUE_PRICE_AVAILABILITY_UNKNOWN,
    ISSUE_PUBLICATION_BEFORE_PERIOD,
    ISSUE_PUBLICATION_MISSING,
    ISSUE_RECORD_BEFORE_EX_DATE,
    ISSUE_RESTATEMENT_WINDOW,
    ISSUE_REVISION_BEFORE_PUBLIC,
    ISSUE_TIMESTAMP_UNPARSEABLE,
    ISSUE_UNIVERSE_NOT_POINT_IN_TIME,
    KIND_BACKTEST,
    KIND_CHECK,
    KIND_CONFIRMED,
    KIND_INSUFFICIENT,
    KIND_SUSPICIOUS,
    LOOKAHEAD_CATEGORY,
    LOOKAHEAD_DATASET_ID,
    LOOKAHEAD_LABEL,
    MAX_EXAMPLES,
    _corporate_action_records_with_counts,
    _financial_records_with_counts,
    _price_records_with_counts,
    attach_table_issues,
    listing_tables,
    load_relevant_tables,
    relative,
)
from .timing import (
    corporate_action_metrics,
    event_price_coverage,
    price_availability_metrics,
    publication_metrics,
    revision_metrics,
    snapshot_summary,
)

NO_CONFIG_REASON = (
    "No backtest configuration was supplied, so only the general temporal "
    "evidence audit ran. Decision-date availability profiles, relied-on "
    "membership timing, and any impact estimate are unavailable."
)

UNIVERSE_REQUIRED_SOURCE = (
    "A dated, authoritative index-constituent membership series covering the "
    "backtest interval (index name, snapshot/effective date, symbol, ISIN)."
)

DERIVED_FAMILIES: tuple[tuple[str, str], ...] = (
    ("derived_financials_legacy", "financials"),
    ("derived_financials_integrated", "integrated_financials"),
    ("derived_prices", "prices"),
    ("derived_corporate_actions", "corporate_actions"),
)


def _finding(
    code: str,
    explanation: str,
    kind: str,
    *,
    check: str | None = None,
    dates: dict[str, Any] | None = None,
    counts: dict[str, Any] | None = None,
    evidence: dict[str, Any] | None = None,
    limitations: Sequence[str] | None = None,
    remediation: str | None = None,
) -> dict[str, Any]:
    """Build one structured finding; omitted fields stay out of the report."""

    entry: dict[str, Any] = {"code": code, "kind": kind}
    entry["explanation"] = explanation
    if check is not None:
        entry["check"] = check
    if dates:
        entry["dates"] = dates
    if counts:
        entry["counts"] = counts
    if evidence:
        entry["evidence"] = evidence
    if limitations:
        entry["limitations"] = list(limitations)
    if remediation:
        entry["remediation"] = remediation
    return entry


class _Findings:
    """Collects structured findings alongside report issues."""

    def __init__(self, result: DatasetResult) -> None:
        self.result = result
        self.entries: list[dict[str, Any]] = []

    def warn(
        self,
        code: str,
        message: str,
        kind: str,
        *,
        remediation: str | None = None,
        **fields: Any,
    ) -> None:
        """Add a warning issue and its structured counterpart."""

        self.result.add_warning(code, message)
        self.entries.append(
            _finding(code, message, kind, remediation=remediation, **fields)
        )

    def add(self, code: str, explanation: str, kind: str, **fields: Any) -> None:
        """Add a structured finding that is not an issue."""

        self.entries.append(_finding(code, explanation, kind, **fields))


def _derived_or_raw(
    tables: Mapping[str, Sequence[Table]],
    *,
    derived_kind: str,
    raw_kind: str,
) -> list[tuple[str, Table]]:
    """Return the preferred kind/table pairs for one dataset family.

    Normalized rows are used when they exist so raw imports and derived
    re-computations never double the evidence for one event.
    """

    derived = [
        (derived_kind, table)
        for table in tables.get(derived_kind, ())
        if table.readable
    ]
    if derived:
        return derived
    return [(raw_kind, table) for table in tables.get(raw_kind, ()) if table.readable]


def _parse_examples(problems: Sequence[str], limit: int = 3) -> str:
    if not problems:
        return ""
    shown = ", ".join(problems[:limit])
    suffix = f", and {len(problems) - limit} more" if len(problems) > limit else ""
    return f"{shown}{suffix}"


def _record_examples(entries: Sequence[Mapping[str, Any]], limit: int = 2) -> str:
    """Render the first entries of a violation list for inline messages."""

    parts = []
    for entry in entries[:limit]:
        symbol = entry.get("symbol") or entry.get("company") or "unknown"
        period = entry.get("period_end")
        moment = (
            entry.get("publication")
            or entry.get("dissemination")
            or entry.get("broadcast")
            or entry.get("revision_published")
        )
        parts.append(f"{symbol} period {period} recorded available at {moment}")
    return "; ".join(parts)


def analyze(
    data_root: str | Path,
    tables: Mapping[str, Sequence[Table]] | None = None,
    config: LookaheadConfig | None = None,
    *,
    backtest: LookaheadConfig | None = None,
) -> DatasetResult:
    """Analyze look-ahead-bias evidence without modifying any source file.

    ``tables`` may inject datasets by kind for tests; when omitted they are
    discovered under ``data_root``. Dated membership snapshots are read from
    ``reference/index_constituents/extracted_csv`` under ``data_root`` unless
    explicitly provided under the ``index_snapshot`` kind (using the shared
    snapshot reader). ``config`` (or ``backtest``) opts in to the
    backtest-specific assessment; without it those results are reported as
    unavailable.
    """

    root = Path(data_root)
    if config is None and backtest is not None:
        config = backtest
    if tables is None:
        tables = load_relevant_tables(root)
    snapshot_source_tables = snapshot_tables(tables, root)
    listing_table = listing_tables(tables)

    selection: dict[str, list[Table]] = {}
    for derived_kind, raw_kind in DERIVED_FAMILIES:
        for kind, table in _derived_or_raw(
            tables, derived_kind=derived_kind, raw_kind=raw_kind
        ):
            selection.setdefault(kind, []).append(table)

    selected: list[Table] = [
        table for kind_tables in selection.values() for table in kind_tables
    ]
    primary_path = (
        relative(selected[0].path, root)
        if selected
        else (relative(listing_table.path, root) if listing_table else "lookahead")
    )
    result = DatasetResult(
        dataset_id=LOOKAHEAD_DATASET_ID,
        category=LOOKAHEAD_CATEGORY,
        label=LOOKAHEAD_LABEL,
        path=primary_path,
    )
    findings = _Findings(result)
    attach_table_issues(result, snapshot_source_tables, root)

    # ------------------------------------------------------------------ parse
    financials, rows_without_period, parse_problems = _financial_records_with_counts(
        selection
    )
    action_records, actions_without_ex_date = _corporate_action_records_with_counts(
        selection
    )
    prices, undated_prices = _price_records_with_counts(selection)

    listings: list[Any] = []
    listing_dates: list[date] = []
    if listing_table is not None:
        listings, listing_dates = parse_current_listings(
            listing_table,
            result,
            relative(listing_table.path, root),
        )
    else:
        result.add_warning(
            ISSUE_CURRENT_LISTING_MISSING,
            "No current listing reference was available, so the check that "
            "rules out present-day listings standing in for the historical "
            "universe could not run.",
        )

    snapshots: list[Any] = []
    excluded_snapshot_rows = 0
    if snapshot_source_tables:
        snapshots, _snapshot_dates, excluded_snapshot_rows = parse_index_snapshots(
            snapshot_source_tables,
            root,
            result,
        )
    groups = snapshot_groups(snapshots)

    result.row_count = len(financials)
    result.coverage = date_coverage(
        [record.period_end for record in financials if record.period_end],
        "PERIOD ENDED / QUARTER END DATE",
    )

    # --------------------------------------------------------------- evidence
    price_dates: dict[str, set[date]] = {}
    for record in prices:
        if record.symbol:
            price_dates.setdefault(record.symbol, set()).add(record.trade_date)
    observed_dates = sorted({record.trade_date for record in prices})

    pub = publication_metrics(financials)
    rev = revision_metrics(financials)
    actions = corporate_action_metrics(action_records)
    events = event_price_coverage(action_records, price_dates)
    actions["event_price_coverage"] = events
    actions["price_symbols"] = sorted(price_dates)
    prices_available = price_availability_metrics(prices)
    universe = snapshot_summary(snapshots)
    listing_symbols = {record.symbol for record in listings if record.symbol}

    derived_inputs = {
        "financials": any(kind.startswith("derived_financials") for kind in selection),
        "prices": any(kind.startswith("derived_price") for kind in selection),
        "corporate_actions": "derived_corporate_actions" in selection,
    }

    inputs = sorted(
        {relative(table.path, root) for table in selected}
        | {relative(table.path, root) for table in snapshot_source_tables}
        | ({relative(listing_table.path, root)} if listing_table is not None else set())
    )
    if config is None:
        assessment = unavailable_assessment(NO_CONFIG_REASON)
    else:
        assessment = assess_backtest(
            config,
            financials=financials,
            action_records=action_records,
            publication=pub,
            revisions=rev,
            actions=actions,
            event_prices=events,
            groups=groups,
            listing_symbols=listing_symbols,
            price_dates=price_dates,
            observed_dates=observed_dates,
            derived_inputs=derived_inputs,
        )

    # ------------------------------------------------------------ base metrics
    result.metrics["analysis"] = {
        "dataset_id": LOOKAHEAD_DATASET_ID,
        "conclusion": (
            "This analysis measures the temporal ordering between decision "
            "dates, the reporting periods those decisions rely on, and the "
            "timestamps at which the underlying information became "
            "available. It never treats future dates inside a dataset as "
            "proof of look-ahead bias, never claims that look-ahead bias is "
            "absent, and never quantifies its return impact."
        ),
        "mode": (
            "backtest_specific_assessment"
            if config is not None
            else "general_temporal_evidence_audit"
        ),
        "backtest_config_supplied": config is not None,
        "read_only": True,
        "inputs": inputs,
    }
    result.metrics["financial_publication"] = pub
    result.metrics["financial_revisions"] = rev
    result.metrics["corporate_action_timing"] = actions
    result.metrics["point_in_time_universe"] = universe
    result.metrics["price_availability"] = prices_available
    result.metrics["backtest_assessment"] = assessment
    result.metrics["data_facts"] = {
        "financial_records_analyzed": len(financials),
        "financial_kinds": pub["kind_counts"],
        "financial_rows_without_period_end": rows_without_period,
        "financial_parse_problems": len(parse_problems),
        "financial_parse_problem_examples": parse_problems[:MAX_EXAMPLES],
        "corporate_action_records": len(action_records),
        "corporate_action_rows_without_ex_date": actions_without_ex_date,
        "price_rows": len(prices),
        "price_rows_undated": undated_prices,
        "price_symbols": sorted(price_dates),
        "price_date_range": prices_available["date_range"],
        "listing_rows": len(listings),
        "listing_date_range": (
            {
                "start": format_date(min(listing_dates)),
                "end": format_date(max(listing_dates)),
            }
            if listing_dates
            else None
        ),
        "membership_snapshot_count": universe["snapshot_count"],
        "membership_snapshot_dates": [
            entry["date"] for entry in universe["snapshot_dates"]
        ],
        "membership_excluded_rows": excluded_snapshot_rows,
        "membership_constituent_rows": len(snapshots),
        "interpolation_performed": False,
    }

    # --------------------------------------------------------------- findings
    confirmed: list[str] = []
    suspicious: list[str] = []
    insufficient: list[str] = []

    if pub["before_period_count"]:
        confirmed.append("publication timestamps precede their reporting periods")
        findings.warn(
            ISSUE_PUBLICATION_BEFORE_PERIOD,
            (
                f"{pub['before_period_count']} financial record(s) record "
                "availability before their reporting period ended "
                f"({_record_examples(pub['before_period_examples'])}). Such a "
                "timestamp is physically impossible; trusting it would make a "
                "result appear usable before the information existed, so the "
                "record's availability cannot be used in a look-ahead "
                "assessment."
            ),
            KIND_CONFIRMED,
            check="publication_timing",
            counts={"violations": pub["before_period_count"]},
            evidence={"examples": pub["before_period_examples"]},
            remediation=(
                "Verify the recorded timestamps against the exchange and the "
                "filing lifecycle; raw values are reported, never corrected "
                "in place."
            ),
        )

    if pub["dissemination_before_receipt_count"]:
        confirmed.append(
            "dissemination timestamps precede the exchange receipt or broadcast"
        )
        findings.warn(
            ISSUE_DISSEMINATION_BEFORE_RECEIPT,
            (
                f"{pub['dissemination_before_receipt_count']} financial "
                "record(s) have an exchange dissemination timestamp earlier "
                "than their receipt or broadcast time; the recorded ordering "
                "cannot be trusted for availability decisions "
                f"({_record_examples(pub['dissemination_before_receipt_examples'])})."
            ),
            KIND_CONFIRMED,
            check="publication_timing",
            counts={"violations": pub["dissemination_before_receipt_count"]},
            evidence={"examples": pub["dissemination_before_receipt_examples"]},
        )

    if rev["revision_before_publication_count"]:
        confirmed.append("revisions precede the publication they correct")
        findings.warn(
            ISSUE_REVISION_BEFORE_PUBLIC,
            (
                f"{rev['revision_before_publication_count']} revised "
                "submission(s) record a revision moment before the original "
                "figures were available; corrected figures could not exist "
                "before the figures they correct ("
                + _record_examples(rev["revision_before_publication_examples"], limit=3)
                + ")."
            ),
            KIND_CONFIRMED,
            check="financial_revisions",
            counts={"violations": rev["revision_before_publication_count"]},
            evidence={"examples": rev["revision_before_publication_examples"]},
        )

    if rev["restatement_window_count"]:
        suspicious.append("restatement windows exist for revised periods")
        findings.warn(
            ISSUE_RESTATEMENT_WINDOW,
            (
                f"{rev['restatement_window_count']} reporting period(s) have "
                "revised figures published after the originals: between the "
                "original publication and the revision publication, the same "
                "line item carries different values. The collected evidence "
                "cannot show which version a decision received, so each such "
                "window is reported for review."
            ),
            KIND_SUSPICIOUS,
            check="financial_revisions",
            counts={"windows": rev["restatement_window_count"]},
            evidence={"examples": rev["restatement_window_examples"]},
        )

    if actions["record_before_ex_count"]:
        suspicious.append("record dates precede ex dates")
        findings.warn(
            ISSUE_RECORD_BEFORE_EX_DATE,
            (
                f"{actions['record_before_ex_count']} corporate-action "
                "record(s) place the record date before the ex date, which "
                "distorts event-time sequencing for any window keyed on the "
                f"ex date ({actions['record_before_ex_examples'][0]['symbol']!r} "
                f"{actions['record_before_ex_examples'][0]['ex_date']}). The "
                "ordering anomaly is reported for review; entitlement dates "
                "are never treated as announcement timestamps."
            ),
            KIND_SUSPICIOUS,
            check="price_action_timing",
            counts={"violations": actions["record_before_ex_count"]},
            evidence={"examples": actions["record_before_ex_examples"]},
        )

    if pub["publication_missing"]:
        insufficient.append("availability timestamps are missing for some records")
        findings.warn(
            ISSUE_PUBLICATION_MISSING,
            (
                f"{pub['publication_missing']} of {pub['records']} financial "
                "record(s) carry no parsable broadcast or dissemination "
                f"timestamp ({_record_examples(pub['missing_examples'])}). "
                "Those records cannot be timed against any decision date; "
                "they are excluded from availability profiles."
            ),
            KIND_INSUFFICIENT,
            check="publication_timing",
            counts={"records": pub["publication_missing"]},
            evidence={"examples": pub["missing_examples"]},
        )

    if pub["period_end_missing"]:
        insufficient.append("reporting periods are missing for some records")
        findings.warn(
            ISSUE_PERIOD_MISSING,
            (
                f"{pub['period_end_missing']} financial record(s) have no "
                "parsable reporting-period end, so their publication timing "
                "cannot be compared with the period at all."
            ),
            KIND_INSUFFICIENT,
            check="publication_timing",
            counts={"records": pub["period_end_missing"]},
        )

    if parse_problems:
        insufficient.append("some date/time cells fail to parse")
        findings.warn(
            ISSUE_TIMESTAMP_UNPARSEABLE,
            (
                f"{len(parse_problems)} financial timestamp/date cell(s) "
                f"could not be parsed ({_parse_examples(parse_problems)}). "
                "They are reported and excluded; no value is substituted."
            ),
            KIND_INSUFFICIENT,
            check="publication_timing",
            counts={"cells": len(parse_problems)},
            evidence={"examples": parse_problems[:MAX_EXAMPLES]},
        )

    if action_records:
        insufficient.append(
            "corporate-action announcements are absent from the exports"
        )
        findings.warn(
            ISSUE_ANNOUNCEMENT_UNAVAILABLE,
            actions["announcement_unavailable_note"],
            KIND_INSUFFICIENT,
            check="price_action_timing",
            counts={"records": len(action_records)},
            remediation=(
                "Collect announcement or board-approval timestamps per "
                "corporate action to verify when an event (and its amount) "
                "became public."
            ),
        )

    if actions_without_ex_date:
        insufficient.append("some actions lack parsable ex dates")
        findings.warn(
            ISSUE_EX_DATE_MISSING,
            (
                f"{actions_without_ex_date} corporate-action record(s) carry "
                "no parsable EX-DATE; event timing around them cannot be "
                "measured."
            ),
            KIND_INSUFFICIENT,
            check="price_action_timing",
            counts={"records": actions_without_ex_date},
        )

    if events["pre_event_prices_missing"]:
        insufficient.append("pre-event prices are missing for some actions")
        findings.warn(
            ISSUE_PRE_EVENT_PRICE_MISSING,
            (
                f"{events['pre_event_prices_missing']} of "
                f"{events['evaluable_actions']} corporate action(s) have no "
                "price rows dated before their ex date, so the events cannot "
                "be mapped onto the collected price series."
            ),
            KIND_INSUFFICIENT,
            check="price_action_timing",
            counts={"actions": events["pre_event_prices_missing"]},
            evidence={
                "missing_examples": events["missing_examples"],
                "symbols_without_prices": events["symbols_without_price_count"],
            },
        )

    if prices_available["rows"]:
        insufficient.append(
            "price rows carry only trade dates, not availability timestamps"
        )
        findings.warn(
            ISSUE_PRICE_AVAILABILITY_UNKNOWN,
            (
                f"{prices_available['rows']} priced row(s) for "
                f"{len(prices_available['symbols'])} symbol(s) carry trade "
                "dates only. Quote availability (and any intraday release "
                "effect) is unknown, so price-based features cannot be shown "
                "to be free of look-ahead here."
            ),
            KIND_INSUFFICIENT,
            check="derived_feature_timing",
            counts={"rows": prices_available["rows"]},
            evidence={"date_range": prices_available["date_range"]},
            remediation=prices_available["required_additional_source"],
        )

    if not universe["point_in_time_snapshots_present"]:
        insufficient.append("no dated membership snapshot is available")
        findings.warn(
            ISSUE_UNIVERSE_NOT_POINT_IN_TIME,
            (
                "No dated point-in-time membership snapshot is present, so "
                "universe-based look-ahead (deciding against a universe list "
                "that was only finalised later) cannot be verified. Current "
                "listings, delisting events, and price history are never "
                "treated as historical membership."
            ),
            KIND_INSUFFICIENT,
            check="point_in_time_universe",
            remediation=UNIVERSE_REQUIRED_SOURCE,
        )
    else:
        findings.add(
            "lookahead.point_in_time_universe_facts",
            (
                f"{universe['snapshot_count']} dated membership snapshot(s) "
                "verify membership only on their own dates ("
                + ", ".join(entry["date"] for entry in universe["snapshot_dates"][:3])
                + "); membership is never interpolated between snapshots."
            ),
            KIND_CHECK,
            evidence={
                "snapshot_count": universe["snapshot_count"],
                "interpolation_performed": False,
            },
        )

    # ------------------------------------------------- backtest-specific issues
    if config is not None:
        if assessment["status"] == "invalid":
            findings.warn(
                "lookahead.backtest_config_invalid",
                "The look-ahead backtest configuration is invalid: "
                + "; ".join(assessment["errors"]),
                KIND_BACKTEST,
                evidence={"errors": assessment["errors"]},
                remediation=(
                    "Correct the backtest inputs (interval, decision dates, "
                    "and membership snapshot dates) and rerun."
                ),
            )
        unavailable_checks = [
            check
            for check in assessment.get("checks", [])
            if check.get("status") == "unavailable"
        ]
        if unavailable_checks:
            summary_text = "; ".join(
                f"{check['check']}: {check.get('reason') or 'unavailable'}"
                for check in unavailable_checks[:MAX_EXAMPLES]
            )
            findings.warn(
                "lookahead.backtest_checks_unavailable",
                (
                    f"{len(unavailable_checks)} backtest check(s) could not "
                    f"be performed with the collected data: {summary_text}"
                ),
                KIND_BACKTEST,
                evidence={
                    "checks": [
                        {"check": check["check"], "reason": check.get("reason")}
                        for check in unavailable_checks
                    ]
                },
                remediation=(
                    "Supply the missing decision dates, membership series, or "
                    "announcement timestamps listed in the backtest "
                    "assessment metrics."
                ),
            )
        for note in assessment.get("insufficient_notes", []):
            findings.add(
                FINDING_INSUFFICIENT_CODE,
                note,
                KIND_INSUFFICIENT,
                check=CHECK_DERIVED
                if "derived" in note
                else "decision_timestamp_coverage",
            )
        if assessment["status"] == "confirmed":
            confirmed.append(
                "the backtest assessment found confirmed temporal violations"
            )
        if assessment["status"] == "suspicious":
            suspicious.append(
                "the backtest assessment found suspicious timing patterns"
            )

    # ---------------------------------------------------------- checks passed
    checks_passed = [
        "no_availability_timestamp_is_inferred_from_period_or_effective_dates",
        "published_figures_are_never_assumed_available_before_their_earliest_recorded_time",
        "membership_is_never_interpolated_between_snapshots",
        "future_dates_inside_a_dataset_are_never_treated_as_lookahead_proof",
        "parse_failures_are_reported_and_excluded_without_substitution",
    ]
    if not pub["publication_missing"] and financials:
        checks_passed.append(
            "every_analyzed_financial_record_carries_availability_evidence"
        )
    if (
        financials
        and not pub["before_period_count"]
        and not pub["dissemination_before_receipt_count"]
    ):
        checks_passed.append(
            "all_recorded_availability_timestamps_follow_their_reporting_periods"
        )
    if action_records and not actions["record_before_ex_count"]:
        checks_passed.append("all_recorded_entitlement_dates_follow_their_ex_dates")
    if not events["pre_event_prices_missing"] and events["evaluable_actions"]:
        checks_passed.append("every_action_has_pre_event_price_rows")

    findings.add(
        "lookahead.data_facts",
        (
            "Counts, date ranges, and parse outcomes of every input actually "
            "read by the analysis (confirmed from the data, not estimated)."
        ),
        KIND_CHECK,
        counts=result.metrics["data_facts"],
        dates={
            "price_date_range": prices_available["date_range"],
            "membership_snapshot_range": universe["date_range"],
        },
    )
    findings.add(
        "lookahead.publication_lag_facts",
        (
            "Publication lags are measured from the earliest recorded "
            "broadcast or exchange dissemination timestamp; the distribution "
            "below is computed from parsed period/publication pairs only."
        ),
        KIND_CHECK,
        counts=pub["lag_days"] or {},
        evidence={"records_with_lag": (pub["lag_days"] or {}).get("count", 0)},
    )
    for check in sorted(set(checks_passed)):
        findings.add(
            "lookahead.check_passed",
            check,
            KIND_CHECK,
            evidence={"check": check},
        )
    findings.add(
        "lookahead.derived_feature_note",
        (
            "Derived financial tables re-expose the same timestamps and are "
            "checked together with the raw schemas; derived price and "
            "corporate-action tables carry no availability timestamps at all "
            f"(represented by the {ISSUE_PRICE_AVAILABILITY_UNKNOWN} finding)."
        ),
        KIND_CHECK,
        check=CHECK_DERIVED,
        evidence={"derived_forward_reference": ISSUE_DERIVED_FORWARD},
    )
    for entry in confirmed:
        findings.add(FINDING_CONFIRMED_CODE, entry, KIND_CONFIRMED)
    for entry in suspicious:
        findings.add(FINDING_SUSPICIOUS_CODE, entry, KIND_SUSPICIOUS)
    for entry in insufficient:
        findings.add(
            FINDING_INSUFFICIENT_CODE,
            entry,
            KIND_INSUFFICIENT,
            remediation=(
                "Supply the missing timestamps named in the conclusion to make "
                "the statement verifiable."
            ),
        )

    if config is None:
        backtest_results: dict[str, Any] = {
            "status": "unavailable",
            "reason": NO_CONFIG_REASON,
            "how_to_enable": (
                "Pass a LookaheadConfig to lookahead.analyze (or use the "
                "--decision-date CLI flag together with the backtest interval "
                "flags)."
            ),
        }
    else:
        backtest_results = {
            "status": assessment["status"],
            "config": assessment.get("config"),
            "checks": [
                {
                    "check": check["check"],
                    "status": check["status"],
                    **({"reason": check["reason"]} if check.get("reason") else {}),
                }
                for check in assessment.get("checks", [])
            ],
            "bias_impact": assessment["bias_impact"]["status"],
            "insufficient_note_count": len(assessment.get("insufficient_notes", [])),
        }

    result.metrics["findings"] = {
        "confirmed_lookahead_violations": confirmed,
        "potential_lookahead_risks": suspicious,
        "insufficient_lookahead_evidence": insufficient,
        "checks_passed": checks_passed,
        "detailed_findings": findings.entries,
        "backtest_specific_results": backtest_results,
    }
    return result
