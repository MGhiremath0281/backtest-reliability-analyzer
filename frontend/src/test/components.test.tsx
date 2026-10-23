import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { Card } from '../components/common/Card';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { EmptyState } from '../components/common/EmptyState';

describe('Common UI Components (Devlab Editorial Aesthetics)', () => {
  describe('Badge', () => {
    it('renders PASS badge correctly', () => {
      render(<Badge variant="pass">PASSED</Badge>);
      const badge = screen.getByText('PASSED');
      expect(badge).toBeInTheDocument();
      expect(badge.parentElement).toHaveClass('font-mono');
    });

    it('renders case-insensitive WARN and FAIL variants', () => {
      const { rerender } = render(<Badge variant="WARN">WARNING</Badge>);
      expect(screen.getByText('WARNING')).toBeInTheDocument();

      rerender(<Badge variant="FAIL">FAILED</Badge>);
      expect(screen.getByText('FAILED')).toBeInTheDocument();
    });

    it('renders with dot indicator when specified', () => {
      const { container } = render(<Badge variant="info" dot>LIVE</Badge>);
      expect(container.querySelector('.rounded-full')).toBeInTheDocument();
    });
  });

  describe('Button', () => {
    it('handles click events', () => {
      const handleClick = vi.fn();
      render(<Button onClick={handleClick}>Click Me</Button>);
      fireEvent.click(screen.getByText('Click Me'));
      expect(handleClick).toHaveBeenCalledTimes(1);
    });

    it('displays loading state and disables button', () => {
      render(<Button isLoading>Submit</Button>);
      const btn = screen.getByRole('button');
      expect(btn).toBeDisabled();
    });

    it('supports loading prop alias', () => {
      render(<Button loading>Execute</Button>);
      const btn = screen.getByRole('button');
      expect(btn).toBeDisabled();
    });
  });

  describe('Card', () => {
    it('renders title, tag, and content', () => {
      render(
        <Card title="RELIABILITY REPORT" tag="AUDIT">
          <p>Verified data contents</p>
        </Card>
      );
      expect(screen.getByText('RELIABILITY REPORT')).toBeInTheDocument();
      expect(screen.getByText('AUDIT')).toBeInTheDocument();
      expect(screen.getByText('Verified data contents')).toBeInTheDocument();
    });

    it('renders header actions when provided', () => {
      render(
        <Card
          title="RUNS"
          headerActions={<button>Filter Runs</button>}
        >
          <div>Table content</div>
        </Card>
      );
      expect(screen.getByText('Filter Runs')).toBeInTheDocument();
    });
  });

  describe('ErrorAlert', () => {
    it('renders error message cleanly', () => {
      render(<ErrorAlert message="Dataset validation rejected." />);
      expect(screen.getByText('Dataset validation rejected.')).toBeInTheDocument();
    });

    it('displays technical diagnostics when expanded', () => {
      render(
        <ErrorAlert
          message="Server error"
          details={{ reason: 'Unadjusted corporate action detected', code: 422 }}
        />
      );
      const toggleBtn = screen.getByText('View technical diagnostics');
      expect(toggleBtn).toBeInTheDocument();

      fireEvent.click(toggleBtn);
      expect(screen.getByText(/Unadjusted corporate action detected/)).toBeInTheDocument();
    });

    it('triggers retry callback when retry button clicked', () => {
      const handleRetry = vi.fn();
      render(
        <ErrorAlert
          message="Network timeout"
          onRetry={handleRetry}
        />
      );
      const retryBtn = screen.getByText('Retry');
      fireEvent.click(retryBtn);
      expect(handleRetry).toHaveBeenCalledTimes(1);
    });
  });

  describe('EmptyState', () => {
    it('renders title, description and calls action', () => {
      const handleAction = vi.fn();
      render(
        <EmptyState
          title="NO DATASETS FOUND"
          description="Upload your first CSV dataset."
          actionLabel="Upload Now"
          onAction={handleAction}
        />
      );
      expect(screen.getByText('NO DATASETS FOUND')).toBeInTheDocument();
      expect(screen.getByText('Upload your first CSV dataset.')).toBeInTheDocument();

      const btn = screen.getByText('Upload Now');
      fireEvent.click(btn);
      expect(handleAction).toHaveBeenCalledTimes(1);
    });
  });
});
