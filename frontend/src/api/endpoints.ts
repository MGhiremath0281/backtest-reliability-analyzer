import { apiClient, API_BASE_URL } from './client';
import * as T from './types';

// ===========================================================================
// 1. Health & System
// ===========================================================================

export async function getRootHealth(): Promise<T.HealthResponse> {
  const res = await apiClient.get<T.HealthResponse>('/health');
  return res.data;
}

export async function getV1Health(): Promise<T.HealthResponse> {
  const res = await apiClient.get<T.HealthResponse>('/api/v1/health');
  return res.data;
}

export async function getMetadata(): Promise<T.MetadataResponse> {
  const res = await apiClient.get<T.MetadataResponse>('/api/v1/metadata');
  return res.data;
}

// ===========================================================================
// 2. Dataset Management
// ===========================================================================

export async function listDatasets(params?: {
  include_existing?: boolean;
  limit?: number;
  offset?: number;
}): Promise<T.DatasetSummary[]> {
  const res = await apiClient.get<T.DatasetSummary[]>('/api/v1/datasets', { params });
  return res.data;
}

export async function getDataset(datasetId: string): Promise<T.DatasetDetail> {
  const res = await apiClient.get<T.DatasetDetail>(`/api/v1/datasets/${encodeURIComponent(datasetId)}`);
  return res.data;
}

export async function uploadDataset(
  files: File[],
  meta?: { name?: string; description?: string }
): Promise<T.DatasetUploadResponse> {
  const formData = new FormData();
  files.forEach((f) => formData.append('files', f));
  if (meta?.name) formData.append('name', meta.name);
  if (meta?.description) formData.append('description', meta.description);

  const res = await apiClient.post<T.DatasetUploadResponse>('/api/v1/datasets/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return res.data;
}

export async function deleteDataset(datasetId: string): Promise<{ message: string }> {
  const res = await apiClient.delete<{ message: string }>(`/api/v1/datasets/${encodeURIComponent(datasetId)}`);
  return res.data;
}

export async function requestDatasetDeletion(datasetId: string): Promise<{ message: string }> {
  const res = await apiClient.post<{ message: string }>(`/api/v1/datasets/${encodeURIComponent(datasetId)}/delete-request`);
  return res.data;
}

export async function previewDataset(
  datasetId: string,
  params?: { file_id?: string; limit?: number; offset?: number }
): Promise<T.DatasetPreviewResponse> {
  const res = await apiClient.get<T.DatasetPreviewResponse>(
    `/api/v1/datasets/${encodeURIComponent(datasetId)}/preview`,
    { params }
  );
  return res.data;
}

export async function getDatasetSchema(datasetId: string): Promise<T.DatasetSchemaResponse> {
  const res = await apiClient.get<T.DatasetSchemaResponse>(
    `/api/v1/datasets/${encodeURIComponent(datasetId)}/schema`
  );
  return res.data;
}

export async function validateDataset(datasetId: string): Promise<T.ValidationResponse> {
  const res = await apiClient.post<T.ValidationResponse>(
    `/api/v1/datasets/${encodeURIComponent(datasetId)}/validate`
  );
  return res.data;
}

export async function getDatasetValidation(datasetId: string): Promise<T.ValidationResponse> {
  const res = await apiClient.get<T.ValidationResponse>(
    `/api/v1/datasets/${encodeURIComponent(datasetId)}/validation`
  );
  return res.data;
}

export async function getDatasetQualitySummary(datasetId: string): Promise<T.QualitySummaryResponse> {
  const res = await apiClient.get<T.QualitySummaryResponse>(
    `/api/v1/datasets/${encodeURIComponent(datasetId)}/quality-summary`
  );
  return res.data;
}

// ===========================================================================
// 3. Schema Mapping & Preparation
// ===========================================================================

export async function listSchemas(): Promise<T.CanonicalSchemaMetadata[]> {
  const res = await apiClient.get<T.CanonicalSchemaMetadata[]>('/api/v1/schemas');
  return res.data;
}

export async function getSchema(schemaType: string): Promise<T.CanonicalSchemaMetadata> {
  const res = await apiClient.get<T.CanonicalSchemaMetadata>(
    `/api/v1/schemas/${encodeURIComponent(schemaType)}`
  );
  return res.data;
}

export async function getDatasetMapping(datasetId: string): Promise<T.DatasetMappingResponse> {
  const res = await apiClient.get<T.DatasetMappingResponse>(
    `/api/v1/datasets/${encodeURIComponent(datasetId)}/mapping`
  );
  return res.data;
}

export async function setDatasetMapping(
  datasetId: string,
  payload: T.SetMappingRequest
): Promise<T.DatasetMappingResponse> {
  const res = await apiClient.post<T.DatasetMappingResponse>(
    `/api/v1/datasets/${encodeURIComponent(datasetId)}/mapping`,
    payload
  );
  return res.data;
}

export async function prepareDataset(datasetId: string): Promise<T.PreparationResponse> {
  const res = await apiClient.post<T.PreparationResponse>(
    `/api/v1/datasets/${encodeURIComponent(datasetId)}/prepare`
  );
  return res.data;
}

export async function getDatasetPreparation(datasetId: string): Promise<T.PreparationResponse> {
  const res = await apiClient.get<T.PreparationResponse>(
    `/api/v1/datasets/${encodeURIComponent(datasetId)}/preparation`
  );
  return res.data;
}

// ===========================================================================
// 4. General Validation
// ===========================================================================

export async function executeValidation(payload: T.ValidationRequest): Promise<T.ValidationResponse> {
  const res = await apiClient.post<T.ValidationResponse>('/api/v1/validate', payload);
  return res.data;
}

export async function getValidation(validationId: string): Promise<T.ValidationResponse> {
  const res = await apiClient.get<T.ValidationResponse>(
    `/api/v1/validations/${encodeURIComponent(validationId)}`
  );
  return res.data;
}

export async function getValidationFindings(
  validationId: string,
  params?: { severity?: string; analyzer?: string; limit?: number; offset?: number }
): Promise<T.FindingModel[]> {
  const res = await apiClient.get<T.FindingModel[]>(
    `/api/v1/validations/${encodeURIComponent(validationId)}/findings`,
    { params }
  );
  return res.data;
}

export async function getValidationSummary(validationId: string): Promise<T.ValidationSummaryModel> {
  const res = await apiClient.get<T.ValidationSummaryModel>(
    `/api/v1/validations/${encodeURIComponent(validationId)}/summary`
  );
  return res.data;
}

// ===========================================================================
// 5. Survivorship Bias Analyzer
// ===========================================================================

export async function triggerSurvivorshipAnalysis(
  payload: T.SurvivorshipAnalysisRequest
): Promise<T.SurvivorshipAnalysisTriggerResponse> {
  const res = await apiClient.post<T.SurvivorshipAnalysisTriggerResponse>(
    '/api/v1/analyze/survivorship',
    payload
  );
  return res.data;
}

export async function getSurvivorshipAnalysis(analysisId: string): Promise<Record<string, any>> {
  const res = await apiClient.get<Record<string, any>>(
    `/api/v1/analyze/survivorship/${encodeURIComponent(analysisId)}`
  );
  return res.data;
}

export async function getSurvivorshipUniverse(analysisId: string): Promise<T.SurvivorshipUniverseResponse> {
  const res = await apiClient.get<T.SurvivorshipUniverseResponse>(
    `/api/v1/analyze/survivorship/${encodeURIComponent(analysisId)}/universe`
  );
  return res.data;
}

export async function getSurvivorshipDelisted(analysisId: string): Promise<T.SurvivorshipDelistedResponse> {
  const res = await apiClient.get<T.SurvivorshipDelistedResponse>(
    `/api/v1/analyze/survivorship/${encodeURIComponent(analysisId)}/delisted`
  );
  return res.data;
}

export async function getSurvivorshipFindings(
  analysisId: string,
  params?: { severity?: string; kind?: string; limit?: number; offset?: number }
): Promise<T.FindingModel[]> {
  const res = await apiClient.get<T.FindingModel[]>(
    `/api/v1/analyze/survivorship/${encodeURIComponent(analysisId)}/findings`,
    { params }
  );
  return res.data;
}

// ===========================================================================
// 6. Look-Ahead Bias Analyzer
// ===========================================================================

export async function triggerLookaheadAnalysis(
  payload: T.LookaheadAnalysisRequest
): Promise<T.LookaheadAnalysisTriggerResponse> {
  const res = await apiClient.post<T.LookaheadAnalysisTriggerResponse>(
    '/api/v1/analyze/lookahead',
    payload
  );
  return res.data;
}

export async function getLookaheadAnalysis(analysisId: string): Promise<Record<string, any>> {
  const res = await apiClient.get<Record<string, any>>(
    `/api/v1/analyze/lookahead/${encodeURIComponent(analysisId)}`
  );
  return res.data;
}

export async function getLookaheadFindings(
  analysisId: string,
  params?: { severity?: string; classification?: string; limit?: number; offset?: number }
): Promise<T.FindingModel[]> {
  const res = await apiClient.get<T.FindingModel[]>(
    `/api/v1/analyze/lookahead/${encodeURIComponent(analysisId)}/findings`,
    { params }
  );
  return res.data;
}

export async function getLookaheadTimeline(analysisId: string): Promise<T.LookaheadTimelineResponse> {
  const res = await apiClient.get<T.LookaheadTimelineResponse>(
    `/api/v1/analyze/lookahead/${encodeURIComponent(analysisId)}/timeline`
  );
  return res.data;
}

// ===========================================================================
// 7. Corporate Actions Analyzer
// ===========================================================================

export async function triggerCorporateActionsAnalysis(
  payload: T.CorporateActionsAnalysisRequest
): Promise<T.CorporateActionsTriggerResponse> {
  const res = await apiClient.post<T.CorporateActionsTriggerResponse>(
    '/api/v1/analyze/corporate-actions',
    payload
  );
  return res.data;
}

export async function getCorporateActionsAnalysis(analysisId: string): Promise<Record<string, any>> {
  const res = await apiClient.get<Record<string, any>>(
    `/api/v1/analyze/corporate-actions/${encodeURIComponent(analysisId)}`
  );
  return res.data;
}

export async function getCorporateActionsFindings(
  analysisId: string,
  params?: { severity?: string; code?: string; limit?: number; offset?: number }
): Promise<T.FindingModel[]> {
  const res = await apiClient.get<T.FindingModel[]>(
    `/api/v1/analyze/corporate-actions/${encodeURIComponent(analysisId)}/findings`,
    { params }
  );
  return res.data;
}

export async function getCorporateActionsCoverage(analysisId: string): Promise<T.CorporateActionsCoverageResponse> {
  const res = await apiClient.get<T.CorporateActionsCoverageResponse>(
    `/api/v1/analyze/corporate-actions/${encodeURIComponent(analysisId)}/coverage`
  );
  return res.data;
}

// ===========================================================================
// 8. Analysis Runs
// ===========================================================================

export async function createAnalysisRun(payload: T.AnalysisRunRequest): Promise<T.AnalysisRunResponse> {
  const res = await apiClient.post<T.AnalysisRunResponse>('/api/v1/analysis-runs', payload);
  return res.data;
}

export async function listAnalysisRuns(params?: {
  dataset_id?: string;
  limit?: number;
  offset?: number;
}): Promise<T.RunListItem[]> {
  const res = await apiClient.get<T.RunListItem[]>('/api/v1/analysis-runs', { params });
  return res.data;
}

export async function getAnalysisRun(runId: string): Promise<T.AnalysisRunDetail> {
  const res = await apiClient.get<T.AnalysisRunDetail>(
    `/api/v1/analysis-runs/${encodeURIComponent(runId)}`
  );
  return res.data;
}

export async function getAnalysisRunFindings(
  runId: string,
  params?: { severity?: string; analyzer?: string; limit?: number; offset?: number }
): Promise<T.FindingModel[]> {
  const res = await apiClient.get<T.FindingModel[]>(
    `/api/v1/analysis-runs/${encodeURIComponent(runId)}/findings`,
    { params }
  );
  return res.data;
}

export async function getAnalysisRunSummary(runId: string): Promise<T.RunSummaryMetrics> {
  const res = await apiClient.get<T.RunSummaryMetrics>(
    `/api/v1/analysis-runs/${encodeURIComponent(runId)}/summary`
  );
  return res.data;
}

export async function cancelAnalysisRun(runId: string): Promise<T.CancelRunResponse> {
  const res = await apiClient.post<T.CancelRunResponse>(
    `/api/v1/analysis-runs/${encodeURIComponent(runId)}/cancel`
  );
  return res.data;
}

export async function getAnalysisRunEvents(runId: string): Promise<T.RunEvent[]> {
  const res = await apiClient.get<T.RunEvent[]>(
    `/api/v1/analysis-runs/${encodeURIComponent(runId)}/events`
  );
  return res.data;
}

// ===========================================================================
// 9. Reports & Exports
// ===========================================================================

export async function listReports(params?: {
  limit?: number;
  offset?: number;
}): Promise<T.ReportSummaryModel[]> {
  const res = await apiClient.get<T.ReportSummaryModel[]>('/api/v1/reports', { params });
  return res.data;
}

export async function getReport(reportId: string): Promise<T.ReportDetailResponse> {
  const res = await apiClient.get<T.ReportDetailResponse>(
    `/api/v1/reports/${encodeURIComponent(reportId)}`
  );
  return res.data;
}

/**
 * Returns direct download URL for a report in given format (json, csv, pdf, xlsx).
 */
export function getReportDownloadUrl(reportId: string, format: string = 'json'): string {
  return `${API_BASE_URL}/api/v1/reports/${encodeURIComponent(reportId)}/download?format=${encodeURIComponent(format)}`;
}

/**
 * Downloads report as a file blob and triggers browser download.
 */
export async function downloadReportFile(reportId: string, format: 'json' | 'csv' | 'pdf' | 'xlsx'): Promise<void> {
  const response = await apiClient.get(`/api/v1/reports/${encodeURIComponent(reportId)}/download`, {
    params: { format },
    responseType: 'blob',
  });

  const blob = new Blob([response.data], {
    type: format === 'pdf' ? 'application/pdf' : format === 'csv' ? 'text/csv' : 'application/json',
  });
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `report_${reportId}.${format}`;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
}
