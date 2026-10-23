import React, { useState } from 'react';
import { useDatasets } from '../../hooks/useDatasets';
import {
  useTriggerSurvivorship,
  useSurvivorshipUniverse,
  useSurvivorshipDelisted,
  useSurvivorshipFindings,
} from '../../hooks/useAnalyzers';
import { Button } from '../../components/common/Button';
import { Card } from '../../components/common/Card';
import { Badge } from '../../components/common/Badge';
import { LoadingSpinner } from '../../components/common/LoadingSpinner';
import { ErrorAlert } from '../../components/common/ErrorAlert';
import { SurvivorshipAnalysisTriggerResponse } from '../../api/types';
import { formatApiError } from '../../api/client';
import { Play } from 'lucide-react';

export const SurvivorshipPage: React.FC = () => {
  const { data: datasets } = useDatasets({ include_existing: true });

  // Form State matching SurvivorshipAnalysisRequest
  const [datasetId, setDatasetId] = useState<string>('existing-data');
  const [targetIndex, setTargetIndex] = useState<string>('NIFTY 50');
  const [startDate, setStartDate] = useState<string>('2021-01-01');
  const [endDate, setEndDate] = useState<string>('2025-12-31');
  const [universeSymbols, setUniverseSymbols] = useState<string>('INFY, TCS, RELIANCE, WIPRO');
  const [minPriceCoverage, setMinPriceCoverage] = useState<string>('0.95');

  const [activeAnalysisId, setActiveAnalysisId] = useState<string | null>(null);
  const [triggerResult, setTriggerResult] = useState<SurvivorshipAnalysisTriggerResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Sub-queries when activeAnalysisId is set
  const { data: universeData, isLoading: isUniverseLoading } = useSurvivorshipUniverse(
    activeAnalysisId || undefined
  );
  const { data: delistedData, isLoading: isDelistedLoading } = useSurvivorshipDelisted(
    activeAnalysisId || undefined
  );
  const { data: findingsData, isLoading: isFindingsLoading } = useSurvivorshipFindings(
    activeAnalysisId || undefined
  );

  const triggerMutation = useTriggerSurvivorship();

  const handleRunAnalysis = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);

    const symbolsArray = universeSymbols
      .split(',')
      .map((s) => s.trim().toUpperCase())
      .filter(Boolean);

    const covNum = minPriceCoverage ? parseFloat(minPriceCoverage) : undefined;

    try {
      const res = await triggerMutation.mutateAsync({
        dataset_id: datasetId,
        target_index: targetIndex.trim() || undefined,
        start_date: startDate.trim() || undefined,
        end_date: endDate.trim() || undefined,
        universe_symbols: symbolsArray.length > 0 ? symbolsArray : undefined,
        min_price_coverage: isNaN(covNum as any) ? undefined : covNum,
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
          <span>BIAS ANALYZER 01</span>
        </div>
        <h1 className="text-3xl font-bold tracking-tight text-black mt-1">
          Survivorship Bias Audit
        </h1>
        <p className="text-xs sm:text-sm text-zinc-600 mt-1 max-w-2xl">
          Evaluate historical index constituent transitions, reconcile delisted securities against trading history,
          and ensure non-surviving companies are represented in your simulation.
        </p>
      </div>

      {errorMsg && <ErrorAlert title="Survivorship Analysis Failed" message={errorMsg} />}

      {/* Configuration Form Card */}
      <Card
        tag="CONFIGURATION MODEL"
        title="Survivorship Analysis Parameters"
        subtitle="Configures historical index targeting, observation dates, and symbol universe"
      >
        <form onSubmit={handleRunAnalysis} className="space-y-5">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
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

            {/* Target Index */}
            <div>
              <label className="block text-xs font-mono font-bold uppercase tracking-wider text-black mb-1">
                Target Index (Optional)
              </label>
              <input
                type="text"
                value={targetIndex}
                onChange={(e) => setTargetIndex(e.target.value)}
                placeholder="e.g. NIFTY 50, NIFTY BANK"
                className="w-full px-3 py-2 text-xs font-mono bg-white border border-black focus:outline-none focus:ring-1 focus:ring-black"
              />
            </div>

            {/* Min Coverage */}
            <div>
              <label className="block text-xs font-mono font-bold uppercase tracking-wider text-black mb-1">
                Min Price Coverage (0.0 – 1.0)
              </label>
              <input
                type="number"
                step="0.05"
                min="0"
                max="1"
                value={minPriceCoverage}
                onChange={(e) => setMinPriceCoverage(e.target.value)}
                className="w-full px-3 py-2 text-xs font-mono bg-white border border-black focus:outline-none focus:ring-1 focus:ring-black"
              />
            </div>

            {/* Start Date */}
            <div>
              <label className="block text-xs font-mono font-bold uppercase tracking-wider text-black mb-1">
                Start Date (YYYY-MM-DD)
              </label>
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="w-full px-3 py-2 text-xs font-mono bg-white border border-black focus:outline-none focus:ring-1 focus:ring-black"
              />
            </div>

            {/* End Date */}
            <div>
              <label className="block text-xs font-mono font-bold uppercase tracking-wider text-black mb-1">
                End Date (YYYY-MM-DD)
              </label>
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="w-full px-3 py-2 text-xs font-mono bg-white border border-black focus:outline-none focus:ring-1 focus:ring-black"
              />
            </div>

            {/* Symbols */}
            <div className="sm:col-span-2 lg:col-span-1">
              <label className="block text-xs font-mono font-bold uppercase tracking-wider text-black mb-1">
                Universe Symbols (Comma-separated)
              </label>
              <input
                type="text"
                value={universeSymbols}
                onChange={(e) => setUniverseSymbols(e.target.value)}
                placeholder="e.g. INFY, TCS, RELIANCE"
                className="w-full px-3 py-2 text-xs font-mono bg-white border border-black focus:outline-none focus:ring-1 focus:ring-black"
              />
            </div>
          </div>

          <div className="pt-4 border-t border-black flex items-center justify-between">
            <span className="text-xs font-mono text-zinc-500">
              * The engine audits coverage, matching evidence, and symbol reuse without fabricating missing entries.
            </span>
            <Button
              type="submit"
              variant="black"
              size="md"
              isLoading={triggerMutation.isPending}
              icon={<Play className="w-4 h-4" />}
            >
              EXECUTE SURVIVORSHIP AUDIT
            </Button>
          </div>
        </form>
      </Card>

      {/* Analysis Results */}
      {triggerMutation.isPending ? (
        <LoadingSpinner label="Auditing survivorship universe and delisted reconciliations..." fullHeight />
      ) : activeAnalysisId ? (
        <div className="space-y-6">
          {/* Header Banner */}
          {triggerResult && (
            <div
              className={`border-2 border-black p-5 shadow-[3px_3px_0px_0px_#000000] flex items-center justify-between ${
                triggerResult.status === 'PASS' ? 'bg-[#dcfce7]' : 'bg-[#fef3c7]'
              }`}
            >
              <div>
                <span className="text-xs font-mono uppercase font-bold text-black block">
                  SURVIVORSHIP AUDIT RUN: {triggerResult.analysis_id}
                </span>
                <div className="text-xl font-bold font-mono text-black mt-0.5">
                  Status: {triggerResult.status} • {triggerResult.findings_count} Finding(s) Documented
                </div>
              </div>
              <Badge variant={triggerResult.status === 'PASS' ? 'pass' : 'warn'} size="md">
                {triggerResult.status}
              </Badge>
            </div>
          )}

          {/* Two Column Metric Grid: Universe Coverage & Delisted Reconciliation */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Card 1: Historical Universe Coverage */}
            <Card
              tag="UNIVERSE RECONSTRUCTION"
              title="Point-in-Time Constituent Coverage"
              subtitle="Reconstructed index membership across historical snapshots"
            >
              {isUniverseLoading ? (
                <LoadingSpinner label="Fetching universe membership..." />
              ) : universeData ? (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-3 text-xs font-mono">
                    <div className="p-3 border border-black bg-zinc-50">
                      <span className="text-[10px] text-zinc-500 uppercase block font-bold">
                        Target Index
                      </span>
                      <span className="text-sm font-bold text-black">
                        {universeData.membership?.target_index || targetIndex || 'NSE Index'}
                      </span>
                    </div>

                    <div className="p-3 border border-black bg-zinc-50">
                      <span className="text-[10px] text-zinc-500 uppercase block font-bold">
                        Historical Constituents
                      </span>
                      <span className="text-sm font-bold text-black">
                        {universeData.membership?.total_historical_constituents ||
                          universeData.universe_coverage?.configured_symbols ||
                          '—'}
                      </span>
                    </div>
                  </div>

                  <div className="p-3 border border-zinc-200 bg-white space-y-2 text-xs font-mono">
                    <div className="font-bold text-black uppercase text-[11px]">
                      Reconciliation Diagnostic:
                    </div>
                    <pre className="text-[11px] text-zinc-700 bg-zinc-50 p-2 border border-zinc-200 overflow-x-auto">
                      {JSON.stringify(
                        {
                          membership: universeData.membership,
                          coverage: universeData.universe_coverage,
                          current_listings: universeData.current_listings,
                        },
                        null,
                        2
                      )}
                    </pre>
                  </div>
                </div>
              ) : null}
            </Card>

            {/* Card 2: Delisted Securities Reconciliation */}
            <Card
              tag="DELISTED EQUITIES"
              title="Delisting Coverage & Identifier Reuse"
              subtitle="Audit of liquidated, acquired, and delisted corporate records"
            >
              {isDelistedLoading ? (
                <LoadingSpinner label="Fetching delisting audits..." />
              ) : delistedData ? (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-3 text-xs font-mono">
                    <div className="p-3 border border-black bg-zinc-50">
                      <span className="text-[10px] text-zinc-500 uppercase block font-bold">
                        Tracked Symbol Changes
                      </span>
                      <span className="text-sm font-bold text-black">
                        {delistedData.symbol_changes?.tracked_changes || 0}
                      </span>
                    </div>

                    <div className="p-3 border border-black bg-zinc-50">
                      <span className="text-[10px] text-zinc-500 uppercase block font-bold">
                        Reused Identifier Conflicts
                      </span>
                      <span className="text-sm font-bold text-[#ff3b30]">
                        {delistedData.identifier_reuse?.reused_symbol_count || 0}
                      </span>
                    </div>
                  </div>

                  <div className="p-3 border border-zinc-200 bg-white space-y-2 text-xs font-mono">
                    <div className="font-bold text-black uppercase text-[11px]">
                      Delisting Price Coverage Metrics:
                    </div>
                    <pre className="text-[11px] text-zinc-700 bg-zinc-50 p-2 border border-zinc-200 overflow-x-auto">
                      {JSON.stringify(
                        {
                          delisted_coverage: delistedData.delisted_coverage,
                          symbol_changes: delistedData.symbol_changes,
                          identifier_reuse: delistedData.identifier_reuse,
                        },
                        null,
                        2
                      )}
                    </pre>
                  </div>
                </div>
              ) : null}
            </Card>
          </div>

          {/* Findings Table */}
          <Card
            tag="FINDINGS LOG"
            title={`Survivorship Findings & Evidence (${findingsData?.length || 0})`}
          >
            {isFindingsLoading ? (
              <LoadingSpinner label="Loading findings..." />
            ) : !findingsData || findingsData.length === 0 ? (
              <div className="py-8 text-center font-mono text-xs text-zinc-500">
                No survivorship bias findings recorded for this run.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left font-mono text-xs border-collapse">
                  <thead>
                    <tr className="bg-zinc-50 border-b border-black">
                      <th className="py-2.5 px-3 font-bold text-black uppercase w-20">Severity</th>
                      <th className="py-2.5 px-3 font-bold text-black uppercase w-28">Kind</th>
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
