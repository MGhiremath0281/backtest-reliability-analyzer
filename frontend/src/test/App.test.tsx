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

describe('Application Shell & Routing', () => {
  it('renders the Top Navigation with // BRA branding', () => {
    render(<App />);
    expect(screen.getByText('BRA')).toBeInTheDocument();
    expect(screen.getByText('Backtest Reliability Analyzer')).toBeInTheDocument();
    expect(screen.getByText('NEW RUN')).toBeInTheDocument();
  });

  it('renders the Sidebar with core navigation sections', () => {
    render(<App />);
    expect(screen.getByText('OVERVIEW')).toBeInTheDocument();
    expect(screen.getByText('DATA MANAGEMENT')).toBeInTheDocument();
    expect(screen.getByText('BIAS ANALYZERS')).toBeInTheDocument();
    expect(screen.getByText('PIPELINE & AUDITS')).toBeInTheDocument();
    expect(screen.getByText('SYSTEM')).toBeInTheDocument();
  });

  it('renders the breadcrumb bar and quant platform label', () => {
    render(<App />);
    expect(screen.getByText('QUANT AUDIT PLATFORM')).toBeInTheDocument();
    expect(screen.getByText('Home')).toBeInTheDocument();
  });

  it('renders the footer with zero-hardcoding engine notice', () => {
    render(<App />);
    expect(screen.getByText(/Zero-Hardcoding Engine/)).toBeInTheDocument();
    expect(screen.getByText(/NSE Point-in-Time/)).toBeInTheDocument();
  });
});
