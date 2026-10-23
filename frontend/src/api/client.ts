import axios, { AxiosError } from 'axios';
import { ApiErrorDetail } from './types';

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Accept': 'application/json',
  },
  timeout: 45000, // 45 seconds for heavy analysis operations
});

/**
 * Extracts a user-friendly error message from an API error response.
 */
export function formatApiError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const axiosErr = error as AxiosError<ApiErrorDetail>;
    if (axiosErr.response) {
      const data = axiosErr.response.data;
      if (data?.detail) {
        if (typeof data.detail === 'string') {
          return data.detail;
        }
        if (Array.isArray(data.detail)) {
          return (data.detail as any[]).map((d: any) => d?.msg || JSON.stringify(d)).join('; ');
        }
      }
      if (data?.errors && Array.isArray(data.errors)) {
        return data.errors.map(e => `${e.loc.join('.')}: ${e.msg}`).join(', ');
      }
      return `Server returned error (${axiosErr.response.status}): ${axiosErr.response.statusText}`;
    }
    if (axiosErr.code === 'ECONNABORTED') {
      return 'Request timed out while communicating with the BRA backend.';
    }
    if (axiosErr.message === 'Network Error' || !axiosErr.response) {
      return `Cannot connect to BRA backend at ${API_BASE_URL}. Ensure the server is running.`;
    }
    return axiosErr.message;
  }
  if (typeof error === 'string') {
    return error;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return 'An unexpected error occurred.';
}
