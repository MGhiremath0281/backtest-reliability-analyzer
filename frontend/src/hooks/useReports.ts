import { useQuery } from '@tanstack/react-query';
import * as api from '../api/endpoints';

export function useReports(params?: { limit?: number; offset?: number }) {
  return useQuery({
    queryKey: ['reports', params],
    queryFn: () => api.listReports(params),
  });
}

export function useReportDetail(reportId: string | undefined) {
  return useQuery({
    queryKey: ['report', reportId],
    queryFn: () => api.getReport(reportId!),
    enabled: Boolean(reportId),
  });
}
