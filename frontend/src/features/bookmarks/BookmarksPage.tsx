import { useSearchParams } from 'react-router';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { Bookmark } from 'lucide-react';
import { apiFetch } from '@/lib/api/client';
import type { CollectionSummary, HarnessSummary, IdeaSummary, Paginated, ResourceSummary } from '@/lib/api/types';
import { CollectionCard, HarnessCard, IdeaCard, ResourceRow } from '@/components/common/Cards';
import { EmptyState, ErrorState, CardSkeleton } from '@/components/common/States';
import { Pagination } from '@/components/common/Pagination';
import { cn } from '@/lib/cn';

interface BM { target_type: 'harness' | 'idea' | 'resource' | 'collection'; target_id: string; bookmarked_at: string; item: unknown; unavailable: boolean }
const TABS: [string, string][] = [['', 'All'], ['harness', 'Harnesses'], ['idea', 'Ideas'], ['resource', 'Resources'], ['collection', 'Collections']];

export default function BookmarksPage() {
  const [sp, setSp] = useSearchParams();
  const type = sp.get('type') ?? '';
  const page = Number(sp.get('page') ?? 1);
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['bookmarks', type, page],
    queryFn: () => apiFetch<Paginated<BM>>('/api/users/me/bookmarks', { query: { type, page } }),
    placeholderData: keepPreviousData,
  });
  return (
    <div className="mx-auto max-w-[1200px] px-4 py-8 md:px-8">
      <title>Bookmarks · DevCommons</title>
      <h1 className="flex items-center gap-2 text-[28px]"><Bookmark size={24} aria-hidden /> Bookmarks</h1>
      <div className="mt-6 flex gap-1 overflow-x-auto border-b border-border" role="tablist">
        {TABS.map(([v, l]) => <button key={v} role="tab" aria-selected={type === v} onClick={() => setSp(v ? { type: v } : {})} className={cn('-mb-px h-10 shrink-0 cursor-pointer border-b-2 px-3 text-sm font-medium', type === v ? 'border-text text-text' : 'border-transparent text-muted hover:text-text')}>{l}</button>)}
      </div>
      <div className="mt-6" id="list-top">
        {isLoading ? <div className="grid gap-4 md:grid-cols-3">{[0, 1, 2].map((i) => <CardSkeleton key={i} />)}</div>
          : error ? <ErrorState error={error} onRetry={() => refetch()} />
          : !data?.data.length ? <EmptyState icon={Bookmark} title="Nothing saved yet.">Use Save on any harness, idea, resource or collection to keep it here.</EmptyState>
          : (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {data.data.map((b) =>
                b.unavailable ? <p key={b.target_id} className="rounded-[10px] border border-dashed border-border p-4 text-sm text-muted">This {b.target_type} is no longer available.</p>
                  : b.target_type === 'harness' ? <HarnessCard key={b.target_id} h={b.item as HarnessSummary} />
                  : b.target_type === 'idea' ? <IdeaCard key={b.target_id} i={b.item as IdeaSummary} />
                  : b.target_type === 'collection' ? <CollectionCard key={b.target_id} c={b.item as CollectionSummary} />
                  : <div key={b.target_id} className="rounded-[10px] border border-border bg-surface px-4"><ResourceRow r={b.item as ResourceSummary} /></div>,
              )}
            </div>
          )}
        {data && <Pagination meta={data.meta} onPage={(p) => setSp({ ...(type ? { type } : {}), page: String(p) })} />}
      </div>
    </div>
  );
}
