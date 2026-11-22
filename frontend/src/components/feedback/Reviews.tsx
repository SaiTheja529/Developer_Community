import { useState } from 'react';
import { FileText, Star } from 'lucide-react';
import { useReviews } from '@/lib/api/queries';
import type { RatingSummary as RS } from '@/lib/api/types';
import { TimeAgo, UserChip } from '@/components/common/Meta';
import { MarkdownView } from '@/components/common/MarkdownView';
import { EmptyState, ErrorState, Skeleton } from '@/components/common/States';
import { cn } from '@/lib/cn';

const DIMS = ['overall', 'documentation', 'setup', 'coordination', 'reliability'] as const;

export function RatingSummary({ r }: { r: RS | null }) {
  if (!r || r.count === 0) return null;
  return (
    <div className="rounded-[10px] border border-border bg-surface p-4">
      <p className="text-sm font-semibold">Community ratings</p>
      <dl className="mt-3 space-y-2">
        {DIMS.map((d) => r[d] != null && (
          <div key={d} className="flex items-center gap-3 text-sm">
            <dt className="w-28 capitalize text-muted">{d}</dt>
            <dd className="flex flex-1 items-center gap-2">
              <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-2"><span className="block h-full rounded-full bg-harness" style={{ width: `${((r[d] as number) / 5) * 100}%` }} /></span>
              <span className="w-24 text-right font-mono text-xs">{(r[d] as number).toFixed(1)} · {r.counts[d]} {r.counts[d] === 1 ? 'rating' : 'ratings'}</span>
            </dd>
          </div>
        ))}
      </dl>
      <p className="mt-3 text-xs text-muted">Community opinions, not guarantees.</p>
    </div>
  );
}

const SECTIONS = [
  ['what_tested', 'What did you test?'], ['worked_well', 'What worked well?'],
  ['did_not_work', 'What did not work as expected?'], ['recommendations', 'What improvements would you recommend?'],
] as const;

export function ReviewList({ harnessId, summary }: { harnessId: string; summary: RS | null }) {
  const [sort, setSort] = useState('helpful');
  const { data, isLoading, error, refetch } = useReviews(harnessId, sort);
  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_300px]">
      <div>
        <div className="mb-4 flex items-center gap-1" role="group" aria-label="Sort reports">
          {['helpful', 'recent'].map((s) => (
            <button key={s} type="button" aria-pressed={sort === s} onClick={() => setSort(s)} className={cn('h-8 cursor-pointer rounded-[6px] px-2.5 text-sm capitalize', sort === s ? 'bg-surface-2 font-medium' : 'text-muted hover:text-text')}>{s}</button>
          ))}
        </div>
        {isLoading ? <div className="space-y-3">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-32" />)}</div>
          : error ? <ErrorState error={error} onRetry={() => refetch()} />
          : !data?.data.length ? <EmptyState icon={FileText} title="No testing reports yet.">Tried it? Share what happened, including what broke.</EmptyState>
          : (
            <ul className="space-y-4">
              {data.data.map((rv) => (
                <li key={rv.id} className="rounded-[10px] border border-border bg-surface p-4">
                  <div className="flex flex-wrap items-center gap-2 text-sm">
                    <UserChip user={rv.author} />
                    <span className="font-mono text-xs text-muted"><TimeAgo iso={rv.created_at} />{rv.environment && ` · ${rv.environment}`}</span>
                    {rv.ratings?.overall != null && <span className="ml-auto inline-flex items-center gap-1 font-mono text-xs"><Star size={12} fill="currentColor" aria-hidden /> {rv.ratings.overall} / 5</span>}
                  </div>
                  <div className="mt-3 space-y-3">
                    {SECTIONS.map(([k, label]) => rv[k] && (
                      <div key={k}>
                        <p className="text-xs font-medium text-muted">{label}</p>
                        <MarkdownView source={rv[k]} className="text-[15px]" />
                      </div>
                    ))}
                  </div>
                  <p className="mt-3 border-t border-border pt-2 text-xs text-muted">Community opinion based on this reviewer's testing.</p>
                </li>
              ))}
            </ul>
          )}
      </div>
      <aside><RatingSummary r={summary} /></aside>
    </div>
  );
}
