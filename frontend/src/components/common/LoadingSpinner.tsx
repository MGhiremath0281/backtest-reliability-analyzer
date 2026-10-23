import React from 'react';
import { Loader2 } from 'lucide-react';

interface LoadingSpinnerProps {
  label?: string;
  size?: 'sm' | 'md' | 'lg';
  fullHeight?: boolean;
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  label = 'Loading analysis data...',
  size = 'md',
  fullHeight = false,
}) => {
  const sizeMap = {
    sm: 'w-4 h-4',
    md: 'w-7 h-7',
    lg: 'w-10 h-10',
  };

  return (
    <div
      className={`flex flex-col items-center justify-center gap-3 p-6 ${
        fullHeight ? 'min-h-[350px] h-full' : ''
      }`}
    >
      <div className="relative">
        <Loader2 className={`${sizeMap[size]} animate-spin text-black`} />
        <span className="absolute -top-1 -right-1 w-2 h-2 rounded-full bg-[#ff3b30]" />
      </div>
      {label && (
        <span className="text-xs font-mono font-medium tracking-wide text-zinc-600 uppercase">
          {label}
        </span>
      )}
    </div>
  );
};
