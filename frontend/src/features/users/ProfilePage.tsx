import { useParams, useSearchParams, Link } from 'react-router';
import { ExternalLink } from 'lucide-react';
import { useContributions, useProfile } from '@/lib/api/queries';
import { Avatar } from '@/components/common/Meta';
import { Chip } from '@/components/common/Badges';
import { CollectionCard, HarnessCard, IdeaCard, ResourceRow } from '@/components/common/Cards';
import { CardSkeleton, DetailSkeleton, EmptyState } from '@/components/common/States';
import { DetailError } from '@/components/common/DetailHelpers';
import { Pagination } from '@/components/common/Pagination';
import { monthYear, safeUrl } from '@/lib/format';
import { useAuth } from '@/features/auth/AuthProvider';
import type { CollectionSummary, HarnessSummary, IdeaSummary, ResourceSummary } from '@/lib/api/types';
import { cn } from '@/lib/cn';

const TABS = ['harnesses', 'ideas', 'resources', 'collections'] as const;

export default function ProfilePage() {
  const { username = '' } = useParams();
  const [sp, setSp] = useSearchParams();
  const tab = (TABS as readonly string[]).includes(sp.get('tab') ?? '') ? (sp.get('tab') as (typeof TABS)[number]) : 'harnesses';
  const page = Number(sp.get('page') ?? 1);
  const { user } = useAuth();
  const { data: p, isLoading, error, refetch } = useProfile(username);
  const contrib = useContributions(username, tab, page);
  if (isLoading) return <DetailSkeleton />;
  if (error || !p) return <DetailError error={error} retry={() => refetch()} noun="profile" listPath="/" />;
  const site = safeUrl(p.website_url);
  const items = (contrib.data?.data ?? []) as unknown[];
  return (
    <div className="mx-auto max-w-[1200px] px-4 py-8 md:px-8">
      <title>{`${p.display_name} (@${p.username}) · DevCommons`}</title>
      <header className="flex flex-col gap-5 sm:flex-row sm:items-start">
        <Avatar user={p} size={72} />
        <div className="min-w-0 flex-1">
          <h1 className="text-[26px]">{p.display_name}</h1>
          <p className="font-mono text-sm text-muted">@{p.username} · joined {monthYear(p.joined_at)}</p>
          {p.bio && <p className="mt-3 max-w-[72ch]">{p.bio}</p>}
          <div className="mt-3 flex flex-wrap gap-1.5">{[...p.skills, ...p.interests].map((s) => <Chip key={s}>{s}</Chip>)}</div>
          <div className="mt-3 flex flex-wrap gap-4 text-sm">
            {site && <a href={site} target="_blank" rel="noopener noreferrer nofollow" className="inline-flex items-center gap-1 underline">{new URL(site).hostname} <ExternalLink size={12} aria-hidden /></a>}
            {p.github_username && <a href={`https://github.com/${encodeURIComponent(p.github_username)}`} target="_blank" rel="noopener noreferrer nofollow" className="inline-flex items-center gap-1 underline">github/{p.github_username} <ExternalLink size={12} aria-hidden /></a>}
            {p.contact_links.map((l) => safeUrl(l.url) && <a key={l.url} href={safeUrl(l.url)!} target="_blank" rel="noopener noreferrer nofollow" className="underline">{l.label}</a>)}
          </div>
        </div>
        {user?.username === p.username && <Link to="/settings/profile" className="inline-flex h-9 items-center rounded-[6px] border border-border px-3 text-sm font-medium hover:bg-surface-2">Edit profile</Link>}
      </header>
      <nav aria-label="Contributions" className="mt-8 flex gap-1 overflow-x-auto border-b border-border" id="list-top">
        {TABS.map((t) => (
          <button key={t} type="button" onClick={() => setSp({ tab: t })} aria-current={tab === t ? 'page' : undefined} className={cn('h-10 shrink-0 cursor-pointer border-b-2 px-3 text-sm font-medium capitalize', tab === t ? 'border-text text-text' : 'border-transparent text-muted hover:text-text')}>
            {t} <span className="font-mono text-xs text-muted">{p.stats[t]}</span>
          </button>
        ))}
      </nav>
      <div className="mt-6">
        {contrib.isLoading ? <div className="grid gap-4 md:grid-cols-3">{[0, 1, 2].map((i) => <CardSkeleton key={i} />)}</div>
          : !items.length ? <EmptyState title={`No ${tab} yet.`} />
          : tab === 'resources' ? <div className="rounded-[10px] border border-border bg-surface px-4">{(items as ResourceSummary[]).map((r) => <ResourceRow key={r.id} r={r} />)}</div>
          : (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {tab === 'harnesses' && (items as HarnessSummary[]).map((h) => <HarnessCard key={h.id} h={h} />)}
              {tab === 'ideas' && (items as IdeaSummary[]).map((i) => <IdeaCard key={i.id} i={i} />)}
              {tab === 'collections' && (items as CollectionSummary[]).map((c) => <CollectionCard key={c.id} c={c} />)}
            </div>
          )}
        {contrib.data && <Pagination meta={contrib.data.meta} onPage={(n) => setSp({ tab, page: String(n) })} />}
      </div>
    </div>
  );
}
