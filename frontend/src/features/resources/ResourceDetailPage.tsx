import { useState } from 'react';
import { Link, useParams } from 'react-router';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { ExternalLink, HeartPulse, Library } from 'lucide-react';
import { useResource } from '@/lib/api/queries';
import { useConfig } from '@/hooks/useConfig';
import { PageHeader } from '@/components/layout/PageHeader';
import { AIBadge, Chip, LinkStatusBadge, OfficialBadge } from '@/components/common/Badges';
import { MetaLine, TimeAgo, UserChip } from '@/components/common/Meta';
import { BookmarkButton, ShareButton, VoteButton } from '@/components/common/Actions';
import { UrlTabs } from '@/components/common/UrlTabs';
import { DetailSkeleton } from '@/components/common/States';
import { DetailError, HiddenBanner, SideCard } from '@/components/common/DetailHelpers';
import { CommentThread } from '@/components/feedback/CommentThread';
import { SuggestionList } from '@/components/feedback/SuggestionList';
import { AskAIButton } from '@/features/ai/AskAIPanel';
import { MoreMenu } from '@/components/common/MoreMenu';
import { ReportDialog } from '@/components/common/ReportDialog';
import { AddToCollection } from '@/features/collections/AddToCollection';
import { Button } from '@/components/common/Button';
import { useAuthAction } from '@/hooks/useAuthAction';
import { apiFetch, ApiError } from '@/lib/api/client';
import type { ResourceDetail } from '@/lib/api/types';
import { MODULES } from '@/lib/modules';
import { humanize, safeUrl } from '@/lib/format';

function LinkActions({ r }: { r: ResourceDetail }) {
  const [report, setReport] = useState(false);
  const [busy, setBusy] = useState(false);
  const guard = useAuthAction();
  const qc = useQueryClient();
  return (
    <div className="mt-3 flex flex-wrap gap-2">
      <Button size="sm" onClick={() => guard(() => setReport(true), { requireVerified: false })}>Report broken or outdated</Button>
      {(r.viewer.is_owner || r.viewer.can_moderate) && (
        <Button size="sm" disabled={busy} onClick={async () => {
          setBusy(true);
          try { await apiFetch(`/api/resources/${r.id}/recheck`, { method: 'POST' }); toast.success('Link re-checked'); void qc.invalidateQueries({ queryKey: ['resources', 'detail', r.id] }); }
          catch (e) { toast.error(e instanceof ApiError ? (e.code === 'rate_limited' ? 'You can re-check once every 10 minutes.' : e.message) : 'Re-check failed.'); }
          finally { setBusy(false); }
        }}>{busy ? 'Checking…' : 'Re-check now'}</Button>
      )}
      {report && <ReportDialog targetType="resource" targetId={r.id} open={report} onOpenChange={setReport} preselect="broken_link" />}
    </div>
  );
}

export default function ResourceDetailPage() {
  const { id } = useParams();
  const { data: r, isLoading, error, refetch } = useResource(id);
  const { data: config } = useConfig();
  if (isLoading) return <DetailSkeleton />;
  if (error || !r) return <DetailError error={error} retry={() => refetch()} noun="resource" listPath="/resources" />;
  const url = safeUrl(r.url);
  const kinds = (config?.enums.suggestion_kinds as Record<string, string[]> | undefined)?.resource ?? ['alternative_resource', 'correction'];
  return (
    <>
      <title>{`${r.name} · Knowledge Hub · DevCommons`}</title>
      <HiddenBanner status={r.status} />
      <PageHeader
        module="knowledge"
        crumbs={[{ to: '/resources', label: 'Knowledge Hub' }, { to: `/resources?category=${r.category.slug}`, label: r.category.name }]}
        title={r.name}
        badges={<><OfficialBadge r={r} />{r.ai_assisted && <AIBadge variant="assisted" />}</>}
        meta={<MetaLine parts={[r.domain, humanize(r.resource_type), r.level, r.language]} />}
        actions={<>
          {url && (
            <a href={url} target="_blank" rel="noopener noreferrer nofollow ugc" className="inline-flex h-9 items-center gap-1.5 rounded-[6px] bg-text px-3.5 text-sm font-medium text-bg" aria-label={`Open resource on ${r.domain}`}>
              Open resource <ExternalLink size={14} aria-hidden />
            </a>
          )}
          <VoteButton t="resource" id={r.id} count={r.counts.votes} viewer={r.viewer} color={MODULES.knowledge.color} label="Recommend" />
          <BookmarkButton t="resource" id={r.id} viewer={r.viewer} />
          <AddToCollection resourceId={r.id} />
          <ShareButton title={r.name} />
          <AskAIButton context={{ type: 'resource', id: r.id, title: r.name }} />
          <MoreMenu targetType="resource" plural="resources" id={r.id} viewer={r.viewer} status={r.status} isFeatured={r.is_featured} editPath={`/resources/${r.id}/edit`} />
        </>}
      />
      <div className="mx-auto grid max-w-[1200px] gap-8 px-4 py-6 md:px-8 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0 max-w-[72ch]">
          <p className="text-[17px]">{r.description}</p>
          <div className="mt-3 flex flex-wrap gap-1.5">{r.tags.map((t) => <Chip key={t}>#{t}</Chip>)}</div>
          <p className="mt-4 text-sm text-muted">Shared by <UserChip user={r.submitter} size={18} /> · <TimeAgo iso={r.created_at} /></p>
          <div className="mt-10">
            <UrlTabs
              color={MODULES.knowledge.color}
              tabs={[
                { id: 'used', label: <>How people used it <span className="font-mono text-xs text-muted">{r.counts.comments}</span></>, content: <CommentThread t="resource" id={r.id} placeholder="How did this resource help you?" /> },
                { id: 'alternatives', label: <>Alternatives and corrections <span className="font-mono text-xs text-muted">{r.counts.suggestions}</span></>, content: <SuggestionList t="resource" id={r.id} kinds={kinds} isOwner={r.viewer.is_owner} /> },
              ]}
            />
          </div>
        </div>
        <aside className="space-y-4">
          <SideCard className="stripe-knowledge">
            <p className="mb-3 flex items-center gap-1.5 text-sm font-semibold"><HeartPulse size={15} aria-hidden /> Link health</p>
            <LinkStatusBadge link={r.link} />
            <dl className="mt-3 space-y-1.5 font-mono text-xs">
              <div className="flex justify-between gap-2"><dt className="text-muted">HTTP status</dt><dd>{r.link.http_status ?? '–'}</dd></div>
              <div className="flex justify-between gap-2"><dt className="text-muted">Last checked</dt><dd>{r.link.last_checked_at ? <TimeAgo iso={r.link.last_checked_at} /> : 'not yet'}</dd></div>
              {r.link.final_url && <div className="flex justify-between gap-2"><dt className="text-muted">Redirects to</dt><dd className="truncate">{r.link.final_url}</dd></div>}
              <div className="flex justify-between gap-2"><dt className="text-muted">Open reports</dt><dd>{r.link.open_reports}</dd></div>
            </dl>
            <p className="mt-3 text-xs text-muted">A working link doesn't guarantee the content is accurate or current.</p>
            <LinkActions r={r} />
          </SideCard>
          {!!r.collections_preview?.length && (
            <SideCard title="In collections">
              <ul className="space-y-1.5">
                {r.collections_preview.map((c) => (
                  <li key={c.id}><Link to={`/collections/${c.id}/${c.slug}`} className="inline-flex items-center gap-1.5 text-sm hover:underline"><Library size={14} className="text-knowledge" aria-hidden /> {c.title}</Link></li>
                ))}
              </ul>
            </SideCard>
          )}
        </aside>
      </div>
    </>
  );
}
