import React, { useState } from 'react';
import { Play, Sparkles } from 'lucide-react';
import { Modal } from '../../components/common/Modal';
import { Button } from '../../components/common/Button';
import { ErrorAlert } from '../../components/common/ErrorAlert';
import { useDatasets } from '../../hooks/useDatasets';
import { useCreateAnalysisRun } from '../../hooks/useAnalysisRuns';
import type { AnalysisRunRequest } from '../../api/types';

interface AnalysisRunModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: (runId: string) => void;
}

export const AnalysisRunModal: React.FC<AnalysisRunModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  const { data: datasets } = useDatasets();
  const createRunMutation = useCreateAnalysisRun();

  const [datasetId, setDatasetId] = useState<string>('existing-data');
  const [selectedAnalyzers, setSelectedAnalyzers] = useState<string[]>([
    'survivorship',
    'lookahead',
    'corporate_actions',
  ]);

  // Backtest / Survivorship config
  const [targetIndex, setTargetIndex] = useState('NIFTY50');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [minCoverage, setMinCoverage] = useState('0.80');

  // Lookahead config
  const [decisionDates, setDecisionDates] = useState('');
  const [lookbackDays, setLookbackDays] = useState('365');

  // Corporate Actions config
  const [expectedSymbol, setExpectedSymbol] = useState('');

  const toggleAnalyzer = (name: string) => {
    setSelectedAnalyzers((prev) =>
      prev.includes(name) ? prev.filter((a) => a !== name) : [...prev, name]
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const payload: AnalysisRunRequest = {
      dataset_id: datasetId,
      analyzers: selectedAnalyzers,
      backtest: selectedAnalyzers.includes('survivorship')
        ? {
            target_index: targetIndex || null,
            start_date: startDate || null,
            end_date: endDate || null,
            min_price_coverage: minCoverage ? parseFloat(minCoverage) : null,
          }
        : null,
      lookahead: selectedAnalyzers.includes('lookahead')
        ? {
            decision_dates: decisionDates
              ? decisionDates.split(',').map((d) => d.trim()).filter(Boolean)
              : undefined,
            lookback_days: lookbackDays ? parseInt(lookbackDays, 10) : null,
            start_date: startDate || null,
            end_date: endDate || null,
          }
        : null,
      corporate_actions: selectedAnalyzers.includes('corporate_actions')
        ? {
            dataset_id: datasetId,
            expected_symbol: expectedSymbol || null,
          }
        : null,
    };

    try {
      const res = await createRunMutation.mutateAsync(payload);
      onClose();
      if (onSuccess) {
        onSuccess(res.run_id);
      }
    } catch {
      // Error handled by mutation state
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="// EXECUTE MULTI-ENGINE ANALYSIS RUN"
      maxWidth="2xl"
    >
      <form onSubmit={handleSubmit} className="space-y-6">
        {createRunMutation.isError && (
          <ErrorAlert
            error={createRunMutation.error}
            title="Failed to initiate analysis run"
          />
        )}

        {/* Dataset Selection */}
        <div>
          <label className="block text-xs font-mono uppercase tracking-widest text-black/70 mb-2">
            Target Dataset <span className="text-bra-red">*</span>
          </label>
          <select
            value={datasetId}
            onChange={(e) => setDatasetId(e.target.value)}
            required
            className="w-full px-3 py-2 bg-white border border-black text-sm font-mono focus:outline-none focus:ring-2 focus:ring-black"
          >
            {datasets?.map((ds) => (
              <option key={ds.dataset_id} value={ds.dataset_id}>
                {ds.name} ({ds.dataset_id}) — {ds.file_count} files
              </option>
            ))}
          </select>
        </div>

        {/* Engine Checkboxes */}
        <div className="border border-black p-4 bg-bra-muted/40">
          <label className="block text-xs font-mono uppercase tracking-widest text-black/70 mb-3">
            Select Verification Engines <span className="text-bra-red">*</span>
          </label>
          <div className="space-y-2">
            {[
              {
                id: 'survivorship',
                label: 'Survivorship Bias Engine',
                desc: 'Reconstruct historical index universe & delisted coverage',
              },
              {
                id: 'lookahead',
                label: 'Look-Ahead Bias Engine',
                desc: 'Verify point-in-time publication chronology and decision timestamps',
              },
              {
                id: 'corporate_actions',
                label: 'Corporate Actions Engine',
                desc: 'Detect unadjusted stock splits, bonus issues, and price leaps',
              },
            ].map((engine) => {
              const active = selectedAnalyzers.includes(engine.id);
              return (
                <div
                  key={engine.id}
                  onClick={() => toggleAnalyzer(engine.id)}
                  className={`flex items-start gap-3 p-3 border transition-colors cursor-pointer select-none ${
                    active
                      ? 'border-black bg-white shadow-bra-sm'
                      : 'border-black/20 bg-transparent hover:border-black/50'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={active}
                    onChange={() => {}}
                    className="mt-1 h-4 w-4 rounded-none border-black text-black focus:ring-0"
                  />
                  <div>
                    <span className="text-sm font-bold uppercase tracking-tight block">
                      {engine.label}
                    </span>
                    <span className="text-xs text-black/60 font-mono">
                      {engine.desc}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Engine Parameters */}
        <div className="border border-black p-4 bg-white space-y-4">
          <div className="flex items-center gap-2 border-b border-black/10 pb-2">
            <Sparkles size={14} className="text-bra-red" />
            <h4 className="text-xs font-mono uppercase tracking-wider font-bold">
              Analysis Parameters (Optional Overrides)
            </h4>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-mono uppercase text-black/70 mb-1">
                Target Benchmark Index
              </label>
              <input
                type="text"
                placeholder="e.g. NIFTY50"
                value={targetIndex}
                onChange={(e) => setTargetIndex(e.target.value)}
                className="w-full px-3 py-1.5 border border-black text-xs font-mono focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-mono uppercase text-black/70 mb-1">
                Min Price Coverage (0 - 1.0)
              </label>
              <input
                type="number"
                step="0.05"
                min="0"
                max="1"
                placeholder="0.80"
                value={minCoverage}
                onChange={(e) => setMinCoverage(e.target.value)}
                className="w-full px-3 py-1.5 border border-black text-xs font-mono focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-mono uppercase text-black/70 mb-1">
                Start Date (YYYY-MM-DD)
              </label>
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="w-full px-3 py-1.5 border border-black text-xs font-mono focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-mono uppercase text-black/70 mb-1">
                End Date (YYYY-MM-DD)
              </label>
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="w-full px-3 py-1.5 border border-black text-xs font-mono focus:outline-none"
              />
            </div>

            <div className="md:col-span-2">
              <label className="block text-xs font-mono uppercase text-black/70 mb-1">
                Lookahead Decision Dates (Comma Separated)
              </label>
              <input
                type="text"
                placeholder="2022-03-31, 2022-06-30, 2022-09-30"
                value={decisionDates}
                onChange={(e) => setDecisionDates(e.target.value)}
                className="w-full px-3 py-1.5 border border-black text-xs font-mono focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-mono uppercase text-black/70 mb-1">
                Lookback Window (Days)
              </label>
              <input
                type="number"
                placeholder="365"
                value={lookbackDays}
                onChange={(e) => setLookbackDays(e.target.value)}
                className="w-full px-3 py-1.5 border border-black text-xs font-mono focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-mono uppercase text-black/70 mb-1">
                Corporate Actions Expected Symbol
              </label>
              <input
                type="text"
                placeholder="e.g. INFY"
                value={expectedSymbol}
                onChange={(e) => setExpectedSymbol(e.target.value)}
                className="w-full px-3 py-1.5 border border-black text-xs font-mono focus:outline-none"
              />
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-3 pt-3 border-t border-black/10">
          <Button
            type="button"
            variant="ghost"
            onClick={onClose}
            disabled={createRunMutation.isPending}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            variant="black"
            icon={<Play size={14} />}
            loading={createRunMutation.isPending}
            disabled={selectedAnalyzers.length === 0}
          >
            Launch Run
          </Button>
        </div>
      </form>
    </Modal>
  );
};
