import { Link, useSearchParams } from 'react-router';
import { useSearch } from '@/lib/api/queries';
import { CollectionCard, HarnessCard, IdeaCard, ResourceRow } from '@/components/common/Cards';
import { CardSkeleton, EmptyState, ErrorState } from '@/components/common/States';
import { MODULES } from '@/lib/modules';

export default function SearchPage() {
  const [sp] = useSearchParams();
  const q = sp.get('q') ?? '';
  const { data, isLoading, error, refetch } = useSearch(q, 10);
  const empty = data && !data.harnesses?.length && !data.ideas?.length && !data.resources?.length && !data.collections?.length;
  return (
    <div className="mx-auto max-w-[1200px] px-4 py-8 md:px-8">
      <title>{`Search: ${q} · DevCommons`}</title>
      <h1 className="text-[26px]">Results for “{q}”</h1>
      {isLoading && <div className="mt-6 grid gap-4 md:grid-cols-3">{Array.from({ length: 3 }, (_, i) => <CardSkeleton key={i} />)}</div>}
      {error && <div className="mt-6"><ErrorState error={error} onRetry={() => refetch()} /></div>}
      {empty && <div className="mt-6"><EmptyState title={`Nothing matches “${q}”.`}>Try a shorter phrase, or a tool name like “claude code”.</EmptyState></div>}
      {!!data?.harnesses?.length && (
        <section className="mt-8">
          <div className="flex items-baseline justify-between"><h2 className="text-lg" style={{ color: MODULES.harness.color }}>Harnesses</h2><Link className="text-sm text-muted hover:underline" to={`/harnesses?q=${encodeURIComponent(q)}`}>See all harnesses</Link></div>
          <div className="mt-3 grid gap-4 md:grid-cols-2 xl:grid-cols-3">{data.harnesses.map((h) => <HarnessCard key={h.id} h={h} />)}</div>
        </section>
      )}
      {!!data?.ideas?.length && (
        <section className="mt-8">
          <div className="flex items-baseline justify-between"><h2 className="text-lg" style={{ color: MODULES.idea.color }}>Ideas</h2><Link className="text-sm text-muted hover:underline" to={`/ideas?q=${encodeURIComponent(q)}`}>See all ideas</Link></div>
          <div className="mt-3 grid gap-4 md:grid-cols-2 xl:grid-cols-3">{data.ideas.map((i) => <IdeaCard key={i.id} i={i} />)}</div>
        </section>
      )}
      {!!data?.resources?.length && (
        <section className="mt-8">
          <div className="flex items-baseline justify-between"><h2 className="text-lg" style={{ color: MODULES.knowledge.color }}>Resources</h2><Link className="text-sm text-muted hover:underline" to={`/resources?q=${encodeURIComponent(q)}`}>See all resources</Link></div>
          <div className="mt-3 rounded-[10px] border border-border bg-surface px-4">{data.resources.map((r) => <ResourceRow key={r.id} r={r} />)}</div>
        </section>
      )}
      {!!data?.collections?.length && (
        <section className="mt-8">
          <h2 className="text-lg" style={{ color: MODULES.knowledge.color }}>Collections</h2>
          <div className="mt-3 grid gap-4 md:grid-cols-2 xl:grid-cols-3">{data.collections.map((c) => <CollectionCard key={c.id} c={c} />)}</div>
        </section>
      )}
    </div>
  );
}
