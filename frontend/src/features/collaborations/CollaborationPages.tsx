import { useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router';
import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query';
import * as Dialog from '@radix-ui/react-dialog';
import { toast } from 'sonner';
import { Mail, Users } from 'lucide-react';
import { apiFetch, ApiError } from '@/lib/api/client';
import type { Collaboration, Paginated } from '@/lib/api/types';
import { useIdea } from '@/lib/api/queries';
import { Badge, Chip } from '@/components/common/Badges';
import { TimeAgo, UserChip } from '@/components/common/Meta';
import { Button } from '@/components/common/Button';
import { EmptyState, ErrorState, Skeleton } from '@/components/common/States';
import { Pagination } from '@/components/common/Pagination';
import { inputClass } from '@/components/forms/Field';
import { safeUrl } from '@/lib/format';
import { cn } from '@/lib/cn';

const STATUS_STYLE: Record<string, string> = {
  pending: 'bg-warning-soft text-warning', accepted: 'bg-success-soft text-success', declined: 'border border-border text-muted', withdrawn: 'border border-border text-muted',
};

function RespondDialog({ c, mode, onClose }: { c: Collaboration; mode: 'accept' | 'decline'; onClose: () => void }) {
  const qc = useQueryClient();
  const [message, setMessage] = useState('');
  const [share, setShare] = useState(false);
  const [busy, setBusy] = useState(false);
  return (
    <Dialog.Root open onOpenChange={(o) => !o && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/30" />
        <Dialog.Content className="fixed top-1/2 left-1/2 z-50 w-[min(94vw,460px)] -translate-x-1/2 -translate-y-1/2 rounded-[14px] border border-border bg-surface p-6 shadow-[var(--shadow-dialog)]">
          <Dialog.Title className="text-lg font-semibold">{mode === 'accept' ? 'Accept request' : 'Decline request'}</Dialog.Title>
          <Dialog.Description className="mt-1 text-sm text-muted">From {c.requester?.display_name ?? 'a deleted user'}. They'll be notified.</Dialog.Description>
          <label htmlFor="resp-msg" className="mt-4 block text-sm font-medium">Message (optional)</label>
          <textarea id="resp-msg" rows={3} maxLength={1000} value={message} onChange={(e) => setMessage(e.target.value)} className={cn(inputClass, 'mt-1 py-2 text-sm')} />
          {mode === 'accept' && (
            <label className="mt-3 flex cursor-pointer items-start gap-2.5 text-sm">
              <input type="checkbox" checked={share} onChange={(e) => setShare(e.target.checked)} className="mt-0.5 size-4" /> Share my email and contact links with this person
            </label>
          )}
          <div className="mt-5 flex justify-end gap-2">
            <Dialog.Close asChild><Button>Cancel</Button></Dialog.Close>
            <Button
              variant={mode === 'accept' ? 'primary' : 'danger'}
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  await apiFetch(`/api/collaborations/${c.id}/${mode}`, { method: 'POST', body: mode === 'accept' ? { message: message.trim() || null, share_contact: share } : { message: message.trim() || null } });
                  toast.success(mode === 'accept' ? 'Request accepted' : 'Request declined');
                  void qc.invalidateQueries({ queryKey: ['collaborations'] });
                  void qc.invalidateQueries({ queryKey: ['ideas'] });
                  onClose();
                } catch (e) {
                  toast.error(e instanceof ApiError ? e.message : 'Could not respond.');
                } finally {
                  setBusy(false);
                }
              }}
            >
              {busy ? 'Working…' : mode === 'accept' ? 'Accept' : 'Decline'}
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

export function CollabCard({ c, role, showTarget = true }: { c: Collaboration; role: 'owner' | 'requester'; showTarget?: boolean }) {
  const qc = useQueryClient();
  const [respond, setRespond] = useState<null | 'accept' | 'decline'>(null);
  const other = role === 'owner' ? c.requester : c.owner;
  return (
    <li className="rounded-[10px] border border-border bg-surface p-4">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <UserChip user={other} />
        <Badge className={cn('capitalize', STATUS_STYLE[c.status])}>{c.status}</Badge>
        <span className="ml-auto font-mono text-xs text-muted"><TimeAgo iso={c.created_at} /></span>
      </div>
      {showTarget && <p className="mt-2 text-sm">On <Link to={c.target.url_path} className="font-medium underline">{c.target.title}</Link></p>}
      <p className="mt-2 text-[15px] whitespace-pre-wrap">{c.message}</p>
      {c.skills.length > 0 && <div className="mt-2 flex flex-wrap gap-1.5">{c.skills.map((s) => <Chip key={s}>{s}</Chip>)}</div>}
      {c.response_message && <blockquote className="mt-3 border-l-2 border-border pl-3 text-sm text-muted">{c.response_message}</blockquote>}
      {c.status === 'accepted' && (
        <div className="mt-3 rounded-[6px] bg-surface-2 p-3 text-sm">
          {c.counterpart_contact ? (
            <>
              <p className="flex items-center gap-1.5 font-medium"><Mail size={14} aria-hidden /> <a href={`mailto:${c.counterpart_contact.email}`} className="underline">{c.counterpart_contact.email}</a></p>
              {c.counterpart_contact.links.map((l) => safeUrl(l.url) && <a key={l.url} href={safeUrl(l.url)!} target="_blank" rel="noopener noreferrer nofollow" className="mr-3 underline">{l.label}</a>)}
            </>
          ) : (
            <p className="text-muted">They chose not to share contact details. You can reply via comments on the {c.target.type}.</p>
          )}
        </div>
      )}
      {c.status === 'pending' && (
        <div className="mt-3 flex gap-2">
          {role === 'owner' ? (
            <>
              <Button variant="primary" size="sm" onClick={() => setRespond('accept')}>Accept</Button>
              <Button size="sm" onClick={() => setRespond('decline')}>Decline</Button>
            </>
          ) : (
            <Button size="sm" onClick={async () => { await apiFetch(`/api/collaborations/${c.id}/withdraw`, { method: 'POST' }); toast('Request withdrawn'); void qc.invalidateQueries({ queryKey: ['collaborations'] }); void qc.invalidateQueries({ queryKey: ['ideas'] }); }}>Withdraw</Button>
          )}
        </div>
      )}
      {respond && <RespondDialog c={c} mode={respond} onClose={() => setRespond(null)} />}
    </li>
  );
}

function Tabs({ value, onChange, options }: { value: string; onChange: (v: string) => void; options: [string, string][] }) {
  return (
    <div className="flex gap-1 border-b border-border" role="tablist">
      {options.map(([v, l]) => (
        <button key={v} role="tab" aria-selected={value === v} onClick={() => onChange(v)} className={cn('-mb-px h-10 cursor-pointer border-b-2 px-3 text-sm font-medium', value === v ? 'border-idea text-text' : 'border-transparent text-muted hover:text-text')}>{l}</button>
      ))}
    </div>
  );
}

export function CollaborationsPage() {
  const [sp, setSp] = useSearchParams();
  const role = sp.get('role') === 'sent' ? 'sent' : 'received';
  const status = sp.get('status') ?? '';
  const page = Number(sp.get('page') ?? 1);
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['collaborations', role, status, page],
    queryFn: () => apiFetch<Paginated<Collaboration>>('/api/collaborations', { query: { role, status, page } }),
    placeholderData: keepPreviousData,
  });
  return (
    <div className="mx-auto max-w-[860px] px-4 py-8 md:px-8">
      <title>Collaborations · DevCommons</title>
      <h1 className="flex items-center gap-2 text-[28px]"><Users size={24} className="text-idea" aria-hidden /> Collaborations</h1>
      <div className="mt-6 flex flex-wrap items-end justify-between gap-3">
        <Tabs value={role} onChange={(v) => setSp({ role: v })} options={[['received', 'Received'], ['sent', 'Sent']]} />
        <select aria-label="Status" value={status} onChange={(e) => setSp({ role, ...(e.target.value ? { status: e.target.value } : {}) })} className={cn(inputClass, 'h-9 w-40 text-sm')}>
          <option value="">All statuses</option><option value="pending">Pending</option><option value="accepted">Accepted</option><option value="declined">Declined</option><option value="withdrawn">Withdrawn</option>
        </select>
      </div>
      <div className="mt-5" id="list-top">
        {isLoading ? <Skeleton className="h-32" /> : error ? <ErrorState error={error} onRetry={() => refetch()} />
          : !data?.data.length ? <EmptyState icon={Users} title={role === 'received' ? 'No requests yet.' : "You haven't sent any requests."}>{role === 'sent' && <>Find an idea <Link to="/ideas?collaboration_status=seeking_collaborators" className="underline">looking for collaborators</Link>.</>}</EmptyState>
          : <ul className="space-y-3">{data.data.map((c) => <CollabCard key={c.id} c={c} role={role === 'received' ? 'owner' : 'requester'} />)}</ul>}
        {data && <Pagination meta={data.meta} onPage={(p) => setSp({ role, ...(status ? { status } : {}), page: String(p) })} />}
      </div>
    </div>
  );
}

export function IdeaRequestsPage() {
  const { id = '' } = useParams();
  const [status, setStatus] = useState('pending');
  const idea = useIdea(id);
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['collaborations', 'idea', id, status],
    queryFn: () => apiFetch<Paginated<Collaboration>>(`/api/ideas/${id}/collaboration-requests`, { query: { status } }),
  });
  if (idea.data && !idea.data.viewer.is_owner) return <div className="px-4 py-20 text-center"><h1 className="text-2xl">Only the idea's owner can see its requests.</h1></div>;
  return (
    <div className="mx-auto max-w-[860px] px-4 py-8 md:px-8">
      <title>Collaboration requests · DevCommons</title>
      {idea.data && <Link to={`/ideas/${id}/${idea.data.slug}`} className="text-sm text-muted hover:underline">{idea.data.title}</Link>}
      <h1 className="mt-1 text-[28px]">Collaboration requests</h1>
      <div className="mt-6"><Tabs value={status} onChange={setStatus} options={[['pending', 'Pending'], ['accepted', 'Accepted'], ['declined', 'Declined']]} /></div>
      <div className="mt-5">
        {isLoading ? <Skeleton className="h-32" /> : error ? <ErrorState error={error} onRetry={() => refetch()} />
          : !data?.data.length ? <EmptyState icon={Users} title={`No ${status} requests.`} />
          : <ul className="space-y-3">{data.data.map((c) => <CollabCard key={c.id} c={c} role="owner" showTarget={false} />)}</ul>}
      </div>
    </div>
  );
}
