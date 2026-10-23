import React from 'react';

interface CardProps {
  children: React.ReactNode;
  className?: string;
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  action?: React.ReactNode;
  headerActions?: React.ReactNode;
  tag?: string;
  hoverable?: boolean;
  shadow?: boolean;
}

export const Card: React.FC<CardProps> = ({
  children,
  className = '',
  title,
  subtitle,
  action,
  headerActions,
  tag,
  hoverable = false,
  shadow = true,
}) => {
  const renderedAction = headerActions || action;
  return (
    <div
      className={`bg-white border border-black rounded-none flex flex-col ${
        shadow ? 'shadow-[3px_3px_0px_0px_#000000]' : ''
      } ${
        hoverable ? 'transition-all duration-150 hover:-translate-x-0.5 hover:-translate-y-0.5 hover:shadow-[5px_5px_0px_0px_#000000]' : ''
      } ${className}`}
    >
      {(title || tag || renderedAction) && (
        <div className="px-5 py-4 border-b border-black flex items-center justify-between gap-4 bg-white">
          <div className="space-y-0.5">
            {tag && (
              <div className="text-[11px] font-mono font-bold uppercase tracking-widest text-[#ff3b30] flex items-center gap-1">
                <span>✦</span>
                <span>{tag}</span>
              </div>
            )}
            {title && (
              <h3 className="font-bold text-lg text-black tracking-tight leading-snug">
                {title}
              </h3>
            )}
            {subtitle && (
              <p className="text-xs text-zinc-500 font-normal">
                {subtitle}
              </p>
            )}
          </div>
          {renderedAction && <div className="shrink-0">{renderedAction}</div>}
        </div>
      )}
      <div className="p-5 flex-1">{children}</div>
    </div>
  );
};
