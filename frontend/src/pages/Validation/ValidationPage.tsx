import React, { useState } from 'react';
import { useDatasets } from '../../hooks/useDatasets';
import { useExecuteValidation } from '../../hooks/useValidations';
import { Button } from '../../components/common/Button';
import { Card } from '../../components/common/Card';
import { Badge } from '../../components/common/Badge';
import { LoadingSpinner } from '../../components/common/LoadingSpinner';
import { ErrorAlert } from '../../components/common/ErrorAlert';
import { ValidationResponse, FindingModel } from '../../api/types';
import { formatApiError } from '../../api/client';
import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Play,
  Filter,
  Search,
  FileCheck,
} from 'lucide-react';

export const ValidationPage: React.FC = () => {
  const { data: datasets, isLoading: isDatasetsLoading } = useDatasets({ include_existing: true });

  const [selectedDatasetId, setSelectedDatasetId] = useState<string>('existing-data');
  const [selectedAnalyzers, setSelectedAnalyzers] = useState<string[]>([
    'survivorship',
    'lookahead',
    'corporate_actions',
  ]);
  const [result, setResult] = useState<ValidationResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Findings table filters
  const [severityFilter, setSeverityFilter] = useState<string>('ALL');
  const [analyzerFilter, setAnalyzerFilter] = useState<string>('ALL');
  const [searchFilter, setSearchFilter] = useState<string>('');

  const validateMutation = useExecuteValidation();

  const handleToggleAnalyzer = (analyzer: string) => {
    setSelectedAnalyzers((prev) =>
      prev.includes(analyzer) ? prev.filter((a) => a !== analyzer) : [...prev, analyzer]
    );
  };

  const handleRunValidation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedDatasetId) {
      setErrorMsg('Please select a dataset to validate.');
      return;
    }

    setErrorMsg(null);
    try {
      const res = await validateMutation.mutateAsync({
        dataset_id: selectedDatasetId,
        analyzers: selectedAnalyzers,
      });
      setResult(res);
    } catch (err) {
      setErrorMsg(formatApiError(err));
    }
  };

  // Filtered findings
  const filteredFindings = React.useMemo(() => {
    if (!result?.findings) return [];
    return result.findings.filter((f) => {
      const matchSeverity =
        severityFilter === 'ALL' || f.severity.toLowerCase() === severityFilter.toLowerCase();
      const matchAnalyzer =
        analyzerFilter === 'ALL' || f.analyzer.toLowerCase() === analyzerFilter.toLowerCase();
      const matchSearch =
        !searchFilter.trim() ||
        f.message.toLowerCase().includes(searchFilter.toLowerCase()) ||
        f.code.toLowerCase().includes(searchFilter.toLowerCase()) ||
        (f.column && f.column.toLowerCase().includes(searchFilter.toLowerCase()));
      return matchSeverity && matchAnalyzer && matchSearch;
    });
  }, [result, severityFilter, analyzerFilter, searchFilter]);

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="border-b border-black pb-5">
        <div className="text-xs font-mono font-bold uppercase tracking-widest text-[#ff3b30] flex items-center gap-1">
          <span>✦</span>
          <span>DATA INTEGRITY</span>
        </div>
        <h1 className="text-3xl font-bold tracking-tight text-black mt-1">
          Structural Data Validation
        </h1>
        <p className="text-xs sm:text-sm text-zinc-600 mt-1">
          Verify delimiter integrity, timestamp formatting, column presence, and schema conformity.
        </p>
      </div>

      {errorMsg && <ErrorAlert title="Validation Failed" message={errorMsg} />}

      {/* Validation Launcher Card */}
      <Card
        tag="EXECUTION CONTROL"
        title="Run Structural Integrity Validation"
        subtitle="Executes table-level CSV inspection and schema conformity checks"
      >
        <form onSubmit={handleRunValidation} className="space-y-5">
          <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
            {/* Dataset Selector */}
            <div className="md:col-span-6 space-y-1">
              <label className="block text-xs font-mono font-bold uppercase tracking-wider text-black">
                Target Dataset
              </label>
              {isDatasetsLoading ? (
                <div className="text-xs font-mono text-zinc-500">Loading datasets...</div>
              ) : (
                <select
                  value={selectedDatasetId}
                  onChange={(e) => setSelectedDatasetId(e.target.value)}
                  className="w-full text-xs font-mono p-2.5 bg-white border border-black focus:outline-none focus:ring-1 focus:ring-black"
                >
                  {datasets?.map((d) => (
                    <option key={d.dataset_id} value={d.dataset_id}>
                      {d.is_existing ? '[CANONICAL] ' : '[UPLOAD] '}
                      {d.name || d.dataset_id} ({d.file_count} files)
                    </option>
                  ))}
                </select>
              )}
            </div>

            {/* Scope / Analyzers Checklist */}
            <div className="md:col-span-6 space-y-2">
              <label className="block text-xs font-mono font-bold uppercase tracking-wider text-black">
                Verification Scope
              </label>
              <div className="flex flex-wrap gap-3">
                {[
                  { id: 'survivorship', label: 'Survivorship Requisites' },
                  { id: 'lookahead', label: 'Look-Ahead Timing' },
                  { id: 'corporate_actions', label: 'Corporate Actions' },
                ].map((item) => (
                  <label
                    key={item.id}
                    className="flex items-center gap-2 text-xs font-mono text-black cursor-pointer select-none"
                  >
                    <input
                      type="checkbox"
                      checked={selectedAnalyzers.includes(item.id)}
                      onChange={() => handleToggleAnalyzer(item.id)}
                      className="accent-black w-4 h-4 cursor-pointer"
                    />
                    <span>{item.label}</span>
                  </label>
                ))}
              </div>
            </div>
          </div>

          <div className="pt-4 border-t border-black flex items-center justify-between">
            <span className="text-xs font-mono text-zinc-500">
              * Validations generate persistent audit records with unique validation IDs.
            </span>
            <Button
              type="submit"
              variant="black"
              size="md"
              isLoading={validateMutation.isPending}
              icon={<Play className="w-4 h-4" />}
            >
              RUN VALIDATION
            </Button>
          </div>
        </form>
      </Card>

      {/* Results View */}
      {validateMutation.isPending ? (
        <LoadingSpinner label="Validating dataset tables..." fullHeight />
      ) : result ? (
        <div className="space-y-6">
          {/* Status Banner */}
          <div
            className={`border-2 border-black p-6 shadow-[4px_4px_0px_0px_#000000] flex flex-col md:flex-row items-start md:items-center justify-between gap-6 ${
              result.status === 'PASS'
                ? 'bg-[#dcfce7]'
                : result.status === 'WARN'
                ? 'bg-[#fef3c7]'
                : 'bg-[#fee2e2]'
            }`}
          >
            <div className="space-y-1">
              <div className="text-xs font-mono font-bold uppercase tracking-wider text-black flex items-center gap-2">
                <span>VALIDATION RESULT:</span>
                <Badge variant={result.status === 'PASS' ? 'pass' : result.status === 'WARN' ? 'warn' : 'fail'}>
                  {result.status}
                </Badge>
              </div>
              <div className="text-2xl font-bold font-mono text-black">
                {result.status === 'PASS'
                  ? 'All Structural Checks Passed'
                  : result.status === 'WARN'
                  ? 'Passed With Non-Fatal Warnings'
                  : 'Critical Verification Defects Detected'}
              </div>
              <div className="text-xs font-mono text-zinc-700">
                Validation ID: <span className="font-bold text-black">{result.validation_id}</span> • Executed At:{' '}
                {new Date(result.created_at).toLocaleString()}
              </div>
            </div>

            {/* Summary Counters */}
            <div className="flex items-center gap-4 border-t md:border-t-0 md:border-l border-black pt-4 md:pt-0 md:pl-6 text-xs font-mono">
              <div>
                <span className="text-[10px] text-zinc-600 block uppercase font-bold">Errors</span>
                <span className="text-2xl font-bold text-[#dc2626]">{result.summary.error_count}</span>
              </div>
              <div>
                <span className="text-[10px] text-zinc-600 block uppercase font-bold">Warnings</span>
                <span className="text-2xl font-bold text-[#d97706]">{result.summary.warning_count}</span>
              </div>
              <div>
                <span className="text-[10px] text-zinc-600 block uppercase font-bold">Passed</span>
                <span className="text-2xl font-bold text-[#16a34a]">{result.summary.pass_count}</span>
              </div>
            </div>
          </div>

          {/* Findings Filter Bar */}
          <div className="border border-black bg-white p-4 shadow-[2px_2px_0px_0px_#000000] space-y-3">
            <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
              {/* Search */}
              <div className="relative flex-1 w-full sm:max-w-xs">
                <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
                <input
                  type="text"
                  value={searchFilter}
                  onChange={(e) => setSearchFilter(e.target.value)}
                  placeholder="Filter findings by code or text..."
                  className="w-full pl-9 pr-3 py-1.5 text-xs font-mono bg-white border border-black focus:outline-none focus:ring-1 focus:ring-black placeholder:text-zinc-400"
                />
              </div>

              {/* Severity & Analyzer Selectors */}
              <div className="flex items-center gap-2 w-full sm:w-auto">
                <select
                  value={severityFilter}
                  onChange={(e) => setSeverityFilter(e.target.value)}
                  className="text-xs font-mono p-1.5 bg-white border border-black focus:outline-none"
                >
                  <option value="ALL">All Severities</option>
                  <option value="error">Errors Only</option>
                  <option value="warning">Warnings Only</option>
                  <option value="info">Info Only</option>
                </select>

                <select
                  value={analyzerFilter}
                  onChange={(e) => setAnalyzerFilter(e.target.value)}
                  className="text-xs font-mono p-1.5 bg-white border border-black focus:outline-none"
                >
                  <option value="ALL">All Analyzers</option>
                  <option value="csv">CSV Engine</option>
                  <option value="survivorship">Survivorship</option>
                  <option value="lookahead">Look-Ahead</option>
                  <option value="corporate_actions">Corporate Actions</option>
                </select>
              </div>
            </div>
          </div>

          {/* Findings Table */}
          <Card tag="FINDINGS LOG" title={`Audit Findings (${filteredFindings.length})`}>
            {filteredFindings.length === 0 ? (
              <div className="py-8 text-center font-mono text-xs text-zinc-500">
                No findings match the selected filter criteria.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left font-mono text-xs border-collapse">
                  <thead>
                    <tr className="bg-zinc-50 border-b border-black">
                      <th className="py-2.5 px-3 font-bold text-black uppercase w-20">Severity</th>
                      <th className="py-2.5 px-3 font-bold text-black uppercase w-28">Analyzer</th>
                      <th className="py-2.5 px-3 font-bold text-black uppercase">Code & Explanation</th>
                      <th className="py-2.5 px-3 font-bold text-black uppercase w-24">Location</th>
                      <th className="py-2.5 px-3 font-bold text-black uppercase">Remediation</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-200">
                    {filteredFindings.map((finding) => (
                      <tr key={finding.id} className="hover:bg-zinc-50">
                        <td className="py-2.5 px-3">
                          <Badge
                            variant={
                              finding.severity === 'error'
                                ? 'fail'
                                : finding.severity === 'warning'
                                ? 'warn'
                                : 'neutral'
                            }
                            size="sm"
                          >
                            {finding.severity}
                          </Badge>
                        </td>
                        <td className="py-2.5 px-3 text-zinc-600 font-bold uppercase text-[10px]">
                          {finding.analyzer}
                        </td>
                        <td className="py-2.5 px-3">
                          <div className="font-bold text-black">{finding.code}</div>
                          <div className="text-zinc-700 text-xs mt-0.5">{finding.message}</div>
                        </td>
                        <td className="py-2.5 px-3 text-zinc-500 text-[11px]">
                          {finding.row ? `Row ${finding.row}` : ''}
                          {finding.column ? ` [${finding.column}]` : 'Dataset'}
                        </td>
                        <td className="py-2.5 px-3 text-zinc-600 text-xs italic">
                          {finding.remediation || '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>
      ) : null}
    </div>
  );
};
