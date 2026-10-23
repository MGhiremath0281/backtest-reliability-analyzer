import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  FileText,
  StopCircle,
  AlertTriangle,
  RotateCw,
  Eye,
} from 'lucide-react';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import { DataTable } from '../../components/common/DataTable';
import { LoadingSpinner } from '../../components/common/LoadingSpinner';
import { ErrorAlert } from '../../components/common/ErrorAlert';
import {
  useAnalysisRunDetail,
  useAnalysisRunSummary,
  useAnalysisRunFindings,
  useAnalysisRunEvents,
  useCancelAnalysisRun,
} from '../../hooks/useAnalysisRuns';
import type { FindingModel, RunEvent } from '../../api/types';

export const AnalysisRunDetailPage: React.FC = () => {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<'overview' | 'findings' | 'events' | 'raw'>('overview');
  const [selectedSeverity, setSelectedSeverity] = useState<string>('all');
  const [activeFinding, setActiveFinding] = useState<FindingModel | null>(null);

  const {
    data: run,
    isLoading: isRunLoading,
    isError: isRunError,
    error: runError,
    refetch: refetchRun,
  } = useAnalysisRunDetail(runId);

  const { data: summary } = useAnalysisRunSummary(runId);
  const { data: findings } = useAnalysisRunFindings(runId);
  const { data: events } = useAnalysisRunEvents(runId);
  const cancelMutation = useCancelAnalysisRun();

  if (isRunLoading) {
    return (
      <div className="py-24">
        <LoadingSpinner label={`Loading analysis run ${runId}...`} />
      </div>
    );
  }

  if (isRunError || !run) {
    return (
      <div className="space-y-6">
        <Button
          variant="ghost"
          icon={<ArrowLeft size={14} />}
          onClick={() => navigate('/runs')}
        >
          Back to Runs
        </Button>
        <ErrorAlert
          error={runError}
          title={`Analysis run "${runId}" not found`}
          onRetry={() => refetchRun()}
        />
      </div>
    );
  }

  const handleCancel = async () => {
    if (!runId) return;
    try {
      await cancelMutation.mutateAsync(runId);
    } catch {
      // Handled by mutation
    }
  };

  const filteredFindings = (findings || run.findings || []).filter((f) => {
    if (selectedSeverity === 'all') return true;
    return f.severity.toLowerCase() === selectedSeverity.toLowerCase();
  });

  const getStatusBadge = (status: string) => {
    const s = status.toUpperCase();
    if (s === 'COMPLETED' || s === 'PASS') return <Badge variant="PASS">COMPLETED</Badge>;
    if (s.includes('PARTIAL') || s === 'WARN') return <Badge variant="WARN">PARTIAL FAILURE</Badge>;
    if (s.includes('FAIL')) return <Badge variant="FAIL">FAILED</Badge>;
    return <Badge variant="info">{s}</Badge>;
  };

  const findingColumns = [
    {
      header: 'SEVERITY',
      accessor: (f: FindingModel) => <Badge variant={f.severity}>{f.severity}</Badge>,
    },
    {
      header: 'ANALYZER',
      accessor: (f: FindingModel) => (
        <span className="font-mono text-xs uppercase px-1.5 py-0.5 bg-black/5 border border-black/20">
          {f.analyzer}
        </span>
      ),
    },
    {
      header: 'CODE',
      accessor: (f: FindingModel) => <span className="font-mono text-xs font-bold">{f.code}</span>,
    },
    {
      header: 'MESSAGE',
      accessor: (f: FindingModel) => <span className="text-xs line-clamp-2">{f.message}</span>,
    },
    {
      header: 'ACTION',
      accessor: (f: FindingModel) => (
        <Button
          variant="ghost"
          size="sm"
          icon={<Eye size={12} />}
          onClick={() => setActiveFinding(f)}
        >
          Inspect
        </Button>
      ),
    },
  ];

  const eventColumns = [
    {
      header: 'TIMESTAMP',
      accessor: (e: RunEvent) => (
        <span className="font-mono text-xs text-black/70">
          {new Date(e.timestamp).toLocaleTimeString()}
        </span>
      ),
    },
    {
      header: 'EVENT DETAILS',
      accessor: (e: RunEvent) => (
        <div className="font-mono text-xs">
          <span className="font-bold">{e.event}</span>
          {e.run_id && <span className="text-[10px] text-black/50 ml-2">[{e.run_id}]</span>}
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-start justify-between gap-4 border-b border-black pb-6">
        <div>
          <button
            onClick={() => navigate('/runs')}
            className="flex items-center gap-1.5 text-xs font-mono uppercase text-black/60 hover:text-black mb-2 transition-colors"
          >
            <ArrowLeft size={12} /> Back to Analysis Runs
          </button>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl md:text-4xl font-black uppercase tracking-tight text-black font-mono">
              {run.run_id}
            </h1>
            {getStatusBadge(run.status)}
          </div>
          <p className="text-xs text-black/60 mt-1 font-mono">
            Dataset: <span className="font-bold text-black">{run.dataset_id}</span> • Created:{' '}
            {new Date(run.created_at).toLocaleString()}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <Button
            variant="white"
            size="sm"
            icon={<RotateCw size={14} />}
            onClick={() => refetchRun()}
          >
            Reload
          </Button>
          {run.status === 'running' && (
            <Button
              variant="red"
              size="sm"
              icon={<StopCircle size={14} />}
              loading={cancelMutation.isPending}
              onClick={handleCancel}
            >
              Cancel Run
            </Button>
          )}
          {run.report_id && (
            <Button
              variant="black"
              size="sm"
              icon={<FileText size={14} />}
              onClick={() => navigate(`/reports`)}
            >
              Inspect Reports
            </Button>
          )}
        </div>
      </div>

      {/* KPI Metric Strip */}
      <div className="grid grid-cols-2 md:grid-cols-5 border border-black bg-white shadow-bra text-center">
        <div className="p-4 border-r border-b md:border-b-0 border-black">
          <div className="text-[10px] font-mono uppercase tracking-wider text-black/60 mb-1">
            Total Findings
          </div>
          <div className="text-3xl font-black font-mono text-bra-red">
            {run.findings_count}
          </div>
        </div>

        <div className="p-4 border-r border-b md:border-b-0 border-black">
          <div className="text-[10px] font-mono uppercase tracking-wider text-black/60 mb-1">
            Errors Flagged
          </div>
          <div className="text-3xl font-black font-mono">{run.error_count}</div>
        </div>

        <div className="p-4 border-r border-b md:border-b-0 border-black">
          <div className="text-[10px] font-mono uppercase tracking-wider text-black/60 mb-1">
            Warnings
          </div>
          <div className="text-3xl font-black font-mono">{run.warning_count}</div>
        </div>

        <div className="p-4 border-r border-black">
          <div className="text-[10px] font-mono uppercase tracking-wider text-black/60 mb-1">
            Engines Run
          </div>
          <div className="text-3xl font-black font-mono">
            {run.analyzers_executed?.length || 0}
          </div>
        </div>

        <div className="p-4">
          <div className="text-[10px] font-mono uppercase tracking-wider text-black/60 mb-1">
            Report ID
          </div>
          <div className="text-xs font-bold font-mono truncate px-2 py-2">
            {run.report_id || 'N/A'}
          </div>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex border-b border-black">
        {[
          { id: 'overview', label: 'OVERVIEW & METRICS' },
          { id: 'findings', label: `FINDINGS (${run.findings_count})` },
          { id: 'events', label: `EVENT STREAM (${events?.length || run.events?.length || 0})` },
          { id: 'raw', label: 'RAW RUN PAYLOAD' },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            className={`px-5 py-2.5 text-xs font-mono uppercase font-bold tracking-wider transition-colors border-r border-black ${
              activeTab === tab.id
                ? 'bg-black text-white'
                : 'bg-white text-black hover:bg-black/5'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* TAB CONTENT: Overview */}
      {activeTab === 'overview' && (
        <div className="space-y-6">
          {/* Engine Status Grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {['survivorship', 'lookahead', 'corporate_actions'].map((engine) => {
              const executed = run.analyzers_executed?.includes(engine);
              const skipped = run.analyzers_skipped?.includes(engine);
              const engineSummary = summary?.by_analyzer?.[engine];

              return (
                <Card
                  key={engine}
                  title={`ENGINE: ${engine.toUpperCase()}`}
                  tag={executed ? '✦ ACTIVE' : 'SKIPPED'}
                >
                  <div className="space-y-3">
                    <div className="flex justify-between items-center text-xs font-mono">
                      <span className="text-black/60">Execution Status:</span>
                      <span className="font-bold uppercase">
                        {executed ? 'EXECUTED' : skipped ? 'SKIPPED' : 'UNREQUESTED'}
                      </span>
                    </div>

                    {engineSummary && (
                      <div className="pt-2 border-t border-black/10 space-y-1 text-xs font-mono">
                        <div className="flex justify-between">
                          <span className="text-black/60">Status:</span>
                          <span className="font-bold">{engineSummary.status}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-black/60">Errors:</span>
                          <span className="font-bold text-bra-red">{engineSummary.errors}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-black/60">Warnings:</span>
                          <span className="font-bold text-amber-600">{engineSummary.warnings}</span>
                        </div>
                      </div>
                    )}
                  </div>
                </Card>
              );
            })}
          </div>

          {/* Limitations Notice */}
          {run.limitations && run.limitations.length > 0 && (
            <div className="border border-black bg-amber-50 p-4">
              <div className="flex items-center gap-2 mb-2">
                <AlertTriangle size={16} className="text-amber-700" />
                <h4 className="text-xs font-mono uppercase font-bold text-amber-900 tracking-wider">
                  Operational Limitations & Assumptions Detected
                </h4>
              </div>
              <ul className="list-disc pl-5 space-y-1 text-xs font-mono text-amber-950">
                {run.limitations.map((limit, idx) => (
                  <li key={idx}>{limit}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* TAB CONTENT: Findings */}
      {activeTab === 'findings' && (
        <Card
          title="CONSOLIDATED VERIFICATION FINDINGS"
          tag="✦ AUDIT TRAIL"
          headerActions={
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono text-black/60 uppercase">Filter Severity:</span>
              <select
                value={selectedSeverity}
                onChange={(e) => setSelectedSeverity(e.target.value)}
                className="px-2 py-1 bg-white border border-black text-xs font-mono"
              >
                <option value="all">ALL SEVERITIES</option>
                <option value="critical">CRITICAL</option>
                <option value="high">HIGH</option>
                <option value="medium">MEDIUM</option>
                <option value="low">LOW</option>
                <option value="info">INFO</option>
              </select>
            </div>
          }
        >
          {filteredFindings.length === 0 ? (
            <div className="py-12 text-center text-xs font-mono text-black/50">
              No findings flagged under selected filter criteria.
            </div>
          ) : (
            <DataTable
              columns={findingColumns}
              data={filteredFindings}
              keyExtractor={(f, i) => `${f.code}-${i}`}
              pageSize={10}
            />
          )}
        </Card>
      )}

      {/* TAB CONTENT: Events */}
      {activeTab === 'events' && (
        <Card title="EXECUTION EVENT STREAM" tag="✦ TELEMETRY">
          <DataTable
            columns={eventColumns}
            data={events || run.events || []}
            keyExtractor={(_, i) => String(i)}
            pageSize={15}
          />
        </Card>
      )}

      {/* TAB CONTENT: Raw JSON */}
      {activeTab === 'raw' && (
        <Card title="RAW RUN RESPONSE" tag="✦ INSPECTION">
          <pre className="p-4 bg-bra-muted border border-black text-xs font-mono overflow-auto max-h-[600px]">
            {JSON.stringify(run, null, 2)}
          </pre>
        </Card>
      )}

      {/* Finding Inspection Modal */}
      {activeFinding && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60"
          onClick={() => setActiveFinding(null)}
        >
          <div
            className="bg-white border-2 border-black max-w-2xl w-full p-6 shadow-bra-lg space-y-4 max-h-[85vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex justify-between items-start border-b border-black pb-3">
              <div>
                <Badge variant={activeFinding.severity}>{activeFinding.severity}</Badge>
                <h3 className="text-lg font-black font-mono uppercase mt-2">
                  {activeFinding.code}: {activeFinding.message}
                </h3>
                <span className="text-xs font-mono text-black/60">
                  Analyzer: {activeFinding.analyzer}
                </span>
              </div>
              <button
                onClick={() => setActiveFinding(null)}
                className="text-black hover:text-bra-red font-mono font-bold text-lg"
              >
                ✕
              </button>
            </div>

            {activeFinding.description && (
              <div>
                <h4 className="text-xs font-mono uppercase tracking-wider text-black/60 mb-1">
                  Description
                </h4>
                <p className="text-xs font-mono bg-bra-muted p-3 border border-black/10">
                  {activeFinding.description}
                </p>
              </div>
            )}

            {activeFinding.evidence && (
              <div>
                <h4 className="text-xs font-mono uppercase tracking-wider text-black/60 mb-1">
                  Evidence Payload
                </h4>
                <pre className="text-xs font-mono bg-bra-muted p-3 border border-black/10 overflow-x-auto">
                  {JSON.stringify(activeFinding.evidence, null, 2)}
                </pre>
              </div>
            )}

            <div className="flex justify-end pt-3 border-t border-black/10">
              <Button variant="black" size="sm" onClick={() => setActiveFinding(null)}>
                Close
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
