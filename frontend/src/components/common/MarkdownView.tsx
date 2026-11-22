import { lazy, Suspense } from 'react';
import { Skeleton } from './States';

const Impl = lazy(() => import('./MarkdownImpl'));

export function MarkdownView({ source, className }: { source: string | null | undefined; className?: string }) {
  if (!source) return null;
  return (
    <Suspense fallback={<Skeleton className="h-16 w-full" />}>
      <Impl source={source} className={className} />
    </Suspense>
  );
}
