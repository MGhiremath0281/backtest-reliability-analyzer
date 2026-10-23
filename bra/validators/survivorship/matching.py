"""Cross-dataset reconciliation: price coverage, matching, identifier risks.

Match classification rules (applied per grouped delisted security):

- ``confirmed`` — the delisted security's ISIN equals a current-listing ISIN,
  that listing's symbol has price rows, and at least one price row falls on or
  after the listing date. ISIN continuity plus a temporally consistent price
  history is the only confirmation this data can provide.
- ``candidate`` — exactly one price symbol is reachable by symbol equality or
  by an effective-dated symbol-change chain, without ISIN confirmation.
- ``ambiguous`` — different methods reach different symbols, several candidate
  symbols exist, or an ISIN-linked symbol's price rows all predate the
  (re)listing date (identity conflict).
- ``unmatched`` — no price symbol is reachable by any method.

Symbol equality alone is never treated as proof of identity.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from typing import Any

from ...parsing import format_date
from .core import (
    COVERAGE_AMBIGUOUS,
    COVERAGE_CLASSES,
    COVERAGE_COMPLETE,
    COVERAGE_MISSING,
    COVERAGE_PARTIAL,
    MATCH_AMBIGUOUS,
    MATCH_CANDIDATE,
    MATCH_CLASSES,
    MATCH_CONFIRMED,
    MATCH_UNMATCHED,
    MAX_EXAMPLES,
    CurrentListing,
    Delisting,
    PriceRecord,
    SymbolChange,
    security_key,
)

BASIS_DIRECT = "direct_symbol"
BASIS_ISIN = "isin_current_listing_symbol"
BASIS_ISIN_CONFLICT = "isin_symbol_date_conflict"
BASIS_ALIAS = "symbol_change_candidate"

MATCH_BASIS_RULES = {
    BASIS_DIRECT: (
        "The delisted symbol equals a price symbol. Symbol equality alone is "
        "not identity proof."
    ),
    BASIS_ISIN: (
        "The delisted ISIN equals a current-listing ISIN, that listing's "
        "symbol has price rows, and at least one price row falls on or after "
        "the listing date."
    ),
    BASIS_ISIN_CONFLICT: (
        "The delisted ISIN equals a current-listing ISIN whose symbol has "
        "price rows, but every price row predates the (re)listing date, so the "
        "rows cannot be attributed to that listing."
    ),
    BASIS_ALIAS: (
        "An effective-dated symbol-change record links the delisted symbol to "
        "a price symbol within the delisting date bound."
    ),
}


def price_metrics(
    prices: Sequence[PriceRecord],
    dates: Sequence[date],
) -> dict[str, Any]:
    """Summarise the price dataset from actual rows only."""

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


def price_dates_by_symbol(
    prices: Sequence[PriceRecord],
) -> dict[str, set[date]]:
    """Return the distinct trade dates present for each price symbol."""

    grouped: dict[str, set[date]] = defaultdict(set)
    for record in prices:
        grouped[record.symbol].add(record.trade_date)
    return dict(grouped)


def symbol_alias_candidates(
    symbols: Sequence[str],
    delisted_date: date | None,
    changes: Sequence[SymbolChange],
) -> dict[str, list[str]]:
    """Return cautious alias candidates reachable through symbol changes.

    The result is not an identity proof. It only says that a symbol-change
    record links the delisted symbol to another symbol that has price data.
    """

    forward: dict[str, list[SymbolChange]] = defaultdict(list)
    reverse: dict[str, list[SymbolChange]] = defaultdict(list)
    for change in changes:
        if not change.old_symbol or not change.new_symbol:
            continue
        forward[change.old_symbol].append(change)
        reverse[change.new_symbol].append(change)

    def allowed(change: SymbolChange) -> bool:
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


def security_groups(
    delistings: Sequence[Delisting],
) -> list[dict[str, Any]]:
    """Group delisting rows into securities by the strongest identifier."""

    grouped: dict[tuple[str, str], list[Delisting]] = defaultdict(list)
    for record in delistings:
        grouped[security_key(record)].append(record)

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


def example(security: dict[str, Any], **extra: Any) -> dict[str, Any]:
    """Build one bounded, deterministic example record for a security."""

    first: Delisting = security["first"]
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


def coverage_class(
    covered_days: int,
    observed_days: int,
    ambiguous: bool,
) -> str:
    """Classify price coverage of one security against observed trading days.

    ``observed_days`` is the number of distinct dated rows in the reference
    price data (the denominator). A security with no rows is ``missing``; a
    security whose rows cannot be attributed to it (conflicting identity
    evidence) is ``ambiguous``; otherwise complete or partial.
    """

    if covered_days <= 0:
        return COVERAGE_MISSING
    if ambiguous:
        return COVERAGE_AMBIGUOUS
    if covered_days >= observed_days:
        return COVERAGE_COMPLETE
    return COVERAGE_PARTIAL


def coverage_summary(
    members: Sequence[str],
    dates_by_symbol: Mapping[str, set[date]],
    observed_dates: Sequence[date],
    ambiguous_symbols: Mapping[str, Sequence[str]],
    observed_days: int | None = None,
) -> dict[str, Any]:
    """Summarise price coverage for a set of eligible securities.

    Denominator: ``len(members)``. Percentages are ``None`` while the
    denominator is zero; that is reported as ``unavailable`` rather than 0%.
    """

    observed_set = set(observed_dates)
    reference_days = len(observed_set) if observed_days is None else observed_days
    counts = {class_name: 0 for class_name in COVERAGE_CLASSES}
    missing_examples: list[dict[str, Any]] = []
    ambiguous_examples: list[dict[str, Any]] = []
    partial_examples: list[dict[str, Any]] = []
    covered_details: dict[str, Any] = {}

    for symbol in sorted(set(members)):
        covered_set = dates_by_symbol.get(symbol, set()) & observed_set
        covered_days = len(covered_set)
        reasons = list(ambiguous_symbols.get(symbol, ()))
        classification = coverage_class(covered_days, reference_days, bool(reasons))
        counts[classification] += 1

        detail: dict[str, Any] = {"classification": classification}
        if covered_days:
            span_start = min(covered_set)
            span_end = max(covered_set)
            in_span = {day for day in observed_set if span_start <= day <= span_end}
            covered_details[symbol] = {
                "classification": classification,
                "covered_days": covered_days,
                "observed_days": reference_days,
                "start": format_date(span_start),
                "end": format_date(span_end),
                "missing_days_within_span": len(in_span - covered_set),
            }
        entry = {"symbol": symbol, **detail}
        if covered_days:
            entry["covered_days"] = covered_days
            entry["observed_days"] = reference_days
        if classification == COVERAGE_MISSING:
            missing_examples.append(entry)
        elif classification == COVERAGE_AMBIGUOUS:
            entry["ambiguous_because"] = reasons
            ambiguous_examples.append(entry)
        elif classification == COVERAGE_PARTIAL:
            partial_examples.append(entry)

    denominator = len(set(members))
    percentages = (
        {
            class_name: round(100.0 * counts[class_name] / denominator, 1)
            for class_name in COVERAGE_CLASSES
        }
        if denominator
        else None
    )
    return {
        "status": "ok" if denominator else "unavailable",
        "denominator": denominator,
        "denominator_basis": "distinct eligible securities in the evaluated universe",
        "observed_trading_days": reference_days,
        "counts": counts,
        "percentages": percentages,
        "covered_symbols": covered_details,
        "missing_examples": missing_examples[:MAX_EXAMPLES],
        "partial_examples": partial_examples[:MAX_EXAMPLES],
        "ambiguous_examples": ambiguous_examples[:MAX_EXAMPLES],
        "examples_truncated": (
            len(missing_examples) > MAX_EXAMPLES
            or len(partial_examples) > MAX_EXAMPLES
            or len(ambiguous_examples) > MAX_EXAMPLES
        ),
    }


def _security_delisting_date(security: dict[str, Any]) -> date | None:
    if not security["delisted_dates"]:
        return None
    return date.fromisoformat(security["delisted_dates"][-1])


def classify_delisted_matches(
    securities: Sequence[dict[str, Any]],
    price_symbols: set[str],
    dates_by_symbol: Mapping[str, set[date]],
    observed_dates: Sequence[date],
    current: Sequence[CurrentListing],
    changes: Sequence[SymbolChange],
) -> tuple[dict[str, Any], dict[tuple[str, str], dict[str, Any]]]:
    """Classify every grouped delisted security against price history.

    Returns the ``delisted_price_coverage`` metrics and a lookup keyed by the
    security group key so later stages (backtest assessment, findings) can use
    the same classification.
    """

    current_by_isin: dict[str, list[CurrentListing]] = defaultdict(list)
    for record in current:
        if record.isin:
            current_by_isin[record.isin].append(record)

    counts = {class_name: 0 for class_name in MATCH_CLASSES}
    type_counts = {BASIS_DIRECT: 0, BASIS_ISIN: 0, BASIS_ALIAS: 0}
    classifications: dict[tuple[str, str], dict[str, Any]] = {}
    matched: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    reference_days = len(set(observed_dates))

    for security in securities:
        symbols = security["symbols"]
        direct = sorted(set(symbols) & price_symbols)

        confirmed_outcomes: set[str] = set()
        conflict_outcomes: set[str] = set()
        isin_evidence: list[dict[str, Any]] = []
        for isin in security["isins"]:
            for record in current_by_isin.get(isin, ()):
                if not record.symbol or record.symbol not in price_symbols:
                    continue
                rows = dates_by_symbol.get(record.symbol, set())
                if record.listing_date is None or any(
                    day >= record.listing_date for day in rows
                ):
                    confirmed_outcomes.add(record.symbol)
                    isin_evidence.append(
                        {
                            "isin": isin,
                            "current_symbol": record.symbol,
                            "listing_date": format_date(record.listing_date),
                            "price_rows_on_or_after_listing": record.listing_date
                            is not None,
                        }
                    )
                else:
                    conflict_outcomes.add(record.symbol)
                    isin_evidence.append(
                        {
                            "isin": isin,
                            "current_symbol": record.symbol,
                            "listing_date": format_date(record.listing_date),
                            "price_rows_on_or_after_listing": False,
                        }
                    )

        aliases = symbol_alias_candidates(
            symbols, _security_delisting_date(security), changes
        )
        alias_hits = sorted(set(aliases) & price_symbols)

        outcomes: dict[str, set[str]] = {}
        for symbol in direct:
            outcomes.setdefault(symbol, set()).add(BASIS_DIRECT)
        for symbol in confirmed_outcomes:
            outcomes.setdefault(symbol, set()).add(BASIS_ISIN)
        for symbol in conflict_outcomes:
            outcomes.setdefault(symbol, set()).add(BASIS_ISIN_CONFLICT)
        for symbol in alias_hits:
            outcomes.setdefault(symbol, set()).add(BASIS_ALIAS)

        outcome_symbols = sorted(outcomes)
        if not outcome_symbols:
            match_class = MATCH_UNMATCHED
            matched_symbol: str | None = None
            match_type: str | None = None
        else:
            conflict_only = any(
                BASIS_ISIN_CONFLICT in bases for bases in outcomes.values()
            )
            if confirmed_outcomes and all(
                symbol in confirmed_outcomes for symbol in outcome_symbols
            ):
                match_class = MATCH_CONFIRMED
            elif outcome_symbols and len(outcome_symbols) == 1 and not conflict_only:
                match_class = MATCH_CANDIDATE
            else:
                match_class = MATCH_AMBIGUOUS
            matched_symbol = outcome_symbols[0]
            if direct:
                match_type = BASIS_DIRECT
            elif any(symbol in confirmed_outcomes for symbol in outcome_symbols) or any(
                BASIS_ISIN_CONFLICT in outcomes[symbol] for symbol in outcome_symbols
            ):
                match_type = BASIS_ISIN
            else:
                match_type = BASIS_ALIAS

        key = (str(security["key"][0]), str(security["key"][1]))
        identity_confirmed = match_class == MATCH_CONFIRMED
        classifications[key] = {
            "match_class": match_class,
            "matched_symbol": matched_symbol,
            "match_type": match_type,
            "identity_confirmed": identity_confirmed,
        }
        counts[match_class] += 1

        if match_class == MATCH_UNMATCHED:
            unmatched.append(example(security, match_class=MATCH_UNMATCHED))
            continue

        if match_type in type_counts:
            type_counts[match_type] += 1

        covered_set = dates_by_symbol.get(matched_symbol or "", set())
        covered_days = len(covered_set & set(observed_dates))
        history_class = (
            match_class
            if match_class == MATCH_AMBIGUOUS
            else coverage_class(covered_days, reference_days, False)
        )
        matched.append(
            example(
                security,
                match_type=match_type,
                match_class=match_class,
                matched_symbol=matched_symbol,
                match_basis=sorted(
                    {basis for bases in outcomes.values() for basis in bases}
                ),
                identity_confirmed=identity_confirmed,
                via_symbol_change=aliases.get(matched_symbol or "", []),
                isin_evidence=isin_evidence[:MAX_EXAMPLES],
                price_history={
                    "covered_days": covered_days,
                    "observed_days": reference_days,
                    "classification": history_class,
                },
            )
        )

    matched.sort(key=lambda item: (item["symbol"], item["isin"]))
    unmatched.sort(key=lambda item: (item["symbol"], item["isin"]))

    denominator = len(securities)
    history_counts = {class_name: 0 for class_name in COVERAGE_CLASSES}
    for entry in matched:
        history_counts[entry["price_history"]["classification"]] += 1
    history_counts[COVERAGE_MISSING] += len(unmatched)

    metrics = {
        "delisting_records": sum(security["record_count"] for security in securities),
        "delisted_securities": denominator,
        "matched_to_price_history": len(matched),
        "direct_symbol_matches": type_counts[BASIS_DIRECT],
        "isin_symbol_matches": type_counts[BASIS_ISIN],
        "symbol_change_candidate_matches": type_counts[BASIS_ALIAS],
        "unmatched": len(unmatched),
        "match_classes": {
            class_name: counts[class_name] for class_name in MATCH_CLASSES
        },
        "match_class_percentages": (
            {
                class_name: round(100.0 * counts[class_name] / denominator, 1)
                for class_name in MATCH_CLASSES
            }
            if denominator
            else None
        ),
        "denominator": {
            "delisted_securities": denominator,
            "basis": "distinct delisted securities grouped by ISIN, then symbol",
        },
        "match_class_rules": dict(MATCH_BASIS_RULES),
        "identity_confirmation": (
            "confirmed_only_where_a_delisting_isin_matches_a_current_listing_isin "
            "and the price history of that listing's symbol starts on or before "
            "the (re)listing date; symbol equality alone is never confirmation"
        ),
        "symbol_equality_is_not_identity": True,
        "price_history_classes": {
            class_name: history_counts[class_name] for class_name in COVERAGE_CLASSES
        },
        "observed_trading_days": reference_days,
        "matched_examples": matched[:MAX_EXAMPLES],
        "unmatched_examples": unmatched[:MAX_EXAMPLES],
    }
    return metrics, classifications


def identifier_reuse_evidence(
    securities: Sequence[dict[str, Any]],
    current: Sequence[CurrentListing],
) -> dict[str, Any]:
    """Find delisted identifiers that also appear in the current snapshot."""

    current_by_symbol: dict[str, list[CurrentListing]] = defaultdict(list)
    current_by_isin: dict[str, list[CurrentListing]] = defaultdict(list)
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
        symbol_hits: list[CurrentListing] = []
        for symbol in security["symbols"]:
            symbol_hits.extend(current_by_symbol.get(symbol, []))
        isin_hits: list[CurrentListing] = []
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
            example(
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


def reused_symbols_in_delistings(
    securities: Sequence[dict[str, Any]],
) -> dict[str, int]:
    """Symbols associated with more than one grouped security identity."""

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


def symbol_change_metrics(
    changes: Sequence[SymbolChange],
) -> tuple[dict[str, Any], dict[str, list[str]], set[str]]:
    """Summarise symbol-change records and unresolved mapping conflicts.

    Conflicts are mappings the collected data cannot resolve on its own:

    - many-to-one: one new symbol targeted by several old symbols;
    - one-to-many: one old symbol mapped to several distinct new symbols.

    Both are reported; neither is silently collapsed.
    """

    old_by_new: dict[str, set[str]] = defaultdict(set)
    new_by_old: dict[str, set[str]] = defaultdict(set)
    noop = 0
    for change in changes:
        if not change.old_symbol or not change.new_symbol:
            continue
        if change.old_symbol == change.new_symbol:
            noop += 1
            continue
        old_by_new[change.new_symbol].add(change.old_symbol)
        new_by_old[change.old_symbol].add(change.new_symbol)

    shared = {
        new_symbol: sorted(old_symbols)
        for new_symbol, old_symbols in sorted(old_by_new.items())
        if len(old_symbols) > 1
    }
    multi_target = {
        old_symbol: sorted(new_symbols)
        for old_symbol, new_symbols in sorted(new_by_old.items())
        if len(new_symbols) > 1
    }
    conflicts = {
        *shared,
        *multi_target,
    }
    metrics = {
        "records": len(changes),
        "noop_changes": noop,
        "shared_new_symbols": shared,
        "multi_target_old_symbols": multi_target,
        "conflicting_mapping_count": len(shared) + len(multi_target),
        "unresolved_mapping_count": len(shared) + len(multi_target),
        "user_supplied_records": sum(
            1 for change in changes if change.source == "backtest_config"
        ),
    }
    return metrics, shared, conflicts


def ambiguous_symbol_reasons(
    reused_symbols: Mapping[str, int],
    conflicts: Iterable[str],
) -> dict[str, list[str]]:
    """Explain why the identity behind a symbol's price rows is uncertain."""

    reasons: dict[str, list[str]] = defaultdict(list)
    for symbol in sorted(reused_symbols):
        reasons[symbol].append(
            "the symbol maps to multiple delisted security identities"
        )
    for symbol in sorted(conflicts):
        reasons[symbol].append(
            "the symbol appears in conflicting symbol-change mappings"
        )
    return dict(sorted(reasons.items()))


def continuity_examples(
    securities: Sequence[dict[str, Any]],
    current: Sequence[CurrentListing],
    symbol_changes: Sequence[SymbolChange],
    name_changes: Sequence[Any],
) -> list[dict[str, Any]]:
    """Surface symbol/name continuity evidence for review, deterministically."""

    current_symbols = {record.symbol for record in current if record.symbol}
    current_isins = {record.isin for record in current if record.isin}
    changes_by_symbol: dict[str, list[SymbolChange]] = defaultdict(list)
    names_by_symbol: dict[str, list[Any]] = defaultdict(list)
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
            example(
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
