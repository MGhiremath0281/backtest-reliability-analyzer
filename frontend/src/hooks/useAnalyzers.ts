import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as api from '../api/endpoints';
import * as T from '../api/types';

// Survivorship
export function useSurvivorshipAnalysis(analysisId: string | undefined) {
  return useQuery({
    queryKey: ['survivorshipAnalysis', analysisId],
    queryFn: () => api.getSurvivorshipAnalysis(analysisId!),
    enabled: Boolean(analysisId),
  });
}

export function useSurvivorshipUniverse(analysisId: string | undefined) {
  return useQuery({
    queryKey: ['survivorshipUniverse', analysisId],
    queryFn: () => api.getSurvivorshipUniverse(analysisId!),
    enabled: Boolean(analysisId),
  });
}

export function useSurvivorshipDelisted(analysisId: string | undefined) {
  return useQuery({
    queryKey: ['survivorshipDelisted', analysisId],
    queryFn: () => api.getSurvivorshipDelisted(analysisId!),
    enabled: Boolean(analysisId),
  });
}

export function useSurvivorshipFindings(
  analysisId: string | undefined,
  params?: { severity?: string; kind?: string; limit?: number; offset?: number }
) {
  return useQuery({
    queryKey: ['survivorshipFindings', analysisId, params],
    queryFn: () => api.getSurvivorshipFindings(analysisId!, params),
    enabled: Boolean(analysisId),
  });
}

export function useTriggerSurvivorship() {
  return useMutation({
    mutationFn: (payload: T.SurvivorshipAnalysisRequest) =>
      api.triggerSurvivorshipAnalysis(payload),
  });
}

// Lookahead
export function useLookaheadAnalysis(analysisId: string | undefined) {
  return useQuery({
    queryKey: ['lookaheadAnalysis', analysisId],
    queryFn: () => api.getLookaheadAnalysis(analysisId!),
    enabled: Boolean(analysisId),
  });
}

export function useLookaheadTimeline(analysisId: string | undefined) {
  return useQuery({
    queryKey: ['lookaheadTimeline', analysisId],
    queryFn: () => api.getLookaheadTimeline(analysisId!),
    enabled: Boolean(analysisId),
  });
}

export function useLookaheadFindings(
  analysisId: string | undefined,
  params?: { severity?: string; classification?: string; limit?: number; offset?: number }
) {
  return useQuery({
    queryKey: ['lookaheadFindings', analysisId, params],
    queryFn: () => api.getLookaheadFindings(analysisId!, params),
    enabled: Boolean(analysisId),
  });
}

export function useTriggerLookahead() {
  return useMutation({
    mutationFn: (payload: T.LookaheadAnalysisRequest) =>
      api.triggerLookaheadAnalysis(payload),
  });
}

// Corporate Actions
export function useCorporateActionsAnalysis(analysisId: string | undefined) {
  return useQuery({
    queryKey: ['corporateActionsAnalysis', analysisId],
    queryFn: () => api.getCorporateActionsAnalysis(analysisId!),
    enabled: Boolean(analysisId),
  });
}

export function useCorporateActionsCoverage(analysisId: string | undefined) {
  return useQuery({
    queryKey: ['corporateActionsCoverage', analysisId],
    queryFn: () => api.getCorporateActionsCoverage(analysisId!),
    enabled: Boolean(analysisId),
  });
}

export function useCorporateActionsFindings(
  analysisId: string | undefined,
  params?: { severity?: string; code?: string; limit?: number; offset?: number }
) {
  return useQuery({
    queryKey: ['corporateActionsFindings', analysisId, params],
    queryFn: () => api.getCorporateActionsFindings(analysisId!, params),
    enabled: Boolean(analysisId),
  });
}

export function useTriggerCorporateActions() {
  return useMutation({
    mutationFn: (payload: T.CorporateActionsAnalysisRequest) =>
      api.triggerCorporateActionsAnalysis(payload),
  });
}
