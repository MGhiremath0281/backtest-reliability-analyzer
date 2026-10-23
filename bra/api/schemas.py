"""Canonical schema definitions, type inference, and detection for BRA."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ..parsing import clean, is_blank, parse_date, parse_timestamp


@dataclass(frozen=True)
class SchemaColumn:
    name: str
    data_type: str  # "string", "date", "timestamp", "float", "int"
    required: bool
    description: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class SchemaDefinition:
    schema_type: str
    label: str
    description: str
    columns: tuple[SchemaColumn, ...]
    key_columns: tuple[str, ...] = ()

    @property
    def required_columns(self) -> list[str]:
        return [c.name for c in self.columns if c.required]

    @property
    def optional_columns(self) -> list[str]:
        return [c.name for c in self.columns if not c.required]

    @property
    def date_columns(self) -> list[str]:
        return [c.name for c in self.columns if c.data_type in {"date", "timestamp"}]

    @property
    def numeric_columns(self) -> list[str]:
        return [c.name for c in self.columns if c.data_type in {"float", "int"}]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_type": self.schema_type,
            "label": self.label,
            "description": self.description,
            "required_columns": self.required_columns,
            "optional_columns": self.optional_columns,
            "date_columns": self.date_columns,
            "numeric_columns": self.numeric_columns,
            "key_columns": list(self.key_columns),
            "columns": [
                {
                    "name": c.name,
                    "data_type": c.data_type,
                    "required": c.required,
                    "description": c.description,
                    "aliases": list(c.aliases),
                }
                for c in self.columns
            ],
        }


# Canonical Schema Definitions
CANONICAL_SCHEMAS: dict[str, SchemaDefinition] = {
    "prices": SchemaDefinition(
        schema_type="prices",
        label="Historical Prices",
        description="Daily OHLCV equity price history.",
        columns=(
            SchemaColumn(
                "Symbol",
                "string",
                True,
                "Security trading symbol",
                ("symbol", "ticker", "tradingsymbol", "code"),
            ),
            SchemaColumn(
                "Series",
                "string",
                False,
                "Market segment series (e.g. EQ)",
                ("series", "segment"),
            ),
            SchemaColumn(
                "Date",
                "date",
                True,
                "Trade date",
                ("date", "trade_date", "tradedate", "timestamp"),
            ),
            SchemaColumn(
                "Open Price",
                "float",
                True,
                "Opening price",
                ("open", "open_price", "opening_price"),
            ),
            SchemaColumn(
                "High Price",
                "float",
                True,
                "Highest traded price",
                ("high", "high_price"),
            ),
            SchemaColumn(
                "Low Price", "float", True, "Lowest traded price", ("low", "low_price")
            ),
            SchemaColumn(
                "Close Price",
                "float",
                True,
                "Closing price",
                ("close", "close_price", "closing_price", "last_price", "adj_close"),
            ),
            SchemaColumn(
                "Prev Close",
                "float",
                False,
                "Previous session closing price",
                ("prev_close", "prevclose", "previous_close"),
            ),
            SchemaColumn(
                "Last Price",
                "float",
                False,
                "Last traded price",
                ("last", "last_price", "ltp"),
            ),
            SchemaColumn(
                "Average Price",
                "float",
                False,
                "Volume weighted average price",
                ("vwap", "average_price", "avg_price"),
            ),
            SchemaColumn(
                "Total Traded Quantity",
                "int",
                False,
                "Traded volume in shares",
                ("volume", "vol", "traded_qty", "qty", "total_traded_qty"),
            ),
            SchemaColumn(
                "Turnover ₹",
                "float",
                False,
                "Gross traded turnover value",
                ("turnover", "turnover_inr", "value"),
            ),
            SchemaColumn(
                "No. of Trades",
                "int",
                False,
                "Total execution trades count",
                ("trades", "total_trades", "no_of_trades"),
            ),
            SchemaColumn(
                "Deliverable Qty",
                "int",
                False,
                "Deliverable volume quantity",
                ("deliverable_qty", "delivery_qty"),
            ),
            SchemaColumn(
                "% Dly Qt to Traded Qty",
                "float",
                False,
                "Percentage delivery to traded volume",
                ("delivery_pct", "delivery_percentage"),
            ),
        ),
        key_columns=("Symbol", "Series", "Date"),
    ),
    "corporate_actions": SchemaDefinition(
        schema_type="corporate_actions",
        label="Corporate Actions",
        description="Cash/stock dividends, splits, bonuses, rights, and AGM notices.",
        columns=(
            SchemaColumn(
                "SYMBOL",
                "string",
                True,
                "Security trading symbol",
                ("symbol", "ticker", "security"),
            ),
            SchemaColumn(
                "COMPANY NAME",
                "string",
                True,
                "Issuer corporate entity name",
                ("company_name", "company", "issuer"),
            ),
            SchemaColumn(
                "PURPOSE",
                "string",
                True,
                "Action description and terms",
                ("purpose", "action", "description", "event"),
            ),
            SchemaColumn(
                "EX-DATE",
                "date",
                True,
                "Ex-entitlement trading date",
                ("ex_date", "exdate", "effective_date"),
            ),
            SchemaColumn(
                "SERIES", "string", False, "Market segment series", ("series",)
            ),
            SchemaColumn(
                "FACE VALUE",
                "float",
                False,
                "Security nominal face value",
                ("face_value", "fv"),
            ),
            SchemaColumn(
                "RECORD DATE",
                "date",
                False,
                "Books record entitlement cutoff date",
                ("record_date", "recorddate"),
            ),
            SchemaColumn(
                "BOOK CLOSURE START DATE",
                "date",
                False,
                "Transfer register closure start",
                ("book_closure_start_date", "bc_start"),
            ),
            SchemaColumn(
                "BOOK CLOSURE END DATE",
                "date",
                False,
                "Transfer register closure end",
                ("book_closure_end_date", "bc_end"),
            ),
        ),
        key_columns=("SYMBOL", "EX-DATE", "PURPOSE"),
    ),
    "financials_legacy": SchemaDefinition(
        schema_type="financials_legacy",
        label="Financial Results (Legacy Format)",
        description="Historical interim and audited corporate financial filings.",
        columns=(
            SchemaColumn(
                "COMPANY NAME",
                "string",
                True,
                "Issuer company name",
                ("company_name", "company"),
            ),
            SchemaColumn(
                "PERIOD ENDED",
                "date",
                True,
                "Filing period cutoff date",
                ("period_ended", "period_end_date", "quarter_ended"),
            ),
            SchemaColumn(
                "Exchange Dissemination Time",
                "timestamp",
                True,
                "Public dissemination timestamp",
                ("exchange_dissemination_time", "dissemination_time", "published_at"),
            ),
            SchemaColumn(
                "AUDITED / UNAUDITED",
                "string",
                False,
                "Audit assurance status",
                ("audited_unaudited", "audit_status"),
            ),
            SchemaColumn(
                "CUMULATIVE / NON-CUMULATIVE",
                "string",
                False,
                "Cumulative accounting flag",
                ("cumulative_non_cumulative", "cumulative"),
            ),
            SchemaColumn(
                "CONSOLIDATED / NON-CONSOLIDATED",
                "string",
                False,
                "Consolidated entity flag",
                ("consolidated_non_consolidated", "consolidation"),
            ),
            SchemaColumn(
                "IND AS/ NON IND AS",
                "string",
                False,
                "Accounting standard regime",
                ("ind_as", "standard"),
            ),
            SchemaColumn(
                "PERIOD",
                "string",
                False,
                "Period interval label",
                ("period", "period_label"),
            ),
            SchemaColumn(
                "RELATING TO", "string", False, "Subject description", ("relating_to",)
            ),
            SchemaColumn(
                "** XBRL", "string", False, "XBRL resource URL", ("xbrl", "xbrl_url")
            ),
            SchemaColumn(
                "Exchange Received Time",
                "timestamp",
                False,
                "Exchange receipt timestamp",
                ("exchange_received_time", "received_time"),
            ),
            SchemaColumn(
                "Time Taken",
                "string",
                False,
                "Filing processing duration",
                ("time_taken",),
            ),
        ),
        key_columns=("COMPANY NAME", "PERIOD ENDED"),
    ),
    "financials_integrated": SchemaDefinition(
        schema_type="financials_integrated",
        label="Integrated Financial Filings",
        description="Structured XBRL corporate quarterly filings with broadcast & revision timestamps.",
        columns=(
            SchemaColumn(
                "SYMBOL", "string", True, "Company equity symbol", ("symbol", "ticker")
            ),
            SchemaColumn(
                "COMPANY NAME",
                "string",
                True,
                "Entity corporate name",
                ("company_name", "company"),
            ),
            SchemaColumn(
                "QUARTER END DATE",
                "date",
                True,
                "Quarter reporting cutoff date",
                ("quarter_end_date", "period_ended"),
            ),
            SchemaColumn(
                "EXCHANGE DISSEMINATION TIME",
                "timestamp",
                True,
                "Public dissemination timestamp",
                ("exchange_dissemination_time", "dissemination_time"),
            ),
            SchemaColumn(
                "TYPE OF SUBMISSION",
                "string",
                False,
                "Initial or revision submission",
                ("submission_type", "type_of_submission"),
            ),
            SchemaColumn(
                "AUDITED / UNAUDITED",
                "string",
                False,
                "Audit assurance status",
                ("audited_unaudited",),
            ),
            SchemaColumn(
                "CONSOLIDATED / STANDALONE",
                "string",
                False,
                "Consolidation boundary",
                ("consolidated_standalone", "consolidation"),
            ),
            SchemaColumn(
                "DETAILS",
                "string",
                False,
                "Filing details URL",
                ("details", "details_url"),
            ),
            SchemaColumn(
                "XBRL", "string", False, "XBRL attachment URL", ("xbrl", "xbrl_url")
            ),
            SchemaColumn(
                "BROADCAST DATE/TIME",
                "timestamp",
                False,
                "Exchange broadcast timestamp",
                ("broadcast_datetime", "broadcast_date_time"),
            ),
            SchemaColumn(
                "REVISED DATE/TIME",
                "timestamp",
                False,
                "Filing revision timestamp",
                ("revised_datetime", "revised_date_time"),
            ),
            SchemaColumn(
                "REVISION REMARKS",
                "string",
                False,
                "Filing revision rationale",
                ("revision_remarks", "remarks"),
            ),
            SchemaColumn(
                "TIME TAKEN", "string", False, "Filing review duration", ("time_taken",)
            ),
        ),
        key_columns=("SYMBOL", "QUARTER END DATE"),
    ),
    "current_listing": SchemaDefinition(
        schema_type="current_listing",
        label="Current Listing Reference",
        description="Active securities listed on the exchange reference master.",
        columns=(
            SchemaColumn(
                "SYMBOL", "string", True, "Trading ticker symbol", ("symbol", "ticker")
            ),
            SchemaColumn(
                "NAME OF COMPANY",
                "string",
                True,
                "Issuer corporate name",
                ("name_of_company", "company_name", "company"),
            ),
            SchemaColumn(
                "SERIES", "string", True, "Trading market series", ("series",)
            ),
            SchemaColumn(
                "DATE OF LISTING",
                "date",
                True,
                "Initial IPO listing date",
                ("date_of_listing", "listing_date"),
            ),
            SchemaColumn(
                "ISIN NUMBER",
                "string",
                True,
                "International Securities Identification Number",
                ("isin_number", "isin"),
            ),
            SchemaColumn(
                "PAID UP VALUE",
                "float",
                False,
                "Paid up capital value",
                ("paid_up_value",),
            ),
            SchemaColumn(
                "MARKET LOT",
                "int",
                False,
                "Minimum market order lot size",
                ("market_lot",),
            ),
            SchemaColumn(
                "FACE VALUE",
                "float",
                False,
                "Face value per share",
                ("face_value", "fv"),
            ),
        ),
        key_columns=("SYMBOL", "SERIES"),
    ),
    "delistings": SchemaDefinition(
        schema_type="delistings",
        label="Historical Delistings",
        description="Records of equities delisted from exchange boards.",
        columns=(
            SchemaColumn(
                "Symbol", "string", True, "Last trading symbol", ("symbol", "ticker")
            ),
            SchemaColumn(
                "ISIN", "string", True, "Security ISIN", ("isin", "isin_number")
            ),
            SchemaColumn(
                "Company Name",
                "string",
                True,
                "Delisted issuer name",
                ("company_name", "company"),
            ),
            SchemaColumn(
                "Delisted Date",
                "date",
                True,
                "Effective cessation date",
                ("delisted_date", "delisting_date"),
            ),
            SchemaColumn(
                "Type of Delisting",
                "string",
                True,
                "Compulsory or voluntary delisting mode",
                ("type_of_delisting", "delisting_type", "reason"),
            ),
            SchemaColumn(
                "Board",
                "string",
                False,
                "Exchange trading board (Main / SME)",
                ("board", "segment"),
            ),
            SchemaColumn("Series", "string", False, "Trading series", ("series",)),
        ),
        key_columns=("Symbol", "ISIN", "Delisted Date"),
    ),
    "name_changes": SchemaDefinition(
        schema_type="name_changes",
        label="Company Name Changes",
        description="Corporate identity modifications and name history.",
        columns=(
            SchemaColumn(
                "SYMBOL", "string", True, "Security symbol", ("symbol", "ticker")
            ),
            SchemaColumn(
                "OLD NAME OF THE COMPANY",
                "string",
                True,
                "Prior corporate entity name",
                ("old_name", "old_company_name", "former_name"),
            ),
            SchemaColumn(
                "NEW NAME OF THE COMPANY",
                "string",
                True,
                "Updated corporate entity name",
                ("new_name", "new_company_name", "current_name"),
            ),
            SchemaColumn(
                "EFFECTIVE DATE",
                "date",
                True,
                "Effective registration date",
                ("effective_date", "date"),
            ),
        ),
        key_columns=(
            "SYMBOL",
            "OLD NAME OF THE COMPANY",
            "NEW NAME OF THE COMPANY",
            "EFFECTIVE DATE",
        ),
    ),
    "symbol_changes": SchemaDefinition(
        schema_type="symbol_changes",
        label="Symbol Changes",
        description="Ticker transitions for listed corporate securities.",
        columns=(
            SchemaColumn(
                "OLD SYMBOL",
                "string",
                True,
                "Previous trading symbol",
                ("old_symbol", "old_ticker", "former_symbol"),
            ),
            SchemaColumn(
                "NEW SYMBOL",
                "string",
                True,
                "New trading symbol",
                ("new_symbol", "new_ticker", "current_symbol"),
            ),
            SchemaColumn(
                "EFFECTIVE DATE",
                "date",
                True,
                "Date symbol change took effect",
                ("effective_date", "date"),
            ),
            SchemaColumn(
                "NAME OF THE COMPANY",
                "string",
                False,
                "Issuer corporate entity name",
                ("company_name", "name_of_the_company", "company"),
            ),
        ),
        key_columns=("OLD SYMBOL", "NEW SYMBOL", "EFFECTIVE DATE"),
    ),
    "index_snapshot": SchemaDefinition(
        schema_type="index_snapshot",
        label="Index Constituent Snapshot",
        description="Dated historical index membership constituent snapshot.",
        columns=(
            SchemaColumn(
                "Index Name",
                "string",
                True,
                "Index benchmark name (e.g. NIFTY 50)",
                ("index_name", "index", "benchmark"),
            ),
            SchemaColumn(
                "Date",
                "date",
                True,
                "Snapshot effective date",
                ("date", "snapshot_date"),
            ),
            SchemaColumn(
                "Symbol",
                "string",
                True,
                "Constituent trading symbol",
                ("symbol", "ticker"),
            ),
            SchemaColumn(
                "ISIN",
                "string",
                False,
                "Constituent security ISIN",
                ("isin", "isin_number"),
            ),
        ),
        key_columns=("Index Name", "Date", "Symbol"),
    ),
}


def normalize_col_name(name: str) -> str:
    """Normalize a column name for fuzzy alias matching."""
    cleaned = clean(name).lower()
    return re.sub(r"[^a-z0-9]", "", cleaned)


def infer_column_type(sample_values: list[str]) -> str:
    """Infer data type ('date', 'timestamp', 'int', 'float', 'string') from sample values."""
    non_empty = [
        clean(v)
        for v in sample_values
        if not is_blank(v) and clean(v) not in {"-", "--", "NA", "N/A"}
    ]
    if not non_empty:
        return "string"

    # Try dates and timestamps
    date_count = 0
    timestamp_count = 0
    int_count = 0
    float_count = 0

    for val in non_empty:
        if parse_timestamp(val) is not None and (":" in val or len(val) > 10):
            timestamp_count += 1
        elif parse_date(val) is not None:
            date_count += 1
        else:
            # Check numbers
            cleaned_num = val.replace(",", "").strip()
            try:
                int(cleaned_num)
                int_count += 1
                continue
            except ValueError:
                pass

            try:
                float(cleaned_num)
                float_count += 1
                continue
            except ValueError:
                pass

    total = len(non_empty)
    if timestamp_count / total >= 0.7:
        return "timestamp"
    if date_count / total >= 0.7:
        return "date"
    if int_count / total >= 0.8:
        return "int"
    if (int_count + float_count) / total >= 0.8:
        return "float"
    return "string"


def detect_candidate_schema(headers: list[str]) -> tuple[str | None, float]:
    """Identify the most likely canonical schema for a given list of headers.

    Returns (schema_type, score) where score is in [0.0, 1.0].
    """
    if not headers:
        return None, 0.0

    normalized_headers = {normalize_col_name(h) for h in headers if h}
    best_schema: str | None = None
    best_score = 0.0

    for schema_type, schema_def in CANONICAL_SCHEMAS.items():
        matched_required = 0
        total_required = len(schema_def.required_columns)
        matched_total = 0

        for col in schema_def.columns:
            target_norm = normalize_col_name(col.name)
            alias_norms = {normalize_col_name(a) for a in col.aliases}
            candidates = {target_norm} | alias_norms

            if candidates & normalized_headers:
                matched_total += 1
                if col.required:
                    matched_required += 1

        required_ratio = (matched_required / total_required) if total_required else 0.0
        overall_ratio = matched_total / len(schema_def.columns)
        score = (required_ratio * 0.7) + (overall_ratio * 0.3)

        if score > best_score:
            best_score = score
            best_schema = schema_type

    if best_score < 0.4:
        return None, best_score
    return best_schema, best_score


def suggest_column_mappings(
    headers: list[str], target_schema: str | None = None
) -> tuple[str, dict[str, str]]:
    """Generate safe, non-ambiguous column mapping suggestions.

    Returns (schema_type, {source_header: canonical_column}).
    """
    if target_schema is None or target_schema not in CANONICAL_SCHEMAS:
        candidate, _ = detect_candidate_schema(headers)
        target_schema = candidate or "prices"

    schema_def = CANONICAL_SCHEMAS[target_schema]
    mapping: dict[str, str] = {}
    used_targets: set[str] = set()

    # Pass 1: exact normalized match to canonical column name
    for header in headers:
        h_norm = normalize_col_name(header)
        for col in schema_def.columns:
            if col.name not in used_targets and h_norm == normalize_col_name(col.name):
                mapping[header] = col.name
                used_targets.add(col.name)
                break

    # Pass 2: match against aliases
    for header in headers:
        if header in mapping:
            continue
        h_norm = normalize_col_name(header)
        for col in schema_def.columns:
            if col.name in used_targets:
                continue
            alias_norms = [normalize_col_name(a) for a in col.aliases]
            if h_norm in alias_norms:
                mapping[header] = col.name
                used_targets.add(col.name)
                break

    return target_schema, mapping
