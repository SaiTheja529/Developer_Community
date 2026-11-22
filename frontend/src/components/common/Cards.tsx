import { Link } from 'react-router';
import { useQueryClient } from '@tanstack/react-query';
import { ArrowBigUp, BookOpen, ExternalLink, FileText, GraduationCap, Hand, Library, MessageSquare, Newspaper, PlayCircle, Star, Lightbulb, type LucideIcon } from 'lucide-react';
import type { CollectionSummary, HarnessSummary, IdeaSummary, ResourceSummary } from '@/lib/api/types';
import { compact, humanize, safeUrl } from '@/lib/format';
import { getData } from '@/lib/api/client';
import { qk } from '@/lib/queryKeys';
import { AIBadge, Chip, CollabBadge, FeaturedBadge, LinkStatusBadge, OfficialBadge, ToolChip } from './Badges';
import { MetaLine, TimeAgo, UserChip } from './Meta';
import { cn } from '@/lib/cn';

function usePrefetch(plural: string, id: string) {
  const qc = useQueryClient();
  return () => void qc.prefetchQuery({ queryKey: qk.detail(plural, id), queryFn: () => getData(`/api/${plural}/${id}`), staleTime: 60_000 });
}

const Count = ({ icon: Icon, n, label }: { icon: LucideIcon; n: number; label: string }) => (
  <span className="inline-flex items-center gap-1" aria-label={`${n} ${label}`}>
    <Icon size={14} aria-hidden /> <span className="font-mono">{compact(n)}</span>
  </span>
);

function CardShell({ stripe, children, className }: { stripe: string; children: React.ReactNode; className?: string }) {
  return (
    <article className={cn('flex flex-col rounded-[10px] border border-border bg-surface p-4 shadow-[var(--shadow-card)]', stripe, className)}>
      {children}
    </article>
  );
}

export function HarnessCard({ h }: { h: HarnessSummary }) {
  const prefetch = usePrefetch('harnesses', h.id);
  return (
    <CardShell stripe="stripe-harness">
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-[17px] font-semibold">
          <Link to={`/harnesses/${h.id}/${h.slug}`} onMouseEnter={prefetch} onFocus={prefetch} className="hover:underline">{h.name}</Link>
        </h3>
        {h.repo.stars != null && (
          <span className="inline-flex shrink-0 items-center gap-1 font-mono text-xs text-muted" aria-label={`${h.repo.stars} GitHub stars`}>
            <Star size={12} aria-hidden /> {compact(h.repo.stars)}
          </span>
        )}
      </div>
      <MetaLine className="mt-1" parts={[h.category.name, `${h.repo.owner}/${h.repo.name}`, h.repo.language]} />
      <p className="mt-2.5 line-clamp-3 text-sm text-muted">{h.short_description}</p>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {h.tools.map((t) => <ToolChip key={t} tool={t} />)}
        {h.ai_assisted && <AIBadge variant="assisted" />}
        {h.is_featured && <FeaturedBadge color="var(--harness)" />}
      </div>
      <div className="mt-auto flex items-center justify-between gap-2 pt-4 text-xs text-muted">
        <UserChip user={h.author} size={18} className="text-xs text-muted" />
        <div className="flex items-center gap-3">
          <Count icon={ArrowBigUp} n={h.counts.votes} label="votes" />
          <Count icon={FileText} n={h.counts.reviews} label="testing reports" />
          <Count icon={Lightbulb} n={h.counts.suggestions} label="suggestions" />
        </div>
      </div>
    </CardShell>
  );
}

export function IdeaCard({ i }: { i: IdeaSummary }) {
  const prefetch = usePrefetch('ideas', i.id);
  const tech = i.tech_stack.slice(0, 4);
  return (
    <CardShell stripe="stripe-idea">
      <h3 className="text-[17px] font-semibold">
        <Link to={`/ideas/${i.id}/${i.slug}`} onMouseEnter={prefetch} onFocus={prefetch} className="hover:underline">{i.title}</Link>
      </h3>
      <MetaLine className="mt-1" parts={[i.category.name, <TimeAgo key="t" iso={i.created_at} />]} />
      <p className="mt-2.5 line-clamp-3 text-sm text-muted">{i.problem_statement}</p>
      <div className="mt-3 flex flex-wrap gap-1.5">
        <CollabBadge status={i.collaboration_status} />
        {tech.map((t) => <Chip key={t}>{t}</Chip>)}
        {i.tech_stack.length > 4 && <Chip>+{i.tech_stack.length - 4}</Chip>}
        {i.ai_assisted && <AIBadge variant="assisted" />}
      </div>
      <div className="mt-auto flex items-center justify-between gap-2 pt-4 text-xs text-muted">
        <UserChip user={i.author} size={18} className="text-xs text-muted" />
        <div className="flex items-center gap-3">
          <Count icon={ArrowBigUp} n={i.counts.votes} label="votes" />
          <Count icon={Hand} n={i.counts.interest} label="interested" />
          <Count icon={MessageSquare} n={i.counts.comments} label="comments" />
        </div>
      </div>
    </CardShell>
  );
}

export function CollectionCard({ c }: { c: CollectionSummary }) {
  const prefetch = usePrefetch('collections', c.id);
  return (
    <CardShell stripe="stripe-knowledge">
      <div className="flex items-start gap-3">
        <Library size={18} className="mt-1 shrink-0 text-knowledge" aria-hidden />
        <div className="min-w-0">
          <h3 className="text-[17px] font-semibold">
            <Link to={`/collections/${c.id}/${c.slug}`} onMouseEnter={prefetch} onFocus={prefetch} className="hover:underline">{c.title}</Link>
          </h3>
          <MetaLine className="mt-1" parts={[`${c.counts.items} ${c.counts.items === 1 ? 'resource' : 'resources'}`, c.category.name]} />
        </div>
      </div>
      {c.description && <p className="mt-2.5 line-clamp-2 text-sm text-muted">{c.description}</p>}
      {c.preview_domains && c.preview_domains.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">{c.preview_domains.slice(0, 3).map((d) => <Chip key={d}>{d}</Chip>)}</div>
      )}
      <div className="mt-auto flex items-center justify-between gap-2 pt-4 text-xs text-muted">
        <UserChip user={c.owner} size={18} className="text-xs text-muted" />
        <Count icon={ArrowBigUp} n={c.counts.votes} label="votes" />
      </div>
    </CardShell>
  );
}

const TYPE_ICON: Record<string, LucideIcon> = {
  official_docs: BookOpen, tutorial: GraduationCap, article: Newspaper, guide: FileText, video: PlayCircle, course: GraduationCap,
};

export function ResourceRow({ r, index }: { r: ResourceSummary; index?: number }) {
  const prefetch = usePrefetch('resources', r.id);
  const Icon = TYPE_ICON[r.resource_type] ?? FileText;
  const url = safeUrl(r.url);
  return (
    <article className="flex gap-3 border-b border-border py-4 last:border-b-0 sm:gap-4">
      {index != null ? (
        <span className="w-6 shrink-0 pt-0.5 text-right font-mono text-sm text-muted">{index}</span>
      ) : (
        <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-[6px] bg-knowledge-soft text-knowledge">
          <Icon size={16} aria-hidden />
        </span>
      )}
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <h3 className="font-semibold">
            <Link to={`/resources/${r.id}`} onMouseEnter={prefetch} onFocus={prefetch} className="hover:underline">{r.name}</Link>
          </h3>
          <span className="font-mono text-xs text-muted">{r.domain}</span>
        </div>
        <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
          <OfficialBadge r={r} />
          <LinkStatusBadge link={r.link} />
          <Chip>{humanize(r.resource_type)}</Chip>
          {r.level && <Chip>{r.level}</Chip>}
          {r.language && r.language !== 'en' && <Chip lang={r.language}>{r.language}</Chip>}
          {r.ai_assisted && <AIBadge variant="assisted" />}
        </div>
        <p className="mt-1.5 line-clamp-2 text-sm text-muted">{r.description}</p>
        <div className="mt-2 flex items-center gap-3 text-xs text-muted">
          <Count icon={ArrowBigUp} n={r.counts.votes} label="recommendations" />
          <Count icon={MessageSquare} n={r.counts.comments} label="comments" />
          <Count icon={Library} n={r.counts.collections} label="collections" />
        </div>
      </div>
      {url && (
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer nofollow ugc"
          className="inline-flex h-9 shrink-0 items-center gap-1.5 self-start rounded-[6px] border border-border bg-surface px-3 text-sm font-medium hover:bg-surface-2"
          aria-label={`Open ${r.name} on ${r.domain}`}
        >
          Open <ExternalLink size={13} aria-hidden />
        </a>
      )}
    </article>
  );
}
