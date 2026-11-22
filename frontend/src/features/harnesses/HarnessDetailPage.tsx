import { useState } from 'react';
import { Link, useParams } from 'react-router';
import { AlertTriangle, ExternalLink, GitFork, Scale, Star, Users } from 'lucide-react';
import { useHarness } from '@/lib/api/queries';
import { useConfig } from '@/hooks/useConfig';
import { PageHeader } from '@/components/layout/PageHeader';
import { AIBadge, Chip, FeaturedBadge, ToolChip } from '@/components/common/Badges';
import { MetaLine, TimeAgo, UserChip } from '@/components/common/Meta';
import { BookmarkButton, ShareButton, VoteButton } from '@/components/common/Actions';
import { MarkdownView } from '@/components/common/MarkdownView';
import { UrlTabs } from '@/components/common/UrlTabs';
import { DetailSkeleton } from '@/components/common/States';
import { DetailError, HiddenBanner, Section, SideCard, useCanonicalSlug } from '@/components/common/DetailHelpers';
import { CommentThread } from '@/components/feedback/CommentThread';
import { SuggestionList } from '@/components/feedback/SuggestionList';
import { ReviewList, RatingSummary } from '@/components/feedback/Reviews';
import { AskAIButton } from '@/features/ai/AskAIPanel';
import { AIFeedbackPanel } from '@/features/ai/AIFeedbackPanel';
import { MoreMenu } from '@/components/common/MoreMenu';
import { ReviewForm } from '@/components/feedback/ReviewForm';
import { CollabRequestDialog } from '@/features/collaborations/CollabRequestDialog';
import { Button } from '@/components/common/Button';
import { useAuthAction } from '@/hooks/useAuthAction';
import { Assembly } from '@/features/three';
import { LAYER_ORDER } from '@/features/three/HarnessAssembly';
import { COMPONENT_LABELS, MODULES, TOOL_LABELS } from '@/lib/modules';
import { compact, safeUrl } from '@/lib/format';
import type { HarnessDetail } from '@/lib/api/types';

function ComponentsTable({ h }: { h: HarnessDetail }) {
  const groups = LAYER_ORDER.map((t) => ({ t, items: h.components.filter((c) => c.type === t) })).filter((g) => g.items.length);
  return (
    <div className="overflow-x-auto rounded-[10px] border border-border">
      <table className="w-full text-sm">
        <caption className="sr-only">Harness components grouped by type</caption>
        <thead className="bg-surface-2 text-left text-xs text-muted">
          <tr><th scope="col" className="px-3 py-2 font-medium">Type</th><th scope="col" className="px-3 py-2 font-medium">Name</th><th scope="col" className="px-3 py-2 font-medium">What it does</th></tr>
        </thead>
        <tbody>
          {groups.flatMap((g) => g.items.map((c, i) => (
            <tr key={`${g.t}${i}`} className="border-t border-border bg-surface">
              <td className="px-3 py-2 whitespace-nowrap text-muted">{i === 0 ? COMPONENT_LABELS[g.t] : ''}</td>
              <td className="px-3 py-2 font-mono text-[13px]">{c.name}</td>
              <td className="px-3 py-2">{c.description}</td>
            </tr>
          )))}
        </tbody>
      </table>
    </div>
  );
}

function Overview({ h }: { h: HarnessDetail }) {
  return (
    <div className="max-w-[72ch]">
      <p className="text-[17px]">{h.short_description}</p>
      {h.repo.archived && (
        <p role="status" className="mt-4 flex items-center gap-2 rounded-[10px] border border-warning bg-warning-soft px-3 py-2 text-sm"><AlertTriangle size={15} className="text-warning" aria-hidden /> This repository is archived on GitHub.</p>
      )}
      <div className="mt-8 space-y-0">
        <Section title="How it works"><MarkdownView source={h.detailed_explanation.replace(/^\s*#{1,3}\s*how it works\s*\n+/i, '')} /></Section>
        {h.architecture && <Section title="Architecture"><MarkdownView source={h.architecture} /></Section>}
        {h.components.length > 0 && (
          <Section title={`Components (${h.components.length})`}>
            <div className="mb-4 h-[300px] rounded-[10px] border border-border bg-[color-mix(in_srgb,var(--harness)_3%,var(--surface))] sm:h-[340px]" role="img" aria-label={`Exploded view of ${h.components.length} components in ${new Set(h.components.map((c) => c.type)).size} layers. The table below lists them.`}>
              <Assembly components={h.components} />
            </div>
            <ComponentsTable h={h} />
          </Section>
        )}
        {h.setup_instructions && <Section title="Setup"><MarkdownView source={h.setup_instructions} /></Section>}
        {h.limitations && <Section title="Known limitations"><MarkdownView source={h.limitations} /></Section>}
      </div>
    </div>
  );
}

function ReviewsTab({ h }: { h: HarnessDetail }) {
  const [open, setOpen] = useState(false);
  const guard = useAuthAction();
  return (
    <>
      {!h.viewer.is_owner && (
        <div className="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-[10px] border border-border bg-surface p-4">
          <p className="text-sm">Tried this harness? Share what worked and what didn't.</p>
          <Button variant="primary" onClick={() => guard(() => setOpen(true))}>Write a testing report</Button>
        </div>
      )}
      <ReviewList harnessId={h.id} summary={h.rating_summary} />
      {open && <ReviewForm harnessId={h.id} open={open} onOpenChange={setOpen} />}
    </>
  );
}

function CollabButton({ h }: { h: HarnessDetail }) {
  const [open, setOpen] = useState(false);
  const guard = useAuthAction();
  return (
    <>
      <Button variant="primary" size="sm" className="mt-3 w-full" onClick={() => guard(() => setOpen(true))}>Request to collaborate</Button>
      {open && <CollabRequestDialog target="harness" id={h.id} title={h.name} open={open} onOpenChange={setOpen} />}
    </>
  );
}

export default function HarnessDetailPage() {
  const { id } = useParams();
  const { data: h, isLoading, error, refetch } = useHarness(id);
  const { data: config } = useConfig();
  useCanonicalSlug('/harnesses', h?.id, h?.slug);
  if (isLoading) return <DetailSkeleton />;
  if (error || !h) return <DetailError error={error} retry={() => refetch()} noun="harness" listPath="/harnesses" />;
  const repoUrl = safeUrl(h.repo.url);
  const kinds = (config?.enums.suggestion_kinds as Record<string, string[]> | undefined)?.harness ?? ['improvement', 'bug_report', 'component_recommendation'];

  return (
    <>
      <title>{`${h.name} · Harness Lab · DevCommons`}</title>
      <meta name="description" content={h.short_description} />
      <HiddenBanner status={h.status} />
      <PageHeader
        module="harness"
        crumbs={[{ to: '/harnesses', label: 'Harness Lab' }, { to: `/harnesses?category=${h.category.slug}`, label: h.category.name }]}
        title={h.name}
        badges={<>{h.ai_assisted && <AIBadge variant="assisted" />}{h.is_featured && <FeaturedBadge color={MODULES.harness.color} />}</>}
        meta={<MetaLine parts={[h.tools.map((t) => TOOL_LABELS[t] ?? t).join(', '), h.category.slug, <span key="a">by <UserChip user={h.author} size={16} className="text-xs" /></span>, <TimeAgo key="t" iso={h.updated_at} prefix="updated" />]} />}
        actions={<>
          <VoteButton t="harness" id={h.id} count={h.counts.votes} viewer={h.viewer} color={MODULES.harness.color} />
          <BookmarkButton t="harness" id={h.id} viewer={h.viewer} />
          <ShareButton title={h.name} />
          <AskAIButton context={{ type: 'harness', id: h.id, title: h.name }} />
          <MoreMenu targetType="harness" plural="harnesses" id={h.id} viewer={h.viewer} status={h.status} isFeatured={h.is_featured} editPath={`/harnesses/${h.id}/edit`} />
        </>}
      />
      <div className="mx-auto grid max-w-[1200px] gap-8 px-4 py-6 md:px-8 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0">
          <UrlTabs
            color={MODULES.harness.color}
            tabs={[
              { id: 'overview', label: 'Overview', content: <Overview h={h} /> },
              { id: 'reviews', label: <>Testing reports <span className="font-mono text-xs text-muted">{h.counts.reviews}</span></>, content: <ReviewsTab h={h} /> },
              { id: 'suggestions', label: <>Suggestions <span className="font-mono text-xs text-muted">{h.counts.suggestions}</span></>, content: <SuggestionList t="harness" id={h.id} kinds={kinds} isOwner={h.viewer.is_owner} /> },
              { id: 'discussion', label: <>Discussion <span className="font-mono text-xs text-muted">{h.counts.comments}</span></>, content: <CommentThread t="harness" id={h.id} /> },
            ]}
          />
        </div>
        <aside className="space-y-4">
          <SideCard className="stripe-harness">
            <p className="font-mono text-sm font-medium">{h.repo.owner}/{h.repo.name}</p>
            {h.repo.description && <p className="mt-1 text-sm text-muted">{h.repo.description}</p>}
            <dl className="mt-3 grid grid-cols-2 gap-2 font-mono text-xs">
              <div className="flex items-center gap-1.5"><Star size={13} aria-hidden /><dt className="sr-only">Stars</dt><dd>{compact(h.repo.stars)}</dd></div>
              <div className="flex items-center gap-1.5"><GitFork size={13} aria-hidden /><dt className="sr-only">Forks</dt><dd>{compact(h.repo.forks)}</dd></div>
              {h.repo.language && <div className="flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-harness" aria-hidden /><dt className="sr-only">Language</dt><dd>{h.repo.language}</dd></div>}
              {h.repo.license && <div className="flex items-center gap-1.5"><Scale size={13} aria-hidden /><dt className="sr-only">License</dt><dd>{h.repo.license}</dd></div>}
            </dl>
            {h.repo.pushed_at && <p className="mt-2 font-mono text-xs text-muted">last push <TimeAgo iso={h.repo.pushed_at} /></p>}
            {repoUrl && (
              <a href={repoUrl} target="_blank" rel="noopener noreferrer nofollow ugc" className="mt-3 inline-flex h-9 w-full items-center justify-center gap-1.5 rounded-[6px] border border-border text-sm font-medium hover:bg-surface-2">
                Open on GitHub <ExternalLink size={13} aria-hidden />
              </a>
            )}
          </SideCard>
          <RatingSummary r={h.rating_summary} />
          <SideCard title="Works with">
            <div className="flex flex-wrap gap-1.5">{h.tools.map((t) => <ToolChip key={t} tool={t} />)}</div>
            {h.tags.length > 0 && <div className="mt-3 flex flex-wrap gap-1.5">{h.tags.map((t) => <Chip key={t}>#{t}</Chip>)}</div>}
          </SideCard>
          <SideCard title="Contributor">
            <UserChip user={h.author} size={28} />
            {h.accepts_collaboration && !h.viewer.is_owner && (
              <>
                <p className="mt-3 flex items-center gap-1.5 text-sm text-muted"><Users size={14} aria-hidden /> Open to collaboration requests</p>
                <CollabButton h={h} />
              </>
            )}
            {h.viewer.is_owner && <Link to="/me/collaborations" className="mt-3 block text-sm underline">Manage collaboration requests</Link>}
          </SideCard>
          <AIFeedbackPanel type="harness" id={h.id} kinds={kinds} />
        </aside>
      </div>
    </>
  );
}
