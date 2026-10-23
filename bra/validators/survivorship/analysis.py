"""Orchestration of the survivorship-bias coverage analysis.

The analysis is descriptive and read-only. It separates confirmed data facts,
potential survivorship risks, coverage limitations, checks that passed,
unverifiable conclusions, and backtest-specific results. It never claims that
survivorship bias is absent, never infers historical index membership from
present-day data, and never quantifies return impact without backtest inputs.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

from ...csv_io import Table
from ...models import DatasetResult
from ...parsing import clean, format_date
from ..common import date_coverage
from .backtest import (
    BacktestConfig,
    assess_backtest,
    unavailable_assessment,
)
from .core import (
    ANALYSIS_CATEGORY,
    ANALYSIS_DATASET_ID,
    ANALYSIS_LABEL,
    KIND_BACKTEST,
    KIND_CHECK,
    KIND_FACT,
    KIND_LIMITATION,
    KIND_RISK,
    KIND_UNVERIFIABLE,
    MATCH_CLASSES,
    MAX_EXAMPLES,
    NameChange,
    SymbolChange,
    attach_table_issues,
    delisting_table,
    load_relevant_tables,
    parse_current_listings,
    parse_delistings,
    parse_index_snapshots,
    parse_name_changes,
    parse_prices,
    parse_symbol_changes,
    price_tables,
    relative,
    select_table,
    snapshot_tables,
)
from .matching import (
    ambiguous_symbol_reasons,
    classify_delisted_matches,
    continuity_examples,
    coverage_summary,
    identifier_reuse_evidence,
    price_dates_by_symbol,
    price_metrics,
    reused_symbols_in_delistings,
    security_groups,
    symbol_change_metrics,
)
from .universe import membership_metrics, universe_symbols

NO_BACKTEST_REASON = (
    "No backtest configuration was supplied, so only the general "
    "data-coverage audit ran. Backtest-specific conclusions, universe "
    "membership for a requested interval, and any return-impact estimate "
    "are unavailable."
)


def _finding(
    code: str,
    explanation: str,
    kind: str,
    *,
    severity: str | None = None,
    sources: Sequence[str] | None = None,
    dates: dict[str, Any] | None = None,
    counts: dict[str, Any] | None = None,
    denominators: dict[str, Any] | None = None,
    match_classification: dict[str, Any] | None = None,
    evidence: dict[str, Any] | None = None,
    limitations: Sequence[str] | None = None,
    remediation: str | None = None,
) -> dict[str, Any]:
    """Build one structured finding; empty fields are omitted."""

    entry: dict[str, Any] = {"code": code, "kind": kind}
    if severity is not None:
        entry["severity"] = severity
    entry["explanation"] = explanation
    if sources:
        entry["sources"] = list(sources)
    if dates:
        entry["dates"] = dates
    if counts:
        entry["counts"] = counts
    if denominators:
        entry["denominators"] = denominators
    if match_classification:
        entry["match_classification"] = match_classification
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
            _finding(
                code,
                message,
                kind,
                severity="warning",
                remediation=remediation,
                **fields,
            )
        )

    def add(self, code: str, explanation: str, kind: str, **fields: Any) -> None:
        """Add a structured finding that is not an issue."""

        self.entries.append(_finding(code, explanation, kind, **fields))


def analyze(
    data_root: str | Path,
    tables: Mapping[str, Sequence[Table]] | None = None,
    backtest: BacktestConfig | None = None,
) -> DatasetResult:
    """Analyze survivorship-bias coverage without modifying any source file.

    ``tables`` may inject datasets by kind for tests; when omitted they are
    discovered under ``data_root``. Index-membership snapshots are read from
    ``reference/index_constituents/extracted_csv`` under ``data_root`` unless
    explicitly provided under the ``index_snapshot`` kind. ``backtest`` opts in
    to the backtest-specific assessment; without it those results are reported
    as unavailable.
    """

    root = Path(data_root)
    if tables is None:
        tables = load_relevant_tables(root)
    snapshot_source_tables = snapshot_tables(tables, root)

    current_table = select_table(
        tables,
        ("derived_current_listings", "current_listing"),
    )
    listing_delisting_table = delisting_table(tables)
    price_table_list = price_tables(tables)
    symbol_change_table = select_table(
        tables,
        ("derived_symbol_changes", "symbol_changes"),
    )
    name_change_table = select_table(
        tables,
        ("derived_name_changes", "name_changes"),
    )

    selected_tables = [
        table
        for table in (
            current_table,
            listing_delisting_table,
            *price_table_list,
            symbol_change_table,
            name_change_table,
        )
        if table is not None
    ]
    primary_path = (
        relative(selected_tables[0].path, root) if selected_tables else "survivorship"
    )
    result = DatasetResult(
        dataset_id=ANALYSIS_DATASET_ID,
        category=ANALYSIS_CATEGORY,
        label=ANALYSIS_LABEL,
        path=primary_path,
    )
    findings = _Findings(result)
    attach_table_issues(result, snapshot_source_tables, root)

    # ------------------------------------------------------------------ parse
    current: list[Any] = []
    current_dates: list[date] = []
    delistings: list[Any] = []
    delisting_dates: list[date] = []
    prices: list[Any] = []
    price_dates: list[date] = []
    symbol_changes: list[SymbolChange] = []
    name_changes: list[NameChange] = []
    snapshots: list[Any] = []
    snapshot_dates: list[date] = []
    excluded_snapshot_rows = 0

    if current_table is not None:
        current, current_dates = parse_current_listings(
            current_table,
            result,
            relative(current_table.path, root),
        )
    else:
        result.add_warning(
            "survivorship.current_listing_missing",
            (
                "No current listing reference was available. The current-snapshot "
                "check and relisting evidence are therefore incomplete."
            ),
        )

    if listing_delisting_table is not None:
        delistings, delisting_dates = parse_delistings(
            listing_delisting_table,
            result,
            relative(listing_delisting_table.path, root),
        )
    else:
        result.add_warning(
            "survivorship.delistings_missing",
            (
                "No delisting history was available. Delisted-security price "
                "coverage cannot be calculated."
            ),
        )

    if price_table_list:
        prices, price_dates = parse_prices(price_table_list, root, result)
    else:
        result.add_warning(
            "survivorship.prices_missing",
            (
                "No price history was available. Price symbol coverage and "
                "delisted-security matching cannot be calculated."
            ),
        )

    if symbol_change_table is not None:
        symbol_changes = parse_symbol_changes(
            symbol_change_table,
            result,
            relative(symbol_change_table.path, root),
        )
    if name_change_table is not None:
        name_changes = parse_name_changes(
            name_change_table,
            result,
            relative(name_change_table.path, root),
        )
    if snapshot_source_tables:
        snapshots, snapshot_dates, excluded_snapshot_rows = parse_index_snapshots(
            snapshot_source_tables,
            root,
            result,
        )

    # row_count and coverage describe the analysis inputs (the delisting
    # records), never the price dataset's date range.
    result.row_count = len(delistings)
    result.coverage = date_coverage(delisting_dates, "Delisted Date")

    # ------------------------------------------------------------- computing
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

    user_changes = [
        SymbolChange(
            old_symbol=clean(mapping.old_symbol).upper(),
            new_symbol=clean(mapping.new_symbol).upper(),
            company_name="",
            effective_date=mapping.effective_date,
            row=0,
            source="backtest_config",
        )
        for mapping in (backtest.identifier_mappings if backtest else ())
    ]
    matching_changes = [*symbol_changes, *user_changes]

    price_summary = price_metrics(prices, price_dates)
    observed_dates = sorted(set(price_dates))
    price_index = price_dates_by_symbol(prices)
    securities = security_groups(delistings)
    delisted_coverage, classifications = classify_delisted_matches(
        securities,
        set(price_summary["symbols"]),
        price_index,
        observed_dates,
        current,
        matching_changes,
    )
    identifier_reuse = identifier_reuse_evidence(securities, current)
    reused_symbols = reused_symbols_in_delistings(securities)
    symbol_metrics, shared_new_symbols, conflicts = symbol_change_metrics(
        matching_changes
    )
    ambiguous_symbols = ambiguous_symbol_reasons(reused_symbols, conflicts)
    continuity = continuity_examples(
        securities,
        current,
        symbol_changes,
        name_changes,
    )
    membership = membership_metrics(
        snapshots,
        root,
        excluded_rows=excluded_snapshot_rows,
    )
    membership_dates = [format_date(day) for day in sorted(set(snapshot_dates))]

    # Universe price coverage against the price dataset's own date range.
    universe_set = sorted(universe_symbols(snapshots))
    if universe_set and observed_dates:
        universe_coverage: dict[str, Any] = coverage_summary(
            universe_set,
            price_index,
            observed_dates,
            ambiguous_symbols,
        )
        universe_coverage["reference"] = {
            "basis": "distinct priced trading days in the collected price data",
            "date_range": price_summary["date_range"],
        }
        universe_coverage["universe_source"] = (
            "dated index-constituent membership snapshots"
        )
    elif not universe_set:
        universe_coverage = {
            "status": "unavailable",
            "reason": (
                "no dated point-in-time membership snapshot is present, so no "
                "historical universe can be reconstructed"
            ),
            "denominator": 0,
            "denominator_basis": "distinct eligible securities in the universe",
            "observed_trading_days": len(observed_dates),
            "counts": None,
            "percentages": None,
            "required_source": membership["required_additional_source"],
        }
    else:
        universe_coverage = {
            "status": "unavailable",
            "reason": (
                "no dated price rows are available to measure membership "
                "coverage against"
            ),
            "denominator": len(universe_set),
            "denominator_basis": "distinct eligible securities in the universe",
            "observed_trading_days": 0,
            "counts": None,
            "percentages": None,
        }

    if backtest is None:
        assessment = unavailable_assessment(NO_BACKTEST_REASON)
    else:
        assessment = assess_backtest(
            backtest,
            snapshots=snapshots,
            price_dates=price_index,
            observed_dates=observed_dates,
            ambiguous_symbols=ambiguous_symbols,
            securities=securities,
            classifications=classifications,
            delistings_available=listing_delisting_table is not None,
        )

    # ---------------------------------------------------------- base metrics
    result.metrics["analysis"] = {
        "dataset_id": ANALYSIS_DATASET_ID,
        "conclusion": (
            "This analysis measures coverage and identifier risks; it does not "
            "measure the magnitude of survivorship bias. The absence of a "
            "reported problem would not prove that survivorship bias is absent."
        ),
        "mode": (
            "backtest_specific_assessment"
            if backtest is not None
            else "general_data_coverage_audit"
        ),
        "backtest_config_supplied": backtest is not None,
        "read_only": True,
        "inputs": sorted(
            {
                relative(table.path, root)
                for table in selected_tables
                if table is not None
            }
            | {relative(table.path, root) for table in snapshot_source_tables}
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
    result.metrics["price_coverage"] = price_summary
    result.metrics["delisted_price_coverage"] = delisted_coverage
    result.metrics["index_membership"] = membership
    result.metrics["universe_price_coverage"] = universe_coverage
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
    result.metrics["backtest_assessment"] = assessment
    result.metrics["data_facts"] = {
        "current_listing_rows": len(current),
        "current_listing_date_range": current_date_range,
        "delisting_records": len(delistings),
        "delisted_securities": len(securities),
        "delisting_date_range": delisting_date_range,
        "price_rows": len(prices),
        "price_symbols": sorted(price_summary["symbols"]),
        "price_date_range": price_summary["date_range"],
        "symbol_change_records": len(symbol_changes),
        "name_change_records": len(name_changes),
        "membership_snapshot_count": membership["snapshot_count"],
        "membership_snapshot_dates": membership_dates,
        "membership_constituent_rows": membership["constituent_rows"],
        "membership_symbol_count": membership["distinct_symbols"],
    }

    # ---------------------------------------------------------------- findings
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
        "membership_not_interpolated_between_snapshots",
        "price_history_not_used_to_infer_index_membership",
        "symbol_equality_not_used_as_identity_without_isin_confirmation",
    ]
    unverifiable: list[str] = [
        (
            "Whether a specific backtest included or excluded any delisted "
            "security is unverifiable without that backtest's configuration "
            "and universe-selection inputs."
        ),
        (
            "Historical index membership on dates without a dated membership "
            "snapshot cannot be verified from the collected data."
        ),
        (
            "The return impact (magnitude) of survivorship bias cannot be "
            "computed from coverage data; see the bias_impact section of the "
            "backtest assessment for the inputs that would be required."
        ),
    ]

    if current_table is not None:
        snapshot_message = (
            "The current listing reference is a present-day snapshot: "
            f"{len(current)} row(s), "
            f"{len({record.symbol for record in current if record.symbol})} "
            "distinct symbol(s). It records listing dates but not historical "
            "universe or index membership, so it is not used as a point-in-time "
            "universe."
        )
        findings.warn(
            "survivorship.current_listing_snapshot_not_point_in_time",
            snapshot_message,
            KIND_LIMITATION,
            sources=(
                [relative(current_table.path, root)]
                if current_table is not None
                else []
            ),
            counts={
                "rows": len(current),
                "distinct_symbols": len(
                    {record.symbol for record in current if record.symbol}
                ),
            },
            remediation=(
                "Supply dated point-in-time membership snapshots to evaluate "
                "universe membership for a historical period."
            ),
        )

    if membership["snapshot_count"]:
        index_message = (
            "Point-in-time index-membership coverage is sparse: "
            f"{membership['snapshot_count']} dated snapshot(s) between "
            f"{membership['date_range']['start']} and "
            f"{membership['date_range']['end']} "
            f"({', '.join(sorted(membership['indexes']))}). Membership on every "
            "other date, including between snapshots, is unverified and is "
            "never interpolated; the project's NSE Indices monthly archive "
            "begins in September 2013. Current listings and delisting records "
            "are not treated as index membership."
        )
        limitations.append(
            "Membership is verified only on the exact snapshot dates; the "
            "intervals between snapshots are unverified and are not "
            "interpolated."
        )
    else:
        index_message = (
            "Point-in-time index-membership coverage is limited: no dated "
            "membership snapshot is present in the supplied data, and the "
            "project's NSE Indices monthly archive begins in September 2013. "
            "Current listings and delisting records are not treated as index "
            "membership."
        )
    findings.warn(
        "survivorship.index_membership_coverage_gap",
        index_message,
        KIND_LIMITATION,
        dates={
            "coverage_start": membership["coverage_start_date"],
            "snapshot_range": membership["date_range"],
        },
        counts={
            "membership_snapshots": membership["snapshot_count"],
            "membership_symbols": membership["distinct_symbols"],
        },
        evidence={
            "documented_in": membership["documented_in"],
            "interpolation_performed": False,
        },
        remediation=(
            "Add a dated point-in-time constituent membership series covering "
            "the required period; see the required_additional_source field of "
            "the index_membership metrics."
        ),
    )

    if listing_delisting_table is not None and delisted_coverage["unmatched"]:
        unmatched_count = delisted_coverage["unmatched"]
        security_count = delisted_coverage["delisted_securities"]
        limitation_text = (
            f"{unmatched_count} of {security_count} delisted security(ies) "
            "have no matching price symbol. This is a coverage limitation, not "
            "proof that a backtest excluded those securities."
        )
        limitations.append(limitation_text)
        findings.warn(
            "survivorship.delisted_price_coverage_gap",
            (
                f"{unmatched_count} of {security_count} delisted "
                "security(ies) have no direct, ISIN, or symbol-change price "
                "match. Missing delisted price history is a coverage "
                "limitation; it is not evidence that a backtest excluded "
                "those stocks."
            ),
            KIND_LIMITATION,
            sources=[relative(listing_delisting_table.path, root)],
            counts=delisted_coverage["match_classes"],
            denominators={
                "delisted_securities": security_count,
                "basis": "distinct delisted securities grouped by ISIN, then symbol",
            },
            remediation=(
                "Collect historical price files for the delisted symbols "
                "(symbol and ISIN per security, covering the period up to the "
                "delisting date)."
            ),
        )

    if identifier_reuse["overlap_count"]:
        risk_text = (
            f"{identifier_reuse['overlap_count']} delisted identifier(s) also "
            "appear in the current listing snapshot."
        )
        risks.append(risk_text)
        findings.warn(
            "survivorship.relisted_or_reused_identifier",
            (
                f"{identifier_reuse['overlap_count']} delisted identifier(s) "
                "also appear in the current listing snapshot "
                f"(symbol and ISIN: {identifier_reuse['symbol_and_isin_overlaps']}, "
                f"symbol only: {identifier_reuse['symbol_only_overlaps']}, "
                f"ISIN only: {identifier_reuse['isin_only_overlaps']}). "
                "This is relisting or identifier-reuse evidence only; the "
                "identifiers are not assumed to prove the same company."
            ),
            KIND_RISK,
            counts={
                "overlap_count": identifier_reuse["overlap_count"],
                "symbol_and_isin": identifier_reuse["symbol_and_isin_overlaps"],
                "symbol_only": identifier_reuse["symbol_only_overlaps"],
                "isin_only": identifier_reuse["isin_only_overlaps"],
            },
            evidence={"examples": identifier_reuse["examples"][:2]},
        )

    if reused_symbols:
        risks.append(
            f"{len(reused_symbols)} delisting symbol(s) occur in more than one "
            "security identity."
        )
        findings.warn(
            "survivorship.reused_symbol_in_delisting_history",
            (
                f"{len(reused_symbols)} delisting symbol(s) are associated with "
                "more than one security identity (for example, different ISINs). "
                "Symbol equality alone is not treated as company identity."
            ),
            KIND_RISK,
            counts={"reused_symbols": len(reused_symbols)},
            evidence={"examples": sorted(reused_symbols)[:MAX_EXAMPLES]},
        )

    if shared_new_symbols or symbol_metrics["multi_target_old_symbols"]:
        shared_count = len(shared_new_symbols)
        multi_count = len(symbol_metrics["multi_target_old_symbols"])
        risks.append(
            f"{shared_count} new symbol(s) are shared by multiple old symbols "
            f"and {multi_count} old symbol(s) map to multiple new symbols in "
            "the change history."
        )
        findings.warn(
            "survivorship.ambiguous_symbol_change",
            (
                f"{shared_count} new symbol(s) are targets of multiple old "
                f"symbols and {multi_count} old symbol(s) map to multiple new "
                "symbols in the symbol-change history. Symbol-change chains "
                "are used only as coverage candidates, not identity proof; the "
                "conflicting mappings remain unresolved."
            ),
            KIND_RISK,
            counts={
                "shared_new_symbols": shared_count,
                "multi_target_old_symbols": multi_count,
                "unresolved_mapping_count": symbol_metrics["unresolved_mapping_count"],
            },
            evidence={
                "shared_new_symbols": dict(
                    list(shared_new_symbols.items())[:MAX_EXAMPLES]
                ),
                "multi_target_old_symbols": dict(
                    list(symbol_metrics["multi_target_old_symbols"].items())[
                        :MAX_EXAMPLES
                    ]
                ),
            },
        )

    if continuity:
        risks.append(
            f"{len(continuity)} identifier(s) have symbol/name continuity "
            "evidence that requires review."
        )

    if universe_coverage["status"] == "ok":
        counts = universe_coverage["counts"]
        without_complete = universe_coverage["denominator"] - counts["complete"]
        if without_complete:
            risk_text = (
                f"{without_complete} of {universe_coverage['denominator']} "
                "historical-universe member(s) do not have complete price "
                "coverage in the collected price data."
            )
            risks.append(risk_text)
            findings.warn(
                "survivorship.universe_price_coverage_gap",
                (
                    f"{without_complete} of {universe_coverage['denominator']} "
                    "historical-universe member(s) lack complete price "
                    "coverage (complete: "
                    f"{counts['complete']}, partial: {counts['partial']}, "
                    f"missing: {counts['missing']}, ambiguous: "
                    f"{counts['ambiguous']}; denominator "
                    f"{universe_coverage['denominator']} distinct universe "
                    f"symbols over {universe_coverage['observed_trading_days']} "
                    "priced trading day(s)). This is a coverage limitation of "
                    "the collected data, not evidence that a backtest excluded "
                    "those securities."
                ),
                KIND_RISK,
                counts=counts,
                denominators={
                    "universe_symbols": universe_coverage["denominator"],
                    "observed_trading_days": universe_coverage["observed_trading_days"],
                },
                evidence={
                    "missing_examples": universe_coverage["missing_examples"],
                },
                remediation=(
                    "Collect price history for the missing universe members "
                    "over the backtest period; do not drop members silently."
                ),
            )

    if not listing_delisting_table:
        limitations.append(
            "No delisting history was available, so delisted-security price "
            "coverage could not be measured."
        )
    if not price_table_list:
        limitations.append(
            "No price history was available, so price coverage could not be measured."
        )

    # ------------------------------------------------- backtest-specific issues
    if backtest is not None:
        if assessment["status"] == "invalid":
            findings.warn(
                "survivorship.backtest_config_invalid",
                (
                    "The backtest configuration is invalid: "
                    + "; ".join(assessment["errors"])
                ),
                KIND_BACKTEST,
                evidence={"errors": assessment["errors"]},
                remediation=(
                    "Correct the backtest inputs (interval, dates, and "
                    "identifier mappings) and rerun."
                ),
            )
        else:
            unavailable_checks = [
                check
                for check in assessment["checks"]
                if check["status"] == "unavailable"
            ]
            if unavailable_checks:
                summary_text = "; ".join(
                    f"{check['check']}: {check.get('reason') or 'unavailable'}"
                    for check in unavailable_checks[:MAX_EXAMPLES]
                )
                findings.warn(
                    "survivorship.backtest_assessment_unavailable",
                    (
                        f"{len(unavailable_checks)} backtest check(s) could not "
                        f"be performed with the collected data: {summary_text}"
                    ),
                    KIND_BACKTEST,
                    evidence={
                        "checks": [
                            {
                                "check": check["check"],
                                "reason": check.get("reason"),
                            }
                            for check in unavailable_checks
                        ]
                    },
                    remediation=(
                        "Supply the missing membership or price sources "
                        "listed in the backtest assessment metrics."
                    ),
                )
            findings.warn(
                "survivorship.backtest_bias_impact_unavailable",
                (
                    "Survivorship-bias return impact was not quantified: "
                    + assessment["bias_impact"]["reason"]
                ),
                KIND_BACKTEST,
                evidence={
                    "missing_inputs": assessment["bias_impact"]["missing_inputs"]
                },
            )

    if not result.issues or all(
        issue.severity.value == "warning" for issue in result.issues
    ):
        checks.append("all_checked_inputs_were_read_without_validation_errors")

    # ------------------------------------------------------ structured findings
    findings.add(
        "survivorship.data_facts",
        (
            "Counts and date ranges of every input actually read by the "
            "analysis (confirmed from the data, not estimated)."
        ),
        KIND_FACT,
        counts=result.metrics["data_facts"],
        dates={
            "current_listing_date_range": current_date_range,
            "delisting_date_range": delisting_date_range,
            "price_date_range": price_summary["date_range"],
            "membership_snapshot_range": membership["date_range"],
        },
    )
    findings.add(
        "survivorship.price_coverage_facts",
        (
            f"The collected price data covers {price_summary['symbol_count']} "
            "symbol(s) over the reported date range, computed from actual "
            "dated rows."
        ),
        KIND_FACT,
        counts={
            "rows": price_summary["rows"],
            "symbols": price_summary["symbol_count"],
        },
        dates=price_summary["date_range"],
    )
    findings.add(
        "survivorship.delisted_match_facts",
        (
            "Delisted securities were matched to price history under the "
            "documented classification rules; unmatched securities are a data "
            "gap, not a backtest property."
        ),
        KIND_FACT,
        counts=delisted_coverage["match_classes"],
        denominators={
            "delisted_securities": delisted_coverage["delisted_securities"],
            "basis": "distinct delisted securities grouped by ISIN, then symbol",
        },
        match_classification={
            "classes": list(MATCH_CLASSES),
            "rules": delisted_coverage["match_class_rules"],
        },
    )
    findings.add(
        "survivorship.membership_snapshot_facts",
        (
            f"{membership['snapshot_count']} dated membership snapshot(s) were "
            "read from "
            f"{membership['snapshot_source']}; membership is reported only for "
            "their exact dates."
        ),
        KIND_FACT,
        counts={
            "snapshots": membership["snapshot_count"],
            "constituent_rows": membership["constituent_rows"],
            "distinct_symbols": membership["distinct_symbols"],
        },
        dates=membership["date_range"],
        evidence={
            "indexes": sorted(membership["indexes"]),
            "gaps": membership["gaps"][:MAX_EXAMPLES],
            "interpolation_performed": False,
        },
    )
    for check in sorted(set(checks)):
        findings.add(
            "survivorship.check_passed",
            check,
            KIND_CHECK,
            evidence={"check": check},
        )
    for limitation in limitations:
        findings.add(
            "survivorship.coverage_limitation",
            limitation,
            KIND_LIMITATION,
        )
    for risk in risks:
        findings.add(
            "survivorship.potential_survivorship_risk",
            risk,
            KIND_RISK,
        )
    for conclusion in unverifiable:
        findings.add(
            "survivorship.unverifiable_conclusion",
            conclusion,
            KIND_UNVERIFIABLE,
            remediation=(
                "Supply the missing inputs named in the conclusion to make "
                "the statement verifiable."
            ),
        )

    if backtest is None:
        backtest_results: dict[str, Any] = {
            "status": "unavailable",
            "reason": NO_BACKTEST_REASON,
            "how_to_enable": (
                "Pass a BacktestConfig to survivorship.analyze (or use the "
                "--backtest-index/--backtest-start/--backtest-end CLI flags)."
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
                for check in assessment["checks"]
            ],
            "bias_impact": assessment["bias_impact"]["status"],
        }

    result.metrics["findings"] = {
        "confirmed_data_facts": result.metrics["data_facts"],
        "potential_survivorship_risks": risks,
        "coverage_limitations": limitations,
        "checks_passed": checks,
        "unverifiable_conclusions": unverifiable,
        "backtest_specific_results": backtest_results,
        "detailed_findings": findings.entries,
    }
    return result
