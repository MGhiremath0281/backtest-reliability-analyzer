import React from 'react';
import { Database } from 'lucide-react';
import { Button } from './Button';

interface EmptyStateProps {
  title: string;
  description: string;
  icon?: React.ReactNode;
  actionLabel?: string;
  onAction?: () => void;
  className?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  description,
  icon,
  actionLabel,
  onAction,
  className = '',
}) => {
  return (
    <div
      className={`border border-dashed border-zinc-400 bg-white/70 p-10 flex flex-col items-center justify-center text-center ${className}`}
    >
      <div className="w-14 h-14 rounded-full border-2 border-black bg-[#f4f4f5] flex items-center justify-center text-zinc-900 mb-4 shadow-[2px_2px_0px_0px_#000000]">
        {icon || <Database className="w-6 h-6" />}
      </div>
      <h3 className="font-bold text-lg text-black tracking-tight">{title}</h3>
      <p className="text-sm text-zinc-600 max-w-md mt-1.5 leading-relaxed">
        {description}
      </p>
      {actionLabel && onAction && (
        <div className="mt-5">
          <Button variant="black" size="sm" onClick={onAction}>
            {actionLabel}
          </Button>
        </div>
      )}
    </div>
  );
};
