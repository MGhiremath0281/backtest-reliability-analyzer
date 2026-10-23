import React, { useState } from 'react';
import { useDatasets } from '../../hooks/useDatasets';
import {
  useTriggerCorporateActions,
  useCorporateActionsCoverage,
  useCorporateActionsFindings,
} from '../../hooks/useAnalyzers';
import { Button } from '../../components/common/Button';
import { Card } from '../../components/common/Card';
import { Badge } from '../../components/common/Badge';
import { LoadingSpinner } from '../../components/common/LoadingSpinner';
import { ErrorAlert } from '../../components/common/ErrorAlert';
import { CorporateActionsTriggerResponse } from '../../api/types';
import { formatApiError } from '../../api/client';
import {
  Sparkles,
  Play,
  Calendar,
  AlertTriangle,
  CheckCircle2,
  PieChart,
  Tag,
  Search,
} from 'lucide-react';

export const CorporateActionsPage: React.FC = () => {
  const { data: datasets } = useDatasets({ include_existing: true });

  const [datasetId, setDatasetId] = useState<string>('existing-data');
  const [expectedSymbol, setExpectedSymbol] = useState<string>('INFY');

  const [activeAnalysisId, setActiveAnalysisId] = useState<string | null>(null);
  const [triggerResult, setTriggerResult] = useState<CorporateActionsTriggerResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Coverage and findings queries
  const { data: coverageData, isLoading: isCoverageLoading } = useCorporateActionsCoverage(
    activeAnalysisId || undefined
  );
  const { data: findingsData, isLoading: isFindingsLoading } = useCorporateActionsFindings(
    activeAnalysisId || undefined
  );

  const triggerMutation = useTriggerCorporateActions();

  const handleRunAnalysis = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);

    try {
      const res = await triggerMutation.mutateAsync({
        dataset_id: datasetId,
        expected_symbol: expectedSymbol.trim() || undefined,
      });
      setTriggerResult(res);
      setActiveAnalysisId(res.analysis_id);
    } catch (err) {
      setErrorMsg(formatApiError(err));
    }
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="border-b border-black pb-5">
        <div className="text-xs font-mono font-bold uppercase tracking-widest text-[#ff3b30] flex items-center gap-1">
          <span>✦</span>
          <span>BIAS ANALYZER 03</span>
        </div>
        <h1 className="text-3xl font-bold tracking-tight text-black mt-1">
          Corporate Actions Consistency
        </h1>
        <p className="text-xs sm:text-sm text-zinc-600 mt-1 max-w-2xl">
          Audit stock splits, bonus emissions, and dividend distributions. Validates record date vs. ex-date
          chronology and flags unadjusted price discontinuities across session transitions.
        </p>
      </div>

      {errorMsg && <ErrorAlert title="Corporate Actions Audit Failed" message={errorMsg} />}

      {/* Form Card */}
      <Card
        tag="AUDIT SCOPE"
        title="Corporate Actions Verification Parameters"
        subtitle="Configure dataset and optional target equity symbol"
      >
        <form onSubmit={handleRunAnalysis} className="space-y-5">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
            {/* Dataset */}
            <div>
              <label className="block text-xs font-mono font-bold uppercase tracking-wider text-black mb-1">
                Target Dataset
              </label>
              <select
                value={datasetId}
                onChange={(e) => setDatasetId(e.target.value)}
                className="w-full text-xs font-mono p-2.5 bg-white border border-black focus:outline-none focus:ring-1 focus:ring-black"
              >
                {datasets?.map((d) => (
                  <option key={d.dataset_id} value={d.dataset_id}>
                    {d.is_existing ? '[CANONICAL] ' : ''}
                    {d.name || d.dataset_id}
                  </option>
                ))}
              </select>
            </div>

            {/* Expected Symbol */}
            <div>
              <label className="block text-xs font-mono font-bold uppercase tracking-wider text-black mb-1">
                Target Equity Symbol (Optional)
              </label>
              <input
                type="text"
                value={expectedSymbol}
                onChange={(e) => setExpectedSymbol(e.target.value)}
                placeholder="e.g. INFY, TCS, RELIANCE"
                className="w-full px-3 py-2 text-xs font-mono bg-white border border-black focus:outline-none focus:ring-1 focus:ring-black"
              />
            </div>
          </div>

          <div className="pt-4 border-t border-black flex items-center justify-between">
            <span className="text-xs font-mono text-zinc-500">
              * Compares ex-dates against daily price leaps to detect unadjusted backtest prices.
            </span>
            <Button
              type="submit"
              variant="black"
              size="md"
              isLoading={triggerMutation.isPending}
              icon={<Play className="w-4 h-4" />}
            >
              RUN ACTIONS AUDIT
            </Button>
          </div>
        </form>
      </Card>

      {/* Analysis Results */}
      {triggerMutation.isPending ? (
        <LoadingSpinner label="Auditing entitlement dates and price continuity..." fullHeight />
      ) : activeAnalysisId ? (
        <div className="space-y-6">
          {/* Header Banner */}
          {triggerResult && (
            <div
              className={`border-2 border-black p-5 shadow-[3px_3px_0px_0px_#000000] flex items-center justify-between ${
                triggerResult.status === 'PASS' ? 'bg-[#dcfce7]' : 'bg-[#fee2e2]'
              }`}
            >
              <div>
                <span className="text-xs font-mono uppercase font-bold text-black block">
                  CORPORATE ACTIONS AUDIT: {triggerResult.analysis_id}
                </span>
                <div className="text-xl font-bold font-mono text-black mt-0.5">
                  Status: {triggerResult.status} • {triggerResult.findings_count} Finding(s) Found
                </div>
              </div>
              <Badge variant={triggerResult.status === 'PASS' ? 'pass' : 'fail'} size="md">
                {triggerResult.status}
              </Badge>
            </div>
          )}

          {/* Breakdown by Purpose & Symbol */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* By Purpose */}
            <Card tag="ACTION TYPES" title="Actions by Purpose">
              {isCoverageLoading ? (
                <LoadingSpinner label="Calculating distribution..." />
              ) : !coverageData?.by_purpose || Object.keys(coverageData.by_purpose).length === 0 ? (
                <div className="py-6 text-center font-mono text-xs text-zinc-500">No actions by purpose.</div>
              ) : (
                <div className="space-y-2 font-mono text-xs">
                  {Object.entries(coverageData.by_purpose).map(([purpose, count]) => (
                    <div
                      key={purpose}
                      className="p-2 border border-zinc-200 bg-zinc-50 flex items-center justify-between"
                    >
                      <span className="font-bold text-black">{purpose}</span>
                      <span className="px-2 py-0.5 bg-black text-white font-bold">{count}</span>
                    </div>
                  ))}
                </div>
              )}
            </Card>

            {/* By Symbol */}
            <Card tag="EQUITY ENTITIES" title="Actions by Symbol">
              {isCoverageLoading ? (
                <LoadingSpinner label="Calculating symbol counts..." />
              ) : !coverageData?.by_symbol || Object.keys(coverageData.by_symbol).length === 0 ? (
                <div className="py-6 text-center font-mono text-xs text-zinc-500">No actions by symbol.</div>
              ) : (
                <div className="space-y-2 font-mono text-xs">
                  {Object.entries(coverageData.by_symbol).map(([sym, count]) => (
                    <div
                      key={sym}
                      className="p-2 border border-zinc-200 bg-zinc-50 flex items-center justify-between"
                    >
                      <span className="font-bold text-black">{sym}</span>
                      <span className="px-2 py-0.5 bg-black text-white font-bold">{count}</span>
                    </div>
                  ))}
                </div>
              )}
            </Card>

            {/* Quality Summary */}
            <Card tag="AUDIT STATS" title="Integrity Diagnostics">
              <div className="space-y-3 font-mono text-xs pt-1">
                <div className="p-3 border border-black bg-zinc-50 flex justify-between items-center">
                  <span className="text-zinc-600">Coverage Ratio:</span>
                  <span className="font-bold text-black text-sm">
                    {coverageData?.coverage !== null && coverageData?.coverage !== undefined
                      ? `${(coverageData.coverage * 100).toFixed(1)}%`
                      : '100%'}
                  </span>
                </div>
                <div className="p-3 border border-black bg-zinc-50 flex justify-between items-center">
                  <span className="text-zinc-600">Duplicate Actions:</span>
                  <span className="font-bold text-black text-sm">
                    {coverageData?.duplicate_records ?? 0}
                  </span>
                </div>
                <div className="p-3 border border-black bg-zinc-50 flex justify-between items-center">
                  <span className="text-zinc-600">Market Series:</span>
                  <span className="font-bold text-black text-sm">
                    {Object.keys(coverageData?.by_series || {}).join(', ') || 'EQ'}
                  </span>
                </div>
              </div>
            </Card>
          </div>

          {/* Findings Table */}
          <Card tag="FINDINGS LOG" title={`Corporate Actions Findings (${findingsData?.length || 0})`}>
            {isFindingsLoading ? (
              <LoadingSpinner label="Loading findings..." />
            ) : !findingsData || findingsData.length === 0 ? (
              <div className="py-8 text-center font-mono text-xs text-zinc-500">
                No corporate action inconsistencies flagged.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left font-mono text-xs border-collapse">
                  <thead>
                    <tr className="bg-zinc-50 border-b border-black">
                      <th className="py-2.5 px-3 font-bold text-black uppercase w-20">Severity</th>
                      <th className="py-2.5 px-3 font-bold text-black uppercase w-28">Classification</th>
                      <th className="py-2.5 px-3 font-bold text-black uppercase">Code & Explanation</th>
                      <th className="py-2.5 px-3 font-bold text-black uppercase">Remediation</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-200">
                    {findingsData.map((finding) => (
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
                        <td className="py-2.5 px-3 uppercase text-[10px] font-bold text-zinc-600">
                          {finding.classification}
                        </td>
                        <td className="py-2.5 px-3">
                          <div className="font-bold text-black">{finding.code}</div>
                          <div className="text-zinc-700 mt-0.5">{finding.message}</div>
                        </td>
                        <td className="py-2.5 px-3 text-zinc-600 italic">
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
