import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router';
import * as Dialog from '@radix-ui/react-dialog';
import { Clock, Search, CornerDownLeft } from 'lucide-react';
import { useSearch } from '@/lib/api/queries';
import { useDebouncedValue } from '@/hooks/useDebouncedValue';
import { MODULES } from '@/lib/modules';
import { cn } from '@/lib/cn';

const RECENT_KEY = 'dc-recent-searches';
const readRecent = (): string[] => {
  try {
    return JSON.parse(localStorage.getItem(RECENT_KEY) ?? '[]');
  } catch {
    return [];
  }
};
const pushRecent = (q: string) => {
  try {
    localStorage.setItem(RECENT_KEY, JSON.stringify([q, ...readRecent().filter((x) => x !== q)].slice(0, 5)));
  } catch {
    /* ignore */
  }
};

interface Row { key: string; group: string; color: string; icon: typeof Search; label: string; sub?: string; to: string }

export function CommandPalette({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const [q, setQ] = useState('');
  const dq = useDebouncedValue(q, 250);
  const { data, isFetching } = useSearch(dq, 5);
  const navigate = useNavigate();
  const [active, setActive] = useState(0);

  useEffect(() => {
    if (!open) setQ('');
  }, [open]);

  const rows = useMemo<Row[]>(() => {
    if (!data || dq.trim().length < 2) return [];
    const out: Row[] = [];
    data.harnesses?.forEach((h) => out.push({ key: h.id, group: 'Harness Lab', color: MODULES.harness.color, icon: MODULES.harness.icon, label: h.name, sub: `${h.repo.owner}/${h.repo.name}`, to: `/harnesses/${h.id}/${h.slug}` }));
    data.ideas?.forEach((i) => out.push({ key: i.id, group: 'Project Ideas', color: MODULES.idea.color, icon: MODULES.idea.icon, label: i.title, sub: i.category.name, to: `/ideas/${i.id}/${i.slug}` }));
    data.resources?.forEach((r) => out.push({ key: r.id, group: 'Knowledge Hub', color: MODULES.knowledge.color, icon: MODULES.knowledge.icon, label: r.name, sub: r.domain, to: `/resources/${r.id}` }));
    data.collections?.forEach((c) => out.push({ key: c.id, group: 'Collections', color: MODULES.knowledge.color, icon: MODULES.knowledge.icon, label: c.title, sub: `${c.counts.items} resources`, to: `/collections/${c.id}/${c.slug}` }));
    return out;
  }, [data, dq]);

  const total = rows.length + (dq.trim().length >= 2 ? 1 : 0);
  useEffect(() => setActive(0), [dq]);

  const go = (to: string) => {
    if (q.trim()) pushRecent(q.trim());
    onOpenChange(false);
    navigate(to);
  };
  const choose = (i: number) => {
    if (i < rows.length) go(rows[i].to);
    else go(`/search?q=${encodeURIComponent(q.trim())}`);
  };

  const recent = readRecent();
  let lastGroup = '';

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/30" />
        <Dialog.Content className="fixed top-[12vh] left-1/2 z-50 w-[min(94vw,600px)] -translate-x-1/2 overflow-hidden rounded-[14px] border border-border bg-surface shadow-[var(--shadow-dialog)]">
          <Dialog.Title className="sr-only">Search DevCommons</Dialog.Title>
          <Dialog.Description className="sr-only">Type to search harnesses, ideas, resources and collections.</Dialog.Description>
          <div className="flex items-center gap-2 border-b border-border px-3">
            <Search size={17} className="text-muted" aria-hidden />
            <input
              autoFocus
              role="combobox"
              aria-expanded={total > 0}
              aria-controls="palette-results"
              aria-activedescendant={total ? `palette-row-${active}` : undefined}
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'ArrowDown') { e.preventDefault(); setActive((a) => Math.min(a + 1, total - 1)); }
                if (e.key === 'ArrowUp') { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
                if (e.key === 'Enter' && total) { e.preventDefault(); choose(active); }
              }}
              placeholder="Search harnesses, ideas, docs…"
              className="h-12 flex-1 bg-transparent text-[15px] outline-none focus-visible:outline-none placeholder:text-muted"
            />
            {isFetching && <span className="font-mono text-xs text-muted">…</span>}
          </div>
          <div id="palette-results" role="listbox" className="max-h-[60vh] overflow-y-auto p-1.5">
            {dq.trim().length < 2 ? (
              recent.length ? (
                <div className="p-1.5">
                  <p className="px-2 pb-1 text-xs font-medium text-muted">Recent searches</p>
                  {recent.map((r) => (
                    <button key={r} type="button" onClick={() => setQ(r)} className="flex w-full cursor-pointer items-center gap-2 rounded-[6px] px-2 py-2 text-left text-sm hover:bg-surface-2">
                      <Clock size={14} className="text-muted" aria-hidden /> {r}
                    </button>
                  ))}
                </div>
              ) : (
                <p className="px-3 py-6 text-center text-sm text-muted">Type at least two characters.</p>
              )
            ) : (
              <>
                {rows.length === 0 && !isFetching && <p className="px-3 py-4 text-sm text-muted">No quick matches.</p>}
                {rows.map((r, i) => {
                  const header = r.group !== lastGroup;
                  lastGroup = r.group;
                  const Icon = r.icon;
                  return (
                    <div key={r.key}>
                      {header && <p className="px-2 pt-2 pb-1 text-xs font-medium" style={{ color: r.color }}>{r.group}</p>}
                      <div
                        id={`palette-row-${i}`}
                        role="option"
                        aria-selected={active === i}
                        onMouseEnter={() => setActive(i)}
                        onClick={() => choose(i)}
                        className={cn('flex cursor-pointer items-center gap-2.5 rounded-[6px] px-2 py-2 text-sm', active === i && 'bg-surface-2')}
                      >
                        <Icon size={15} style={{ color: r.color }} aria-hidden />
                        <span className="truncate">{r.label}</span>
                        {r.sub && <span className="ml-auto shrink-0 font-mono text-xs text-muted">{r.sub}</span>}
                      </div>
                    </div>
                  );
                })}
                <div
                  id={`palette-row-${rows.length}`}
                  role="option"
                  aria-selected={active === rows.length}
                  onMouseEnter={() => setActive(rows.length)}
                  onClick={() => choose(rows.length)}
                  className={cn('mt-1 flex cursor-pointer items-center gap-2 rounded-[6px] border-t border-border px-2 py-2.5 text-sm', active === rows.length && 'bg-surface-2')}
                >
                  <CornerDownLeft size={14} className="text-muted" aria-hidden /> See all results for “{q.trim()}”
                </div>
              </>
            )}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
