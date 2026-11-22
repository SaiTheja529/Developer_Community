import { Link, useNavigate } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { ArrowUpRight, MessageSquare, Sparkles } from 'lucide-react';
import { useHome } from '@/lib/api/queries';
import { Diorama } from '@/features/three';
import { CollectionCard, HarnessCard, IdeaCard, ResourceRow } from '@/components/common/Cards';
import { CardSkeleton, ErrorState, Skeleton } from '@/components/common/States';
import { buttonClass } from '@/components/common/Button';
import { MODULES, type ModuleKey } from '@/lib/modules';
import { compact } from '@/lib/format';
import { useAuth } from '@/features/auth/AuthProvider';
import { getData } from '@/lib/api/client';
import { qk } from '@/lib/queryKeys';
import type { ConversationSummary } from '@/lib/api/types';
import { TimeAgo } from '@/components/common/Meta';
import { cn } from '@/lib/cn';

function Legend() {
  const row = 'flex items-start gap-2.5';
  return (
    <dl className="grid gap-2.5 text-sm text-muted sm:grid-cols-2">
      <div className={row}>
        <dt><svg width="16" height="18" viewBox="0 0 16 18" aria-hidden><rect x="3" y="2" width="10" height="3" fill="var(--harness)" /><rect x="3" y="7" width="10" height="3" fill="var(--harness)" /><rect x="3" y="12" width="10" height="3" fill="var(--harness)" /></svg><span className="sr-only">Towers</span></dt>
        <dd>Harnesses. More floors, more votes and GitHub stars.</dd>
      </div>
      <div className={row}>
        <dt><svg width="16" height="18" viewBox="0 0 16 18" aria-hidden><path d="M8 1 12 5 8 9 4 5z" fill="var(--idea)" /><path d="M6 11h4v6H6z" fill="var(--idea)" opacity=".5" /></svg><span className="sr-only">Beacons</span></dt>
        <dd>Ideas. A glowing lantern is looking for collaborators.</dd>
      </div>
      <div className={row}>
        <dt><svg width="16" height="18" viewBox="0 0 16 18" aria-hidden><rect x="2" y="12" width="12" height="3" fill="var(--knowledge)" /><rect x="3" y="8" width="10" height="3" fill="var(--knowledge)" opacity=".6" /><rect x="2.5" y="4" width="11" height="3" fill="var(--knowledge)" /></svg><span className="sr-only">Book stacks and shelves</span></dt>
        <dd>Resources stack a book per recommendation. Shelves are collections.</dd>
      </div>
      <div className={row}>
        <dt><svg width="16" height="18" viewBox="0 0 16 18" aria-hidden><circle cx="8" cy="9" r="6" fill="none" stroke="var(--ai)" strokeWidth="1.5" strokeDasharray="2.5 2" /><path d="M8 5.5 10.5 9 8 12.5 5.5 9z" fill="var(--ai)" /></svg><span className="sr-only">AI core</span></dt>
        <dd>AI is dashed, here and everywhere. It reaches every district.</dd>
      </div>
    </dl>
  );
}

function ModuleTile({ k, count, countLabel, to }: { k: ModuleKey; count?: number; countLabel: string; to: string }) {
  const m = MODULES[k];
  const Icon = m.icon;
  return (
    <Link
      to={to}
      className={cn('group flex flex-col rounded-[10px] border border-border bg-surface p-4 shadow-[var(--shadow-card)] hover:border-[color:var(--tile)]', `stripe-${k}`, k === 'ai' && 'border-dashed')}
      style={{ ['--tile' as string]: m.color }}
    >
      <div className="flex items-center justify-between">
        <Icon size={18} style={{ color: m.color }} aria-hidden />
        <ArrowUpRight size={16} className="text-muted group-hover:text-text" aria-hidden />
      </div>
      <p className="mt-3 font-semibold">{m.name}</p>
      <p className="font-mono text-xs" style={{ color: m.color }}>{m.tagline}</p>
      <p className="mt-3 text-sm text-muted">
        {count == null ? countLabel : count === 0 ? `Be the first to add one.` : <><span className="font-mono text-text">{compact(count)}</span> {countLabel}</>}
      </p>
    </Link>
  );
}

function Section({ title, to, color, children }: { title: string; to: string; color: string; children: React.ReactNode }) {
  return (
    <section className="mt-12">
      <div className="mb-4 flex items-baseline justify-between gap-4">
        <h2 className="flex items-center gap-2 text-xl">
          <span className="h-4 w-1 rounded-full" style={{ background: color }} aria-hidden />
          {title}
        </h2>
        <Link to={to} className="shrink-0 text-sm text-muted hover:text-text hover:underline">See all</Link>
      </div>
      {children}
    </section>
  );
}

function ContinueStrip() {
  const { status } = useAuth();
  const { data } = useQuery({
    queryKey: qk.conversations,
    queryFn: () => getData<ConversationSummary[]>('/api/ai/conversations'),
    enabled: status === 'signed_in',
  });
  if (!data?.length) return null;
  return (
    <section className="mt-10">
      <h2 className="mb-3 text-lg">Continue where you left off</h2>
      <div className="grid gap-3 md:grid-cols-3">
        {data.slice(0, 3).map((c) => (
          <Link key={c.id} to={`/ai/c/${c.id}`} className="ai-surface flex items-start gap-3 rounded-[10px] p-3.5 hover:bg-ai-soft">
            <MessageSquare size={16} className="mt-0.5 shrink-0 text-ai" aria-hidden />
            <span className="min-w-0">
              <span className="block truncate text-sm font-medium">{c.title ?? 'Untitled chat'}</span>
              <span className="font-mono text-xs text-muted">{c.context ? `${c.context.type} · ` : ''}{c.last_message_at ? <TimeAgo iso={c.last_message_at} /> : 'new'}</span>
            </span>
          </Link>
        ))}
      </div>
    </section>
  );
}

export default function HomePage() {
  const { data, isLoading, error, refetch } = useHome();
  const navigate = useNavigate();
  const seeking = data?.ideas.recent.concat(data.ideas.trending).filter((i, idx, a) => i.collaboration_status === 'seeking_collaborators' && a.findIndex((x) => x.id === i.id) === idx).slice(0, 3);

  return (
    <>
      <title>DevCommons · Harnesses, ideas and docs for building with AI agents</title>
      <section className="relative overflow-hidden border-b border-border">
        <div className="mx-auto grid max-w-[1200px] gap-6 px-4 pt-10 pb-6 md:px-8 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:items-center lg:gap-4 lg:py-12">
          <div className="relative z-10 max-w-xl">
            <h1 className="text-[34px] leading-[1.12] font-semibold tracking-[-0.015em] md:text-[44px]">
              The commons for people building with AI coding agents.
            </h1>
            <p className="mt-4 text-[17px] text-muted">
              Share the harnesses that keep your agents on track, swap project ideas and find collaborators, and keep the docs that actually helped. AI assists, and you decide what gets published.
            </p>
            <div className="mt-6 flex flex-wrap gap-2">
              <Link to="/harnesses" className={buttonClass('primary', 'lg')}>Explore harnesses</Link>
              <Link to="/ideas/new" className={buttonClass('secondary', 'lg')}>Share an idea</Link>
              <Link to="/ai" className={buttonClass('ai', 'lg')}><Sparkles size={16} aria-hidden /> Ask AI</Link>
            </div>
            <div className="mt-8 hidden lg:block"><Legend /></div>
          </div>
          <div
            role="img"
            aria-label={data ? `A 3D model of the community: ${data.counts.harnesses} harnesses, ${data.counts.ideas} ideas, ${data.counts.resources} resources and ${data.counts.collections} collections. The same items are listed below.` : 'Loading the community model'}
            className="relative -mx-4 h-[340px] sm:h-[420px] md:mx-0 lg:h-[520px]"
          >
            {isLoading ? <Skeleton className="h-full w-full rounded-[14px] opacity-50" /> : data ? <Diorama data={data} onSelect={(to) => navigate(to)} /> : null}
            <p className="pointer-events-none absolute right-2 bottom-1 hidden font-mono text-[11px] text-muted md:block" aria-hidden>Drag to turn · click a piece to open it</p>
          </div>
          <div className="lg:hidden"><Legend /></div>
        </div>
      </section>

      <div className="mx-auto max-w-[1200px] px-4 md:px-8">
        {error && <div className="mt-8"><ErrorState error={error} onRetry={() => refetch()} /></div>}

        <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <ModuleTile k="harness" to="/harnesses" count={data?.counts.harnesses} countLabel="harnesses shared" />
          <ModuleTile k="idea" to="/ideas" count={data?.counts.ideas} countLabel="project ideas" />
          <ModuleTile k="knowledge" to="/resources" count={data?.counts.resources} countLabel="resources checked" />
          <ModuleTile k="ai" to="/ai" countLabel="Chat with page context, or draft docs from a repo." />
        </div>

        <ContinueStrip />

        <Section title="Trending harnesses" to="/harnesses?sort=trending" color={MODULES.harness.color}>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {isLoading ? Array.from({ length: 3 }, (_, i) => <CardSkeleton key={i} />) : (data?.harnesses.trending.length ? data.harnesses.trending : data?.harnesses.recent ?? []).slice(0, 3).map((h) => <HarnessCard key={h.id} h={h} />)}
          </div>
        </Section>

        <Section title="Ideas looking for collaborators" to="/ideas?collaboration_status=seeking_collaborators" color={MODULES.idea.color}>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {isLoading ? Array.from({ length: 3 }, (_, i) => <CardSkeleton key={i} />) : seeking?.length ? seeking.map((i) => <IdeaCard key={i.id} i={i} />) : <p className="text-sm text-muted">No open calls right now. <Link to="/ideas/new" className="underline">Share an idea</Link> and ask for help.</p>}
          </div>
        </Section>

        <div className="grid gap-x-8 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
          <Section title="Recently added resources" to="/resources" color={MODULES.knowledge.color}>
            <div className="rounded-[10px] border border-border bg-surface px-4">
              {isLoading ? <div className="space-y-3 py-4">{Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-12" />)}</div> : data?.resources.recent.slice(0, 5).map((r) => <ResourceRow key={r.id} r={r} />)}
            </div>
          </Section>
          <Section title="Featured collections" to="/collections" color={MODULES.knowledge.color}>
            <div className="grid gap-4">
              {(data?.collections.featured.length ? data.collections.featured : data?.collections.recent ?? []).slice(0, 3).map((c) => <CollectionCard key={c.id} c={c} />)}
            </div>
          </Section>
        </div>
      </div>
    </>
  );
}
