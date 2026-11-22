import { useEffect, useState, type ReactNode } from 'react';
import { Search, SlidersHorizontal, X } from 'lucide-react';
import { useDebouncedValue } from '@/hooks/useDebouncedValue';
import type { ListParams } from '@/hooks/useListParams';
import { SORT_LABELS } from '@/lib/modules';
import { cn } from '@/lib/cn';

export const fieldClass =
  'h-9 rounded-[6px] border border-border bg-surface px-2.5 text-sm text-text placeholder:text-muted focus-visible:outline-2 focus-visible:outline-focus';

export function Select({ label, value, onChange, options, className }: { label: string; value: string; onChange: (v: string) => void; options: { value: string; label: string }[]; className?: string }) {
  return (
    <label className={cn('flex flex-col gap-1', className)}>
      <span className="text-xs font-medium text-muted">{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)} className={cn(fieldClass, 'pr-7')}>
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </label>
  );
}

export function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="inline-flex h-9 cursor-pointer items-center gap-2 self-end text-sm">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="size-4 accent-[var(--text)]" />
      {label}
    </label>
  );
}

export function FilterBar({ params, set, clear, activeCount, sorts, searchLabel, children }: {
  params: ListParams; set: (p: ListParams) => void; clear: () => void; activeCount: number; sorts: string[]; searchLabel: string; children?: ReactNode;
}) {
  const [q, setQ] = useState(params.q ?? '');
  const dq = useDebouncedValue(q, 300);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if ((params.q ?? '') !== dq) set({ q: dq });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dq]);
  useEffect(() => setQ(params.q ?? ''), [params.q]);

  return (
    <div className="rounded-[10px] border border-border bg-surface p-3">
      <div className="flex gap-2">
        <label className="relative flex-1">
          <span className="sr-only">{searchLabel}</span>
          <Search size={15} className="pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2 text-muted" aria-hidden />
          <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder={searchLabel} className={cn(fieldClass, 'w-full pl-8')} />
        </label>
        <button
          type="button"
          className={cn(fieldClass, 'inline-flex items-center gap-1.5 md:hidden')}
          aria-expanded={open}
          onClick={() => setOpen((o) => !o)}
        >
          <SlidersHorizontal size={15} aria-hidden /> Filters
          {activeCount > 0 && <span className="rounded-full bg-text px-1.5 font-mono text-[11px] text-bg">{activeCount}</span>}
        </button>
      </div>
      <div className={cn('mt-3 flex-wrap items-end gap-3', open ? 'flex' : 'hidden md:flex')}>
        {children}
        <Select
          label="Sort"
          value={params.sort ?? sorts[0]}
          onChange={(v) => set({ sort: v })}
          options={sorts.map((s) => ({ value: s, label: SORT_LABELS[s] ?? s }))}
        />
        {activeCount > 0 && (
          <button type="button" onClick={clear} className="inline-flex h-9 items-center gap-1 self-end px-2 text-sm text-muted hover:text-text cursor-pointer">
            <X size={14} aria-hidden /> Clear filters
          </button>
        )}
      </div>
    </div>
  );
}
