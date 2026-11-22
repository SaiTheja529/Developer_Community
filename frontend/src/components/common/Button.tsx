import { forwardRef, type ButtonHTMLAttributes } from 'react';
import { cn } from '@/lib/cn';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'ai';
const styles: Record<Variant, string> = {
  primary: 'bg-text text-bg hover:opacity-90 border border-transparent',
  secondary: 'bg-surface text-text border border-border hover:bg-surface-2',
  ghost: 'bg-transparent text-text border border-transparent hover:bg-surface-2',
  danger: 'bg-danger text-bg border border-transparent hover:opacity-90',
  ai: 'bg-ai-soft text-ai border border-dashed border-ai hover:bg-[color-mix(in_srgb,var(--ai)_16%,var(--surface))]',
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: 'sm' | 'md' | 'lg';
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button({ variant = 'secondary', size = 'md', className, ...p }, ref) {
  return (
    <button
      ref={ref}
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-[6px] font-medium whitespace-nowrap transition-colors duration-150 disabled:opacity-50 disabled:pointer-events-none cursor-pointer',
        size === 'sm' && 'h-8 px-2.5 text-[13px]',
        size === 'md' && 'h-9 px-3.5 text-sm',
        size === 'lg' && 'h-11 px-5 text-[15px]',
        styles[variant],
        className,
      )}
      {...p}
    />
  );
});

export function buttonClass(variant: Variant = 'secondary', size: 'sm' | 'md' | 'lg' = 'md', extra?: string) {
  return cn(
    'inline-flex items-center justify-center gap-2 rounded-[6px] font-medium whitespace-nowrap transition-colors duration-150',
    size === 'sm' && 'h-8 px-2.5 text-[13px]',
    size === 'md' && 'h-9 px-3.5 text-sm',
    size === 'lg' && 'h-11 px-5 text-[15px]',
    styles[variant],
    extra,
  );
}
