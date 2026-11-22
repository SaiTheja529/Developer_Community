import { Link } from 'react-router';
import { Plus } from 'lucide-react';
import { useHarnessList } from '@/lib/api/queries';
import { useListParams } from '@/hooks/useListParams';
import { useConfig } from '@/hooks/useConfig';
import { ModuleHero } from '@/components/layout/PageHeader';
import { FilterBar, Select, Toggle } from '@/components/common/FilterBar';
import { HarnessCard } from '@/components/common/Cards';
import { CardSkeleton, EmptyState, ErrorState } from '@/components/common/States';
import { Pagination } from '@/components/common/Pagination';
import { buttonClass } from '@/components/common/Button';
import { TOOL_LABELS } from '@/lib/modules';

export default function HarnessListPage() {
  const lp = useListParams({ sort: 'recent' });
  const { params, set, page } = lp;
  const { data: config } = useConfig();
  const { data, isLoading, error, refetch, isPlaceholderData } = useHarnessList(params);
  const tools = (config?.enums.tools as string[] | undefined) ?? Object.keys(TOOL_LABELS);
  return (
    <>
      <title>Harness Lab · DevCommons</title>
      {page === 1 && <ModuleHero module="harness" cta={<Link to="/harnesses/new" className={buttonClass('primary', 'lg')}><Plus size={16} aria-hidden /> Submit a harness</Link>} />}
      <div className="mx-auto max-w-[1200px] px-4 py-6 md:px-8" id="list-top">
        <FilterBar {...lp} sorts={config?.sorts.harnesses ?? ['recent', 'popular', 'trending', 'most_reviewed', 'most_discussed']} searchLabel="Search harnesses">
          <Select label="Category" value={params.category ?? ''} onChange={(v) => set({ category: v })} options={[{ value: '', label: 'All categories' }, ...(config?.categories.harness ?? []).map((c) => ({ value: c.slug, label: c.name }))]} />
          <Select label="Tool" value={params.tools ?? ''} onChange={(v) => set({ tools: v })} options={[{ value: '', label: 'Any tool' }, ...tools.map((t) => ({ value: t, label: TOOL_LABELS[t] ?? t }))]} />
          <Toggle label="Featured only" checked={params.featured === 'true'} onChange={(v) => set({ featured: v ? 'true' : '' })} />
        </FilterBar>
        <div className="mt-6" aria-busy={isLoading || isPlaceholderData}>
          {error ? (
            <ErrorState error={error} onRetry={() => refetch()} />
          ) : isLoading ? (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{Array.from({ length: 6 }, (_, i) => <CardSkeleton key={i} />)}</div>
          ) : data && data.data.length === 0 ? (
            lp.activeCount ? (
              <EmptyState title="No harnesses match these filters." action={<button className={buttonClass()} onClick={lp.clear}>Clear filters</button>} />
            ) : (
              <EmptyState title="No harnesses yet." action={<Link to="/harnesses/new" className={buttonClass('primary')}>Submit the first one</Link>} />
            )
          ) : (
            <>
              <p className="mb-3 font-mono text-xs text-muted">{data?.meta.total} {data?.meta.total === 1 ? 'harness' : 'harnesses'}</p>
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{data?.data.map((h) => <HarnessCard key={h.id} h={h} />)}</div>
              {data && <Pagination meta={data.meta} onPage={(p) => set({ page: String(p) })} />}
            </>
          )}
        </div>
      </div>
    </>
  );
}
