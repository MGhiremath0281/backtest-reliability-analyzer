import React from 'react';
import { Loader2 } from 'lucide-react';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'black' | 'white' | 'red' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
  loading?: boolean;
  icon?: React.ReactNode;
}

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = 'black',
  size = 'md',
  isLoading = false,
  loading = false,
  icon,
  className = '',
  disabled,
  ...props
}) => {
  const isCurrentlyLoading = isLoading || loading;
  const baseStyles = 'inline-flex items-center justify-center font-medium rounded-full transition-all focus:outline-none focus:ring-2 focus:ring-black focus:ring-offset-1 select-none active:translate-y-0.5 cursor-pointer disabled:cursor-not-allowed disabled:opacity-50 disabled:transform-none';

  const sizeStyles = {
    sm: 'text-xs px-3 py-1.5 gap-1.5',
    md: 'text-sm px-5 py-2.5 gap-2 font-semibold',
    lg: 'text-base px-6 py-3 gap-2.5 font-bold',
  };

  const variantStyles = {
    black: 'bg-black text-white border border-black hover:bg-zinc-800 hover:shadow-sm',
    white: 'bg-white text-black border border-black hover:bg-zinc-50 hover:shadow-sm',
    red: 'bg-[#ff3b30] text-white border border-black hover:bg-[#e63946] shadow-[2px_2px_0px_0px_#000000]',
    ghost: 'bg-transparent text-zinc-900 hover:bg-zinc-100 border border-transparent hover:border-black',
  };

  return (
    <button
      className={`${baseStyles} ${sizeStyles[size]} ${variantStyles[variant]} ${className}`}
      disabled={disabled || isCurrentlyLoading}
      {...props}
    >
      {isCurrentlyLoading ? (
        <Loader2 className="w-4 h-4 animate-spin" />
      ) : icon ? (
        <span className="shrink-0">{icon}</span>
      ) : null}
      <span>{children}</span>
    </button>
  );
};
