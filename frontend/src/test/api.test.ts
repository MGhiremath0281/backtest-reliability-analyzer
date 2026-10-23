import { describe, it, expect } from 'vitest';
import { formatApiError } from '../api/client';

describe('API Client & Error Handling', () => {
  it('formats standard Javascript error objects', () => {
    const error = new Error('Custom connection failure');
    expect(formatApiError(error)).toBe('Custom connection failure');
  });

  it('formats raw string error objects', () => {
    expect(formatApiError('Unrecognized runtime failure')).toBe('Unrecognized runtime failure');
  });

  it('formats Axios responses with detail string', () => {
    const axiosLikeError = {
      isAxiosError: true,
      response: {
        status: 400,
        statusText: 'Bad Request',
        data: {
          detail: 'Cannot delete canonical dataset existing-data',
        },
      },
    };
    expect(formatApiError(axiosLikeError)).toBe('Cannot delete canonical dataset existing-data');
  });

  it('formats Axios responses with FastAPI Pydantic validation error lists', () => {
    const axiosLikeValidationError = {
      isAxiosError: true,
      response: {
        status: 422,
        statusText: 'Unprocessable Entity',
        data: {
          detail: [
            { loc: ['body', 'dataset_id'], msg: 'field required', type: 'value_error.missing' },
            { loc: ['body', 'min_price_coverage'], msg: 'must be less than or equal to 1.0', type: 'value_error' },
          ],
        },
      },
    };
    const formatted = formatApiError(axiosLikeValidationError);
    expect(formatted).toContain('field required');
    expect(formatted).toContain('must be less than or equal to 1.0');
  });

  it('formats network disconnection errors', () => {
    const networkError = {
      isAxiosError: true,
      message: 'Network Error',
      response: undefined,
    };
    expect(formatApiError(networkError)).toContain('Cannot connect to BRA backend');
  });

  it('formats request timeout errors', () => {
    const timeoutError = {
      isAxiosError: true,
      code: 'ECONNABORTED',
      message: 'timeout of 45000ms exceeded',
      response: undefined,
    };
    expect(formatApiError(timeoutError)).toContain('Request timed out while communicating with the BRA backend');
  });
});
