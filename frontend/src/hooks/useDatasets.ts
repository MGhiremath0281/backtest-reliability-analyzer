import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as api from '../api/endpoints';
import * as T from '../api/types';

export function useDatasets(params?: { include_existing?: boolean; limit?: number; offset?: number }) {
  return useQuery({
    queryKey: ['datasets', params],
    queryFn: () => api.listDatasets(params),
  });
}

export function useDatasetDetail(datasetId: string | undefined) {
  return useQuery({
    queryKey: ['dataset', datasetId],
    queryFn: () => api.getDataset(datasetId!),
    enabled: Boolean(datasetId),
  });
}

export function useDatasetPreview(
  datasetId: string | undefined,
  params?: { file_id?: string; limit?: number; offset?: number }
) {
  return useQuery({
    queryKey: ['datasetPreview', datasetId, params],
    queryFn: () => api.previewDataset(datasetId!, params),
    enabled: Boolean(datasetId),
  });
}

export function useDatasetSchema(datasetId: string | undefined) {
  return useQuery({
    queryKey: ['datasetSchema', datasetId],
    queryFn: () => api.getDatasetSchema(datasetId!),
    enabled: Boolean(datasetId),
  });
}

export function useDatasetQualitySummary(datasetId: string | undefined) {
  return useQuery({
    queryKey: ['datasetQuality', datasetId],
    queryFn: () => api.getDatasetQualitySummary(datasetId!),
    enabled: Boolean(datasetId),
  });
}

export function useDatasetMapping(datasetId: string | undefined) {
  return useQuery({
    queryKey: ['datasetMapping', datasetId],
    queryFn: () => api.getDatasetMapping(datasetId!),
    enabled: Boolean(datasetId),
  });
}

export function useDatasetPreparation(datasetId: string | undefined) {
  return useQuery({
    queryKey: ['datasetPreparation', datasetId],
    queryFn: () => api.getDatasetPreparation(datasetId!),
    enabled: Boolean(datasetId),
    retry: false,
  });
}

export function useUploadDataset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ files, meta }: { files: File[]; meta?: { name?: string; description?: string } }) =>
      api.uploadDataset(files, meta),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['datasets'] });
    },
  });
}

export function useDeleteDataset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (datasetId: string) => api.deleteDataset(datasetId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['datasets'] });
    },
  });
}

export function usePrepareDataset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (datasetId: string) => api.prepareDataset(datasetId),
    onSuccess: (_, datasetId) => {
      queryClient.invalidateQueries({ queryKey: ['dataset', datasetId] });
      queryClient.invalidateQueries({ queryKey: ['datasetPreparation', datasetId] });
      queryClient.invalidateQueries({ queryKey: ['datasets'] });
    },
  });
}

export function useSetDatasetMapping() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ datasetId, payload }: { datasetId: string; payload: T.SetMappingRequest }) =>
      api.setDatasetMapping(datasetId, payload),
    onSuccess: (_, { datasetId }) => {
      queryClient.invalidateQueries({ queryKey: ['datasetMapping', datasetId] });
      queryClient.invalidateQueries({ queryKey: ['dataset', datasetId] });
    },
  });
}
