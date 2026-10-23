import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as api from '../api/endpoints';
import * as T from '../api/types';

export function useAnalysisRuns(params?: { dataset_id?: string; limit?: number; offset?: number }) {
  return useQuery({
    queryKey: ['analysisRuns', params],
    queryFn: () => api.listAnalysisRuns(params),
    refetchInterval: 10000,
  });
}

export function useAnalysisRunDetail(runId: string | undefined) {
  return useQuery({
    queryKey: ['analysisRun', runId],
    queryFn: () => api.getAnalysisRun(runId!),
    enabled: Boolean(runId),
  });
}

export function useAnalysisRunFindings(
  runId: string | undefined,
  params?: { severity?: string; analyzer?: string; limit?: number; offset?: number }
) {
  return useQuery({
    queryKey: ['analysisRunFindings', runId, params],
    queryFn: () => api.getAnalysisRunFindings(runId!, params),
    enabled: Boolean(runId),
  });
}

export function useAnalysisRunSummary(runId: string | undefined) {
  return useQuery({
    queryKey: ['analysisRunSummary', runId],
    queryFn: () => api.getAnalysisRunSummary(runId!),
    enabled: Boolean(runId),
  });
}

export function useAnalysisRunEvents(runId: string | undefined) {
  return useQuery({
    queryKey: ['analysisRunEvents', runId],
    queryFn: () => api.getAnalysisRunEvents(runId!),
    enabled: Boolean(runId),
    refetchInterval: 3000,
  });
}

export function useCreateAnalysisRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: T.AnalysisRunRequest) => api.createAnalysisRun(payload),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['analysisRuns'] });
      queryClient.setQueryData(['analysisRun', data.run_id], data);
    },
  });
}

export function useCancelAnalysisRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (runId: string) => api.cancelAnalysisRun(runId),
    onSuccess: (_, runId) => {
      queryClient.invalidateQueries({ queryKey: ['analysisRun', runId] });
      queryClient.invalidateQueries({ queryKey: ['analysisRuns'] });
    },
  });
}
