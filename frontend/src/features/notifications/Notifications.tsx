import { Link, useNavigate, useSearchParams } from 'react-router';
import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query';
import * as Popover from '@radix-ui/react-popover';
import { Bell, Check, FileText, Flag, Lightbulb, Link2Off, MessageSquare, Reply, Users, type LucideIcon } from 'lucide-react';
import { apiFetch, getData } from '@/lib/api/client';
import type { NotificationItem, Paginated } from '@/lib/api/types';
import { qk } from '@/lib/queryKeys';
import { useAuth } from '@/features/auth/AuthProvider';
import { TimeAgo } from '@/components/common/Meta';
import { Button } from '@/components/common/Button';
import { EmptyState, ErrorState, Skeleton } from '@/components/common/States';
import { Pagination } from '@/components/common/Pagination';
import { cn } from '@/lib/cn';

const ICON: Record<string, LucideIcon> = {
  comment_on_content: MessageSquare, reply_to_comment: Reply, suggestion_on_content: Lightbulb, suggestion_status_changed: Lightbulb,
  review_on_harness: FileText, collab_request_received: Users, collab_request_accepted: Users, collab_request_declined: Users,
  content_moderated: Flag, resource_link_broken: Link2Off,
};
const VERB: Record<string, string> = {
  comment_on_content: 'commented on', reply_to_comment: 'replied to your comment on', suggestion_on_content: 'suggested an improvement on',
  suggestion_status_changed: 'updated your suggestion on', review_on_harness: 'posted a testing report on', collab_request_received: 'asked to collaborate on',
  collab_request_accepted: 'accepted your request on', collab_request_declined: 'declined your request on', content_moderated: 'A moderator acted on',
  resource_link_broken: 'A link looks broken on',
};

function Text({ n }: { n: NotificationItem }) {
  const who = n.data.actor_display_name ?? n.actor?.display_name;
  const others = (n.data.count ?? 1) > 1 ? ` and ${(n.data.count ?? 1) - 1} others` : '';
  const verb = VERB[n.type] ?? 'updated';
  const actorless = n.type === 'content_moderated' || n.type === 'resource_link_broken';
  return (
    <span>
      {!actorless && <><strong>{who ?? 'Someone'}</strong>{others} </>}{verb} <strong>{n.data.target_title ?? 'your post'}</strong>
      {n.data.snippet && <span className="mt-0.5 block truncate text-muted">“{n.data.snippet}”</span>}
    </span>
  );
}

function useMarkRead() {
  const qc = useQueryClient();
  return async (id?: string) => {
    await apiFetch(id ? `/api/notifications/${id}/read` : '/api/notifications/read-all', { method: 'POST' });
    void qc.invalidateQueries({ queryKey: ['notifications'] });
  };
}

function Row({ n, onOpen }: { n: NotificationItem; onOpen: (n: NotificationItem) => void }) {
  const Icon = ICON[n.type] ?? Bell;
  return (
    <li>
      <button type="button" onClick={() => onOpen(n)} className={cn('flex w-full cursor-pointer items-start gap-3 rounded-[6px] px-3 py-2.5 text-left text-sm hover:bg-surface-2', !n.read && 'bg-[color-mix(in_srgb,var(--focus)_6%,transparent)]')}>
        <Icon size={16} className="mt-0.5 shrink-0 text-muted" aria-hidden />
        <span className="min-w-0 flex-1"><Text n={n} /><span className="mt-0.5 block font-mono text-xs text-muted"><TimeAgo iso={n.created_at} /></span></span>
        {!n.read && <span className="mt-1.5 size-2 shrink-0 rounded-full bg-focus" aria-label="Unread" />}
      </button>
    </li>
  );
}

export function NotificationBell() {
  const { status } = useAuth();
  const navigate = useNavigate();
  const markRead = useMarkRead();
  const { data: unread } = useQuery({
    queryKey: qk.unreadCount,
    queryFn: () => getData<{ count: number }>('/api/notifications/unread-count'),
    enabled: status === 'signed_in',
    refetchInterval: () => (document.visibilityState === 'visible' ? 60_000 : false),
  });
  const { data, refetch } = useQuery({
    queryKey: ['notifications', 'list', { popover: true }],
    queryFn: () => apiFetch<Paginated<NotificationItem>>('/api/notifications', { query: { page_size: 10 } }),
    enabled: false,
  });
  const n = unread?.count ?? 0;
  const open = async (item: NotificationItem) => {
    if (!item.read) await markRead(item.id);
    if (item.data.url_path?.startsWith('/')) navigate(item.data.url_path);
  };
  return (
    <Popover.Root onOpenChange={(o) => o && void refetch()}>
      <Popover.Trigger className="relative grid size-9 cursor-pointer place-items-center rounded-[6px] hover:bg-surface-2" aria-label={`Notifications${n ? `, ${n} unread` : ''}`}>
        <Bell size={17} aria-hidden />
        {n > 0 && <span className="absolute top-1 right-0.5 min-w-4 rounded-full bg-danger px-1 text-center font-mono text-[10px] leading-4 text-bg">{n > 9 ? '9+' : n}</span>}
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content align="end" sideOffset={8} className="z-50 w-[min(94vw,380px)] rounded-[14px] border border-border bg-surface shadow-[var(--shadow-dialog)]">
          <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
            <p className="text-sm font-semibold">Notifications</p>
            {n > 0 && <button type="button" onClick={() => markRead()} className="inline-flex cursor-pointer items-center gap-1 text-xs text-muted hover:text-text"><Check size={13} aria-hidden /> Mark all as read</button>}
          </div>
          <ul className="max-h-[60vh] overflow-y-auto p-1.5">
            {!data ? <li className="p-3"><Skeleton className="h-10" /></li> : data.data.length === 0 ? <li className="px-3 py-6 text-center text-sm text-muted">You're all caught up.</li> : data.data.map((x) => <Row key={x.id} n={x} onOpen={open} />)}
          </ul>
          <Popover.Close asChild><Link to="/notifications" className="block border-t border-border px-4 py-2.5 text-center text-sm font-medium hover:bg-surface-2">See all</Link></Popover.Close>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

export function NotificationsPage() {
  const [sp, setSp] = useSearchParams();
  const unreadOnly = sp.get('filter') === 'unread';
  const page = Number(sp.get('page') ?? 1);
  const navigate = useNavigate();
  const markRead = useMarkRead();
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['notifications', 'list', { unreadOnly, page }],
    queryFn: () => apiFetch<Paginated<NotificationItem>>('/api/notifications', { query: { unread_only: unreadOnly, page } }),
    placeholderData: keepPreviousData,
  });
  return (
    <div className="mx-auto max-w-[760px] px-4 py-8 md:px-8">
      <title>Notifications · DevCommons</title>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="text-[28px]">Notifications</h1>
        <Button size="sm" onClick={() => markRead()}><Check size={14} aria-hidden /> Mark all as read</Button>
      </div>
      <div className="mt-5 flex gap-1" role="group" aria-label="Filter">
        {[['all', 'All'], ['unread', 'Unread']].map(([v, l]) => (
          <button key={v} type="button" aria-pressed={(v === 'unread') === unreadOnly} onClick={() => setSp(v === 'unread' ? { filter: 'unread' } : {})} className={cn('h-8 cursor-pointer rounded-full border px-3 text-sm', (v === 'unread') === unreadOnly ? 'border-text bg-text text-bg' : 'border-border')}>{l}</button>
        ))}
      </div>
      <div className="mt-4" id="list-top">
        {isLoading ? <Skeleton className="h-40" /> : error ? <ErrorState error={error} onRetry={() => refetch()} />
          : !data?.data.length ? <EmptyState icon={Bell} title={unreadOnly ? "You're all caught up." : 'No notifications yet.'}>Comments, suggestions and collaboration requests on your posts show up here.</EmptyState>
          : <ul className="rounded-[10px] border border-border bg-surface p-1.5">{data.data.map((x) => <Row key={x.id} n={x} onOpen={async (item) => { if (!item.read) await markRead(item.id); if (item.data.url_path?.startsWith('/')) navigate(item.data.url_path); }} />)}</ul>}
        {data && <Pagination meta={data.meta} onPage={(p) => setSp({ ...(unreadOnly ? { filter: 'unread' } : {}), page: String(p) })} />}
      </div>
    </div>
  );
}
