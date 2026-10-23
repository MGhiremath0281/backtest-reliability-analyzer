/**
 * TypeScript type definitions for Backtest Reliability Analyzer (BRA) REST API.
 * Accurately matching backend Pydantic models from bra/api/models.py and OpenAPI spec.
 */

// ---------------------------------------------------------------------------
// Health & System Types
// ---------------------------------------------------------------------------

export interface HealthResponse {
  status: 'ok' | 'degraded' | string;
  app: string;
  version: string;
  storage: 'healthy' | 'storage_unavailable' | string;
  analyzers: Record<string, 'available' | string>;
}

export interface AnalyzerMetadata {
  name: string;
  label: string;
  description: string;
  supported_inputs: string[];
  supports_backtest_config: boolean;
}

export interface SchemaColumnMetadata {
  name: string;
  data_type: string;
  required: boolean;
  description: string;
  aliases: string[];
}

export interface CanonicalSchemaMetadata {
  schema_type: string;
  label: string;
  description: string;
  required_columns: string[];
  optional_columns: string[];
  date_columns: string[];
  numeric_columns: string[];
  key_columns: string[];
  columns: SchemaColumnMetadata[];
}

export interface FileHandlingMetadata {
  max_upload_size_bytes: number;
  max_upload_size_mb: number;
  supported_extensions: string[];
  supported_encodings: string[];
  csv_delimiter: string;
}

export interface ApplicationConfigMetadata {
  app_name: string;
  version: string;
  storage_mode: string;
  read_only_canonical: boolean;
}

export interface MetadataResponse {
  version: string;
  app_name: string;
  registered_analyzers: AnalyzerMetadata[];
  supported_schemas: CanonicalSchemaMetadata[];
  file_handling: FileHandlingMetadata;
  application_config: ApplicationConfigMetadata;
}

// ---------------------------------------------------------------------------
// Dataset Models
// ---------------------------------------------------------------------------

export interface FileInfo {
  file_id: string;
  original_filename: string;
  stored_filename: string;
  size_bytes: number;
  row_count: number;
  headers: string[];
  detected_schema: string | null;
  confidence: number | null;
  uploaded_at: string;
}

export interface DatasetSummary {
  dataset_id: string;
  name: string | null;
  description: string | null;
  is_existing: boolean;
  file_count: number;
  total_rows: number;
  created_at: string;
  status: 'uploaded' | 'mapped' | 'prepared' | 'ready' | 'validated' | 'error' | string;
  mapping_status: 'unmapped' | 'partial' | 'mapped' | string;
  preparation_status: 'unprepared' | 'prepared' | 'error' | string;
}

export interface DatasetDetail extends DatasetSummary {
  files: FileInfo[];
}

export interface DatasetUploadResponse {
  dataset_id: string;
  message: string;
  files: FileInfo[];
}

export interface DatasetPreviewResponse {
  dataset_id: string;
  file_id: string;
  filename: string;
  headers: string[];
  rows: Record<string, any>[];
  total_rows: number;
  limit: number;
  offset: number;
}

export interface FileSchemaDetail {
  file_id: string;
  filename: string;
  headers: string[];
  inferred_types: Record<string, string>;
  detected_schema: string | null;
  confidence: number | null;
}

export interface DatasetSchemaResponse {
  dataset_id: string;
  files: FileSchemaDetail[];
}

export interface QualitySummaryResponse {
  dataset_id: string;
  file_count: number;
  total_rows: number;
  quality_score: number; // 0 to 100
  blank_row_counts: Record<string, number>;
  missing_required_counts: Record<string, number>;
  duplicate_counts: Record<string, number>;
  supported_analyzers: string[];
  missing_evidence: string[];
}

// ---------------------------------------------------------------------------
// Mapping & Preparation Models
// ---------------------------------------------------------------------------

export interface FileMappingItem {
  file_id: string;
  schema_type: string;
  column_mapping: Record<string, string>;
}

export interface SetMappingRequest {
  mappings: FileMappingItem[];
  auto_suggest?: boolean;
}

export interface FileMappingDetail {
  file_id: string;
  filename: string;
  schema_type: string;
  column_mapping: Record<string, string>;
  unmapped_source_columns: string[];
  missing_required_columns: string[];
  valid: boolean;
  errors: string[];
}

export interface DatasetMappingResponse {
  dataset_id: string;
  mappings: FileMappingDetail[];
  all_valid: boolean;
  auto_suggestions: Record<string, Record<string, string>>;
}

export interface PreparedFileDetail {
  filename: string;
  schema_type: string;
  row_count: number;
  columns: string[];
}

export interface PreparationResponse {
  dataset_id: string;
  status: string;
  prepared_files: PreparedFileDetail[];
  total_records: number;
  review_flags: Record<string, number>;
  warnings: string[];
}

// ---------------------------------------------------------------------------
// Finding & Validation Models
// ---------------------------------------------------------------------------

export interface FindingModel {
  id: string;
  analyzer: string;
  code: string;
  classification: 'violation' | 'suspicious' | 'fact' | 'risk' | 'limitation' | 'check' | string;
  severity: 'error' | 'warning' | 'info' | string;
  message: string;
  description?: string | null;
  row?: number | null;
  column?: string | null;
  symbol?: string | null;
  date?: string | null;
  evidence?: Record<string, any> | null;
  limitations?: string[] | null;
  remediation?: string | null;
}

export interface ValidationSummaryModel {
  status: 'PASS' | 'WARN' | 'FAIL' | string;
  error_count: number;
  warning_count: number;
  pass_count: number;
  dataset_count: number;
}

export interface ValidationResponse {
  validation_id: string;
  dataset_id: string;
  status: 'PASS' | 'WARN' | 'FAIL' | string;
  summary: ValidationSummaryModel;
  findings: FindingModel[];
  supported_analyses: string[];
  missing_evidence: string[];
  created_at: string;
}

export interface ValidationRequest {
  dataset_id?: string | null;
  run_id?: string | null;
  analyzers?: string[];
  backtest?: BacktestConfigModel | null;
  lookahead_config?: LookaheadConfigModel | null;
}

// ---------------------------------------------------------------------------
// Bias Analyzer Request & Response Models
// ---------------------------------------------------------------------------

export interface BacktestConfigModel {
  target_index?: string | null;
  universe_symbols?: string[];
  start_date?: string | null;
  end_date?: string | null;
  min_price_coverage?: number | null;
}

export interface LookaheadConfigModel {
  decision_dates?: string[];
  target_index?: string | null;
  universe_symbols?: string[];
  start_date?: string | null;
  end_date?: string | null;
  lookback_days?: number | null;
}

export interface SurvivorshipAnalysisRequest {
  dataset_id: string;
  target_index?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  universe_symbols?: string[];
  min_price_coverage?: number | null;
}

export interface SurvivorshipAnalysisTriggerResponse {
  analysis_id: string;
  dataset_id: string;
  status: 'PASS' | 'WARN' | 'FAIL' | string;
  error_count: number;
  warning_count: number;
  findings_count: number;
  created_at: string;
}

export interface SurvivorshipUniverseResponse {
  analysis_id: string;
  dataset_id: string;
  membership: Record<string, any>;
  universe_coverage: Record<string, any>;
  current_listings: Record<string, any>;
  index_membership: Record<string, any>;
  universe_price_coverage: Record<string, any>;
  current_listing_snapshot: Record<string, any>;
  price_coverage: Record<string, any>;
}

export interface SurvivorshipDelistedResponse {
  analysis_id: string;
  dataset_id: string;
  delisted_coverage: Record<string, any>;
  delisted_price_coverage: Record<string, any>;
  symbol_changes: Record<string, any>;
  identifier_reuse: Record<string, any>;
  delisting_symbol_reuse: Record<string, any>;
}

export interface LookaheadAnalysisRequest {
  dataset_id: string;
  decision_dates?: string[];
  target_index?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  universe_symbols?: string[];
  lookback_days?: number | null;
}

export interface LookaheadAnalysisTriggerResponse {
  analysis_id: string;
  dataset_id: string;
  status: 'PASS' | 'WARN' | 'FAIL' | string;
  error_count: number;
  warning_count: number;
  findings_count: number;
  created_at: string;
}

export interface TimelineEvent {
  date: string;
  event_type: 'decision_date' | 'financial_publication' | 'corporate_action' | 'universe_snapshot' | string;
  symbol: string | null;
  description: string;
  classification: 'ok' | 'suspicious' | 'confirmed' | 'insufficient' | string;
  details: Record<string, any>;
}

export interface LookaheadTimelineResponse {
  analysis_id: string;
  dataset_id: string;
  event_count: number;
  events: TimelineEvent[];
  financial_publication: Record<string, any>;
  financial_revisions: Record<string, any>;
  corporate_action_timing: Record<string, any>;
  point_in_time_universe: Record<string, any>;
  price_availability: Record<string, any>;
}

export interface CorporateActionsAnalysisRequest {
  dataset_id: string;
  expected_symbol?: string | null;
}

export interface CorporateActionsTriggerResponse {
  analysis_id: string;
  dataset_id: string;
  status: 'PASS' | 'WARN' | 'FAIL' | string;
  error_count: number;
  warning_count: number;
  findings_count: number;
  created_at: string;
}

export interface CorporateActionsCoverageResponse {
  analysis_id: string;
  dataset_id: string;
  coverage: number | null;
  by_symbol: Record<string, number>;
  by_purpose: Record<string, number>;
  by_series: Record<string, number>;
  duplicate_records: number;
}

// ---------------------------------------------------------------------------
// Combined Analysis Runs Models
// ---------------------------------------------------------------------------

export interface AnalysisRunRequest {
  dataset_id: string;
  analyzers?: string[];
  backtest?: BacktestConfigModel | null;
  lookahead?: LookaheadConfigModel | null;
  corporate_actions?: CorporateActionsAnalysisRequest | null;
}

export interface RunSummaryMetrics {
  overall_status: 'PASS' | 'WARN' | 'FAIL' | string;
  total_analyzers: number;
  executed_count: number;
  skipped_count: number;
  error_count: number;
  warning_count: number;
  findings_count: number;
  by_analyzer: Record<string, {
    status: string;
    errors: number;
    warnings: number;
  }>;
}

export interface AnalysisRunResponse {
  run_id: string;
  dataset_id: string;
  status: 'completed' | 'partial_failure' | 'failed' | string;
  created_at: string;
  completed_at: string | null;
  analyzers_requested: string[];
  analyzers_executed: string[];
  analyzers_skipped: string[];
  error_count: number;
  warning_count: number;
  findings_count: number;
  summary: RunSummaryMetrics;
  report_id: string;
}

export interface RunListItem {
  run_id: string;
  dataset_id: string;
  status: string;
  created_at: string;
  completed_at?: string | null;
  analyzers_executed: string[];
  findings_count: number;
  report_id?: string;
}

export interface RunEvent {
  timestamp: string;
  event: string;
  run_id?: string;
  [key: string]: any;
}

export interface AnalysisRunDetail extends AnalysisRunResponse {
  analyzer_results: Record<string, any>;
  findings: FindingModel[];
  limitations: string[];
  events: RunEvent[];
}

export interface CancelRunResponse {
  run_id: string;
  status: string;
  cancellable: boolean;
  message: string;
}

// ---------------------------------------------------------------------------
// Reports & Exports Models
// ---------------------------------------------------------------------------

export interface ReportSummaryModel {
  report_id: string;
  run_id: string;
  dataset_id: string;
  created_at: string;
  overall_status: 'PASS' | 'WARN' | 'FAIL' | string;
  error_count: number;
  warning_count: number;
  available_formats: string[];
}

export interface ReportDetailResponse {
  report_id: string;
  run_id: string;
  dataset_id: string;
  created_at: string;
  overall_status: string;
  summary: RunSummaryMetrics | Record<string, any>;
  analyzers: string[];
  findings: FindingModel[];
  limitations: string[];
  available_formats: string[];
}

// ---------------------------------------------------------------------------
// Error Response Models
// ---------------------------------------------------------------------------

export interface ApiErrorDetail {
  detail: string;
  errors?: Array<{
    loc: (string | number)[];
    msg: string;
    type: string;
  }>;
}
