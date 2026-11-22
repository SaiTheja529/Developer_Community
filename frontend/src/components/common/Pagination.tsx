import { ChevronLeft, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/cn';
import type { PageMeta } from '@/lib/api/types';

export function Pagination({ meta, onPage }: { meta: PageMeta; onPage: (p: number) => void }) {
  if (meta.total_pages <= 1) return null;
  const go = (p: number) => {
    onPage(p);
    document.getElementById('list-top')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };
  const pages = Array.from({ length: meta.total_pages }, (_, i) => i + 1).filter(
    (p) => p === 1 || p === meta.total_pages || Math.abs(p - meta.page) <= 1,
  );
  const cell = 'inline-grid h-9 min-w-9 place-items-center rounded-[6px] px-2 text-sm font-mono cursor-pointer';
  return (
    <nav aria-label="Pagination" className="mt-8 flex items-center justify-center gap-1">
      <button className={cn(cell, 'hover:bg-surface-2 disabled:opacity-40')} disabled={meta.page <= 1} onClick={() => go(meta.page - 1)} aria-label="Previous page">
        <ChevronLeft size={16} />
      </button>
      {pages.map((p, i) => (
        <span key={p} className="contents">
          {i > 0 && p - pages[i - 1] > 1 && <span className="px-1 text-muted">…</span>}
          <button
            className={cn(cell, p === meta.page ? 'bg-text text-bg' : 'hover:bg-surface-2')}
            aria-current={p === meta.page ? 'page' : undefined}
            onClick={() => go(p)}
          >
            {p}
          </button>
        </span>
      ))}
      <button className={cn(cell, 'hover:bg-surface-2 disabled:opacity-40')} disabled={meta.page >= meta.total_pages} onClick={() => go(meta.page + 1)} aria-label="Next page">
        <ChevronRight size={16} />
      </button>
    </nav>
  );
}
