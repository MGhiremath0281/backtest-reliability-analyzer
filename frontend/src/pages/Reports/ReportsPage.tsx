import React, { useState } from 'react';
import {
  Download,
  AlertTriangle,
  RotateCw,
  FileCheck,
  Eye,
} from 'lucide-react';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import { DataTable } from '../../components/common/DataTable';
import { EmptyState } from '../../components/common/EmptyState';
import { LoadingSpinner } from '../../components/common/LoadingSpinner';
import { ErrorAlert } from '../../components/common/ErrorAlert';
import { useReports, useReportDetail } from '../../hooks/useReports';
import { downloadReportFile } from '../../api/endpoints';
import type { ReportSummaryModel } from '../../api/types';

export const ReportsPage: React.FC = () => {
  const [selectedReportId, setSelectedReportId] = useState<string | null>(null);
  const [downloadingFormat, setDownloadingFormat] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const { data: reports, isLoading, isError, error, refetch, isFetching } = useReports();
  const { data: reportDetail, isLoading: isDetailLoading } = useReportDetail(selectedReportId || undefined);

  const handleDownload = async (reportId: string, format: 'json' | 'csv' | 'pdf' | 'xlsx') => {
    setDownloadingFormat(`${reportId}-${format}`);
    setDownloadError(null);
    try {
      await downloadReportFile(reportId, format);
    } catch (err: any) {
      if (err.response?.status === 501 || format === 'xlsx') {
        setDownloadError(
          'Format "XLSX" is not implemented in the backend (HTTP 501 Not Implemented). Please download as PDF, CSV, or JSON.'
        );
      } else {
        setDownloadError(
          err.response?.data?.detail || err.message || 'Failed to download report file.'
        );
      }
    } finally {
      setDownloadingFormat(null);
    }
  };

  const columns = [
    {
      header: 'REPORT ID',
      accessor: (r: ReportSummaryModel) => (
        <div className="font-mono text-xs">
          <span className="font-bold text-black">{r.report_id}</span>
          <div className="text-[10px] text-black/50">
            {new Date(r.created_at).toLocaleString()}
          </div>
        </div>
      ),
    },
    {
      header: 'ASSOCIATED RUN',
      accessor: (r: ReportSummaryModel) => (
        <span className="font-mono text-xs px-2 py-0.5 bg-bra-muted border border-black/10">
          {r.run_id}
        </span>
      ),
    },
    {
      header: 'OVERALL STATUS',
      accessor: (r: ReportSummaryModel) => <Badge variant={r.overall_status}>{r.overall_status}</Badge>,
    },
    {
      header: 'ISSUES FLAGGED',
      accessor: (r: ReportSummaryModel) => (
        <div className="font-mono text-xs">
          <span className="text-bra-red font-bold">{r.error_count} errors</span>,{' '}
          <span className="text-amber-600">{r.warning_count} warnings</span>
        </div>
      ),
    },
    {
      header: 'SUPPORTED EXPORTS',
      accessor: (r: ReportSummaryModel) => (
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => handleDownload(r.report_id, 'pdf')}
            disabled={downloadingFormat === `${r.report_id}-pdf`}
            title="Download PDF Report"
            className="px-2 py-0.5 text-[10px] font-mono uppercase font-bold border border-black bg-white hover:bg-black hover:text-white transition-colors disabled:opacity-50"
          >
            {downloadingFormat === `${r.report_id}-pdf` ? '...' : 'PDF'}
          </button>
          <button
            onClick={() => handleDownload(r.report_id, 'csv')}
            disabled={downloadingFormat === `${r.report_id}-csv`}
            title="Download CSV"
            className="px-2 py-0.5 text-[10px] font-mono uppercase font-bold border border-black bg-white hover:bg-black hover:text-white transition-colors disabled:opacity-50"
          >
            {downloadingFormat === `${r.report_id}-csv` ? '...' : 'CSV'}
          </button>
          <button
            onClick={() => handleDownload(r.report_id, 'json')}
            disabled={downloadingFormat === `${r.report_id}-json`}
            title="Download JSON"
            className="px-2 py-0.5 text-[10px] font-mono uppercase font-bold border border-black bg-white hover:bg-black hover:text-white transition-colors disabled:opacity-50"
          >
            {downloadingFormat === `${r.report_id}-json` ? '...' : 'JSON'}
          </button>
          <button
            onClick={() => handleDownload(r.report_id, 'xlsx')}
            title="Excel Export (501 Not Implemented)"
            className="px-2 py-0.5 text-[10px] font-mono uppercase font-bold border border-black/30 bg-black/5 text-black/40 hover:bg-black/10 transition-colors"
          >
            XLSX
          </button>
        </div>
      ),
    },
    {
      header: 'ACTION',
      accessor: (r: ReportSummaryModel) => (
        <Button
          variant="ghost"
          size="sm"
          icon={<Eye size={12} />}
          onClick={() => setSelectedReportId(r.report_id)}
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
            // DOCUMENTATION & COMPLIANCE
          </div>
          <h1 className="text-3xl md:text-5xl font-black uppercase tracking-tight text-black">
            Generated Reports
          </h1>
          <p className="text-sm text-black/70 mt-2 max-w-2xl font-mono">
            Download formal quantitative audit dossiers in PDF, CSV, and JSON formats for audit
            committees, quantitative investment teams, and regulatory records.
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
        </div>
      </div>

      {downloadError && (
        <div className="border border-black bg-amber-50 p-4 flex items-start gap-3">
          <AlertTriangle size={18} className="text-amber-700 shrink-0 mt-0.5" />
          <div className="text-xs font-mono">
            <span className="font-bold text-amber-900 uppercase block mb-1">
              Notice: Format Limitation
            </span>
            <span className="text-amber-950">{downloadError}</span>
          </div>
        </div>
      )}

      {isError && (
        <ErrorAlert
          error={error}
          title="Could not retrieve reports list"
          onRetry={() => refetch()}
        />
      )}

      {/* Main Reports Table */}
      <Card title="REPORT ARCHIVE" tag="✦ FORMAL AUDIT TRAIL">
        {isLoading ? (
          <div className="py-16">
            <LoadingSpinner label="Fetching generated reports archive..." />
          </div>
        ) : !reports || reports.length === 0 ? (
          <EmptyState
            title="NO REPORTS GENERATED YET"
            description="Reports are created automatically whenever an analysis run completes. Launch an analysis run to generate your first audit report."
          />
        ) : (
          <DataTable
            columns={columns}
            data={reports}
            keyExtractor={(r) => r.report_id}
            pageSize={10}
          />
        )}
      </Card>

      {/* Format Support Matrix Card */}
      <div className="border border-black bg-white p-6 shadow-bra-sm">
        <h3 className="text-xs font-mono uppercase tracking-wider font-bold mb-4 flex items-center gap-2">
          <FileCheck size={14} className="text-bra-red" />
          Supported Export Formats Specification
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="border border-black p-3 bg-bra-muted/30">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-mono font-bold uppercase">PDF Report</span>
              <span className="text-[10px] font-mono text-emerald-600 font-bold">200 OK</span>
            </div>
            <p className="text-[11px] font-mono text-black/60">
              Formal visual report generated by ReportLab with tables and branding.
            </p>
          </div>

          <div className="border border-black p-3 bg-bra-muted/30">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-mono font-bold uppercase">CSV Flat</span>
              <span className="text-[10px] font-mono text-emerald-600 font-bold">200 OK</span>
            </div>
            <p className="text-[11px] font-mono text-black/60">
              Flat tabular findings export compatible with Pandas, Excel, and R.
            </p>
          </div>

          <div className="border border-black p-3 bg-bra-muted/30">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-mono font-bold uppercase">JSON Schema</span>
              <span className="text-[10px] font-mono text-emerald-600 font-bold">200 OK</span>
            </div>
            <p className="text-[11px] font-mono text-black/60">
              Full machine-readable nested JSON payload with complete evidence trees.
            </p>
          </div>

          <div className="border border-black p-3 bg-black/5">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-mono font-bold uppercase text-black/40">Excel (.XLSX)</span>
              <span className="text-[10px] font-mono text-amber-700 font-bold">501 NOT IMPL</span>
            </div>
            <p className="text-[11px] font-mono text-black/40">
              Native multi-sheet workbook generation is currently unsupported by the backend engine.
            </p>
          </div>
        </div>
      </div>

      {/* Report Inspection Modal */}
      {selectedReportId && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60"
          onClick={() => setSelectedReportId(null)}
        >
          <div
            className="bg-white border-2 border-black max-w-3xl w-full p-6 shadow-bra-lg space-y-5 max-h-[85vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            {isDetailLoading || !reportDetail ? (
              <div className="py-12">
                <LoadingSpinner label="Loading report details..." />
              </div>
            ) : (
              <>
                <div className="flex justify-between items-start border-b border-black pb-4">
                  <div>
                    <Badge variant={reportDetail.overall_status}>
                      {reportDetail.overall_status}
                    </Badge>
                    <h3 className="text-xl font-black font-mono uppercase mt-2">
                      Report: {reportDetail.report_id}
                    </h3>
                    <p className="text-xs font-mono text-black/60">
                      Run ID: {reportDetail.run_id} • Dataset: {reportDetail.dataset_id}
                    </p>
                  </div>
                  <button
                    onClick={() => setSelectedReportId(null)}
                    className="text-black hover:text-bra-red font-mono font-bold text-lg"
                  >
                    ✕
                  </button>
                </div>

                {/* Direct Download Action Row */}
                <div className="flex flex-wrap items-center gap-2 p-3 bg-bra-muted border border-black">
                  <span className="text-xs font-mono uppercase font-bold text-black/70 mr-2">
                    Download Report:
                  </span>
                  <Button
                    variant="black"
                    size="sm"
                    icon={<Download size={12} />}
                    onClick={() => handleDownload(reportDetail.report_id, 'pdf')}
                  >
                    PDF Format
                  </Button>
                  <Button
                    variant="white"
                    size="sm"
                    icon={<Download size={12} />}
                    onClick={() => handleDownload(reportDetail.report_id, 'csv')}
                  >
                    CSV Flat
                  </Button>
                  <Button
                    variant="white"
                    size="sm"
                    icon={<Download size={12} />}
                    onClick={() => handleDownload(reportDetail.report_id, 'json')}
                  >
                    JSON Payload
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    icon={<AlertTriangle size={12} />}
                    onClick={() => handleDownload(reportDetail.report_id, 'xlsx')}
                  >
                    Excel (.xlsx)
                  </Button>
                </div>

                {/* Limitations */}
                {reportDetail.limitations && reportDetail.limitations.length > 0 && (
                  <div className="border border-black bg-amber-50 p-3">
                    <h4 className="text-xs font-mono uppercase font-bold text-amber-900 mb-1">
                      Report Limitations & Warnings
                    </h4>
                    <ul className="list-disc pl-5 text-xs font-mono text-amber-950 space-y-0.5">
                      {reportDetail.limitations.map((lim, i) => (
                        <li key={i}>{lim}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Findings Count */}
                <div>
                  <h4 className="text-xs font-mono uppercase font-bold text-black/70 mb-2">
                    Report Findings ({reportDetail.findings?.length || 0})
                  </h4>
                  <div className="max-h-56 overflow-y-auto border border-black divide-y divide-black/10">
                    {reportDetail.findings?.map((f, i) => (
                      <div key={i} className="p-2.5 flex items-start gap-3 text-xs font-mono">
                        <Badge variant={f.severity}>{f.severity}</Badge>
                        <div>
                          <span className="font-bold">{f.code}</span>
                          <span className="text-black/50 ml-2">[{f.analyzer}]</span>
                          <p className="text-black/70 mt-0.5">{f.message}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="flex justify-end pt-3 border-t border-black/10">
                  <Button variant="black" size="sm" onClick={() => setSelectedReportId(null)}>
                    Close
                  </Button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
