import React from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  listDatasets,
  listAnalysisRuns,
  listReports,
  getRootHealth,
} from '../api/endpoints';
import { Button } from '../components/common/Button';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { GeometricGraphic } from '../components/common/GeometricGraphic';
import { FindingsBreakdownChart } from '../components/charts/FindingsBreakdownChart';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { ErrorAlert } from '../components/common/ErrorAlert';
import {
  ArrowUpRight,
  Database,
  PlaySquare,
  FileText,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Sparkles,
} from 'lucide-react';

export const OverviewDashboard: React.FC = () => {
  const {
    data: health,
    isLoading: isHealthLoading,
    isError: isHealthError,
    error: healthError,
  } = useQuery({
    queryKey: ['rootHealth'],
    queryFn: getRootHealth,
  });

  const {
    data: datasets,
    isLoading: isDatasetsLoading,
  } = useQuery({
    queryKey: ['datasets'],
    queryFn: () => listDatasets({ include_existing: true }),
  });

  const {
    data: runs,
    isLoading: isRunsLoading,
  } = useQuery({
    queryKey: ['analysisRuns'],
    queryFn: () => listAnalysisRuns({ limit: 10 }),
  });

  const {
    data: reports,
    isLoading: isReportsLoading,
  } = useQuery({
    queryKey: ['reports'],
    queryFn: () => listReports({ limit: 10 }),
  });

  const isLoading = isHealthLoading || isDatasetsLoading || isRunsLoading || isReportsLoading;

  // Compute metrics from actual API data
  const totalDatasets = datasets?.length ?? 0;
  const totalRuns = runs?.length ?? 0;
  const totalReports = reports?.length ?? 0;
  const totalFindingsAcrossRuns = runs?.reduce((acc, r) => acc + (r.findings_count || 0), 0) ?? 0;

  // Construct chart data from recent runs
  const analyzerBreakdown = React.useMemo(() => {
    let surv = 0;
    let look = 0;
    let corp = 0;
    runs?.forEach((r) => {
      if (r.analyzers_executed?.includes('survivorship')) surv += 1;
      if (r.analyzers_executed?.includes('lookahead')) look += 1;
      if (r.analyzers_executed?.includes('corporate_actions')) corp += 1;
    });
    return [
      { name: 'Survivorship', count: surv, color: '#4a8b9f' },
      { name: 'Look-Ahead', count: look, color: '#ff3b30' },
      { name: 'Corporate Actions', count: corp, color: '#09090b' },
    ];
  }, [runs]);

  return (
    <div className="space-y-8">
      {/* Devlab Hero Section */}
      <section className="border border-black bg-white shadow-[4px_4px_0px_0px_#000000]">
        <div className="grid grid-cols-1 lg:grid-cols-12">
          {/* Hero Left Content */}
          <div className="lg:col-span-7 p-6 sm:p-10 flex flex-col justify-between border-b lg:border-b-0 lg:border-r border-black">
            <div className="space-y-4">
              <div className="inline-flex items-center gap-1.5 text-xs font-mono font-bold uppercase tracking-widest text-[#ff3b30]">
                <span>✦</span>
                <span>QUANTITATIVE RELIABILITY AUDITOR</span>
              </div>

              <h1 className="text-3xl sm:text-5xl font-bold tracking-tight text-black leading-tight">
                Backtest reliability analysis for quantitative strategies.
              </h1>

              <p className="text-sm sm:text-base text-zinc-600 max-w-xl leading-relaxed">
                Detect survivorship bias, temporal look-ahead leakage, and unadjusted corporate actions
                anomalies before deploying live capital.
              </p>

              {/* Devlab Pill CTA buttons */}
              <div className="pt-2 flex flex-wrap items-center gap-3">
                <Link to="/runs">
                  <Button variant="black" size="lg" icon={<PlaySquare className="w-4 h-4" />}>
                    <span>LAUNCH AUDIT</span>
                    <ArrowUpRight className="w-4 h-4" />
                  </Button>
                </Link>
                <Link to="/datasets">
                  <Button variant="white" size="lg" icon={<Database className="w-4 h-4" />}>
                    MANAGE DATASETS
                  </Button>
                </Link>
              </div>
            </div>

            {/* Sub-bullet annotations (Devlab style) */}
            <div className="mt-8 pt-6 border-t border-zinc-200 flex flex-wrap items-center gap-6 text-xs font-mono text-zinc-600">
              <div className="flex items-center gap-1.5">
                <span className="text-[#ff3b30] font-bold">*</span>
                <span>Zero Hardcoded Data</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-[#ff3b30] font-bold">*</span>
                <span>Point-in-Time Universe</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-[#ff3b30] font-bold">*</span>
                <span>Audit-Grade PDF Exports</span>
              </div>
            </div>
          </div>

          {/* Hero Right: Geometric Graphic */}
          <div className="lg:col-span-5 bg-white p-4 sm:p-6 flex items-center justify-center">
            <GeometricGraphic className="w-full max-w-[340px] h-[340px] sm:h-[380px]" />
          </div>
        </div>

        {/* Devlab Bottom Metrics Row (Thin Black Grid Columns) */}
        <div className="grid grid-cols-2 md:grid-cols-4 border-t border-black bg-[#fafafa]">
          <div className="p-4 sm:p-6 border-r border-b md:border-b-0 border-black">
            <div className="text-2xl sm:text-4xl font-bold font-mono text-black">
              {isLoading ? '...' : totalDatasets}
            </div>
            <div className="text-xs font-mono uppercase tracking-wider text-zinc-500 mt-1">
              Active Datasets
            </div>
          </div>

          <div className="p-4 sm:p-6 border-b md:border-b-0 md:border-r border-black">
            <div className="text-2xl sm:text-4xl font-bold font-mono text-black">
              {isLoading ? '...' : totalRuns}
            </div>
            <div className="text-xs font-mono uppercase tracking-wider text-zinc-500 mt-1">
              Completed Runs
            </div>
          </div>

          <div className="p-4 sm:p-6 border-r border-black">
            <div className="text-2xl sm:text-4xl font-bold font-mono text-black">
              {isLoading ? '...' : totalReports}
            </div>
            <div className="text-xs font-mono uppercase tracking-wider text-zinc-500 mt-1">
              Audit Reports
            </div>
          </div>

          <div className="p-4 sm:p-6 bg-white">
            <div className="text-2xl sm:text-4xl font-bold font-mono flex items-center gap-2">
              <span
                className={`w-3.5 h-3.5 rounded-full inline-block ${
                  health?.status === 'ok' ? 'bg-[#16a34a]' : 'bg-[#dc2626]'
                }`}
              />
              <span className="text-black text-xl sm:text-2xl uppercase">
                {health?.status === 'ok' ? 'ONLINE' : 'OFFLINE'}
              </span>
            </div>
            <div className="text-xs font-mono uppercase tracking-wider text-zinc-500 mt-1">
              FastAPI Backend Status
            </div>
          </div>
        </div>
      </section>

      {/* Backend connection warning if offline */}
      {isHealthError && (
        <ErrorAlert
          title="Backend Connection Error"
          message="Could not connect to FastAPI server at http://localhost:8000. Verify the backend process is running."
          details={healthError instanceof Error ? healthError.message : undefined}
        />
      )}

      {/* Mid Section: Engines & Quick Launcher */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Engine 1: Survivorship */}
        <Card
          tag="ANALYZER 01"
          title="Survivorship Bias"
          subtitle="Reconciles historical index constituents against delisted firms"
          hoverable
        >
          <p className="text-xs text-zinc-600 mb-4 leading-relaxed">
            Checks that inactive, delisted, or acquired stocks are included in historical universe backtests.
          </p>
          <div className="pt-3 border-t border-zinc-200 flex items-center justify-between">
            <Badge variant="blue">UNIVERSE RECON</Badge>
            <Link to="/survivorship">
              <Button variant="black" size="sm">
                RUN ↗
              </Button>
            </Link>
          </div>
        </Card>

        {/* Engine 2: Look-Ahead */}
        <Card
          tag="ANALYZER 02"
          title="Look-Ahead Bias"
          subtitle="Temporal sequencing & exchange dissemination times"
          hoverable
        >
          <p className="text-xs text-zinc-600 mb-4 leading-relaxed">
            Prevents trading strategies from acting on financial results or corporate actions before public publication.
          </p>
          <div className="pt-3 border-t border-zinc-200 flex items-center justify-between">
            <Badge variant="red">TEMPORAL AUDIT</Badge>
            <Link to="/lookahead">
              <Button variant="black" size="sm">
                RUN ↗
              </Button>
            </Link>
          </div>
        </Card>

        {/* Engine 3: Corporate Actions */}
        <Card
          tag="ANALYZER 03"
          title="Corporate Actions"
          subtitle="Ex-date vs Record-date entitlement and price leaps"
          hoverable
        >
          <p className="text-xs text-zinc-600 mb-4 leading-relaxed">
            Audits stock splits, bonuses, and dividend records for unadjusted price discontinuities and inverted dates.
          </p>
          <div className="pt-3 border-t border-zinc-200 flex items-center justify-between">
            <Badge variant="neutral">PRICE DISCONTINUITY</Badge>
            <Link to="/corporate-actions">
              <Button variant="black" size="sm">
                RUN ↗
              </Button>
            </Link>
          </div>
        </Card>
      </div>

      {/* Analytics & Recent Runs */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Execution Frequency Chart */}
        <div className="lg:col-span-5">
          <Card
            tag="AUDIT METRICS"
            title="Analysis Engine Coverage"
            subtitle="Distribution of recent analysis run executions"
          >
            <FindingsBreakdownChart data={analyzerBreakdown} />
            <div className="mt-4 pt-3 border-t border-zinc-200 text-xs font-mono text-zinc-600 space-y-1">
              <div className="flex justify-between">
                <span>Total Accumulated Findings:</span>
                <span className="font-bold text-black">{totalFindingsAcrossRuns}</span>
              </div>
              <div className="flex justify-between">
                <span>Storage Directory Mode:</span>
                <span className="font-bold text-black">Isolated Subtrees</span>
              </div>
            </div>
          </Card>
        </div>

        {/* Right: Recent Runs Table */}
        <div className="lg:col-span-7">
          <Card
            tag="RECENT AUDITS"
            title="Recent Analysis Runs"
            subtitle="Execution status, findings count, and reports"
            action={
              <Link to="/runs">
                <Button variant="white" size="sm">
                  VIEW ALL
                </Button>
              </Link>
            }
          >
            {isRunsLoading ? (
              <LoadingSpinner label="Fetching recent runs..." />
            ) : !runs || runs.length === 0 ? (
              <div className="py-8 text-center font-mono text-xs text-zinc-500 border border-dashed border-zinc-200">
                No analysis runs recorded yet. Start your first run above.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left font-mono text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-black bg-zinc-50">
                      <th className="py-2 px-3 font-bold text-black">RUN ID</th>
                      <th className="py-2 px-3 font-bold text-black">STATUS</th>
                      <th className="py-2 px-3 font-bold text-black">ANALYZERS</th>
                      <th className="py-2 px-3 font-bold text-black text-right">FINDINGS</th>
                      <th className="py-2 px-3 font-bold text-black text-right">ACTION</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-200">
                    {runs.slice(0, 5).map((run) => (
                      <tr key={run.run_id} className="hover:bg-zinc-50">
                        <td className="py-2.5 px-3 font-bold text-black">{run.run_id}</td>
                        <td className="py-2.5 px-3">
                          <Badge
                            variant={
                              run.status === 'completed'
                                ? 'pass'
                                : run.status === 'failed'
                                ? 'fail'
                                : 'warn'
                            }
                            size="sm"
                          >
                            {run.status}
                          </Badge>
                        </td>
                        <td className="py-2.5 px-3 text-zinc-600">
                          {run.analyzers_executed?.join(', ') || 'None'}
                        </td>
                        <td className="py-2.5 px-3 text-right font-bold">
                          {run.findings_count}
                        </td>
                        <td className="py-2.5 px-3 text-right">
                          <Link
                            to={`/runs/${run.run_id}`}
                            className="text-[#ff3b30] hover:underline font-bold"
                          >
                            Inspect ↗
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
};
