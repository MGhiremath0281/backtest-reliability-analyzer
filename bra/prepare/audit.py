"""Cross-dataset audit and documentation rendering.

The audit combines the raw-source inventory with the transformation metadata.
It deliberately separates facts about the source files from facts about the
derived outputs, and it records what the data cannot support as clearly as what
it can.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from ..csv_io import read_csv
from ..parsing import clean
from .common import TransformResult, sha256_file
from .inventory import build_inventory


def _transform_map(transforms: list[TransformResult]) -> dict[str, TransformResult]:
    return {transform.name: transform for transform in transforms}


def _price_dates(prices: TransformResult) -> dict[str, set[str]]:
    dates: dict[str, set[str]] = defaultdict(set)
    for row in prices.rows:
        if row.get("series", "").upper() == "EQ" and row.get("trade_date"):
            dates[row["symbol"]].add(row["trade_date"])
    return dates


def _cross_dataset(
    root: Path,
    transforms: list[TransformResult],
) -> dict[str, Any]:
    mapped = _transform_map(transforms)
    prices = mapped["prices"]
    corporate_actions = mapped["corporate_actions"]
    legacy = mapped["financial_results_legacy"]
    integrated = mapped["financial_results_integrated"]
    current_listings = mapped["current_listings"]
    name_changes = mapped["name_changes"]
    symbol_changes = mapped["symbol_changes"]
    delistings = mapped["delistings"]

    price_dates = _price_dates(prices)
    price_symbols = sorted(price_dates)

    name_by_symbol: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in name_changes.rows:
        name_by_symbol[row["symbol"]].append(row)

    symbol_references: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in symbol_changes.rows:
        for symbol in (row["old_symbol"], row["new_symbol"]):
            if symbol:
                symbol_references[symbol].append(row)

    delisting_by_symbol: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in delistings.rows:
        delisting_by_symbol[row["symbol"]].append(row)

    price_symbol_cross_reference = {}
    for symbol in price_symbols:
        price_symbol_cross_reference[symbol] = {
            "name_changes": len(name_by_symbol.get(symbol, [])),
            "symbol_change_records": len(symbol_references.get(symbol, [])),
            "delisting_records": len(delisting_by_symbol.get(symbol, [])),
        }

    action_rows_by_symbol: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in corporate_actions.rows:
        action_rows_by_symbol[row["symbol"]].append(row)
    action_date_coverage: dict[str, Any] = {}
    for symbol in sorted(action_rows_by_symbol):
        known = price_dates.get(symbol, set())
        ex_dates = [row["ex_date"] for row in action_rows_by_symbol[symbol] if row["ex_date"]]
        missing = sorted({value for value in ex_dates if value not in known})
        action_date_coverage[symbol] = {
            "corporate_actions": len(action_rows_by_symbol[symbol]),
            "ex_dates": len(set(ex_dates)),
            "ex_dates_without_eq_price_date": missing,
        }

    legacy_keys = {
        (row["symbol"], row["period_end_date"], row["consolidated_non_consolidated"])
        for row in legacy.rows
    }
    integrated_keys = {
        (row["symbol"], row["quarter_end_date"], row["consolidated_standalone"])
        for row in integrated.rows
    }
    financial_overlap = sorted(
        {
            (symbol, period)
            for symbol, period, _ in legacy_keys & integrated_keys
        }
    )

    primary_delistings = {
        (row["symbol"], row["delisted_date"]) for row in delistings.rows
    }
    processed_delistings: dict[str, Any] = {}
    for filename in (
        "delisted_companies_2021-2026.csv",
        "main_board_delistings_2021-2026.csv",
    ):
        path = root / "processed" / filename
        if not path.is_file():
            processed_delistings[filename] = {"present": False}
            continue
        table = read_csv(path)
        records = {
            (clean(row.get("Symbol")), clean(row.get("Delisted Date")))
            for row in table.rows
        }
        missing_from_workbook = sorted(records - primary_delistings)
        processed_delistings[filename] = {
            "present": True,
            "rows": len(table.rows),
            "covered_by_primary_workbook_sheet": len(records & primary_delistings),
            "not_in_primary_workbook_sheet": [
                {"symbol": symbol, "delisted_date": value}
                for symbol, value in missing_from_workbook
            ],
        }

    listing_cross_references = current_listings.details.get(
        "delisting_cross_references", []
    )
    relisted = []
    for reference in listing_cross_references:
        matches = reference.get("matched_delistings", [])
        relisted.append(
            {
                **reference,
                "delisting_dates": sorted(
                    {
                        match["delisted_date"]
                        for match in matches
                        if match.get("delisted_date")
                    }
                ),
                "interpretation": (
                    "The symbol/ISIN appears in both the current snapshot and "
                    "the delisting history. Treat the identifier as "
                    "time-dependent; this is not silently repaired."
                ),
            }
        )

    return {
        "price_symbols": price_symbols,
        "price_symbol_cross_reference": price_symbol_cross_reference,
        "corporate_action_ex_date_coverage": action_date_coverage,
        "financial_period_overlap": [
            {"symbol": symbol, "period_end_date": period}
            for symbol, period in financial_overlap
        ],
        "delisting_workbook_vs_processed": processed_delistings,
        "current_listing_relisting_candidates": relisted,
        "auxiliary_delisting_sheets": delistings.details.get("auxiliary_sheets", []),
        "name_change_duplicate_groups": {
            "groups": name_changes.details.get("exact_duplicate_group_count", 0),
            "extra_records": name_changes.details.get(
                "exact_duplicate_extra_records", 0
            ),
            "overlapping_variant_groups": len(
                name_changes.details.get("overlapping_variant_groups", [])
            ),
            "shared_event_groups": len(
                name_changes.details.get("shared_event_groups", [])
            ),
            "decisions": name_changes.details.get("decisions", []),
        },
        "symbol_change_ambiguities": {
            "repeated_company_date_groups": len(
                symbol_changes.details.get("repeated_company_date_groups", [])
            ),
            "shared_new_symbols": symbol_changes.details.get("shared_new_symbols", {}),
            "noop_changes": symbol_changes.details.get("noop_changes", 0),
        },
    }


def _assessments(cross: dict[str, Any], transforms: list[TransformResult]) -> dict[str, Any]:
    mapped = _transform_map(transforms)
    current_rows = len(mapped["current_listings"].rows)
    delisting_rows = len(mapped["delistings"].rows)
    price_symbols = cross["price_symbols"]
    ex_date_findings = cross["corporate_action_ex_date_coverage"]
    missing_ex_dates = sum(
        len(item["ex_dates_without_eq_price_date"])
        for item in ex_date_findings.values()
    )

    return {
        "A_survivorship_bias": {
            "verdict": "not_supported_by_current_data",
            "answer": (
                "The data cannot support a survivorship-bias analysis. The "
                "current listing file is a present-day snapshot, not a "
                "historical constituent universe."
            ),
            "evidence": [
                f"Current listing snapshot rows: {current_rows}.",
                f"Full-history delisting sheet rows: {delisting_rows}.",
                (
                    "No historical index membership, historical listed-universe "
                    "snapshot, or delisted-security price history is present."
                ),
                (
                    "Price history covers only "
                    f"{len(price_symbols)} symbols: {', '.join(price_symbols)}."
                ),
            ],
            "limitations": [
                "A current snapshot excludes companies that left the market.",
                "The delisting history records events but does not provide returns after delisting.",
                "No announcement, suspension, or index-reconstitution history is available.",
            ],
            "next_steps": [
                "Collect point-in-time index constituents or historical listing snapshots.",
                "Collect delisted-security prices and delisting returns.",
                "Define the intended universe and measurement window before computing bias.",
            ],
        },
        "B_look_ahead_bias": {
            "verdict": "partially_supported_for_event_timing_only",
            "answer": (
                "The data supports checking when financial results and corporate "
                "actions became available, but it is not sufficient for a full "
                "look-ahead-bias analysis."
            ),
            "evidence": [
                "Financial exports retain exchange receipt and dissemination timestamps.",
                "Publication-lag days are computed from the reporting period and dissemination time.",
                "Corporate actions retain ex-dates; no announcement or publication time is present.",
                "Name/symbol changes retain effective dates, not announcement timestamps.",
                "The current listing snapshot is not a point-in-time universe.",
            ],
            "limitations": [
                "Price rows contain no information-availability timestamp.",
                "Effective dates are not publication timestamps.",
                "Historical universe membership is unavailable, so universe-based look-ahead cannot be tested.",
                "No intraday release-time model or exchange calendar is included.",
            ],
            "next_steps": [
                "Collect announcement timestamps for corporate actions and name/symbol changes.",
                "Collect point-in-time universe membership.",
                "Define the exact signal-availability rule for each event type.",
            ],
        },
        "C_corporate_actions": {
            "verdict": "event_dates_supported_adjustments_not_verifiable",
            "answer": (
                "Corporate-action events and ex-dates are present, but adjusted "
                "prices, adjustment factors, and an adjustment methodology are "
                "absent. Adjustment correctness cannot be verified."
            ),
            "evidence": [
                f"Corporate-action rows: {len(mapped['corporate_actions'].rows)}.",
                (
                    "All corporate-action ex-dates match an EQ trading date in "
                    "the collected price history."
                    if missing_ex_dates == 0
                    else f"{missing_ex_dates} ex-date(s) lack an EQ price date."
                ),
                (
                    "PURPOSE text is preserved verbatim; action ratios are not "
                    "parsed into structured factors."
                ),
            ],
            "limitations": [
                "No adjusted price series or adjustment-factor file is present.",
                "No split/bonus ratio fields exist; ratios appear only in free text.",
                "No dividend amount fields exist beyond the purpose text.",
                "Matching an ex-date to a trading date does not verify an adjustment.",
            ],
            "next_steps": [
                "Collect or compute adjustment factors with a documented method.",
                "Add adjusted-price columns as derived data, never as raw replacements.",
                "Test adjusted returns around each ex-date after factors are available.",
            ],
        },
    }


def _unresolved_issues(
    cross: dict[str, Any],
    transforms: list[TransformResult],
) -> list[dict[str, Any]]:
    mapped = _transform_map(transforms)
    issues: list[dict[str, Any]] = []

    duplicate_summary = cross["name_change_duplicate_groups"]
    if duplicate_summary["groups"]:
        issues.append(
            {
                "id": "raw_name_change_duplicates",
                "severity": "critical_raw_review",
                "summary": (
                    f"{duplicate_summary['groups']} exact name-change duplicate "
                    f"groups ({duplicate_summary['extra_records']} extra source "
                    "records) remain in the raw file."
                ),
                "handling": (
                    "Retained in raw data; collapsed only in the derived event "
                    "dataset with every source line recorded."
                ),
            }
        )
    if duplicate_summary["overlapping_variant_groups"]:
        issues.append(
            {
                "id": "name_change_spelling_variants",
                "severity": "review",
                "summary": (
                    f"{duplicate_summary['overlapping_variant_groups']} same-symbol/"
                    "same-date name-change groups have different spellings."
                ),
                "handling": "All variants retained and flagged; no spelling chosen.",
            }
        )
    if duplicate_summary["shared_event_groups"]:
        issues.append(
            {
                "id": "name_change_shared_events",
                "severity": "review",
                "summary": (
                    f"{duplicate_summary['shared_event_groups']} name-change events "
                    "appear under more than one symbol."
                ),
                "handling": "All records retained and flagged as shared events.",
            }
        )

    for sheet in cross["auxiliary_delisting_sheets"]:
        if sheet["conflict_rows"]:
            issues.append(
                {
                    "id": "delisting_auxiliary_conflict",
                    "severity": "review",
                    "summary": (
                        f"{sheet['sheet']} has "
                        f"{len(sheet['conflict_rows'])} date conflict(s) with the "
                        "primary sheet."
                    ),
                    "handling": (
                        "Primary sheet retained; auxiliary row not merged; affected "
                        "primary rows flagged."
                    ),
                    "conflicts": sheet["conflict_rows"],
                }
            )

    for filename, summary in cross["delisting_workbook_vs_processed"].items():
        if summary.get("not_in_primary_workbook_sheet"):
            issues.append(
                {
                    "id": "processed_delisting_not_in_workbook",
                    "severity": "critical_review",
                    "summary": (
                        f"{filename} has "
                        f"{len(summary['not_in_primary_workbook_sheet'])} row(s) "
                        "not found in the workbook primary sheet."
                    ),
                    "handling": "Existing processed file was not modified.",
                }
            )

    for row in mapped["delistings"].rows:
        if "malformed_isin" in row.get("review_flags", ""):
            issues.append(
                {
                    "id": "malformed_delisting_isin",
                    "severity": "review",
                    "summary": (
                        f"Delisting row {row['symbol']} has ISIN "
                        f"{row['isin']!r}, which is not well-formed."
                    ),
                    "handling": "Value preserved verbatim and flagged.",
                }
            )

    for candidate in cross["current_listing_relisting_candidates"]:
        matches = candidate.get("matched_delistings", [])
        match_text = ", ".join(
            f"{match['symbol']} on {match['delisted_date'] or 'unknown date'}"
            for match in matches
        )
        issues.append(
            {
                "id": "relisted_or_reused_identifier",
                "severity": "review",
                "summary": (
                    f"{candidate['symbol']} appears in the current snapshot and "
                    "in the delisting history"
                    + (f" ({match_text})." if match_text else ".")
                ),
                "handling": (
                    "Retained in both datasets and flagged as a time-dependent "
                    "identifier."
                ),
            }
        )

    symbol_summary = cross["symbol_change_ambiguities"]
    if symbol_summary["noop_changes"]:
        issues.append(
            {
                "id": "symbol_change_noops",
                "severity": "review",
                "summary": (
                    f"{symbol_summary['noop_changes']} symbol-change row(s) have "
                    "identical old and new symbols."
                ),
                "handling": "Retained and flagged.",
            }
        )
    if symbol_summary["shared_new_symbols"]:
        issues.append(
            {
                "id": "shared_new_symbols",
                "severity": "review",
                "summary": (
                    f"{len(symbol_summary['shared_new_symbols'])} new symbol(s) "
                    "are targeted by changes from more than one old symbol."
                ),
                "handling": "All rows retained and flagged; no canonical mapping inferred.",
            }
        )

    return issues


def build_audit(
    root: Path,
    transforms: list[TransformResult],
    *,
    output_paths: dict[str, Path],
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Build the complete machine-readable audit object."""

    derived_dir = output_dir or (root / "processed" / "normalized")
    inventory = build_inventory(
        root,
        exclude_directories=[derived_dir],
    )
    derived_inventory = (
        build_inventory(derived_dir)
        if derived_dir.is_dir()
        else {"file_count": 0, "files": []}
    )

    cross = _cross_dataset(root, transforms)
    output_metadata = {}
    for transform in transforms:
        path = output_paths[transform.name]
        output_metadata[transform.name] = {
            "path": path.relative_to(root).as_posix()
            if path.is_relative_to(root)
            else str(path),
            "filename": transform.filename,
            "headers": list(transform.headers),
            "sources": [str(source) for source in transform.sources],
            "input_records": transform.input_records,
            "output_records": transform.output_records,
            "column_map": transform.column_map,
            "rules": transform.rules,
            "counts": dict(sorted(transform.counts.items())),
            "details": transform.details,
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
        }

    source_files = [
        {
            "path": item["path"],
            "format": item["format"],
            "sha256": item.get("sha256"),
            "size_bytes": item.get("size_bytes"),
        }
        for item in inventory["files"]
    ]

    return {
        "schema_version": 1,
        "tool": "backtest-reliability-analyzer",
        "data_root": str(root),
        "scope": (
            "Audit of collected source files and reproducible normalized outputs. "
            "Raw files are never modified."
        ),
        "source_inventory": inventory,
        "derived_inventory": derived_inventory,
        "transformations": output_metadata,
        "cross_dataset": cross,
        "assessments": _assessments(cross, transforms),
        "unresolved_issues": _unresolved_issues(cross, transforms),
        "source_hashes": source_files,
        "reproduce": [
            "python -m bra.prepare",
            "python -m bra",
            "python -m pytest -q",
        ],
    }


def _fmt(value: Any) -> str:
    if value is None or value == "":
        return "—"
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("|", "\\|")
        .replace("\r", "\\r")
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )


def _coverage(item: dict[str, Any]) -> str:
    dates = item.get("date_columns", {})
    for details in dates.values():
        if details.get("start"):
            return f"{details['start']} to {details['end']}"
    timestamps = item.get("timestamp_columns", {})
    for details in timestamps.values():
        if details.get("start"):
            return f"{details['start']} to {details['end']}"
    return "—"


def render_markdown(audit: dict[str, Any]) -> str:
    """Render a tracked, human-readable audit document."""

    lines: list[str] = []
    add = lines.append
    add("# Data audit")
    add("")
    add(
        "This document is generated by `python -m bra.prepare` from the collected "
        "source files. Raw files are read-only; normalized outputs are written "
        "under `data/processed/normalized/`."
    )
    add("")
    add("## Reproduce")
    add("")
    add("```bash")
    for command in audit["reproduce"]:
        add(command)
    add("```")
    add("")
    add("No timestamps are written into the audit. Repeated runs with the same "
        "arguments over unchanged inputs produce identical output.")
    add("")

    add("## Source inventory")
    add("")
    add("| File | Format | Rows | Date coverage | Exact duplicate extras | Notes |")
    add("|---|---|---:|---|---:|---|")
    for item in audit["source_inventory"]["files"]:
        if item["format"] == "csv":
            notes = []
            missing = sum(
                details["missing"] for details in item["identifiers"].values()
            )
            if missing:
                notes.append(f"{missing} missing identifier value(s)")
            malformed = sum(
                details.get("malformed", 0) for details in item["identifiers"].values()
            )
            if malformed:
                notes.append(f"{malformed} malformed ISIN(s)")
            if item["exact_duplicate_extra_records"]:
                notes.append(
                    f"{item['exact_duplicate_groups']} duplicate group(s)"
                )
            for issue in item["issues"]:
                if issue["severity"] == "error":
                    notes.append(issue["code"])
            add(
                f"| `{_fmt(item['path'])}` | csv | {item['row_count']} | "
                f"{_fmt(_coverage(item))} | {item['exact_duplicate_extra_records']} | "
                f"{_fmt('; '.join(notes))} |"
            )
        else:
            if not item.get("readable"):
                add(
                    f"| `{_fmt(item['path'])}` | xlsx | — | — | — | "
                    f"{_fmt(item.get('error'))} |"
                )
                continue
            for sheet in item["sheets"]:
                notes = []
                missing = sum(
                    details["missing"] for details in sheet["identifiers"].values()
                )
                if missing:
                    notes.append(f"{missing} missing identifier value(s)")
                malformed = sum(
                    details.get("malformed", 0)
                    for details in sheet["identifiers"].values()
                )
                if malformed:
                    notes.append(f"{malformed} malformed ISIN(s)")
                if sheet["exact_duplicate_extra_records"]:
                    notes.append(
                        f"{sheet['exact_duplicate_groups']} duplicate group(s)"
                    )
                add(
                    f"| `{_fmt(item['path'])}` :: `{_fmt(sheet['name'])}` | xlsx | "
                    f"{sheet['row_count']} | {_fmt(_coverage(sheet))} | "
                    f"{sheet['exact_duplicate_extra_records']} | "
                    f"{_fmt('; '.join(notes))} |"
                )
    add("")

    inventory_files = audit["source_inventory"]["files"]
    csv_files = [item for item in inventory_files if item["format"] == "csv"]
    structural_errors = sum(
        1
        for item in csv_files
        for issue in item["issues"]
        if issue["severity"] == "error"
    )
    missing_identifiers = sum(
        details["missing"]
        for item in csv_files
        for details in item["identifiers"].values()
    )
    malformed_isins = sum(
        details.get("malformed", 0)
        for item in csv_files
        for details in item["identifiers"].values()
    )
    duplicate_extras = sum(
        item["exact_duplicate_extra_records"] for item in csv_files
    )
    add("### Completeness summary")
    add("")
    add(f"- CSV structural errors: **{structural_errors}**.")
    add(f"- Missing identifier values in CSVs: **{missing_identifiers}**.")
    add(f"- Malformed ISIN values in CSVs: **{malformed_isins}**.")
    add(
        f"- Exact duplicate extra CSV records: **{duplicate_extras}** "
        "(all are preserved; only exact name-change copies are collapsed in the "
        "derived event file)."
    )
    add(
        "- Per-year and per-entity counts are recorded for every file and "
        "workbook sheet in `reports/data_audit.json`."
    )
    add("")

    add("## Normalized outputs")
    add("")
    add("| Dataset | Output | Input rows | Output rows | SHA-256 (first 12) |")
    add("|---|---|---:|---:|---|")
    for name, item in sorted(audit["transformations"].items()):
        add(
            f"| {_fmt(name)} | `{_fmt(item['path'])}` | {item['input_records']} | "
            f"{item['output_records']} | `{item['sha256'][:12]}` |"
        )
    add("")
    add("### Transformation rules")
    add("")
    for name, item in sorted(audit["transformations"].items()):
        add(f"**{name}**")
        add("")
        for rule in item["rules"]:
            add(f"- {rule}")
        if item["column_map"]:
            add("")
            add("Column mapping:")
            add("")
            add("| Derived column | Source column |")
            add("|---|---|")
            for derived, source in item["column_map"].items():
                add(f"| `{_fmt(derived)}` | `{_fmt(source)}` |")
        add("")

    add("## Name-change duplicate investigation")
    add("")
    summary = audit["cross_dataset"]["name_change_duplicate_groups"]
    add(
        f"- Exact duplicate groups in the raw file: **{summary['groups']}** "
        f"({summary['extra_records']} extra records)."
    )
    add(
        f"- Same-symbol/date spelling-variant groups retained: "
        f"**{summary['overlapping_variant_groups']}**."
    )
    add(
        f"- Shared events across symbols retained: "
        f"**{summary['shared_event_groups']}**."
    )
    for decision in summary["decisions"]:
        add(f"- Decision: {decision}")
    add("")

    group_details = audit["transformations"]["name_changes"]["details"].get(
        "duplicate_groups", []
    )
    if group_details:
        size_counts = Counter(item["source_record_count"] for item in group_details)
        add("Group sizes (source records per duplicate group):")
        add("")
        add("| Records in group | Groups | Extra records after collapse |")
        add("|---:|---:|---:|")
        for size, count in sorted(size_counts.items()):
            add(f"| {size} | {count} | {(size - 1) * count} |")
        add("")
        add("Largest groups:")
        add("")
        add("| Symbol | Effective date | Source records | Raw exact |")
        add("|---|---|---:|---|")
        for item in sorted(
            group_details,
            key=lambda value: (-value["source_record_count"], value["key"]["symbol"]),
        )[:8]:
            key = item["key"]
            add(
                f"| {_fmt(key['symbol'])} | {_fmt(key['effective_date'])} | "
                f"{item['source_record_count']} | "
                f"{'yes' if item['raw_exact_across_all_columns'] else 'no'} |"
            )
        add("")

    add("## Cross-dataset findings")
    add("")
    add("### Price-symbol references")
    add("")
    add("| Symbol | Name changes | Symbol-change records | Delisting records |")
    add("|---|---:|---:|---:|")
    for symbol, item in sorted(
        audit["cross_dataset"]["price_symbol_cross_reference"].items()
    ):
        add(
            f"| {_fmt(symbol)} | {item['name_changes']} | "
            f"{item['symbol_change_records']} | {item['delisting_records']} |"
        )
    add("")
    add("### Corporate-action ex-dates versus EQ price dates")
    add("")
    add("| Symbol | Actions | Distinct ex-dates | Ex-dates without EQ price date |")
    add("|---|---:|---:|---|")
    for symbol, item in sorted(
        audit["cross_dataset"]["corporate_action_ex_date_coverage"].items()
    ):
        missing = ", ".join(item["ex_dates_without_eq_price_date"]) or "none"
        add(
            f"| {_fmt(symbol)} | {item['corporate_actions']} | "
            f"{item['ex_dates']} | {_fmt(missing)} |"
        )
    add("")
    add("### Processed delistings versus workbook primary sheet")
    add("")
    add("| Processed file | Rows | Covered by workbook | Missing from workbook |")
    add("|---|---:|---:|---|")
    for filename, item in sorted(
        audit["cross_dataset"]["delisting_workbook_vs_processed"].items()
    ):
        if not item.get("present"):
            add(f"| `{filename}` | — | — | file not present |")
            continue
        missing = item["not_in_primary_workbook_sheet"]
        add(
            f"| `{filename}` | {item['rows']} | "
            f"{item['covered_by_primary_workbook_sheet']} | "
            f"{_fmt(len(missing))} |"
        )
    add("")

    add("## Does the data support the three analyses?")
    add("")
    for key in (
        "A_survivorship_bias",
        "B_look_ahead_bias",
        "C_corporate_actions",
    ):
        assessment = audit["assessments"][key]
        add(f"### {key.replace('_', ' ')}")
        add("")
        add(f"**Verdict:** `{assessment['verdict']}`")
        add("")
        add(assessment["answer"])
        add("")
        add("Evidence:")
        add("")
        for item in assessment["evidence"]:
            add(f"- {item}")
        add("")
        add("Limitations:")
        add("")
        for item in assessment["limitations"]:
            add(f"- {item}")
        add("")
        add("Next steps:")
        add("")
        for item in assessment["next_steps"]:
            add(f"- {item}")
        add("")

    add("## Unresolved issues")
    add("")
    if not audit["unresolved_issues"]:
        add("No unresolved issues were recorded.")
    for issue in audit["unresolved_issues"]:
        add(f"- **{issue['id']}** ({issue['severity']}): {issue['summary']}")
        add(f"  Handling: {issue['handling']}")
    add("")

    add("## Next steps")
    add("")
    for item in (
        (
            "Decide whether raw name-change duplicates should be treated as a "
            "source defect or an accepted replication artifact; the derived "
            "events already collapse exact copies while preserving every source "
            "line."
        ),
        (
            "Collect point-in-time universe membership and delisted-security "
            "prices before attempting survivorship-bias measurement."
        ),
        (
            "Collect corporate-action announcement timestamps and adjustment "
            "factors before attempting look-ahead or adjustment verification."
        ),
        (
            "Resolve or accept the secondary-sheet delisting date conflict; the "
            "primary workbook sheet remains authoritative."
        ),
    ):
        add(f"- {item}")
    add("")
    return "\n".join(lines)


def write_audit(audit: dict[str, Any], json_path: Path, doc_path: Path) -> None:
    """Write the JSON audit and the tracked Markdown document."""

    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.write_text(render_markdown(audit), encoding="utf-8")
