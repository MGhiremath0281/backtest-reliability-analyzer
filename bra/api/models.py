"""Pydantic models for the BRA API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Health and System Models
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    status: str = "ok"
    app: str = "backtest-reliability-analyzer"
    version: str = "0.1.0"
    storage: str = "healthy"
    analyzers: dict[str, str] = Field(default_factory=dict)


class MetadataResponse(BaseModel):
    version: str
    app_name: str
    registered_analyzers: list[dict[str, Any]]
    supported_schemas: list[dict[str, Any]]
    file_handling: dict[str, Any]
    application_config: dict[str, Any]


# ---------------------------------------------------------------------------
# Dataset Models
# ---------------------------------------------------------------------------


class FileInfo(BaseModel):
    file_id: str
    original_filename: str
    stored_filename: str
    size_bytes: int
    row_count: int
    headers: list[str]
    detected_schema: str | None = None
    confidence: float | None = None
    uploaded_at: str


class DatasetSummary(BaseModel):
    dataset_id: str
    name: str | None = None
    description: str | None = None
    is_existing: bool = False
    file_count: int = 0
    total_rows: int = 0
    created_at: str
    status: str = "uploaded"  # uploaded, mapped, prepared, validated, error
    mapping_status: str = "unmapped"  # unmapped, partial, mapped
    preparation_status: str = "unprepared"  # unprepared, prepared, error


class DatasetDetail(DatasetSummary):
    files: list[FileInfo] = Field(default_factory=list)


class DatasetPreviewResponse(BaseModel):
    dataset_id: str
    file_id: str
    filename: str
    headers: list[str]
    rows: list[dict[str, Any]]
    total_rows: int
    limit: int
    offset: int


class FileSchemaDetail(BaseModel):
    file_id: str
    filename: str
    headers: list[str]
    inferred_types: dict[str, str]
    detected_schema: str | None = None
    confidence: float | None = None


class DatasetSchemaResponse(BaseModel):
    dataset_id: str
    files: list[FileSchemaDetail]


class DatasetUploadResponse(BaseModel):
    dataset_id: str
    message: str
    files: list[FileInfo]


class QualitySummaryResponse(BaseModel):
    dataset_id: str
    file_count: int
    total_rows: int
    quality_score: float  # 0 to 100
    blank_row_counts: dict[str, int]
    missing_required_counts: dict[str, int]
    duplicate_counts: dict[str, int]
    supported_analyzers: list[str]
    missing_evidence: list[str]


# ---------------------------------------------------------------------------
# Mapping and Preparation Models
# ---------------------------------------------------------------------------


class FileMappingItem(BaseModel):
    file_id: str
    schema_type: str
    column_mapping: dict[str, str] = Field(default_factory=dict)


class SetMappingRequest(BaseModel):
    mappings: list[FileMappingItem] = Field(default_factory=list)
    auto_suggest: bool = False


class FileMappingDetail(BaseModel):
    file_id: str
    filename: str
    schema_type: str
    column_mapping: dict[str, str]
    unmapped_source_columns: list[str]
    missing_required_columns: list[str]
    valid: bool
    errors: list[str] = Field(default_factory=list)


class DatasetMappingResponse(BaseModel):
    dataset_id: str
    mappings: list[FileMappingDetail]
    all_valid: bool
    auto_suggestions: dict[str, dict[str, str]] = Field(default_factory=dict)


class PreparedFileDetail(BaseModel):
    filename: str
    schema_type: str
    row_count: int
    columns: list[str]


class PreparationResponse(BaseModel):
    dataset_id: str
    status: str
    prepared_files: list[PreparedFileDetail]
    total_records: int
    review_flags: dict[str, int] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Validation Models
# ---------------------------------------------------------------------------


class FindingModel(BaseModel):
    id: str
    analyzer: str
    code: str
    classification: str = "violation"  # violation, suspicious, fact, limitation, check
    severity: str  # error, warning, info
    message: str
    row: int | None = None
    column: str | None = None
    symbol: str | None = None
    date: str | None = None
    evidence: dict[str, Any] | None = None
    limitations: list[str] | None = None
    remediation: str | None = None


class ValidationSummaryModel(BaseModel):
    status: str  # PASS, WARN, FAIL
    error_count: int
    warning_count: int
    pass_count: int
    dataset_count: int


class ValidationResponse(BaseModel):
    validation_id: str
    dataset_id: str
    status: str
    summary: ValidationSummaryModel
    findings: list[FindingModel]
    supported_analyses: list[str]
    missing_evidence: list[str]
    created_at: str


class ValidationRequest(BaseModel):
    dataset_id: str | None = None
    run_id: str | None = None
    analyzers: list[str] = Field(
        default_factory=lambda: ["survivorship", "lookahead", "corporate_actions"]
    )
    backtest: dict[str, Any] | None = None
    lookahead_config: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Analyzer Configurations and Requests
# ---------------------------------------------------------------------------


class BacktestConfigModel(BaseModel):
    target_index: str | None = None
    universe_symbols: list[str] = Field(default_factory=list)
    start_date: str | None = None
    end_date: str | None = None
    min_price_coverage: float | None = None


class LookaheadConfigModel(BaseModel):
    decision_dates: list[str] = Field(default_factory=list)
    target_index: str | None = None
    universe_symbols: list[str] = Field(default_factory=list)
    start_date: str | None = None
    end_date: str | None = None
    lookback_days: int | None = None


class SurvivorshipAnalysisRequest(BaseModel):
    dataset_id: str
    target_index: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    universe_symbols: list[str] = Field(default_factory=list)
    min_price_coverage: float | None = None


class LookaheadAnalysisRequest(BaseModel):
    dataset_id: str
    decision_dates: list[str] = Field(default_factory=list)
    target_index: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    universe_symbols: list[str] = Field(default_factory=list)
    lookback_days: int | None = None


class CorporateActionsAnalysisRequest(BaseModel):
    dataset_id: str
    expected_symbol: str | None = None


# ---------------------------------------------------------------------------
# Analysis Run Models
# ---------------------------------------------------------------------------


class AnalysisRunRequest(BaseModel):
    dataset_id: str
    analyzers: list[str] = Field(
        default_factory=lambda: ["survivorship", "lookahead", "corporate_actions"]
    )
    backtest: BacktestConfigModel | None = None
    lookahead: LookaheadConfigModel | None = None
    corporate_actions: CorporateActionsAnalysisRequest | None = None


class AnalysisRunResponse(BaseModel):
    run_id: str
    dataset_id: str
    status: str  # completed, partial_failure, failed
    created_at: str
    completed_at: str | None = None
    analyzers_requested: list[str]
    analyzers_executed: list[str]
    analyzers_skipped: list[str]
    error_count: int
    warning_count: int
    findings_count: int
    summary: dict[str, Any]
    report_id: str


# ---------------------------------------------------------------------------
# Report Models
# ---------------------------------------------------------------------------


class ReportSummaryModel(BaseModel):
    report_id: str
    run_id: str
    dataset_id: str
    created_at: str
    overall_status: str
    error_count: int
    warning_count: int
    findings_count: int
    available_formats: list[str] = Field(default_factory=lambda: ["json", "csv"])


class ReportDetailResponse(BaseModel):
    report_id: str
    run_id: str
    dataset_id: str
    created_at: str
    overall_status: str
    summary: dict[str, Any]
    analyzers: list[str]
    findings: list[FindingModel]
    limitations: list[str]
    available_formats: list[str]


# ---------------------------------------------------------------------------
# Error Response Model
# ---------------------------------------------------------------------------


class ErrorResponse(BaseModel):
    detail: str
    error_code: str | None = None
