"""Shared schema for the normalized, derived datasets.

Keeping the headers and validation keys in one place prevents the preparation
step and the processed-data validator from drifting apart.
"""

from __future__ import annotations

DERIVED_HEADERS: dict[str, tuple[str, ...]] = {
    "derived_prices": (
        "symbol",
        "series",
        "trade_date",
        "prev_close",
        "open",
        "high",
        "low",
        "last",
        "close",
        "average",
        "volume",
        "turnover",
        "trades",
        "deliverable_qty",
        "delivery_pct",
        "source_file",
        "source_line",
        "review_flags",
    ),
    "derived_corporate_actions": (
        "symbol",
        "company_name",
        "series",
        "purpose",
        "face_value",
        "ex_date",
        "record_date",
        "book_closure_start_date",
        "book_closure_end_date",
        "source_file",
        "source_line",
        "review_flags",
    ),
    "derived_financials_legacy": (
        "symbol",
        "symbol_source",
        "company_name",
        "audited_unaudited",
        "cumulative_non_cumulative",
        "consolidated_non_consolidated",
        "ind_as",
        "period_label",
        "period_end_date",
        "relating_to",
        "xbrl_url",
        "exchange_received_time",
        "exchange_dissemination_time",
        "publication_lag_days",
        "time_taken",
        "source_file",
        "source_line",
        "review_flags",
    ),
    "derived_financials_integrated": (
        "symbol",
        "symbol_source",
        "company_name",
        "quarter_end_date",
        "submission_type",
        "audited_unaudited",
        "consolidated_standalone",
        "details_url",
        "xbrl_url",
        "broadcast_datetime",
        "revised_datetime",
        "revision_remarks",
        "exchange_dissemination_time",
        "publication_lag_days",
        "time_taken",
        "source_file",
        "source_line",
        "review_flags",
    ),
    "derived_current_listings": (
        "symbol",
        "company_name",
        "series",
        "listing_date",
        "paid_up_value",
        "market_lot",
        "isin",
        "face_value",
        "source_file",
        "source_line",
        "review_flags",
    ),
    "derived_name_changes": (
        "symbol",
        "old_name",
        "new_name",
        "effective_date",
        "source_record_count",
        "source_lines",
        "source_line",
        "source_file",
        "review_status",
        "review_flags",
    ),
    "derived_symbol_changes": (
        "company_name",
        "old_symbol",
        "new_symbol",
        "effective_date",
        "source_file",
        "source_line",
        "review_flags",
    ),
    "derived_delistings": (
        "symbol",
        "isin",
        "company_name",
        "board",
        "delisted_date",
        "delisting_type",
        "source_file",
        "source_sheet",
        "source_row",
        "review_flags",
    ),
}

DERIVED_FILENAMES: dict[str, str] = {
    "derived_prices": "prices.csv",
    "derived_corporate_actions": "corporate_actions.csv",
    "derived_financials_legacy": "financial_results_legacy.csv",
    "derived_financials_integrated": "financial_results_integrated.csv",
    "derived_current_listings": "current_listings.csv",
    "derived_name_changes": "name_changes.csv",
    "derived_symbol_changes": "symbol_changes.csv",
    "derived_delistings": "delistings.csv",
}

DERIVED_KEY_COLUMNS: dict[str, tuple[str, ...]] = {
    "derived_prices": ("symbol", "series", "trade_date"),
    "derived_corporate_actions": ("symbol", "ex_date", "purpose"),
    "derived_financials_legacy": (
        "symbol",
        "period_end_date",
        "consolidated_non_consolidated",
    ),
    "derived_financials_integrated": (
        "symbol",
        "quarter_end_date",
        "consolidated_standalone",
        "submission_type",
    ),
    "derived_current_listings": ("symbol", "series"),
    "derived_name_changes": ("symbol", "old_name", "new_name", "effective_date"),
    "derived_symbol_changes": (
        "company_name",
        "old_symbol",
        "new_symbol",
        "effective_date",
    ),
    "derived_delistings": ("symbol", "isin", "delisted_date"),
}

DERIVED_DATE_COLUMNS: dict[str, tuple[str, ...]] = {
    "derived_prices": ("trade_date",),
    "derived_corporate_actions": (
        "ex_date",
        "record_date",
        "book_closure_start_date",
        "book_closure_end_date",
    ),
    "derived_financials_legacy": ("period_end_date",),
    "derived_financials_integrated": ("quarter_end_date",),
    "derived_current_listings": ("listing_date",),
    "derived_name_changes": ("effective_date",),
    "derived_symbol_changes": ("effective_date",),
    "derived_delistings": ("delisted_date",),
}

DERIVED_REQUIRED_DATE_COLUMNS: dict[str, tuple[str, ...]] = {
    "derived_prices": ("trade_date",),
    "derived_corporate_actions": ("ex_date",),
    "derived_financials_legacy": ("period_end_date",),
    "derived_financials_integrated": ("quarter_end_date",),
    "derived_current_listings": ("listing_date",),
    "derived_name_changes": ("effective_date",),
    "derived_symbol_changes": ("effective_date",),
    "derived_delistings": ("delisted_date",),
}

DERIVED_TIMESTAMP_COLUMNS: dict[str, tuple[str, ...]] = {
    "derived_financials_legacy": (
        "exchange_received_time",
        "exchange_dissemination_time",
    ),
    "derived_financials_integrated": (
        "broadcast_datetime",
        "revised_datetime",
        "exchange_dissemination_time",
    ),
}

DERIVED_REQUIRED_TIMESTAMP_COLUMNS: dict[str, tuple[str, ...]] = {
    "derived_financials_legacy": ("exchange_dissemination_time",),
    "derived_financials_integrated": ("exchange_dissemination_time",),
}

DERIVED_IDENTIFIER_COLUMNS: dict[str, tuple[str, ...]] = {
    "derived_prices": ("symbol", "series"),
    "derived_corporate_actions": ("symbol",),
    "derived_financials_legacy": ("symbol",),
    "derived_financials_integrated": ("symbol",),
    "derived_current_listings": ("symbol", "series", "isin"),
    "derived_name_changes": ("symbol",),
    "derived_symbol_changes": ("old_symbol", "new_symbol"),
    "derived_delistings": ("symbol", "isin"),
}

DERIVED_ISIN_COLUMNS: dict[str, tuple[str, ...]] = {
    "derived_current_listings": ("isin",),
    "derived_delistings": ("isin",),
}

DERIVED_ENTITY_COLUMNS: dict[str, str] = {
    "derived_prices": "symbol",
    "derived_corporate_actions": "symbol",
    "derived_financials_legacy": "company_name",
    "derived_financials_integrated": "company_name",
    "derived_current_listings": "company_name",
    "derived_name_changes": "symbol",
    "derived_symbol_changes": "company_name",
    "derived_delistings": "symbol",
}

REVIEW_FLAG_MESSAGES: dict[str, str] = {
    "auxiliary_sheet_conflict": (
        "Another workbook sheet records a different value for this event."
    ),
    "disseminated_before_period": (
        "Dissemination timestamp precedes the reporting period end."
    ),
    "dissemination_before_receipt": (
        "Dissemination timestamp precedes the exchange receipt/broadcast time."
    ),
    "duplicate_key": (
        "More than one source record shares this dataset's natural key; all "
        "records were retained."
    ),
    "identifier_whitespace_trimmed": (
        "Harmless surrounding identifier whitespace was trimmed in derived data."
    ),
    "invalid_date": "A source date could not be parsed and was left blank.",
    "invalid_number": "A source number could not be parsed and was left blank.",
    "invalid_timestamp": (
        "A source timestamp could not be parsed and was left blank."
    ),
    "malformed_isin": "The source ISIN does not match the expected format.",
    "missing_company_name": "The source row has no company name.",
    "missing_isin": "The source row has no ISIN.",
    "missing_ohlc": "One or more OHLC price fields are blank or unparseable.",
    "missing_record_date": (
        "Neither a record date nor book-closure dates were supplied."
    ),
    "missing_symbol": "The source row has no symbol.",
    "noop_symbol_change": "The old and new symbols are identical.",
    "ohlc_anomaly_auxiliary": (
        "An auxiliary market series has an OHLC relationship anomaly."
    ),
    "ohlc_anomaly_primary": (
        "The primary EQ series has an OHLC relationship anomaly."
    ),
    "overlapping_variant": (
        "Another record represents the same event with a different name spelling."
    ),
    "relisted_or_reused_identifier": (
        "The symbol/ISIN also appears in the delisting history; treat the "
        "identifier as time-dependent."
    ),
    "same_company_date_multiple_records": (
        "Multiple symbol-change records share this company and effective date."
    ),
    "shared_event_across_symbols": (
        "The same old/new name pair and date appears under more than one symbol."
    ),
    "shared_new_symbol": (
        "This new symbol is also the target of a change from another old symbol."
    ),
    "symbol_filename_mismatch": (
        "The symbol in the row differs from the symbol encoded in the filename."
    ),
}
