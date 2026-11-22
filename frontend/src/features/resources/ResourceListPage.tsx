import { Link, NavLink } from 'react-router';
import { Plus } from 'lucide-react';
import { useResourceList } from '@/lib/api/queries';
import { useListParams } from '@/hooks/useListParams';
import { useConfig } from '@/hooks/useConfig';
import { ModuleHero } from '@/components/layout/PageHeader';
import { FilterBar, Select, Toggle } from '@/components/common/FilterBar';
import { ResourceRow } from '@/components/common/Cards';
import { EmptyState, ErrorState, Skeleton } from '@/components/common/States';
import { Pagination } from '@/components/common/Pagination';
import { buttonClass } from '@/components/common/Button';
import { humanize } from '@/lib/format';
import { cn } from '@/lib/cn';

export function KnowledgeTabs() {
  const tab = (to: string, label: string) => (
    <NavLink to={to} className={({ isActive }) => cn('h-10 border-b-2 px-3 text-sm leading-10 font-medium', isActive ? 'border-knowledge text-text' : 'border-transparent text-muted hover:text-text')}>
      {label}
    </NavLink>
  );
  return <nav aria-label="Knowledge Hub" className="flex gap-1 border-b border-border">{tab('/resources', 'Resources')}{tab('/collections', 'Collections')}</nav>;
}

export default function ResourceListPage() {
  const lp = useListParams({ sort: 'recent' });
  const { params, set, page } = lp;
  const { data: config } = useConfig();
  const { data, isLoading, error, refetch } = useResourceList(params);
  const types = (config?.enums.resource_types as string[] | undefined) ?? [];
  const levels = (config?.enums.resource_levels as string[] | undefined) ?? ['beginner', 'intermediate', 'advanced'];
  return (
    <>
      <title>Knowledge Hub · DevCommons</title>
      {page === 1 && <ModuleHero module="knowledge" cta={<Link to="/resources/new" className={buttonClass('primary', 'lg')}><Plus size={16} aria-hidden /> Add a resource</Link>} />}
      <div className="mx-auto max-w-[1200px] px-4 py-6 md:px-8" id="list-top">
        <KnowledgeTabs />
        <div className="mt-5">
          <FilterBar {...lp} sorts={config?.sorts.resources ?? ['recent', 'popular', 'trending']} searchLabel="Search resources">
            <Select label="Category" value={params.category ?? ''} onChange={(v) => set({ category: v })} options={[{ value: '', label: 'All categories' }, ...(config?.categories.resource ?? []).map((c) => ({ value: c.slug, label: c.name }))]} />
            <Select label="Type" value={params.resource_type ?? ''} onChange={(v) => set({ resource_type: v })} options={[{ value: '', label: 'Any type' }, ...types.map((t) => ({ value: t, label: humanize(t) }))]} />
            <Select label="Level" value={params.level ?? ''} onChange={(v) => set({ level: v })} options={[{ value: '', label: 'Any level' }, ...levels.map((t) => ({ value: t, label: humanize(t) }))]} />
            <Toggle label="Official docs only" checked={params.official === 'true'} onChange={(v) => set({ official: v ? 'true' : '' })} />
            <Toggle label="Include possibly broken links" checked={params.include_broken === 'true'} onChange={(v) => set({ include_broken: v ? 'true' : '' })} />
          </FilterBar>
        </div>
        <div className="mt-6">
          {error ? <ErrorState error={error} onRetry={() => refetch()} /> : isLoading ? (
            <div className="space-y-3">{Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-20" />)}</div>
          ) : data?.data.length === 0 ? (
            lp.activeCount ? <EmptyState title="No resources match these filters." action={<button className={buttonClass()} onClick={lp.clear}>Clear filters</button>} />
              : <EmptyState title="No resources yet." action={<Link to="/resources/new" className={buttonClass('primary')}>Add the first one</Link>} />
          ) : (
            <>
              <p className="mb-3 font-mono text-xs text-muted">{data?.meta.total} resources</p>
              <div className="rounded-[10px] border border-border bg-surface px-4">{data?.data.map((r) => <ResourceRow key={r.id} r={r} />)}</div>
              {data && <Pagination meta={data.meta} onPage={(p) => set({ page: String(p) })} />}
            </>
          )}
        </div>
      </div>
    </>
  );
}
