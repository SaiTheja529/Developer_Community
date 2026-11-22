import { useParams } from 'react-router';
import { Quote } from 'lucide-react';
import { useCollection } from '@/lib/api/queries';
import { PageHeader } from '@/components/layout/PageHeader';
import { AIBadge, PrivateBadge } from '@/components/common/Badges';
import { MetaLine, UserChip } from '@/components/common/Meta';
import { BookmarkButton, ShareButton, VoteButton } from '@/components/common/Actions';
import { ResourceRow } from '@/components/common/Cards';
import { UrlTabs } from '@/components/common/UrlTabs';
import { DetailSkeleton, EmptyState } from '@/components/common/States';
import { DetailError, HiddenBanner, useCanonicalSlug } from '@/components/common/DetailHelpers';
import { CommentThread } from '@/components/feedback/CommentThread';
import { AskAIButton } from '@/features/ai/AskAIPanel';
import { MoreMenu } from '@/components/common/MoreMenu';
import { MODULES } from '@/lib/modules';

export default function CollectionDetailPage() {
  const { id } = useParams();
  const { data: c, isLoading, error, refetch } = useCollection(id);
  useCanonicalSlug('/collections', c?.id, c?.slug);
  if (isLoading) return <DetailSkeleton />;
  if (error || !c) return <DetailError error={error} retry={() => refetch()} noun="collection" listPath="/collections" />;
  const items = [...c.items].sort((a, b) => a.position - b.position);
  return (
    <>
      <title>{`${c.title} · Collections · DevCommons`}</title>
      <HiddenBanner status={c.status} />
      {c.visibility === 'private' && <p role="status" className="border-b border-border bg-surface-2 px-4 py-2 text-sm md:px-8">Only you can see this collection.</p>}
      <PageHeader
        module="knowledge"
        crumbs={[{ to: '/collections', label: 'Collections' }]}
        title={c.title}
        badges={<>{c.visibility === 'private' && <PrivateBadge />}{c.ai_assisted && <AIBadge variant="assisted" />}</>}
        meta={<MetaLine parts={[`${c.counts.items} resources`, c.category.slug, <span key="o">curated by <UserChip user={c.owner} size={16} className="text-xs" /></span>]} />}
        actions={<>
          <VoteButton t="collection" id={c.id} count={c.counts.votes} viewer={c.viewer} color={MODULES.knowledge.color} />
          <BookmarkButton t="collection" id={c.id} viewer={c.viewer} />
          <ShareButton title={c.title} />
          <AskAIButton context={{ type: 'collection', id: c.id, title: c.title }} />
          <MoreMenu targetType="collection" plural="collections" id={c.id} viewer={c.viewer} status={c.status} isFeatured={c.is_featured} editPath={`/collections/${c.id}/edit`} />
        </>}
      />
      <div className="mx-auto max-w-[900px] px-4 py-6 md:px-8">
        {c.description && <p className="max-w-[72ch] text-[17px]">{c.description}</p>}
        <div className="mt-8">
          <UrlTabs
            color={MODULES.knowledge.color}
            tabs={[
              {
                id: 'items', label: <>Resources <span className="font-mono text-xs text-muted">{items.length}</span></>,
                content: items.length ? (
                  <ol className="rounded-[10px] border border-border bg-surface px-4">
                    {items.map((it, k) => (
                      <li key={it.resource_id ?? k}>
                        {it.unavailable || !it.resource ? (
                          <p className="flex gap-4 border-b border-border py-4 text-sm text-muted last:border-0"><span className="w-6 text-right font-mono">{k + 1}</span> This resource is no longer available.</p>
                        ) : (
                          <>
                            <ResourceRow r={it.resource} index={k + 1} />
                            {it.note && (
                              <blockquote className="-mt-2 mb-4 ml-10 flex gap-2 border-l-2 border-knowledge pl-3 text-sm text-muted">
                                <Quote size={13} className="mt-1 shrink-0" aria-hidden /> {it.note}
                              </blockquote>
                            )}
                          </>
                        )}
                      </li>
                    ))}
                  </ol>
                ) : <EmptyState title="This collection is empty." />,
              },
              { id: 'discussion', label: <>Discussion <span className="font-mono text-xs text-muted">{c.counts.comments}</span></>, content: <CommentThread t="collection" id={c.id} /> },
            ]}
          />
        </div>
      </div>
    </>
  );
}
