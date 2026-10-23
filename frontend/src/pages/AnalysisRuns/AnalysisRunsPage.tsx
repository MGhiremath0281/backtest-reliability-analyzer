import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Play, RotateCw, ExternalLink, Activity, AlertTriangle, CheckCircle2, XCircle } from 'lucide-react';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import { DataTable } from '../../components/common/DataTable';
import { EmptyState } from '../../components/common/EmptyState';
import { ErrorAlert } from '../../components/common/ErrorAlert';
import { LoadingSpinner } from '../../components/common/LoadingSpinner';
import { AnalysisRunModal } from './AnalysisRunModal';
import { useAnalysisRuns } from '../../hooks/useAnalysisRuns';
import type { RunListItem } from '../../api/types';

export const AnalysisRunsPage: React.FC = () => {
  const navigate = useNavigate();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');

  const { data: runs, isLoading, isError, error, refetch, isFetching } = useAnalysisRuns();

  const handleRunCreated = (runId: string) => {
    navigate(`/runs/${runId}`);
  };

  const filteredRuns = (runs || []).filter((run) => {
    const matchesStatus =
      statusFilter === 'all' ||
      run.status.toLowerCase() === statusFilter.toLowerCase();
    const matchesSearch =
      run.run_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      run.dataset_id.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesStatus && matchesSearch;
  });

  const totalRuns = runs?.length || 0;
  const completedRuns = runs?.filter((r) => r.status.toLowerCase() === 'completed').length || 0;
  const partialRuns = runs?.filter((r) => r.status.toLowerCase().includes('partial')).length || 0;
  const failedRuns = runs?.filter((r) => r.status.toLowerCase().includes('fail')).length || 0;

  const columns = [
    {
      header: 'RUN ID',
      accessor: (run: RunListItem) => (
        <div className="font-mono text-xs">
          <span className="font-bold text-black">{run.run_id}</span>
          <div className="text-[10px] text-black/50">
            {new Date(run.created_at).toLocaleString()}
          </div>
        </div>
      ),
    },
    {
      header: 'DATASET',
      accessor: (run: RunListItem) => (
        <span className="font-mono text-xs px-2 py-0.5 bg-bra-muted border border-black/10">
          {run.dataset_id}
        </span>
      ),
    },
    {
      header: 'ENGINES EXECUTED',
      accessor: (run: RunListItem) => (
        <div className="flex flex-wrap gap-1">
          {run.analyzers_executed?.map((eng) => (
            <span
              key={eng}
              className="text-[10px] font-mono uppercase px-1.5 py-0.5 bg-black/5 border border-black/20"
            >
              {eng}
            </span>
          ))}
        </div>
      ),
    },
    {
      header: 'FINDINGS',
      accessor: (run: RunListItem) => (
        <div className="font-mono text-xs font-bold">
          {run.findings_count > 0 ? (
            <span className="text-bra-red">{run.findings_count} flagged</span>
          ) : (
            <span className="text-black/60">0 findings</span>
          )}
        </div>
      ),
    },
    {
      header: 'STATUS',
      accessor: (run: RunListItem) => {
        const s = run.status.toUpperCase();
        if (s === 'COMPLETED') return <Badge variant="PASS">COMPLETED</Badge>;
        if (s.includes('PARTIAL')) return <Badge variant="WARN">PARTIAL FAILURE</Badge>;
        if (s.includes('FAIL')) return <Badge variant="FAIL">FAILED</Badge>;
        return <Badge variant="info">{s}</Badge>;
      },
    },
    {
      header: 'ACTIONS',
      accessor: (run: RunListItem) => (
        <Button
          variant="ghost"
          size="sm"
          icon={<ExternalLink size={12} />}
          onClick={() => navigate(`/runs/${run.run_id}`)}
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
            // EXECUTION PIPELINE
          </div>
          <h1 className="text-3xl md:text-5xl font-black uppercase tracking-tight text-black">
            Analysis Runs
          </h1>
          <p className="text-sm text-black/70 mt-2 max-w-2xl font-mono">
            Orchestrate multi-engine reliability scans, track verification history, and inspect
            historical runs with full reproducibility.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant="white"
            size="md"
            icon={<RotateCw size={14} className={isFetching ? 'animate-spin' : ''} />}
            onClick={() => refetch()}
          >
            Refresh
          </Button>
          <Button
            variant="black"
            size="md"
            icon={<Play size={14} />}
            onClick={() => setIsModalOpen(true)}
          >
            New Run
          </Button>
        </div>
      </div>

      {/* Summary KPI Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 border border-black bg-white shadow-bra">
        <div className="p-4 border-r border-b md:border-b-0 border-black">
          <div className="text-[10px] font-mono uppercase tracking-wider text-black/60 mb-1 flex items-center gap-1.5">
            <Activity size={12} /> Total Executions
          </div>
          <div className="text-3xl font-black font-mono">{totalRuns}</div>
        </div>

        <div className="p-4 border-r border-b md:border-b-0 border-black">
          <div className="text-[10px] font-mono uppercase tracking-wider text-black/60 mb-1 flex items-center gap-1.5">
            <CheckCircle2 size={12} className="text-emerald-600" /> Completed Cleanly
          </div>
          <div className="text-3xl font-black font-mono">{completedRuns}</div>
        </div>

        <div className="p-4 border-r border-black">
          <div className="text-[10px] font-mono uppercase tracking-wider text-black/60 mb-1 flex items-center gap-1.5">
            <AlertTriangle size={12} className="text-amber-600" /> Partial Failures
          </div>
          <div className="text-3xl font-black font-mono">{partialRuns}</div>
        </div>

        <div className="p-4">
          <div className="text-[10px] font-mono uppercase tracking-wider text-black/60 mb-1 flex items-center gap-1.5">
            <XCircle size={12} className="text-bra-red" /> Execution Failures
          </div>
          <div className="text-3xl font-black font-mono">{failedRuns}</div>
        </div>
      </div>

      {isError && (
        <ErrorAlert
          error={error}
          title="Could not load analysis runs"
          onRetry={() => refetch()}
        />
      )}

      {/* Main Runs Table Card */}
      <Card
        title="EXECUTION REGISTRY"
        tag="✦ REAL-TIME"
        headerActions={
          <div className="flex items-center gap-3">
            <input
              type="text"
              placeholder="Search run ID or dataset..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="px-3 py-1 bg-white border border-black text-xs font-mono focus:outline-none w-48 md:w-64"
            />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-3 py-1 bg-white border border-black text-xs font-mono focus:outline-none"
            >
              <option value="all">ALL STATUSES</option>
              <option value="completed">COMPLETED</option>
              <option value="partial_failure">PARTIAL FAILURE</option>
              <option value="failed">FAILED</option>
            </select>
          </div>
        }
      >
        {isLoading ? (
          <div className="py-16">
            <LoadingSpinner label="Fetching analysis runs from engine..." />
          </div>
        ) : filteredRuns.length === 0 ? (
          <EmptyState
            title="NO ANALYSIS RUNS FOUND"
            description={
              runs && runs.length > 0
                ? 'No runs match your current status or search filter.'
                : 'No analysis runs have been executed yet. Launch your first multi-engine run to evaluate backtest reliability.'
            }
            actionLabel="Launch First Run"
            onAction={() => setIsModalOpen(true)}
          />
        ) : (
          <DataTable
            columns={columns}
            data={filteredRuns}
            keyExtractor={(run) => run.run_id}
            pageSize={10}
          />
        )}
      </Card>

      {/* Modal for launching runs */}
      <AnalysisRunModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSuccess={handleRunCreated}
      />
    </div>
  );
};
