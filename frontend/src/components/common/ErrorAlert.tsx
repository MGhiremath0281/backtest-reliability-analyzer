import React, { useState } from 'react';
import { AlertCircle, ChevronDown, ChevronUp, RefreshCw } from 'lucide-react';
import { Button } from './Button';

interface ErrorAlertProps {
  title?: string;
  message?: string;
  error?: any;
  details?: string | Record<string, any>;
  onRetry?: () => void;
  className?: string;
}

export const ErrorAlert: React.FC<ErrorAlertProps> = ({
  title = 'API Operation Failed',
  message,
  error,
  details,
  onRetry,
  className = '',
}) => {
  const [showDetails, setShowDetails] = useState(false);

  const displayMessage =
    message ||
    (error?.response?.data?.detail
      ? typeof error.response.data.detail === 'string'
        ? error.response.data.detail
        : JSON.stringify(error.response.data.detail)
      : error?.message || (typeof error === 'string' ? error : 'An unexpected error occurred.'));

  const displayDetails = details || (error?.response?.data || error?.stack || null);

  return (
    <div
      className={`border-2 border-black bg-[#fff5f5] p-5 shadow-[3px_3px_0px_0px_#000000] ${className}`}
    >
      <div className="flex items-start gap-3">
        <div className="w-8 h-8 rounded-full bg-[#ff3b30] border border-black flex items-center justify-center shrink-0 text-white font-bold text-sm">
          !
        </div>
        <div className="flex-1">
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <h4 className="font-bold text-black text-sm uppercase tracking-wide">
              {title}
            </h4>
            {onRetry && (
              <Button
                variant="white"
                size="sm"
                onClick={onRetry}
                icon={<RefreshCw className="w-3.5 h-3.5" />}
              >
                Retry
              </Button>
            )}
          </div>
          <p className="text-sm text-zinc-800 mt-1 font-medium leading-relaxed">
            {displayMessage}
          </p>

          {displayDetails && (
            <div className="mt-3">
              <button
                type="button"
                onClick={() => setShowDetails(!showDetails)}
                className="text-xs font-mono font-bold text-zinc-700 hover:text-black flex items-center gap-1 underline underline-offset-2"
              >
                {showDetails ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                <span>{showDetails ? 'Hide technical diagnostics' : 'View technical diagnostics'}</span>
              </button>

              {showDetails && (
                <pre className="mt-2 p-3 bg-white border border-black text-xs font-mono text-zinc-800 overflow-x-auto whitespace-pre-wrap max-h-60">
                  {typeof displayDetails === 'string' ? displayDetails : JSON.stringify(displayDetails, null, 2)}
                </pre>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
