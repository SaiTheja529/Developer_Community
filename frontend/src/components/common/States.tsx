import type { ReactNode } from 'react';
import { AlertCircle, Inbox, type LucideIcon } from 'lucide-react';
import { ApiError } from '@/lib/api/client';
import { Button } from './Button';
import { cn } from '@/lib/cn';

export function EmptyState({ icon: Icon = Inbox, title, children, action }: { icon?: LucideIcon; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-[10px] border border-dashed border-border px-6 py-12 text-center">
      <Icon size={28} className="text-muted" aria-hidden />
      <p className="font-medium">{title}</p>
      {children && <p className="max-w-md text-sm text-muted">{children}</p>}
      {action}
    </div>
  );
}

export function ErrorState({ error, onRetry, title = "This didn't load." }: { error: unknown; onRetry?: () => void; title?: string }) {
  const reqId = error instanceof ApiError ? error.requestId : undefined;
  const msg = error instanceof ApiError ? error.message : 'Check your connection, then try again.';
  return (
    <div role="alert" className="flex flex-col items-center gap-3 rounded-[10px] border border-border bg-surface px-6 py-10 text-center">
      <AlertCircle size={28} className="text-danger" aria-hidden />
      <p className="font-medium">{title}</p>
      <p className="max-w-md text-sm text-muted">{msg}</p>
      {onRetry && <Button onClick={onRetry}>Try again</Button>}
      {reqId && <p className="font-mono text-xs text-muted">Reference: {reqId}</p>}
    </div>
  );
}

export const Skeleton = ({ className }: { className?: string }) => (
  <div aria-hidden className={cn('animate-pulse rounded-[6px] bg-surface-2', className)} />
);

export function CardSkeleton() {
  return (
    <div className="rounded-[10px] border border-border bg-surface p-4" aria-hidden>
      <Skeleton className="h-5 w-2/3" />
      <Skeleton className="mt-3 h-3 w-1/2" />
      <Skeleton className="mt-4 h-3 w-full" />
      <Skeleton className="mt-2 h-3 w-5/6" />
      <Skeleton className="mt-5 h-4 w-1/3" />
    </div>
  );
}

export function DetailSkeleton() {
  return (
    <div className="mx-auto max-w-[1200px] px-4 py-8 md:px-8" aria-busy="true" aria-label="Loading">
      <Skeleton className="h-8 w-1/2" />
      <Skeleton className="mt-3 h-4 w-1/3" />
      <div className="mt-8 grid gap-8 lg:grid-cols-[1fr_320px]">
        <div className="space-y-3">{Array.from({ length: 8 }, (_, i) => <Skeleton key={i} className="h-4 w-full" />)}</div>
        <Skeleton className="h-64" />
      </div>
    </div>
  );
}
