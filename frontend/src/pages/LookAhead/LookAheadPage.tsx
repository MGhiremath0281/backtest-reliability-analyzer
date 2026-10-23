import React, { useState } from 'react';
import { useDatasets } from '../../hooks/useDatasets';
import {
  useTriggerLookahead,
  useLookaheadTimeline,
  useLookaheadFindings,
} from '../../hooks/useAnalyzers';
import { Button } from '../../components/common/Button';
import { Card } from '../../components/common/Card';
import { Badge } from '../../components/common/Badge';
import { LoadingSpinner } from '../../components/common/LoadingSpinner';
import { ErrorAlert } from '../../components/common/ErrorAlert';
import { LookaheadAnalysisTriggerResponse, TimelineEvent } from '../../api/types';
import { formatApiError } from '../../api/client';
import {
  Clock,
  Play,
  Calendar,
  AlertCircle,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  Filter,
} from 'lucide-react';

export const LookAheadPage: React.FC = () => {
  const { data: datasets } = useDatasets({ include_existing: true });

  // Form State
  const [datasetId, setDatasetId] = useState<string>('existing-data');
  const [decisionDates, setDecisionDates] = useState<string>('2022-04-01, 2023-04-01, 2024-04-01');
  const [targetIndex, setTargetIndex] = useState<string>('NIFTY 50');
  const [startDate, setStartDate] = useState<string>('2021-01-01');
  const [endDate, setEndDate] = useState<string>('2025-12-31');
  const [universeSymbols, setUniverseSymbols] = useState<string>('INFY, TCS, RELIANCE');
  const [lookbackDays, setLookbackDays] = useState<string>('90');

  const [activeAnalysisId, setActiveAnalysisId] = useState<string | null>(null);
  const [triggerResult, setTriggerResult] = useState<LookaheadAnalysisTriggerResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Timeline & findings queries
  const { data: timelineData, isLoading: isTimelineLoading } = useLookaheadTimeline(
    activeAnalysisId || undefined
  );
  const { data: findingsData, isLoading: isFindingsLoading } = useLookaheadFindings(
    activeAnalysisId || undefined
  );

  const triggerMutation = useTriggerLookahead();

  const handleRunAnalysis = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);

    const datesArray = decisionDates
      .split(',')
      .map((d) => d.trim())
      .filter(Boolean);

    const symbolsArray = universeSymbols
      .split(',')
      .map((s) => s.trim().toUpperCase())
      .filter(Boolean);

    const lookbackNum = lookbackDays ? parseInt(lookbackDays, 10) : undefined;

    try {
      const res = await triggerMutation.mutateAsync({
        dataset_id: datasetId,
        decision_dates: datesArray,
        target_index: targetIndex.trim() || undefined,
        start_date: startDate.trim() || undefined,
        end_date: endDate.trim() || undefined,
        universe_symbols: symbolsArray.length > 0 ? symbolsArray : undefined,
        lookback_days: isNaN(lookbackNum as any) ? undefined : lookbackNum,
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
          <span>BIAS ANALYZER 02</span>
        </div>
        <h1 className="text-3xl font-bold tracking-tight text-black mt-1">
          Look-Ahead Bias Audit
        </h1>
        <p className="text-xs sm:text-sm text-zinc-600 mt-1 max-w-2xl">
          Validate chronological timing between portfolio rebalancing decision timestamps, period-end financial
          reporting dates, and exchange public dissemination feeds.
        </p>
      </div>

      {errorMsg && <ErrorAlert title="Look-Ahead Analysis Failed" message={errorMsg} />}

      {/* Configuration Form Card */}
      <Card
        tag="TEMPORAL PARAMETERS"
        title="Look-Ahead Detection Configuration"
        subtitle="Specify portfolio decision points to audit against company reporting dissemination times"
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

            {/* Decision Dates */}
            <div className="sm:col-span-2">
              <label className="block text-xs font-mono font-bold uppercase tracking-wider text-black mb-1">
                Decision Dates (Comma-separated YYYY-MM-DD)
              </label>
              <input
                type="text"
                value={decisionDates}
                onChange={(e) => setDecisionDates(e.target.value)}
                placeholder="2022-04-01, 2023-04-01, 2024-04-01"
                className="w-full px-3 py-2 text-xs font-mono bg-white border border-black focus:outline-none focus:ring-1 focus:ring-black"
              />
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
                placeholder="e.g. NIFTY 50"
                className="w-full px-3 py-2 text-xs font-mono bg-white border border-black focus:outline-none focus:ring-1 focus:ring-black"
              />
            </div>

            {/* Lookback Days */}
            <div>
              <label className="block text-xs font-mono font-bold uppercase tracking-wider text-black mb-1">
                Lookback Window (Days)
              </label>
              <input
                type="number"
                value={lookbackDays}
                onChange={(e) => setLookbackDays(e.target.value)}
                placeholder="90"
                className="w-full px-3 py-2 text-xs font-mono bg-white border border-black focus:outline-none focus:ring-1 focus:ring-black"
              />
            </div>

            {/* Universe Symbols */}
            <div>
              <label className="block text-xs font-mono font-bold uppercase tracking-wider text-black mb-1">
                Universe Symbols (Comma-separated)
              </label>
              <input
                type="text"
                value={universeSymbols}
                onChange={(e) => setUniverseSymbols(e.target.value)}
                placeholder="INFY, TCS"
                className="w-full px-3 py-2 text-xs font-mono bg-white border border-black focus:outline-none focus:ring-1 focus:ring-black"
              />
            </div>
          </div>

          <div className="pt-4 border-t border-black flex items-center justify-between">
            <span className="text-xs font-mono text-zinc-500">
              * Flags cases where financial results disseminated after the decision date were factored into calculations.
            </span>
            <Button
              type="submit"
              variant="black"
              size="md"
              isLoading={triggerMutation.isPending}
              icon={<Play className="w-4 h-4" />}
            >
              RUN LOOK-AHEAD AUDIT
            </Button>
          </div>
        </form>
      </Card>

      {/* Analysis Results */}
      {triggerMutation.isPending ? (
        <LoadingSpinner label="Auditing chronological publication timelines and decision boundaries..." fullHeight />
      ) : activeAnalysisId ? (
        <div className="space-y-6">
          {/* Status Banner */}
          {triggerResult && (
            <div
              className={`border-2 border-black p-5 shadow-[3px_3px_0px_0px_#000000] flex items-center justify-between ${
                triggerResult.status === 'PASS' ? 'bg-[#dcfce7]' : 'bg-[#fee2e2]'
              }`}
            >
              <div>
                <span className="text-xs font-mono uppercase font-bold text-black block">
                  LOOK-AHEAD AUDIT RUN: {triggerResult.analysis_id}
                </span>
                <div className="text-xl font-bold font-mono text-black mt-0.5">
                  Status: {triggerResult.status} • {triggerResult.findings_count} Finding(s) Logged
                </div>
              </div>
              <Badge variant={triggerResult.status === 'PASS' ? 'pass' : 'fail'} size="md">
                {triggerResult.status}
              </Badge>
            </div>
          )}

          {/* Chronological Timeline Card */}
          <Card
            tag="CHRONOLOGICAL EVENT STREAM"
            title={`Temporal Sequence Timeline (${timelineData?.event_count || 0} Events)`}
            subtitle="Ordered timeline mapping decision boundaries against actual financial announcements"
          >
            {isTimelineLoading ? (
              <LoadingSpinner label="Constructing chronological timeline..." />
            ) : !timelineData || timelineData.events.length === 0 ? (
              <div className="py-8 text-center font-mono text-xs text-zinc-500 border border-dashed border-zinc-200">
                No chronological events recorded. Ensure the dataset contains financial publication or corporate action dates.
              </div>
            ) : (
              <div className="space-y-4">
                {/* Timeline Stream */}
                <div className="relative pl-6 sm:pl-8 border-l-2 border-black space-y-6 py-2 font-mono">
                  {timelineData.events.map((ev: TimelineEvent, idx: number) => {
                    const isDecision = ev.event_type === 'decision_date';
                    const isViolation = ev.classification === 'suspicious' || ev.classification === 'confirmed';

                    return (
                      <div key={idx} className="relative group">
                        {/* Timeline Marker Dot */}
                        <div
                          className={`absolute -left-[31px] sm:-left-[39px] top-1 w-4 h-4 rounded-full border-2 border-black ${
                            isViolation
                              ? 'bg-[#ff3b30]'
                              : isDecision
                              ? 'bg-black'
                              : 'bg-white'
                          }`}
                        />

                        {/* Event Card */}
                        <div
                          className={`p-4 border border-black bg-white shadow-[2px_2px_0px_0px_#000000] ${
                            isViolation ? 'border-l-4 border-l-[#ff3b30]' : ''
                          }`}
                        >
                          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-zinc-200 pb-2 mb-2">
                            <div className="flex items-center gap-2">
                              <span className="font-bold text-black text-sm">{ev.date}</span>
                              <Badge
                                variant={
                                  ev.classification === 'ok'
                                    ? 'pass'
                                    : ev.classification === 'suspicious'
                                    ? 'warn'
                                    : ev.classification === 'confirmed'
                                    ? 'fail'
                                    : 'neutral'
                                }
                                size="sm"
                              >
                                {ev.event_type.replace(/_/g, ' ')}
                              </Badge>
                            </div>

                            <div className="text-[11px] font-bold text-zinc-500 uppercase">
                              Class: {ev.classification}
                            </div>
                          </div>

                          <p className="text-xs text-zinc-800 leading-relaxed font-sans">
                            {ev.description}
                          </p>

                          {/* Event Details pill tags */}
                          {ev.details && Object.keys(ev.details).length > 0 && (
                            <div className="mt-3 pt-2 border-t border-zinc-100 flex flex-wrap gap-2 text-[10px]">
                              {Object.entries(ev.details).map(([k, v]) => (
                                <span key={k} className="px-1.5 py-0.5 bg-zinc-100 border border-zinc-300 text-zinc-700">
                                  {k}: <span className="font-bold text-black">{String(v)}</span>
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </Card>

          {/* Findings Table */}
          <Card tag="FINDINGS LOG" title={`Look-Ahead Findings (${findingsData?.length || 0})`}>
            {isFindingsLoading ? (
              <LoadingSpinner label="Loading findings..." />
            ) : !findingsData || findingsData.length === 0 ? (
              <div className="py-8 text-center font-mono text-xs text-zinc-500">
                No look-ahead violations detected for this run.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left font-mono text-xs border-collapse">
                  <thead>
                    <tr className="bg-zinc-50 border-b border-black">
                      <th className="py-2.5 px-3 font-bold text-black uppercase w-20">Severity</th>
                      <th className="py-2.5 px-3 font-bold text-black uppercase w-28">Classification</th>
                      <th className="py-2.5 px-3 font-bold text-black uppercase">Finding & Explanation</th>
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
