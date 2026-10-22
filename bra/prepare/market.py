"""Preparation of normalized price, corporate-action, and financial datasets."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from ..derived_schema import DERIVED_HEADERS
from ..discovery import (
    FINANCIAL_SYMBOL_RE,
    INTEGRATED_SYMBOL_RE,
    PRICE_SYMBOL_RE,
)
from ..parsing import parse_date, parse_number, parse_timestamp
from .common import (
    TransformResult,
    add_flag,
    build_column_map,
    clean_text,
    date_text,
    load_csv,
    number_text,
    timestamp_text,
)

OHLC_FIELDS = (
    ("open", "Open Price"),
    ("high", "High Price"),
    ("low", "Low Price"),
    ("close", "Close Price"),
)
TOLERANCE = 1e-6


def _relative(path: Path, data_root: Path) -> str:
    try:
        return path.relative_to(data_root).as_posix()
    except ValueError:
        return path.name


def _flag_ohlc_anomaly(row: dict[str, str], series: str) -> None:
    values: dict[str, float] = {}
    for field, _ in OHLC_FIELDS:
        parsed = parse_number(row.get(field))
        if parsed is not None:
            values[field] = parsed
    if len(values) != len(OHLC_FIELDS):
        return

    reason = None
    if values["high"] + TOLERANCE < values["low"]:
        reason = "high is below low"
    elif values["high"] + TOLERANCE < max(values["open"], values["close"]):
        reason = "high is below open or close"
    elif values["low"] - TOLERANCE > min(values["open"], values["close"]):
        reason = "low is above open or close"
    if reason is None:
        return

    if series.upper() == "EQ":
        add_flag(row, "ohlc_anomaly_primary")
    else:
        add_flag(row, "ohlc_anomaly_auxiliary")


def prepare_prices(data_root: Path) -> TransformResult:
    """Combine per-symbol price exports into one normalized long table."""

    sources = sorted((data_root / "raw").glob("*-ALL-N.csv"))
    result = TransformResult(
        name="prices",
        filename="prices.csv",
        headers=DERIVED_HEADERS["derived_prices"],
        rows=[],
        sources=sources,
        rules=[
            "Read every raw/*-ALL-N.csv file in stable filename order.",
            "Keep every source row; no price records are deduplicated or removed.",
            "Trim symbol and series identifiers; preserve source case.",
            "Convert DD-Mon-YYYY trade dates to ISO 8601.",
            "Parse Indian-grouped numbers and emit canonical decimal text.",
            "Map OHLC anomalies to review flags, with stricter primary-series flags.",
            "Record source_file and physical source_line for every row.",
        ],
    )

    numeric_mapping = {
        "prev_close": "Prev Close",
        "open": "Open Price",
        "high": "High Price",
        "low": "Low Price",
        "last": "Last Price",
        "close": "Close Price",
        "average": "Average Price",
        "volume": "Total Traded Quantity",
        "turnover": "Turnover ₹",
        "trades": "No. of Trades",
        "deliverable_qty": "Deliverable Qty",
        "delivery_pct": "% Dly Qt to Traded Qty",
    }

    for path in sources:
        table = load_csv(path)
        if not result.column_map:
            mapping = {"symbol": "Symbol", "series": "Series", "trade_date": "Date"}
            mapping.update(
                {
                    derived: source
                    for derived, source in numeric_mapping.items()
                }
            )
            result.column_map = build_column_map(table, mapping)

        match = PRICE_SYMBOL_RE.search(path.name)
        expected_symbol = match.group("symbol").upper() if match else None
        source_file = _relative(path, data_root)

        for source_row in table.rows:
            row = {"review_flags": ""}
            row["symbol"] = clean_text(
                row, "symbol", source_row.get("Symbol"), result, identifier=True
            )
            row["series"] = clean_text(
                row, "series", source_row.get("Series"), result, identifier=True
            )
            row["trade_date"] = date_text(
                row, "trade_date", source_row.get("Date"), result
            )
            for derived, source in numeric_mapping.items():
                row[derived] = number_text(
                    row, derived, source_row.get(source), result
                )
            if expected_symbol and row["symbol"].upper() != expected_symbol:
                add_flag(row, "symbol_filename_mismatch")
            if any(not row.get(field) for field, _ in OHLC_FIELDS):
                add_flag(row, "missing_ohlc")
            _flag_ohlc_anomaly(row, row["series"])
            row["source_file"] = source_file
            row["source_line"] = str(source_row.number)
            result.rows.append(row)
            result.input_records += 1

    return result


def prepare_corporate_actions(data_root: Path) -> TransformResult:
    """Combine corporate-action exports without inferring action types."""

    sources = sorted((data_root / "reference/corporate_actions").glob("*.csv"))
    result = TransformResult(
        name="corporate_actions",
        filename="corporate_actions.csv",
        headers=DERIVED_HEADERS["derived_corporate_actions"],
        rows=[],
        sources=sources,
        rules=[
            "Read every reference/corporate_actions/*.csv file.",
            "Preserve PURPOSE verbatim apart from harmless surrounding whitespace.",
            "Normalize ex-date, record-date, and book-closure dates to ISO 8601.",
            "Represent source '-' sentinels as blank normalized dates.",
            "Keep duplicate rows and flag duplicate keys rather than deleting them.",
            "Record source_file and physical source_line for every row.",
        ],
    )

    for path in sources:
        table = load_csv(path)
        if not result.column_map:
            result.column_map = build_column_map(
                table,
                {
                    "symbol": "SYMBOL",
                    "company_name": "COMPANY NAME",
                    "series": "SERIES",
                    "purpose": "PURPOSE",
                    "face_value": "FACE VALUE",
                    "ex_date": "EX-DATE",
                    "record_date": "RECORD DATE",
                    "book_closure_start_date": "BOOK CLOSURE START DATE",
                    "book_closure_end_date": "BOOK CLOSURE END DATE",
                },
            )
        source_file = _relative(path, data_root)

        for source_row in table.rows:
            row = {"review_flags": ""}
            row["symbol"] = clean_text(
                row, "symbol", source_row.get("SYMBOL"), result, identifier=True
            )
            row["company_name"] = clean_text(
                row, "company_name", source_row.get("COMPANY NAME"), result
            )
            row["series"] = clean_text(
                row, "series", source_row.get("SERIES"), result, identifier=True
            )
            row["purpose"] = clean_text(
                row, "purpose", source_row.get("PURPOSE"), result
            )
            row["face_value"] = number_text(
                row, "face_value", source_row.get("FACE VALUE"), result
            )
            row["ex_date"] = date_text(
                row, "ex_date", source_row.get("EX-DATE"), result
            )
            row["record_date"] = date_text(
                row, "record_date", source_row.get("RECORD DATE"), result
            )
            row["book_closure_start_date"] = date_text(
                row,
                "book_closure_start_date",
                source_row.get("BOOK CLOSURE START DATE"),
                result,
            )
            row["book_closure_end_date"] = date_text(
                row,
                "book_closure_end_date",
                source_row.get("BOOK CLOSURE END DATE"),
                result,
            )
            if not row["record_date"] and not (
                row["book_closure_start_date"] or row["book_closure_end_date"]
            ):
                add_flag(row, "missing_record_date")
            row["source_file"] = source_file
            row["source_line"] = str(source_row.number)
            result.rows.append(row)
            result.input_records += 1

    groups: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in result.rows:
        if row["symbol"] and row["ex_date"] and row["purpose"]:
            groups[(row["symbol"], row["ex_date"], row["purpose"])].append(row)
    duplicate_groups = {key: value for key, value in groups.items() if len(value) > 1}
    for rows in duplicate_groups.values():
        for row in rows:
            add_flag(row, "duplicate_key")
    result.counts["duplicate_key_groups"] = len(duplicate_groups)
    return result


def prepare_financials_legacy(data_root: Path) -> TransformResult:
    """Normalize legacy quarterly-results exports."""

    sources = sorted((data_root / "reference/financial_results").glob("CF-FR-*.csv"))
    result = TransformResult(
        name="financial_results_legacy",
        filename="financial_results_legacy.csv",
        headers=DERIVED_HEADERS["derived_financials_legacy"],
        rows=[],
        sources=sources,
        rules=[
            "Read legacy CF-FR-equities-* exports.",
            "Derive SYMBOL from the filename because this schema has no symbol column.",
            "Keep reporting-period date separate from exchange timestamps.",
            "Normalize dates and timestamps to ISO 8601 without adding a timezone.",
            "Compute publication_lag_days only when both period and dissemination parse.",
            "Flag dissemination before the period end or before exchange receipt.",
            "Record source_file and physical source_line for every row.",
        ],
    )

    for path in sources:
        table = load_csv(path)
        if not result.column_map:
            result.column_map = build_column_map(
                table,
                {
                    "company_name": "COMPANY NAME",
                    "audited_unaudited": "AUDITED / UNAUDITED",
                    "cumulative_non_cumulative": "CUMULATIVE / NON-CUMULATIVE",
                    "consolidated_non_consolidated": (
                        "CONSOLIDATED / NON-CONSOLIDATED"
                    ),
                    "ind_as": "IND AS/ NON IND AS",
                    "period_label": "PERIOD",
                    "period_end_date": "PERIOD ENDED",
                    "relating_to": "RELATING TO",
                    "xbrl_url": "** XBRL",
                    "exchange_received_time": "Exchange Received Time",
                    "exchange_dissemination_time": (
                        "Exchange Dissemination Time"
                    ),
                    "time_taken": "Time Taken",
                },
            )
            result.column_map["symbol"] = "filename (derived)"
        match = FINANCIAL_SYMBOL_RE.search(path.name)
        symbol = match.group("symbol").upper() if match else ""
        source_file = _relative(path, data_root)

        for source_row in table.rows:
            row = {"review_flags": ""}
            row["symbol"] = symbol
            row["symbol_source"] = "filename"
            row["company_name"] = clean_text(
                row, "company_name", source_row.get("COMPANY NAME"), result
            )
            row["audited_unaudited"] = clean_text(
                row, "audited_unaudited", source_row.get("AUDITED / UNAUDITED"), result
            )
            row["cumulative_non_cumulative"] = clean_text(
                row,
                "cumulative_non_cumulative",
                source_row.get("CUMULATIVE / NON-CUMULATIVE"),
                result,
            )
            row["consolidated_non_consolidated"] = clean_text(
                row,
                "consolidated_non_consolidated",
                source_row.get("CONSOLIDATED / NON-CONSOLIDATED"),
                result,
            )
            row["ind_as"] = clean_text(
                row, "ind_as", source_row.get("IND AS/ NON IND AS"), result
            )
            row["period_label"] = clean_text(
                row, "period_label", source_row.get("PERIOD"), result
            )
            row["period_end_date"] = date_text(
                row, "period_end_date", source_row.get("PERIOD ENDED"), result
            )
            row["relating_to"] = clean_text(
                row, "relating_to", source_row.get("RELATING TO"), result
            )
            row["xbrl_url"] = clean_text(
                row, "xbrl_url", source_row.get("** XBRL"), result
            )
            received_raw = source_row.get("Exchange Received Time")
            disseminated_raw = source_row.get("Exchange Dissemination Time")
            row["exchange_received_time"] = timestamp_text(
                row, "exchange_received_time", received_raw, result
            )
            row["exchange_dissemination_time"] = timestamp_text(
                row, "exchange_dissemination_time", disseminated_raw, result
            )
            row["time_taken"] = clean_text(
                row, "time_taken", source_row.get("Time Taken"), result
            )
            _apply_publication_lag(row, result)
            _check_dissemination_order(row, received_raw)
            if not row["company_name"]:
                add_flag(row, "missing_company_name")
            row["source_file"] = source_file
            row["source_line"] = str(source_row.number)
            result.rows.append(row)
            result.input_records += 1

    return result


def prepare_financials_integrated(data_root: Path) -> TransformResult:
    """Normalize the newer integrated-filing financial exports."""

    sources = sorted((data_root / "reference/financial_results/additional").glob("*.csv"))
    result = TransformResult(
        name="financial_results_integrated",
        filename="financial_results_integrated.csv",
        headers=DERIVED_HEADERS["derived_financials_integrated"],
        rows=[],
        sources=sources,
        rules=[
            "Read integrated-filing exports, including headers with newlines.",
            "Use the row SYMBOL where present; flag a filename fallback.",
            "Keep quarter-end date separate from dissemination timestamps.",
            "Normalize dates and timestamps to ISO 8601 without adding a timezone.",
            "Compute publication_lag_days only when both dates parse.",
            "Flag dissemination before the quarter end or before broadcast.",
            "Record source_file and physical source_line for every row.",
        ],
    )

    for path in sources:
        table = load_csv(path)
        if not result.column_map:
            result.column_map = build_column_map(
                table,
                {
                    "symbol": "SYMBOL",
                    "company_name": "COMPANY NAME",
                    "quarter_end_date": "QUARTER END DATE",
                    "submission_type": "TYPE OF SUBMISSION",
                    "audited_unaudited": "AUDITED / UNAUDITED",
                    "consolidated_standalone": "CONSOLIDATED / STANDALONE",
                    "details_url": "DETAILS",
                    "xbrl_url": "XBRL",
                    "broadcast_datetime": "BROADCAST DATE/TIME",
                    "revised_datetime": "REVISED DATE/TIME",
                    "revision_remarks": "REVISION REMARKS",
                    "exchange_dissemination_time": (
                        "EXCHANGE DISSEMINATION TIME"
                    ),
                    "time_taken": "TIME TAKEN",
                },
            )
        match = INTEGRATED_SYMBOL_RE.search(path.name)
        filename_symbol = match.group("symbol").upper() if match else ""
        source_file = _relative(path, data_root)

        for source_row in table.rows:
            row = {"review_flags": ""}
            symbol = clean_text(
                row, "symbol", source_row.get("SYMBOL"), result, identifier=True
            )
            if symbol:
                row["symbol"] = symbol
                row["symbol_source"] = "row"
            else:
                row["symbol"] = filename_symbol
                row["symbol_source"] = "filename_fallback"
                add_flag(row, "missing_symbol")
            row["company_name"] = clean_text(
                row, "company_name", source_row.get("COMPANY NAME"), result
            )
            row["quarter_end_date"] = date_text(
                row, "quarter_end_date", source_row.get("QUARTER END DATE"), result
            )
            row["submission_type"] = clean_text(
                row, "submission_type", source_row.get("TYPE OF SUBMISSION"), result
            )
            row["audited_unaudited"] = clean_text(
                row, "audited_unaudited", source_row.get("AUDITED / UNAUDITED"), result
            )
            row["consolidated_standalone"] = clean_text(
                row,
                "consolidated_standalone",
                source_row.get("CONSOLIDATED / STANDALONE"),
                result,
            )
            row["details_url"] = clean_text(
                row, "details_url", source_row.get("DETAILS"), result
            )
            row["xbrl_url"] = clean_text(
                row, "xbrl_url", source_row.get("XBRL"), result
            )
            broadcast_raw = source_row.get("BROADCAST DATE/TIME")
            row["broadcast_datetime"] = timestamp_text(
                row, "broadcast_datetime", broadcast_raw, result
            )
            row["revised_datetime"] = timestamp_text(
                row, "revised_datetime", source_row.get("REVISED DATE/TIME"), result
            )
            row["revision_remarks"] = clean_text(
                row, "revision_remarks", source_row.get("REVISION REMARKS"), result
            )
            row["exchange_dissemination_time"] = timestamp_text(
                row,
                "exchange_dissemination_time",
                source_row.get("EXCHANGE DISSEMINATION TIME"),
                result,
            )
            row["time_taken"] = clean_text(
                row, "time_taken", source_row.get("TIME TAKEN"), result
            )
            _apply_publication_lag(row, result)
            _check_dissemination_order(row, broadcast_raw)
            if not row["company_name"]:
                add_flag(row, "missing_company_name")
            row["source_file"] = source_file
            row["source_line"] = str(source_row.number)
            result.rows.append(row)
            result.input_records += 1

    return result


def _apply_publication_lag(
    row: dict[str, str],
    result: TransformResult,
) -> None:
    period = parse_date(row.get("period_end_date") or row.get("quarter_end_date"))
    dissemination = parse_timestamp(row.get("exchange_dissemination_time"))
    if period is None or dissemination is None:
        row["publication_lag_days"] = ""
        return
    if dissemination.date() < period:
        add_flag(row, "disseminated_before_period")
        row["publication_lag_days"] = ""
        result.counts["disseminated_before_period"] += 1
        return
    row["publication_lag_days"] = str((dissemination.date() - period).days)


def _check_dissemination_order(
    row: dict[str, str],
    secondary_raw: str | None,
) -> None:
    received = parse_timestamp(secondary_raw)
    dissemination = parse_timestamp(row.get("exchange_dissemination_time"))
    if received is not None and dissemination is not None and dissemination < received:
        add_flag(row, "dissemination_before_receipt")
