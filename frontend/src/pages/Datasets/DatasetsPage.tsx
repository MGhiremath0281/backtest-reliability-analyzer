import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useDatasets, useDeleteDataset } from '../../hooks/useDatasets';
import { Button } from '../../components/common/Button';
import { Card } from '../../components/common/Card';
import { Badge } from '../../components/common/Badge';
import { LoadingSpinner } from '../../components/common/LoadingSpinner';
import { ErrorAlert } from '../../components/common/ErrorAlert';
import { EmptyState } from '../../components/common/EmptyState';
import { DatasetUploadModal } from './DatasetUploadModal';
import {
  Database,
  Plus,
  Trash2,
  CheckCircle2,
  Search,
  ArrowUpRight,
  ShieldCheck,
  FileSpreadsheet,
} from 'lucide-react';
import { formatApiError } from '../../api/client';

export const DatasetsPage: React.FC = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const { data: datasets, isLoading, isError, error, refetch } = useDatasets({
    include_existing: true,
  });

  const deleteMutation = useDeleteDataset();

  const filteredDatasets = React.useMemo(() => {
    if (!datasets) return [];
    if (!searchQuery.trim()) return datasets;
    const q = searchQuery.toLowerCase().trim();
    return datasets.filter(
      (d) =>
        d.dataset_id.toLowerCase().includes(q) ||
        (d.name && d.name.toLowerCase().includes(q)) ||
        (d.description && d.description.toLowerCase().includes(q))
    );
  }, [datasets, searchQuery]);

  const handleDelete = async (datasetId: string, isExisting: boolean) => {
    if (isExisting) {
      setDeleteError('Cannot delete canonical repository dataset. It is protected and read-only.');
      return;
    }

    if (!window.confirm(`Are you sure you want to permanently delete dataset ${datasetId}?`)) {
      return;
    }

    setDeleteError(null);
    try {
      await deleteMutation.mutateAsync(datasetId);
    } catch (err) {
      setDeleteError(formatApiError(err));
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-black pb-5">
        <div>
          <div className="text-xs font-mono font-bold uppercase tracking-widest text-[#ff3b30] flex items-center gap-1">
            <span>✦</span>
            <span>DATA MANAGEMENT</span>
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-black mt-1">
            Historical Datasets
          </h1>
          <p className="text-xs sm:text-sm text-zinc-600 mt-1">
            Manage canonical NSE reference data and uploaded equity files for bias testing.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant="black"
            onClick={() => setIsUploadOpen(true)}
            icon={<Plus className="w-4 h-4" />}
          >
            UPLOAD DATASET
          </Button>
        </div>
      </div>

      {deleteError && (
        <ErrorAlert
          title="Deletion Restrained"
          message={deleteError}
          onRetry={() => setDeleteError(null)}
        />
      )}

      {isError && (
        <ErrorAlert
          title="Failed to Load Datasets"
          message={formatApiError(error)}
          onRetry={() => refetch()}
        />
      )}

      {/* Filter / Search Bar */}
      <div className="flex items-center justify-between gap-4 bg-white p-3 border border-black shadow-[2px_2px_0px_0px_#000000]">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search datasets by ID or name..."
            className="w-full pl-9 pr-3 py-1.5 text-xs font-mono bg-white border border-black focus:outline-none focus:ring-1 focus:ring-black placeholder:text-zinc-400"
          />
        </div>

        <div className="text-xs font-mono text-zinc-500 font-bold hidden sm:block">
          TOTAL: {filteredDatasets.length} DATASETS
        </div>
      </div>

      {/* Datasets List */}
      {isLoading ? (
        <LoadingSpinner label="Loading dataset inventory..." />
      ) : filteredDatasets.length === 0 ? (
        <EmptyState
          title="No Datasets Found"
          description={
            searchQuery
              ? `No datasets matched query "${searchQuery}". Try a different keyword.`
              : 'Upload your first CSV market dataset to begin running bias analyses.'
          }
          actionLabel="UPLOAD DATASET"
          onAction={() => setIsUploadOpen(true)}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredDatasets.map((dataset) => (
            <Card
              key={dataset.dataset_id}
              tag={dataset.is_existing ? 'CANONICAL REPOSITORY' : 'USER UPLOAD'}
              title={dataset.name || dataset.dataset_id}
              subtitle={`ID: ${dataset.dataset_id}`}
              hoverable
            >
              <div className="space-y-4">
                <p className="text-xs text-zinc-600 line-clamp-2 min-h-[32px]">
                  {dataset.description || 'No description provided.'}
                </p>

                {/* Metadata Pills */}
                <div className="grid grid-cols-2 gap-2 pt-3 border-t border-zinc-200 text-xs font-mono">
                  <div className="p-2 border border-zinc-200 bg-zinc-50">
                    <span className="text-[10px] text-zinc-500 block uppercase">Files</span>
                    <span className="font-bold text-black">{dataset.file_count} CSV(s)</span>
                  </div>
                  <div className="p-2 border border-zinc-200 bg-zinc-50">
                    <span className="text-[10px] text-zinc-500 block uppercase">Rows</span>
                    <span className="font-bold text-black">
                      {dataset.total_rows > 0 ? dataset.total_rows.toLocaleString() : 'Tree'}
                    </span>
                  </div>
                </div>

                {/* Status Badges */}
                <div className="flex flex-wrap items-center gap-1.5 text-[10px]">
                  <Badge
                    variant={dataset.mapping_status === 'mapped' ? 'pass' : 'warn'}
                    size="sm"
                  >
                    MAP: {dataset.mapping_status}
                  </Badge>
                  <Badge
                    variant={dataset.preparation_status === 'prepared' ? 'pass' : 'neutral'}
                    size="sm"
                  >
                    PREP: {dataset.preparation_status}
                  </Badge>
                  {dataset.is_existing && (
                    <Badge variant="blue" size="sm">
                      READ-ONLY
                    </Badge>
                  )}
                </div>

                {/* Card Actions */}
                <div className="pt-3 border-t border-black flex items-center justify-between gap-2">
                  <Link to={`/datasets/${dataset.dataset_id}`} className="flex-1">
                    <Button variant="black" size="sm" className="w-full">
                      <span>INSPECT</span>
                      <ArrowUpRight className="w-3.5 h-3.5" />
                    </Button>
                  </Link>

                  {!dataset.is_existing && (
                    <button
                      type="button"
                      onClick={() => handleDelete(dataset.dataset_id, dataset.is_existing)}
                      className="p-2 border border-black hover:bg-red-50 text-red-600 cursor-pointer"
                      title="Delete Dataset"
                      disabled={deleteMutation.isPending}
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Upload Modal */}
      <DatasetUploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onSuccess={() => refetch()}
      />
    </div>
  );
};
