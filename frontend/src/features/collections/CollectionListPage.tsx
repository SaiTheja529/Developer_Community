import { Link } from 'react-router';
import { Plus } from 'lucide-react';
import { useCollectionList } from '@/lib/api/queries';
import { useListParams } from '@/hooks/useListParams';
import { useConfig } from '@/hooks/useConfig';
import { ModuleHero } from '@/components/layout/PageHeader';
import { FilterBar, Select } from '@/components/common/FilterBar';
import { CollectionCard } from '@/components/common/Cards';
import { CardSkeleton, EmptyState, ErrorState } from '@/components/common/States';
import { Pagination } from '@/components/common/Pagination';
import { buttonClass } from '@/components/common/Button';
import { KnowledgeTabs } from '@/features/resources/ResourceListPage';

export default function CollectionListPage() {
  const lp = useListParams({ sort: 'recent' });
  const { params, set, page } = lp;
  const { data: config } = useConfig();
  const { data, isLoading, error, refetch } = useCollectionList(params);
  return (
    <>
      <title>Collections · Knowledge Hub · DevCommons</title>
      {page === 1 && <ModuleHero module="knowledge" cta={<Link to="/collections/new" className={buttonClass('primary', 'lg')}><Plus size={16} aria-hidden /> Create a collection</Link>} />}
      <div className="mx-auto max-w-[1200px] px-4 py-6 md:px-8" id="list-top">
        <KnowledgeTabs />
        <div className="mt-5">
          <FilterBar {...lp} sorts={config?.sorts.collections ?? ['recent', 'popular', 'trending']} searchLabel="Search collections">
            <Select label="Category" value={params.category ?? ''} onChange={(v) => set({ category: v })} options={[{ value: '', label: 'All categories' }, ...(config?.categories.collection ?? []).map((c) => ({ value: c.slug, label: c.name }))]} />
          </FilterBar>
        </div>
        <div className="mt-6">
          {error ? <ErrorState error={error} onRetry={() => refetch()} /> : isLoading ? (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{Array.from({ length: 6 }, (_, i) => <CardSkeleton key={i} />)}</div>
          ) : data?.data.length === 0 ? (
            <EmptyState title="No collections yet." action={<Link to="/collections/new" className={buttonClass('primary')}>Create the first one</Link>} />
          ) : (
            <>
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{data?.data.map((c) => <CollectionCard key={c.id} c={c} />)}</div>
              {data && <Pagination meta={data.meta} onPage={(p) => set({ page: String(p) })} />}
            </>
          )}
        </div>
      </div>
    </>
  );
}
