import { useState } from 'react';
import { Link, useParams } from 'react-router';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { CheckSquare, ExternalLink, Users } from 'lucide-react';
import { useIdea } from '@/lib/api/queries';
import { useConfig } from '@/hooks/useConfig';
import { PageHeader } from '@/components/layout/PageHeader';
import { AIBadge, Chip, CollabBadge, FeaturedBadge } from '@/components/common/Badges';
import { MetaLine, TimeAgo, UserChip } from '@/components/common/Meta';
import { BookmarkButton, InterestButton, ShareButton, VoteButton } from '@/components/common/Actions';
import { MarkdownView } from '@/components/common/MarkdownView';
import { UrlTabs } from '@/components/common/UrlTabs';
import { DetailSkeleton } from '@/components/common/States';
import { DetailError, HiddenBanner, Section, SideCard, useCanonicalSlug } from '@/components/common/DetailHelpers';
import { CommentThread } from '@/components/feedback/CommentThread';
import { SuggestionList } from '@/components/feedback/SuggestionList';
import { AskAIButton } from '@/features/ai/AskAIPanel';
import { AIFeedbackPanel } from '@/features/ai/AIFeedbackPanel';
import { MoreMenu } from '@/components/common/MoreMenu';
import { CollabRequestDialog } from '@/features/collaborations/CollabRequestDialog';
import { Button } from '@/components/common/Button';
import { useAuthAction } from '@/hooks/useAuthAction';
import { apiFetch, ApiError } from '@/lib/api/client';
import type { CollaborationStatus, IdeaDetail } from '@/lib/api/types';
import { MODULES } from '@/lib/modules';
import { safeUrl } from '@/lib/format';

function CollabActions({ i }: { i: IdeaDetail }) {
  const [open, setOpen] = useState(false);
  const guard = useAuthAction();
  const qc = useQueryClient();
  const req = i.collaboration.viewer_request;
  const refresh = () => qc.invalidateQueries({ queryKey: ['ideas'] });
  if (i.viewer.is_owner)
    return (
      <div className="mt-3 space-y-2">
        <label className="block text-xs font-medium text-muted" htmlFor="collab-status">Status</label>
        <select
          id="collab-status"
          value={i.collaboration_status}
          onChange={async (e) => {
            try { await apiFetch(`/api/ideas/${i.id}`, { method: 'PATCH', body: { collaboration_status: e.target.value as CollaborationStatus } }); toast.success('Status updated'); void refresh(); }
            catch (err) { toast.error(err instanceof ApiError ? err.message : 'Could not update.'); }
          }}
          className="h-9 w-full rounded-[6px] border border-border bg-surface px-2 text-sm"
        >
          <option value="sharing">Just sharing</option><option value="seeking_collaborators">Looking for collaborators</option><option value="team_formed">Team formed</option>
        </select>
        <Link to={`/ideas/${i.id}/requests`} className="block text-sm font-medium underline">Manage requests</Link>
      </div>
    );
  if (req)
    return (
      <div className="mt-3 rounded-[6px] bg-surface-2 px-3 py-2 text-sm">
        {req.status === 'pending' ? (
          <div className="flex items-center justify-between gap-2">Request pending
            <Button size="sm" onClick={async () => { await apiFetch(`/api/collaborations/${req.id}/withdraw`, { method: 'POST' }); toast('Request withdrawn'); void refresh(); }}>Withdraw</Button>
          </div>
        ) : req.status === 'accepted' ? <>Accepted · <Link to="/me/collaborations?role=sent" className="underline">View details</Link></> : <span className="capitalize">Your request: {req.status}</span>}
      </div>
    );
  if (i.collaboration.status !== 'seeking_collaborators') return null;
  return (
    <>
      <Button variant="primary" size="sm" className="mt-3 w-full" onClick={() => guard(() => setOpen(true))}>Request to collaborate</Button>
      <p className="mt-2 text-xs text-muted">Your contact details stay private unless you choose to share them.</p>
      {open && <CollabRequestDialog target="idea" id={i.id} title={i.title} open={open} onOpenChange={setOpen} />}
    </>
  );
}

export default function IdeaDetailPage() {
  const { id } = useParams();
  const { data: i, isLoading, error, refetch } = useIdea(id);
  const { data: config } = useConfig();
  useCanonicalSlug('/ideas', i?.id, i?.slug);
  if (isLoading) return <DetailSkeleton />;
  if (error || !i) return <DetailError error={error} retry={() => refetch()} noun="idea" listPath="/ideas" />;
  const kinds = (config?.enums.suggestion_kinds as Record<string, string[]> | undefined)?.idea ?? ['feature', 'tech_stack', 'architecture'];
  const gh = safeUrl(i.github_url);

  return (
    <>
      <title>{`${i.title} · Project Ideas · DevCommons`}</title>
      <HiddenBanner status={i.status} />
      <PageHeader
        module="idea"
        crumbs={[{ to: '/ideas', label: 'Project Ideas' }, { to: `/ideas?category=${i.category.slug}`, label: i.category.name }]}
        title={i.title}
        badges={<><CollabBadge status={i.collaboration_status} />{i.ai_assisted && <AIBadge variant="assisted" />}{i.is_featured && <FeaturedBadge color={MODULES.idea.color} />}</>}
        meta={<MetaLine parts={[i.category.slug, <span key="a">by <UserChip user={i.author} size={16} className="text-xs" /></span>, <TimeAgo key="t" iso={i.created_at} />]} />}
        actions={<>
          <VoteButton t="idea" id={i.id} count={i.counts.votes} viewer={i.viewer} color={MODULES.idea.color} />
          <InterestButton id={i.id} count={i.counts.interest} viewer={i.viewer} />
          <BookmarkButton t="idea" id={i.id} viewer={i.viewer} />
          <ShareButton title={i.title} />
          <AskAIButton context={{ type: 'idea', id: i.id, title: i.title }} />
          <MoreMenu targetType="idea" plural="ideas" id={i.id} viewer={i.viewer} status={i.status} isFeatured={i.is_featured} editPath={`/ideas/${i.id}/edit`} />
        </>}
      />
      <div className="mx-auto grid max-w-[1200px] gap-8 px-4 py-6 md:px-8 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0 max-w-[72ch]">
          <Section title="Problem"><p className="text-[17px]">{i.problem_statement}</p></Section>
          <Section title="Proposed solution"><MarkdownView source={i.proposed_solution} /></Section>
          {i.description && <Section title="Details"><MarkdownView source={i.description} /></Section>}
          {i.expected_features.length > 0 && (
            <Section title="Expected features">
              <ul className="space-y-2">
                {i.expected_features.map((f, k) => (
                  <li key={k} className="flex gap-2.5">
                    <CheckSquare size={17} className="mt-0.5 shrink-0 text-idea" aria-hidden />
                    <span><span className="font-medium">{f.title}</span>{f.detail && <span className="text-muted"> — {f.detail}</span>}</span>
                  </li>
                ))}
              </ul>
            </Section>
          )}
          <div className="mt-10">
            <UrlTabs
              color={MODULES.idea.color}
              tabs={[
                { id: 'suggestions', label: <>Suggestions <span className="font-mono text-xs text-muted">{i.counts.suggestions}</span></>, content: <SuggestionList t="idea" id={i.id} kinds={kinds} isOwner={i.viewer.is_owner} /> },
                { id: 'discussion', label: <>Discussion <span className="font-mono text-xs text-muted">{i.counts.comments}</span></>, content: <CommentThread t="idea" id={i.id} /> },
              ]}
            />
          </div>
        </div>
        <aside className="space-y-4">
          <SideCard className="stripe-idea" title="Collaboration">
            <CollabBadge status={i.collaboration.status} />
            {i.collaboration.status === 'sharing' && <p className="text-sm text-muted">Shared for feedback. The author isn't recruiting.</p>}
            <p className="mt-2 flex items-center gap-1.5 text-sm"><Users size={14} aria-hidden /> <span className="font-mono">{i.collaboration.collaborator_count}</span> collaborators</p>
            <CollabActions i={i} />
          </SideCard>
          <AIFeedbackPanel type="idea" id={i.id} kinds={kinds} />
          {i.tech_stack.length > 0 && (
            <SideCard title="Suggested tech stack"><div className="flex flex-wrap gap-1.5">{i.tech_stack.map((t) => <Chip key={t}>{t}</Chip>)}</div></SideCard>
          )}
          {gh && (
            <SideCard title="Repository">
              <a href={gh} target="_blank" rel="noopener noreferrer nofollow ugc" className="inline-flex items-center gap-1.5 font-mono text-sm underline">{gh.replace('https://github.com/', '')} <ExternalLink size={12} aria-hidden /></a>
            </SideCard>
          )}
        </aside>
      </div>
    </>
  );
}
