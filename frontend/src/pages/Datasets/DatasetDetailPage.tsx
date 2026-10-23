import React, { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  useDatasetDetail,
  useDatasetPreview,
  useDatasetSchema,
  useDatasetQualitySummary,
  useDatasetPreparation,
  usePrepareDataset,
} from '../../hooks/useDatasets';
import { useValidateDataset } from '../../hooks/useValidations';
import { Button } from '../../components/common/Button';
import { Card } from '../../components/common/Card';
import { Badge } from '../../components/common/Badge';
import { LoadingSpinner } from '../../components/common/LoadingSpinner';
import { ErrorAlert } from '../../components/common/ErrorAlert';
import { ColumnMappingModal } from './ColumnMappingModal';
import {
  Sliders,
  CheckCircle2,
  Sparkles,
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { formatApiError } from '../../api/client';

export const DatasetDetailPage: React.FC = () => {
  const { id: datasetId } = useParams<{ id: string }>();

  const [activeTab, setActiveTab] = useState<'files' | 'preview' | 'schema' | 'prep' | 'quality'>('files');
  const [selectedFileId, setSelectedFileId] = useState<string>('');
  const [previewOffset, setPreviewOffset] = useState<number>(0);
  const [previewLimit] = useState<number>(25);
  const [isMappingModalOpen, setIsMappingModalOpen] = useState(false);
  const [actionMessage, setActionMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const { data: dataset, isLoading, isError, error, refetch } = useDatasetDetail(datasetId);

  // Schema query
  const { data: schemaData, isLoading: isSchemaLoading } = useDatasetSchema(datasetId);

  // Quality query
  const { data: qualityData, isLoading: isQualityLoading } = useDatasetQualitySummary(datasetId);

  // Preparation query
  const { data: prepData, isLoading: isPrepLoading, refetch: refetchPrep } = useDatasetPreparation(datasetId);

  // Preview query
  const effectiveFileId = selectedFileId || (dataset?.files?.[0]?.file_id ?? '');
  const { data: previewData, isLoading: isPreviewLoading } = useDatasetPreview(datasetId, {
    file_id: effectiveFileId || undefined,
    limit: previewLimit,
    offset: previewOffset,
  });

  const validateMutation = useValidateDataset();
  const prepareMutation = usePrepareDataset();

  if (isLoading) {
    return <LoadingSpinner label="Loading dataset profile..." fullHeight />;
  }

  if (isError || !dataset) {
    return (
      <div className="space-y-4">
        <Link to="/datasets" className="inline-flex items-center gap-1.5 text-xs font-mono font-bold hover:underline">
          <ArrowLeft className="w-3.5 h-3.5" /> Back to Datasets
        </Link>
        <ErrorAlert
          title="Dataset Not Found"
          message={formatApiError(error) || `Could not find dataset with ID "${datasetId}".`}
          onRetry={() => refetch()}
        />
      </div>
    );
  }

  const handleRunValidation = async () => {
    setActionMessage(null);
    try {
      const res = await validateMutation.mutateAsync(dataset.dataset_id);
      setActionMessage({
        type: 'success',
        text: `Validation completed with status ${res.status}. Error count: ${res.summary.error_count}, Warnings: ${res.summary.warning_count}.`,
      });
    } catch (err) {
      setActionMessage({ type: 'error', text: formatApiError(err) });
    }
  };

  const handleRunPreparation = async () => {
    setActionMessage(null);
    try {
      const res = await prepareMutation.mutateAsync(dataset.dataset_id);
      setActionMessage({
        type: 'success',
        text: `Normalization successful! ${res.prepared_files.length} canonical table(s) generated with ${res.total_records} total records.`,
      });
      refetchPrep();
    } catch (err) {
      setActionMessage({ type: 'error', text: formatApiError(err) });
    }
  };

  return (
    <div className="space-y-6">
      {/* Back button */}
      <div>
        <Link
          to="/datasets"
          className="inline-flex items-center gap-1.5 text-xs font-mono font-bold text-zinc-600 hover:text-black hover:underline"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Back to Datasets Inventory
        </Link>
      </div>

      {/* Top Profile Header */}
      <div className="border border-black bg-white p-6 shadow-[3px_3px_0px_0px_#000000]">
        <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
          <div className="space-y-2">
            <div className="flex items-center gap-2 flex-wrap">
              <Badge variant={dataset.is_existing ? 'blue' : 'neutral'}>
                {dataset.is_existing ? 'CANONICAL REPOSITORY' : 'USER UPLOADED'}
              </Badge>
              <Badge variant={dataset.preparation_status === 'prepared' ? 'pass' : 'warn'}>
                PREP: {dataset.preparation_status}
              </Badge>
              <span className="text-xs font-mono text-zinc-500">ID: {dataset.dataset_id}</span>
            </div>

            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-black">
              {dataset.name || dataset.dataset_id}
            </h1>

            <p className="text-xs sm:text-sm text-zinc-600 max-w-2xl">
              {dataset.description || 'No description provided.'}
            </p>
          </div>

          {/* Action Buttons */}
          <div className="flex flex-wrap items-center gap-2 shrink-0">
            <Button
              variant="white"
              size="sm"
              onClick={() => setIsMappingModalOpen(true)}
              icon={<Sliders className="w-3.5 h-3.5" />}
            >
              EDIT MAPPINGS
            </Button>
            <Button
              variant="white"
              size="sm"
              onClick={handleRunPreparation}
              isLoading={prepareMutation.isPending}
              icon={<Sparkles className="w-3.5 h-3.5 text-[#ff3b30]" />}
            >
              PREPARE WORKING DATA
            </Button>
            <Button
              variant="black"
              size="sm"
              onClick={handleRunValidation}
              isLoading={validateMutation.isPending}
              icon={<CheckCircle2 className="w-3.5 h-3.5" />}
            >
              VALIDATE DATASET
            </Button>
          </div>
        </div>

        {/* Action notification feedback */}
        {actionMessage && (
          <div
            className={`mt-4 p-3 border font-mono text-xs flex items-center justify-between ${
              actionMessage.type === 'success'
                ? 'bg-[#dcfce7] border-[#16a34a] text-[#14532d]'
                : 'bg-[#fee2e2] border-[#dc2626] text-[#7f1d1d]'
            }`}
          >
            <span>{actionMessage.text}</span>
            <button
              onClick={() => setActionMessage(null)}
              className="font-bold underline ml-2 cursor-pointer"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Quick Metrics Strip */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-6 pt-5 border-t border-zinc-200 text-xs font-mono">
          <div>
            <span className="text-[10px] text-zinc-400 block uppercase">Total Files</span>
            <span className="font-bold text-black text-sm">{dataset.file_count}</span>
          </div>
          <div>
            <span className="text-[10px] text-zinc-400 block uppercase">Total Rows</span>
            <span className="font-bold text-black text-sm">
              {dataset.total_rows > 0 ? dataset.total_rows.toLocaleString() : 'Tree'}
            </span>
          </div>
          <div>
            <span className="text-[10px] text-zinc-400 block uppercase">Mapping Status</span>
            <span className="font-bold text-black text-sm uppercase">{dataset.mapping_status}</span>
          </div>
          <div>
            <span className="text-[10px] text-zinc-400 block uppercase">Created At</span>
            <span className="font-bold text-black text-sm">
              {dataset.created_at ? dataset.created_at.split('T')[0] : 'Canonical'}
            </span>
          </div>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex items-center gap-1 border-b border-black text-xs font-mono font-bold uppercase overflow-x-auto">
        <button
          onClick={() => setActiveTab('files')}
          className={`px-4 py-2.5 border-t border-x transition-colors cursor-pointer whitespace-nowrap ${
            activeTab === 'files'
              ? 'bg-black text-white border-black'
              : 'bg-white text-zinc-700 border-transparent hover:border-black'
          }`}
        >
          Files Inventory ({dataset.files?.length || 0})
        </button>

        <button
          onClick={() => setActiveTab('preview')}
          className={`px-4 py-2.5 border-t border-x transition-colors cursor-pointer whitespace-nowrap ${
            activeTab === 'preview'
              ? 'bg-black text-white border-black'
              : 'bg-white text-zinc-700 border-transparent hover:border-black'
          }`}
        >
          Row Preview
        </button>

        <button
          onClick={() => setActiveTab('schema')}
          className={`px-4 py-2.5 border-t border-x transition-colors cursor-pointer whitespace-nowrap ${
            activeTab === 'schema'
              ? 'bg-black text-white border-black'
              : 'bg-white text-zinc-700 border-transparent hover:border-black'
          }`}
        >
          Inferred Schema
        </button>

        <button
          onClick={() => setActiveTab('prep')}
          className={`px-4 py-2.5 border-t border-x transition-colors cursor-pointer whitespace-nowrap ${
            activeTab === 'prep'
              ? 'bg-black text-white border-black'
              : 'bg-white text-zinc-700 border-transparent hover:border-black'
          }`}
        >
          Prepared Normalization
        </button>

        <button
          onClick={() => setActiveTab('quality')}
          className={`px-4 py-2.5 border-t border-x transition-colors cursor-pointer whitespace-nowrap ${
            activeTab === 'quality'
              ? 'bg-black text-white border-black'
              : 'bg-white text-zinc-700 border-transparent hover:border-black'
          }`}
        >
          Quality Summary
        </button>
      </div>

      {/* Tab 1: Files Inventory */}
      {activeTab === 'files' && (
        <Card tag="FILE STORAGE" title="Registered CSV Files">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono border-collapse">
              <thead>
                <tr className="bg-zinc-50 border-b border-black">
                  <th className="py-2.5 px-4 font-bold text-black uppercase">Original Filename</th>
                  <th className="py-2.5 px-4 font-bold text-black uppercase">Stored Name / ID</th>
                  <th className="py-2.5 px-4 font-bold text-black uppercase">Detected Schema</th>
                  <th className="py-2.5 px-4 font-bold text-black uppercase text-right">Row Count</th>
                  <th className="py-2.5 px-4 font-bold text-black uppercase text-right">Size</th>
                  <th className="py-2.5 px-4 font-bold text-black uppercase text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-200">
                {dataset.files?.map((file) => (
                  <tr key={file.file_id} className="hover:bg-zinc-50">
                    <td className="py-2.5 px-4 font-bold text-black truncate max-w-xs">
                      {file.original_filename}
                    </td>
                    <td className="py-2.5 px-4 text-zinc-500 truncate max-w-xs">
                      {file.file_id}
                    </td>
                    <td className="py-2.5 px-4">
                      {file.detected_schema ? (
                        <Badge variant="blue" size="sm">
                          {file.detected_schema}
                        </Badge>
                      ) : (
                        <span className="text-zinc-400">Unclassified</span>
                      )}
                    </td>
                    <td className="py-2.5 px-4 text-right font-bold text-black">
                      {file.row_count > 0 ? file.row_count.toLocaleString() : '—'}
                    </td>
                    <td className="py-2.5 px-4 text-right text-zinc-600">
                      {(file.size_bytes / 1024).toFixed(1)} KB
                    </td>
                    <td className="py-2.5 px-4 text-right">
                      <button
                        type="button"
                        onClick={() => {
                          setSelectedFileId(file.file_id);
                          setPreviewOffset(0);
                          setActiveTab('preview');
                        }}
                        className="text-xs font-bold text-[#ff3b30] hover:underline cursor-pointer"
                      >
                        Preview ↗
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Tab 2: Row Preview */}
      {activeTab === 'preview' && (
        <Card
          tag="DATA PREVIEW"
          title="Sample Data Inspection"
          subtitle="Direct sample rows queried from the backend storage"
          action={
            dataset.files?.length > 1 ? (
              <select
                value={effectiveFileId}
                onChange={(e) => {
                  setSelectedFileId(e.target.value);
                  setPreviewOffset(0);
                }}
                className="text-xs font-mono p-1.5 bg-white border border-black focus:outline-none"
              >
                {dataset.files.map((f) => (
                  <option key={f.file_id} value={f.file_id}>
                    {f.original_filename}
                  </option>
                ))}
              </select>
            ) : null
          }
        >
          {isPreviewLoading ? (
            <LoadingSpinner label="Fetching row preview..." />
          ) : !previewData || !previewData.rows || previewData.rows.length === 0 ? (
            <div className="py-8 text-center font-mono text-xs text-zinc-500">
              No preview rows available for this file.
            </div>
          ) : (
            <div className="space-y-4">
              <div className="overflow-x-auto border border-black">
                <table className="w-full text-left text-xs font-mono">
                  <thead>
                    <tr className="bg-zinc-100 border-b border-black">
                      <th className="py-2 px-3 font-bold text-zinc-400 text-center w-12">#</th>
                      {previewData.headers.map((h) => (
                        <th key={h} className="py-2 px-3 font-bold text-black whitespace-nowrap">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-200">
                    {previewData.rows.map((row, rIdx) => (
                      <tr key={rIdx} className="hover:bg-zinc-50">
                        <td className="py-1.5 px-3 text-center text-zinc-400 font-bold text-[10px]">
                          {previewOffset + rIdx + 1}
                        </td>
                        {previewData.headers.map((h) => (
                          <td key={h} className="py-1.5 px-3 text-zinc-800 whitespace-nowrap">
                            {row[h] !== null && row[h] !== undefined ? String(row[h]) : ''}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Preview Pagination */}
              <div className="flex items-center justify-between text-xs font-mono pt-2">
                <div className="text-zinc-500">
                  Showing rows <span className="font-bold text-black">{previewOffset + 1}</span> to{' '}
                  <span className="font-bold text-black">
                    {Math.min(previewOffset + previewLimit, previewData.total_rows)}
                  </span>{' '}
                  of <span className="font-bold text-black">{previewData.total_rows}</span>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="white"
                    size="sm"
                    disabled={previewOffset === 0}
                    onClick={() => setPreviewOffset((prev) => Math.max(0, prev - previewLimit))}
                    icon={<ChevronLeft className="w-3 h-3" />}
                  >
                    PREV
                  </Button>
                  <Button
                    variant="white"
                    size="sm"
                    disabled={previewOffset + previewLimit >= previewData.total_rows}
                    onClick={() => setPreviewOffset((prev) => prev + previewLimit)}
                    icon={<ChevronRight className="w-3 h-3" />}
                  >
                    NEXT
                  </Button>
                </div>
              </div>
            </div>
          )}
        </Card>
      )}

      {/* Tab 3: Schema & Inferred Types */}
      {activeTab === 'schema' && (
        <Card tag="SCHEMA INFERENCE" title="Column Headers & Detected Data Types">
          {isSchemaLoading ? (
            <LoadingSpinner label="Analyzing column data types..." />
          ) : !schemaData?.files || schemaData.files.length === 0 ? (
            <div className="py-8 text-center font-mono text-xs text-zinc-500">
              No schema information inferred.
            </div>
          ) : (
            <div className="space-y-6">
              {schemaData.files.map((fileSchema) => (
                <div key={fileSchema.file_id} className="space-y-3">
                  <div className="flex items-center justify-between bg-zinc-50 p-2.5 border border-black font-mono text-xs">
                    <span className="font-bold text-black">{fileSchema.filename}</span>
                    <Badge variant="blue">
                      SCHEMA: {fileSchema.detected_schema || 'Custom'} ({((fileSchema.confidence || 1) * 100).toFixed(0)}% MATCH)
                    </Badge>
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
                    {fileSchema.headers.map((h) => {
                      const inferredType = fileSchema.inferred_types[h] || 'string';
                      return (
                        <div key={h} className="p-2 border border-zinc-200 bg-white font-mono text-xs">
                          <span className="text-[10px] text-zinc-400 block uppercase font-bold">{inferredType}</span>
                          <span className="font-bold text-black truncate block" title={h}>{h}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* Tab 4: Prepared Normalization */}
      {activeTab === 'prep' && (
        <Card
          tag="NORMALIZED WORKING DATA"
          title="Canonical Preparation Artifacts"
          subtitle="Normalized tables ready for bias analyzers in storage/prepared/"
          action={
            <Button
              variant="black"
              size="sm"
              onClick={handleRunPreparation}
              isLoading={prepareMutation.isPending}
            >
              RUN PREPARATION NOW
            </Button>
          }
        >
          {isPrepLoading ? (
            <LoadingSpinner label="Checking prepared status..." />
          ) : !prepData || prepData.prepared_files.length === 0 ? (
            <div className="py-8 text-center font-mono text-xs text-zinc-500 border border-dashed border-zinc-200">
              Dataset has not been prepared yet. Click "Run Preparation Now" above to normalize tables.
            </div>
          ) : (
            <div className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {prepData.prepared_files.map((pf) => (
                  <div key={pf.filename} className="p-4 border border-black bg-zinc-50 font-mono text-xs space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-black text-sm">{pf.filename}</span>
                      <Badge variant="pass">{pf.schema_type}</Badge>
                    </div>
                    <div className="text-zinc-600">
                      Total Records: <span className="font-bold text-black">{pf.row_count.toLocaleString()}</span>
                    </div>
                    <div>
                      <span className="text-[10px] text-zinc-400 uppercase font-bold block mb-1">Normalized Columns:</span>
                      <div className="flex flex-wrap gap-1">
                        {pf.columns.map((c) => (
                          <span key={c} className="px-1.5 py-0.5 bg-white border border-zinc-300 text-[10px]">
                            {c}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Card>
      )}

      {/* Tab 5: Quality Summary */}
      {activeTab === 'quality' && (
        <Card tag="QUALITY AUDIT" title="Dataset Health & Verification Score">
          {isQualityLoading ? (
            <LoadingSpinner label="Calculating quality score..." />
          ) : !qualityData ? (
            <div className="py-8 text-center font-mono text-xs text-zinc-500">
              No quality summary generated yet.
            </div>
          ) : (
            <div className="space-y-6">
              {/* Score Gauge Strip */}
              <div className="p-6 border border-black bg-zinc-50 flex flex-col sm:flex-row items-center justify-between gap-6">
                <div>
                  <div className="text-xs font-mono font-bold uppercase tracking-wider text-zinc-500">
                    Data Quality Score
                  </div>
                  <div className="text-4xl sm:text-5xl font-bold font-mono text-black mt-1">
                    {qualityData.quality_score.toFixed(1)} / 100
                  </div>
                  <p className="text-xs text-zinc-600 mt-1 font-mono">
                    Deterministic score auditing duplicate rows, blank values, and missing required headers.
                  </p>
                </div>

                <div className="w-32 h-32 rounded-full border-4 border-black flex items-center justify-center font-mono font-bold text-2xl bg-white shadow-[3px_3px_0px_0px_#000000]">
                  <span className={qualityData.quality_score >= 80 ? 'text-[#16a34a]' : 'text-[#ff3b30]'}>
                    {qualityData.quality_score >= 80 ? 'PASS' : 'REVIEW'}
                  </span>
                </div>
              </div>

              {/* Supported Analyzers List */}
              <div className="space-y-2">
                <div className="text-xs font-mono font-bold uppercase text-black">
                  Supported Analyzers For This Dataset:
                </div>
                <div className="flex flex-wrap gap-2">
                  {qualityData.supported_analyzers?.map((a) => (
                    <Badge key={a} variant="pass" size="md">
                      ✓ {a.replace(/_/g, ' ')}
                    </Badge>
                  ))}
                  {qualityData.missing_evidence?.map((m) => (
                    <Badge key={m} variant="warn" size="md">
                      Missing: {m}
                    </Badge>
                  ))}
                </div>
              </div>
            </div>
          )}
        </Card>
      )}

      {/* Column Mapping Modal */}
      <ColumnMappingModal
        datasetId={dataset.dataset_id}
        isOpen={isMappingModalOpen}
        onClose={() => setIsMappingModalOpen(false)}
        onSuccess={() => {
          refetch();
          refetchPrep();
        }}
      />
    </div>
  );
};
