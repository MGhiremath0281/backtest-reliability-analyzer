import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { App } from '../App';

// Mock TanStack React Query to avoid background timers in unit tests
vi.mock('@tanstack/react-query', async (importOriginal) => {
  const actual: any = await importOriginal();
  return {
    ...actual,
    useQuery: vi.fn(() => ({
      data: undefined,
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    })),
  };
});

describe('Public Landing Page & Routing', () => {
  it('renders the public landing page with Devlab headline at /', () => {
    window.history.pushState({}, 'Test', '/');
    render(<App />);

    expect(screen.getByText(/Trust Your Backtests/i)).toBeInTheDocument();
    expect(screen.getByText(/Challenge Your Assumptions/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /OPEN DASHBOARD/i })).toBeInTheDocument();
  });

  it('renders landing page metrics and feature sections', () => {
    window.history.pushState({}, 'Test', '/');
    render(<App />);

    expect(screen.getByText(/3 Core/i)).toBeInTheDocument();
    expect(screen.getByText(/46 Endpoints/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Point-in-Time/i).length).toBeGreaterThan(0);
    expect(screen.getByRole('heading', { name: /How It Works/i })).toBeInTheDocument();
  });

  it('renders the internal application shell on /dashboard', () => {
    window.history.pushState({}, 'Test', '/dashboard');
    render(<App />);

    expect(screen.getByText('OVERVIEW')).toBeInTheDocument();
    expect(screen.getByText('DATA MANAGEMENT')).toBeInTheDocument();
    expect(screen.getByText('BIAS ANALYZERS')).toBeInTheDocument();
    expect(screen.getByText('PIPELINE & AUDITS')).toBeInTheDocument();
    expect(screen.getByText('QUANT AUDIT PLATFORM')).toBeInTheDocument();
  });
});
