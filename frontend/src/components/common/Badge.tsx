import React from 'react';

export type BadgeVariant =
  | 'pass'
  | 'warn'
  | 'fail'
  | 'error'
  | 'warning'
  | 'info'
  | 'neutral'
  | 'outline'
  | 'blue'
  | 'red'
  | 'critical'
  | 'high'
  | 'medium'
  | 'low'
  | string;

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  size?: 'sm' | 'md';
  className?: string;
  dot?: boolean;
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'neutral',
  size = 'md',
  className = '',
  dot = false,
}) => {
  const normalized = (variant || '').toLowerCase();

  const variantStyles: Record<string, string> = {
    pass: 'bg-[#dcfce7] text-[#14532d] border-[#16a34a]',
    warn: 'bg-[#fef3c7] text-[#78350f] border-[#d97706]',
    fail: 'bg-[#fee2e2] text-[#7f1d1d] border-[#dc2626]',
    error: 'bg-[#fee2e2] text-[#7f1d1d] border-[#dc2626]',
    critical: 'bg-[#fee2e2] text-[#7f1d1d] border-[#dc2626]',
    high: 'bg-[#ffebee] text-[#991b1b] border-[#ef4444]',
    medium: 'bg-[#fef3c7] text-[#78350f] border-[#d97706]',
    low: 'bg-[#e0f2fe] text-[#0369a1] border-[#0284c7]',
    warning: 'bg-[#fef3c7] text-[#78350f] border-[#d97706]',
    info: 'bg-[#e0f2fe] text-[#0369a1] border-[#0284c7]',
    blue: 'bg-[#eaf4f7] text-[#2c5866] border-[#4a8b9f]',
    red: 'bg-[#ffebee] text-[#b71c1c] border-[#ff3b30]',
    neutral: 'bg-zinc-100 text-zinc-800 border-zinc-900',
    outline: 'bg-white text-zinc-900 border-black',
  };

  const dotColors: Record<string, string> = {
    pass: 'bg-[#16a34a]',
    warn: 'bg-[#d97706]',
    fail: 'bg-[#dc2626]',
    error: 'bg-[#dc2626]',
    critical: 'bg-[#dc2626]',
    high: 'bg-[#ef4444]',
    medium: 'bg-[#d97706]',
    low: 'bg-[#0284c7]',
    warning: 'bg-[#d97706]',
    info: 'bg-[#0284c7]',
    blue: 'bg-[#4a8b9f]',
    red: 'bg-[#ff3b30]',
    neutral: 'bg-zinc-500',
    outline: 'bg-black',
  };

  const sizeStyles = {
    sm: 'text-[10px] px-1.5 py-0.5 tracking-wider',
    md: 'text-xs px-2.5 py-0.5 tracking-wider',
  };

  const styleClass = variantStyles[normalized] || variantStyles.neutral;
  const dotClass = dotColors[normalized] || dotColors.neutral;

  return (
    <span
      className={`inline-flex items-center gap-1.5 font-bold uppercase border font-mono rounded-none select-none ${sizeStyles[size]} ${styleClass} ${className}`}
    >
      {dot && <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${dotClass}`} />}
      <span>{children}</span>
    </span>
  );
};
