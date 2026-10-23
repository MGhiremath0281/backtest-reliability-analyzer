import React, { useState, useMemo } from 'react';
import {
  Search,
  Filter,
  Eye,
  AlertTriangle,
  FileCode,
  Download,
  RefreshCw,
  Layers,
  CheckCircle,
} from 'lucide-react';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import { DataTable } from '../../components/common/DataTable';
import { EmptyState } from '../../components/common/EmptyState';
import { LoadingSpinner } from '../../components/common/LoadingSpinner';
import { useAnalysisRuns, useAnalysisRunFindings } from '../../hooks/useAnalysisRuns';
import type { FindingModel } from '../../api/types';

export const FindingsExplorerPage: React.FC = () => {
  const { data: runs, isLoading: isRunsLoading, refetch: refetchRuns } = useAnalysisRuns();

  const [selectedRunId, setSelectedRunId] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState('');
  const [severityFilter, setSeverityFilter] = useState<string>('all');
  const [analyzerFilter, setAnalyzerFilter] = useState<string>('all');
  const [selectedFinding, setSelectedFinding] = useState<FindingModel | null>(null);

  // Default to first run with findings, or first run in list
  React.useEffect(() => {
    if (!selectedRunId && runs && runs.length > 0) {
      const runWithFindings = runs.find((r) => r.findings_count > 0);
      setSelectedRunId(runWithFindings ? runWithFindings.run_id : runs[0].run_id);
    }
  }, [runs, selectedRunId]);

  const {
    data: findings,
    isLoading: isFindingsLoading,
    refetch: refetchFindings,
  } = useAnalysisRunFindings(selectedRunId || undefined);

  // Filter findings client-side
  const filteredFindings = useMemo(() => {
    if (!findings) return [];

    return findings.filter((f) => {
      const matchesSeverity =
        severityFilter === 'all' ||
        f.severity.toLowerCase() === severityFilter.toLowerCase();
      const matchesAnalyzer =
        analyzerFilter === 'all' ||
        f.analyzer?.toLowerCase() === analyzerFilter.toLowerCase();
      const matchesSearch =
        !searchQuery ||
        f.code.toLowerCase().includes(searchQuery.toLowerCase()) ||
        f.message.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (f.description && f.description.toLowerCase().includes(searchQuery.toLowerCase()));

      return matchesSeverity && matchesAnalyzer && matchesSearch;
    });
  }, [findings, severityFilter, analyzerFilter, searchQuery]);

  // Metric counts
  const severityCounts = useMemo(() => {
    const counts: Record<string, number> = {
      critical: 0,
      high: 0,
      medium: 0,
      low: 0,
      info: 0,
    };
    (findings || []).forEach((f) => {
      const sev = f.severity?.toLowerCase() || 'info';
      if (counts[sev] !== undefined) counts[sev]++;
    });
    return counts;
  }, [findings]);

  const handleExportJson = () => {
    if (!filteredFindings.length) return;
    const blob = new Blob([JSON.stringify(filteredFindings, null, 2)], {
      type: 'application/json',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `findings_${selectedRunId || 'export'}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const columns = [
    {
      header: 'SEVERITY',
      accessor: (f: FindingModel) => <Badge variant={f.severity}>{f.severity}</Badge>,
    },
    {
      header: 'ANALYZER',
      accessor: (f: FindingModel) => (
        <span className="font-mono text-xs uppercase px-2 py-0.5 bg-black/5 border border-black/20">
          {f.analyzer}
        </span>
      ),
    },
    {
      header: 'CODE',
      accessor: (f: FindingModel) => (
        <span className="font-mono text-xs font-bold text-black">{f.code}</span>
      ),
    },
    {
      header: 'MESSAGE',
      accessor: (f: FindingModel) => (
        <div className="text-xs font-mono max-w-md">
          <p className="line-clamp-2 text-black font-medium">{f.message}</p>
        </div>
      ),
    },
    {
      header: 'ACTIONS',
      accessor: (f: FindingModel) => (
        <Button
          variant="ghost"
          size="sm"
          icon={<Eye size={12} />}
          onClick={() => setSelectedFinding(f)}
        >
          Inspect
        </Button>
      ),
    },
  ];

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 border-b border-black pb-6">
        <div>
          <div className="text-xs font-mono uppercase tracking-widest text-black/60 mb-1">
            // RISK & INTEGRITY AUDITING
          </div>
          <h1 className="text-3xl md:text-5xl font-black uppercase tracking-tight text-black">
            Findings Explorer
          </h1>
          <p className="text-sm text-black/70 mt-2 max-w-2xl font-mono">
            Investigate flagged anomalies, survivorship distortions, look-ahead leaks, and
            unadjusted corporate action anomalies with full granular evidence.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant="white"
            size="md"
            icon={<RefreshCw size={14} />}
            onClick={() => {
              refetchRuns();
              if (selectedRunId) refetchFindings();
            }}
          >
            Refresh
          </Button>
          <Button
            variant="black"
            size="md"
            icon={<Download size={14} />}
            disabled={!filteredFindings.length}
            onClick={handleExportJson}
          >
            Export JSON
          </Button>
        </div>
      </div>

      {/* Metric Breakdown Grid */}
      <div className="grid grid-cols-2 md:grid-cols-5 border border-black bg-white shadow-bra text-center">
        <div className="p-4 border-r border-b md:border-b-0 border-black">
          <div className="text-[10px] font-mono uppercase tracking-wider text-bra-red mb-1">
            Critical
          </div>
          <div className="text-3xl font-black font-mono text-bra-red">
            {severityCounts.critical}
          </div>
        </div>

        <div className="p-4 border-r border-b md:border-b-0 border-black">
          <div className="text-[10px] font-mono uppercase tracking-wider text-rose-600 mb-1">
            High
          </div>
          <div className="text-3xl font-black font-mono text-rose-600">
            {severityCounts.high}
          </div>
        </div>

        <div className="p-4 border-r border-b md:border-b-0 border-black">
          <div className="text-[10px] font-mono uppercase tracking-wider text-amber-600 mb-1">
            Medium
          </div>
          <div className="text-3xl font-black font-mono text-amber-600">
            {severityCounts.medium}
          </div>
        </div>

        <div className="p-4 border-r border-black">
          <div className="text-[10px] font-mono uppercase tracking-wider text-bra-blue mb-1">
            Low
          </div>
          <div className="text-3xl font-black font-mono text-bra-blue">
            {severityCounts.low}
          </div>
        </div>

        <div className="p-4">
          <div className="text-[10px] font-mono uppercase tracking-wider text-black/60 mb-1">
            Info
          </div>
          <div className="text-3xl font-black font-mono">{severityCounts.info}</div>
        </div>
      </div>

      {/* Filter and Selection Bar */}
      <div className="p-4 border border-black bg-white shadow-bra-sm flex flex-col md:flex-row gap-4 items-stretch md:items-center justify-between">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono uppercase text-black/70 font-bold flex items-center gap-1">
              <Layers size={13} /> Source Run:
            </span>
            <select
              value={selectedRunId}
              onChange={(e) => setSelectedRunId(e.target.value)}
              className="px-3 py-1.5 bg-white border border-black text-xs font-mono focus:outline-none"
            >
              {runs?.map((r) => (
                <option key={r.run_id} value={r.run_id}>
                  {r.run_id} ({r.findings_count} findings) — {r.dataset_id}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs font-mono uppercase text-black/70 font-bold">Severity:</span>
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="px-3 py-1.5 bg-white border border-black text-xs font-mono focus:outline-none"
            >
              <option value="all">ALL SEVERITIES</option>
              <option value="critical">CRITICAL</option>
              <option value="high">HIGH</option>
              <option value="medium">MEDIUM</option>
              <option value="low">LOW</option>
              <option value="info">INFO</option>
            </select>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs font-mono uppercase text-black/70 font-bold">Engine:</span>
            <select
              value={analyzerFilter}
              onChange={(e) => setAnalyzerFilter(e.target.value)}
              className="px-3 py-1.5 bg-white border border-black text-xs font-mono focus:outline-none"
            >
              <option value="all">ALL ENGINES</option>
              <option value="survivorship">SURVIVORSHIP</option>
              <option value="lookahead">LOOK-AHEAD</option>
              <option value="corporate_actions">CORPORATE ACTIONS</option>
              <option value="validation">VALIDATION</option>
            </select>
          </div>
        </div>

        <div className="relative min-w-[240px]">
          <Search size={14} className="absolute left-3 top-2.5 text-black/40" />
          <input
            type="text"
            placeholder="Search code, message, symbol..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 bg-white border border-black text-xs font-mono focus:outline-none"
          />
        </div>
      </div>

      {/* Main Findings Table */}
      <Card
        title={`AUDIT FINDINGS REGISTRY (${filteredFindings.length})`}
        tag="✦ VERIFIED FINDINGS"
      >
        {isFindingsLoading || isRunsLoading ? (
          <div className="py-16">
            <LoadingSpinner label="Fetching audit findings..." />
          </div>
        ) : !runs || runs.length === 0 ? (
          <EmptyState
            title="NO RUNS AVAILABLE"
            description="Execute an analysis run first to inspect verification findings."
          />
        ) : filteredFindings.length === 0 ? (
          <EmptyState
            title="NO FINDINGS FLAGGED"
            description={
              findings && findings.length > 0
                ? 'No findings match your current filters.'
                : 'This analysis run executed cleanly with zero anomalies detected.'
            }
          />
        ) : (
          <DataTable
            columns={columns}
            data={filteredFindings}
            keyExtractor={(f, i) => `${f.code}-${i}`}
            pageSize={12}
          />
        )}
      </Card>

      {/* Finding Detail Inspection Drawer */}
      {selectedFinding && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60"
          onClick={() => setSelectedFinding(null)}
        >
          <div
            className="bg-white border-2 border-black max-w-2xl w-full p-6 shadow-bra-lg space-y-4 max-h-[85vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex justify-between items-start border-b border-black pb-3">
              <div>
                <Badge variant={selectedFinding.severity}>{selectedFinding.severity}</Badge>
                <h3 className="text-lg font-black font-mono uppercase mt-2">
                  {selectedFinding.code}: {selectedFinding.message}
                </h3>
                <span className="text-xs font-mono text-black/60">
                  Engine: <span className="font-bold uppercase">{selectedFinding.analyzer}</span>
                </span>
              </div>
              <button
                onClick={() => setSelectedFinding(null)}
                className="text-black hover:text-bra-red font-mono font-bold text-lg"
              >
                ✕
              </button>
            </div>

            {selectedFinding.description && (
              <div>
                <h4 className="text-xs font-mono uppercase tracking-wider text-black/60 mb-1">
                  Description & Context
                </h4>
                <p className="text-xs font-mono bg-bra-muted p-3 border border-black/10">
                  {selectedFinding.description}
                </p>
              </div>
            )}

            {selectedFinding.evidence && (
              <div>
                <h4 className="text-xs font-mono uppercase tracking-wider text-black/60 mb-1 flex items-center gap-1.5">
                  <FileCode size={13} /> Evidence Payload
                </h4>
                <pre className="text-xs font-mono bg-bra-muted p-3 border border-black/10 overflow-x-auto max-h-64">
                  {JSON.stringify(selectedFinding.evidence, null, 2)}
                </pre>
              </div>
            )}

            <div className="flex justify-end pt-3 border-t border-black/10">
              <Button variant="black" size="sm" onClick={() => setSelectedFinding(null)}>
                Close
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
