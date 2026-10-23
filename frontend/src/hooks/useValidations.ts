import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as api from '../api/endpoints';
import * as T from '../api/types';

export function useValidation(validationId: string | undefined) {
  return useQuery({
    queryKey: ['validation', validationId],
    queryFn: () => api.getValidation(validationId!),
    enabled: Boolean(validationId),
  });
}

export function useValidationFindings(
  validationId: string | undefined,
  params?: { severity?: string; analyzer?: string; limit?: number; offset?: number }
) {
  return useQuery({
    queryKey: ['validationFindings', validationId, params],
    queryFn: () => api.getValidationFindings(validationId!, params),
    enabled: Boolean(validationId),
  });
}

export function useExecuteValidation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: T.ValidationRequest) => api.executeValidation(payload),
    onSuccess: (data) => {
      queryClient.setQueryData(['validation', data.validation_id], data);
      if (data.dataset_id) {
        queryClient.invalidateQueries({ queryKey: ['dataset', data.dataset_id] });
      }
    },
  });
}

export function useValidateDataset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (datasetId: string) => api.validateDataset(datasetId),
    onSuccess: (data, datasetId) => {
      queryClient.setQueryData(['validation', data.validation_id], data);
      queryClient.invalidateQueries({ queryKey: ['dataset', datasetId] });
      queryClient.invalidateQueries({ queryKey: ['datasetValidation', datasetId] });
    },
  });
}
