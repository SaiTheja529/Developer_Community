import { Link } from 'react-router';
import { Plus } from 'lucide-react';
import { useIdeaList } from '@/lib/api/queries';
import { useListParams } from '@/hooks/useListParams';
import { useConfig } from '@/hooks/useConfig';
import { ModuleHero } from '@/components/layout/PageHeader';
import { FilterBar, Select, fieldClass } from '@/components/common/FilterBar';
import { IdeaCard } from '@/components/common/Cards';
import { CardSkeleton, EmptyState, ErrorState } from '@/components/common/States';
import { Pagination } from '@/components/common/Pagination';
import { buttonClass } from '@/components/common/Button';

export default function IdeaListPage() {
  const lp = useListParams({ sort: 'recent' });
  const { params, set, page } = lp;
  const { data: config } = useConfig();
  const { data, isLoading, error, refetch } = useIdeaList(params);
  return (
    <>
      <title>Project Ideas · DevCommons</title>
      {page === 1 && <ModuleHero module="idea" cta={<Link to="/ideas/new" className={buttonClass('primary', 'lg')}><Plus size={16} aria-hidden /> Share an idea</Link>} />}
      <div className="mx-auto max-w-[1200px] px-4 py-6 md:px-8" id="list-top">
        <FilterBar {...lp} sorts={config?.sorts.ideas ?? ['recent', 'popular', 'trending', 'most_interest', 'most_discussed']} searchLabel="Search ideas">
          <Select label="Category" value={params.category ?? ''} onChange={(v) => set({ category: v })} options={[{ value: '', label: 'All categories' }, ...(config?.categories.idea ?? []).map((c) => ({ value: c.slug, label: c.name }))]} />
          <Select
            label="Collaboration"
            value={params.collaboration_status ?? ''}
            onChange={(v) => set({ collaboration_status: v })}
            options={[{ value: '', label: 'All' }, { value: 'seeking_collaborators', label: 'Looking for collaborators' }, { value: 'sharing', label: 'Just sharing' }, { value: 'team_formed', label: 'Team formed' }]}
          />
          <label className="flex flex-col gap-1">
            <span className="text-xs font-medium text-muted">Tech</span>
            <input defaultValue={params.tech ?? ''} onBlur={(e) => set({ tech: e.target.value.toLowerCase().replace(/\s+/g, '') })} onKeyDown={(e) => e.key === 'Enter' && set({ tech: e.currentTarget.value.toLowerCase().replace(/\s+/g, '') })} placeholder="python,react" className={`${fieldClass} w-40 font-mono`} />
          </label>
        </FilterBar>
        <div className="mt-6">
          {error ? <ErrorState error={error} onRetry={() => refetch()} /> : isLoading ? (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{Array.from({ length: 6 }, (_, i) => <CardSkeleton key={i} />)}</div>
          ) : data?.data.length === 0 ? (
            lp.activeCount ? <EmptyState title="No ideas match these filters." action={<button className={buttonClass()} onClick={lp.clear}>Clear filters</button>} />
              : <EmptyState title="No ideas yet." action={<Link to="/ideas/new" className={buttonClass('primary')}>Share the first one</Link>} />
          ) : (
            <>
              <p className="mb-3 font-mono text-xs text-muted">{data?.meta.total} ideas</p>
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{data?.data.map((i) => <IdeaCard key={i.id} i={i} />)}</div>
              {data && <Pagination meta={data.meta} onPage={(p) => set({ page: String(p) })} />}
            </>
          )}
        </div>
      </div>
    </>
  );
}
