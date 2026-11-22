import { useState } from 'react';
import { Link, NavLink, Outlet, useSearchParams } from 'react-router';
import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { ExternalLink, Shield, Trash2 } from 'lucide-react';
import { apiFetch, ApiError, getData } from '@/lib/api/client';
import type { Paginated, UserSummary } from '@/lib/api/types';
import { useAuth } from '@/features/auth/AuthProvider';
import { NotFoundPage } from '@/features/static/StaticPages';
import { Badge } from '@/components/common/Badges';
import { TimeAgo, UserChip } from '@/components/common/Meta';
import { Button } from '@/components/common/Button';
import { EmptyState, ErrorState, Skeleton } from '@/components/common/States';
import { Pagination } from '@/components/common/Pagination';
import { inputClass } from '@/components/forms/Field';
import { humanize } from '@/lib/format';
import { cn } from '@/lib/cn';

/** Renders 404 for non-moderators so admin pages aren't revealed (spec §8.4). */
export function RequireRole({ role, children }: { role: 'moderator' | 'admin'; children: React.ReactNode }) {
  const { user, status } = useAuth();
  if (status === 'loading') return <Skeleton className="m-8 h-40" />;
  const ok = user && (user.role === 'admin' || (role === 'moderator' && user.role === 'moderator'));
  return ok ? <>{children}</> : <NotFoundPage />;
}

export function AdminLayout() {
  const { user } = useAuth();
  const link = ({ isActive }: { isActive: boolean }) => cn('block shrink-0 rounded-[6px] px-3 py-2 text-sm', isActive ? 'bg-surface-2 font-medium' : 'text-muted hover:text-text');
  return (
    <div className="mx-auto max-w-[1200px] px-4 py-8 md:px-8">
      <title>Moderation · DevCommons</title>
      <h1 className="flex items-center gap-2 text-[28px]"><Shield size={24} aria-hidden /> Moderation</h1>
      <div className="mt-6 grid gap-8 md:grid-cols-[190px_minmax(0,1fr)]">
        <nav aria-label="Admin" className="flex gap-1 overflow-x-auto md:block md:space-y-1">
          {user?.role === 'admin' && <NavLink end to="/admin" className={link}>Overview</NavLink>}
          <NavLink to="/admin/reports" className={link}>Reports</NavLink>
          {user?.role === 'admin' && <NavLink to="/admin/users" className={link}>Users</NavLink>}
          {user?.role === 'admin' && <NavLink to="/admin/trusted-domains" className={link}>Trusted domains</NavLink>}
          <NavLink to="/admin/log" className={link}>Moderation log</NavLink>
        </nav>
        <div className="min-w-0"><Outlet /></div>
      </div>
    </div>
  );
}

interface Stats { counts: Record<string, number>; new_users: { last_7_days: number; last_30_days: number }; open_reports: number; ai: { cost_month_to_date_usd: number; monthly_budget_usd: number; requests_per_day: { date: string; requests: number; cost_usd: number }[] } }

export function AdminOverviewPage() {
  const { user } = useAuth();
  const { data, error, refetch } = useQuery({ queryKey: ['admin', 'stats'], queryFn: () => getData<Stats>('/api/admin/stats'), enabled: user?.role === 'admin' });
  if (user?.role !== 'admin') return <p className="text-sm text-muted">Open the <Link to="/admin/reports" className="underline">reports queue</Link>.</p>;
  if (error) return <ErrorState error={error} onRetry={() => refetch()} />;
  if (!data) return <Skeleton className="h-64" />;
  const pct = Math.min(100, (data.ai.cost_month_to_date_usd / data.ai.monthly_budget_usd) * 100);
  const tile = 'rounded-[10px] border border-border bg-surface p-4';
  return (
    <div className="space-y-6">
      <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {Object.entries(data.counts).map(([k, n]) => <div key={k} className={tile}><p className="text-sm text-muted capitalize">{k}</p><p className="mt-1 font-mono text-2xl">{n}</p></div>)}
        <div className={tile}><p className="text-sm text-muted">New users (7 / 30 days)</p><p className="mt-1 font-mono text-2xl">{data.new_users.last_7_days} / {data.new_users.last_30_days}</p></div>
        <Link to="/admin/reports" className={cn(tile, 'hover:border-text')}><p className="text-sm text-muted">Open reports</p><p className={cn('mt-1 font-mono text-2xl', data.open_reports && 'text-danger')}>{data.open_reports}</p></Link>
      </div>
      <section className={tile}>
        <div className="flex items-baseline justify-between text-sm"><p className="font-medium">AI cost this month</p><p className="font-mono">${data.ai.cost_month_to_date_usd.toFixed(4)} / ${data.ai.monthly_budget_usd.toFixed(0)}</p></div>
        <div className="mt-2 h-2 overflow-hidden rounded-full bg-surface-2" role="progressbar" aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100} aria-label="AI budget used"><div className={cn('h-full rounded-full', pct > 80 ? 'bg-danger' : 'bg-ai')} style={{ width: `${Math.max(pct, 0.5)}%` }} /></div>
        <p className="mt-2 font-mono text-xs text-muted">{data.ai.requests_per_day.reduce((a, d) => a + d.requests, 0)} AI requests in the last 30 days</p>
      </section>
    </div>
  );
}

interface Report {
  id: string; reporter: UserSummary | null; target_type: string; target_id: string; reason: string; details: string | null; status: string; resolution_note: string | null; created_at: string;
  target_preview: { exists: boolean; title?: string; snippet?: string; content?: string; author?: UserSummary; status?: string; url_path?: string; deleted?: boolean };
}

export function AdminReportsPage() {
  const qc = useQueryClient();
  const [sp, setSp] = useSearchParams();
  const status = sp.get('status') ?? 'open';
  const type = sp.get('type') ?? '';
  const page = Number(sp.get('page') ?? 1);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['admin', 'reports', status, type, page],
    queryFn: () => apiFetch<Paginated<Report>>('/api/admin/reports', { query: { status, target_type: type, page } }),
    placeholderData: keepPreviousData,
  });
  const act = async (r: Report, kind: 'hide' | 'restore' | 'remove' | 'resolved' | 'dismissed') => {
    try {
      if (kind === 'resolved' || kind === 'dismissed') await apiFetch(`/api/admin/reports/${r.id}`, { method: 'PATCH', body: { status: kind, resolution_note: notes[r.id] || null } });
      else await apiFetch('/api/admin/moderate', { method: 'POST', body: { target_type: r.target_type, target_id: r.target_id, action: kind, reason: notes[r.id] || `Report: ${r.reason}` } });
      toast.success(humanize(kind));
      void qc.invalidateQueries({ queryKey: ['admin'] });
    } catch (e) { toast.error(e instanceof ApiError ? e.message : 'Action failed.'); }
  };
  const moderatable = ['harness', 'idea', 'resource', 'collection', 'comment', 'suggestion', 'review'];
  return (
    <div>
      <div className="flex flex-wrap gap-3">
        <select aria-label="Status" value={status} onChange={(e) => setSp({ status: e.target.value, ...(type ? { type } : {}) })} className={cn(inputClass, 'h-9 w-36 text-sm')}>
          <option value="open">Open</option><option value="resolved">Resolved</option><option value="dismissed">Dismissed</option>
        </select>
        <select aria-label="Target type" value={type} onChange={(e) => setSp({ status, ...(e.target.value ? { type: e.target.value } : {}) })} className={cn(inputClass, 'h-9 w-44 text-sm')}>
          <option value="">All types</option>{['harness', 'idea', 'resource', 'collection', 'comment', 'suggestion', 'review', 'user', 'ai_message', 'ai_draft'].map((t) => <option key={t} value={t}>{humanize(t)}</option>)}
        </select>
      </div>
      <div className="mt-4" id="list-top">
        {isLoading ? <Skeleton className="h-40" /> : error ? <ErrorState error={error} onRetry={() => refetch()} />
          : !data?.data.length ? <EmptyState icon={Shield} title={status === 'open' ? 'No open reports. Nice.' : `No ${status} reports.`} />
          : (
            <ul className="space-y-3">
              {data.data.map((r) => (
                <li key={r.id} className="rounded-[10px] border border-border bg-surface p-4">
                  <div className="flex flex-wrap items-center gap-2 text-sm">
                    <Badge className="bg-danger-soft text-danger">{humanize(r.reason)}</Badge>
                    <Badge className="border border-border">{humanize(r.target_type)}</Badge>
                    {r.target_preview.status && <Badge className="border border-border text-muted">{r.target_preview.status}</Badge>}
                    <span className="ml-auto font-mono text-xs text-muted">by {r.reporter?.username ?? 'deleted'} · <TimeAgo iso={r.created_at} /></span>
                  </div>
                  {r.target_preview.exists ? (
                    <div className="mt-3 rounded-[6px] bg-surface-2 p-3 text-sm">
                      <p className="font-medium">{r.target_preview.title}{r.target_preview.url_path && <Link to={r.target_preview.url_path} className="ml-2 inline-flex items-center gap-1 text-xs font-normal underline">Open <ExternalLink size={11} aria-hidden /></Link>}</p>
                      {r.target_preview.author && <p className="mt-0.5 text-xs text-muted">by {r.target_preview.author.display_name}</p>}
                      {(r.target_preview.snippet || r.target_preview.content) && <p className="mt-1.5 max-h-40 overflow-y-auto whitespace-pre-wrap text-muted">{r.target_preview.snippet ?? r.target_preview.content}</p>}
                    </div>
                  ) : <p className="mt-3 text-sm text-muted">The reported item no longer exists.</p>}
                  {r.details && <p className="mt-2 text-sm"><span className="font-medium">Reporter says:</span> {r.details}</p>}
                  {r.status === 'open' ? (
                    <div className="mt-3 space-y-2">
                      <input aria-label="Note" placeholder="Note for the log (optional)" value={notes[r.id] ?? ''} onChange={(e) => setNotes({ ...notes, [r.id]: e.target.value })} className={cn(inputClass, 'h-9 text-sm')} />
                      <div className="flex flex-wrap gap-2">
                        {moderatable.includes(r.target_type) && r.target_preview.exists && (
                          <>
                            {r.target_preview.status === 'published' ? <Button size="sm" onClick={() => act(r, 'hide')}>Hide</Button> : <Button size="sm" onClick={() => act(r, 'restore')}>Restore</Button>}
                            <Button size="sm" variant="danger" onClick={() => act(r, 'remove')}>Remove</Button>
                          </>
                        )}
                        <Button size="sm" variant="primary" onClick={() => act(r, 'resolved')}>Resolve</Button>
                        <Button size="sm" variant="ghost" onClick={() => act(r, 'dismissed')}>Dismiss</Button>
                      </div>
                    </div>
                  ) : r.resolution_note && <p className="mt-2 text-sm text-muted">Note: {r.resolution_note}</p>}
                </li>
              ))}
            </ul>
          )}
        {data && <Pagination meta={data.meta} onPage={(p) => setSp({ status, ...(type ? { type } : {}), page: String(p) })} />}
      </div>
    </div>
  );
}

interface AdminUser extends UserSummary { email: string; email_verified: boolean; role: string; status: string; created_at: string; last_login_at: string | null }

export function AdminUsersPage() {
  const qc = useQueryClient();
  const [q, setQ] = useState('');
  const [page, setPage] = useState(1);
  const { data, isLoading } = useQuery({ queryKey: ['admin', 'users', q, page], queryFn: () => apiFetch<Paginated<AdminUser>>('/api/admin/users', { query: { q, page } }), placeholderData: keepPreviousData });
  const update = async (u: AdminUser, patch: { status?: string; role?: string }) => {
    const reason = window.prompt(`Reason for changing @${u.username}?`);
    if (!reason) return;
    try { await apiFetch(`/api/admin/users/${u.id}`, { method: 'PATCH', body: { ...patch, reason } }); toast.success('User updated'); void qc.invalidateQueries({ queryKey: ['admin', 'users'] }); }
    catch (e) { toast.error(e instanceof ApiError ? e.message : 'Update failed.'); }
  };
  return (
    <div>
      <input aria-label="Search users" placeholder="Search by name, username or email" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} className={cn(inputClass, 'h-10 max-w-md')} />
      <div className="mt-4 overflow-x-auto rounded-[10px] border border-border" id="list-top">
        {isLoading ? <Skeleton className="h-40" /> : (
          <table className="w-full text-sm">
            <thead className="bg-surface-2 text-left text-xs text-muted"><tr><th className="px-3 py-2 font-medium">User</th><th className="px-3 py-2 font-medium">Email</th><th className="px-3 py-2 font-medium">Role</th><th className="px-3 py-2 font-medium">Status</th><th className="px-3 py-2 font-medium">Last login</th></tr></thead>
            <tbody>
              {data?.data.map((u) => (
                <tr key={u.id} className="border-t border-border bg-surface">
                  <td className="px-3 py-2"><UserChip user={u} /></td>
                  <td className="px-3 py-2 font-mono text-xs">{u.email}</td>
                  <td className="px-3 py-2">
                    <select aria-label={`Role for ${u.username}`} value={u.role} onChange={(e) => update(u, { role: e.target.value })} className={cn(inputClass, 'h-8 w-32 text-sm')}>
                      <option value="user">User</option><option value="moderator">Moderator</option><option value="admin">Admin</option>
                    </select>
                  </td>
                  <td className="px-3 py-2">
                    {u.status === 'deleted' ? <span className="text-muted">Deleted</span> : (
                      <Button size="sm" variant={u.status === 'suspended' ? 'primary' : 'secondary'} onClick={() => update(u, { status: u.status === 'suspended' ? 'active' : 'suspended' })}>
                        {u.status === 'suspended' ? 'Unsuspend' : 'Suspend'}
                      </Button>
                    )}
                  </td>
                  <td className="px-3 py-2 font-mono text-xs text-muted">{u.last_login_at ? <TimeAgo iso={u.last_login_at} /> : 'never'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      {data && <Pagination meta={data.meta} onPage={setPage} />}
    </div>
  );
}

interface Domain { id: number; domain: string; kind: string; label: string | null; created_at: string }

export function AdminDomainsPage() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ['admin', 'domains'], queryFn: () => getData<Domain[]>('/api/admin/trusted-domains') });
  const [v, setV] = useState({ domain: '', kind: 'official_docs', label: '' });
  return (
    <div className="space-y-5">
      <form className="flex flex-wrap items-end gap-2 rounded-[10px] border border-border bg-surface p-4" onSubmit={async (e) => {
        e.preventDefault();
        try { await apiFetch('/api/admin/trusted-domains', { method: 'POST', body: { ...v, label: v.label || null } }); setV({ domain: '', kind: 'official_docs', label: '' }); toast.success('Domain added'); void qc.invalidateQueries({ queryKey: ['admin', 'domains'] }); }
        catch (err) { toast.error(err instanceof ApiError ? err.message : 'Could not add.'); }
      }}>
        <label className="flex flex-col gap-1 text-xs font-medium text-muted">Domain<input required value={v.domain} onChange={(e) => setV({ ...v, domain: e.target.value })} placeholder="docs.example.com" className={cn(inputClass, 'h-9 w-52 font-mono text-sm text-text')} /></label>
        <label className="flex flex-col gap-1 text-xs font-medium text-muted">Kind<select value={v.kind} onChange={(e) => setV({ ...v, kind: e.target.value })} className={cn(inputClass, 'h-9 w-40 text-sm text-text')}><option value="official_docs">Official docs</option><option value="reputable">Reputable</option></select></label>
        <label className="flex flex-col gap-1 text-xs font-medium text-muted">Label<input value={v.label} onChange={(e) => setV({ ...v, label: e.target.value })} placeholder="Example" className={cn(inputClass, 'h-9 w-40 text-sm text-text')} /></label>
        <Button type="submit" variant="primary">Add domain</Button>
      </form>
      {isLoading ? <Skeleton className="h-40" /> : (
        <div className="overflow-x-auto rounded-[10px] border border-border">
          <table className="w-full text-sm">
            <thead className="bg-surface-2 text-left text-xs text-muted"><tr><th className="px-3 py-2 font-medium">Domain</th><th className="px-3 py-2 font-medium">Kind</th><th className="px-3 py-2 font-medium">Label</th><th className="px-3 py-2"><span className="sr-only">Actions</span></th></tr></thead>
            <tbody>
              {data?.map((d) => (
                <tr key={d.id} className="border-t border-border bg-surface">
                  <td className="px-3 py-2 font-mono text-[13px]">{d.domain}</td>
                  <td className="px-3 py-2">{humanize(d.kind)}</td>
                  <td className="px-3 py-2 text-muted">{d.label}</td>
                  <td className="px-3 py-2 text-right">
                    <button type="button" aria-label={`Delete ${d.domain}`} className="grid size-8 cursor-pointer place-items-center rounded-[6px] text-muted hover:bg-surface-2 hover:text-danger" onClick={async () => {
                      if (!window.confirm(`Remove ${d.domain} from trusted domains?`)) return;
                      await apiFetch(`/api/admin/trusted-domains/${d.id}`, { method: 'DELETE' }); void qc.invalidateQueries({ queryKey: ['admin', 'domains'] });
                    }}><Trash2 size={15} /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

interface LogRow { id: string; actor: UserSummary | null; action: string; target_type: string; target_id: string; reason: string | null; created_at: string }

export function AdminLogPage() {
  const [page, setPage] = useState(1);
  const { data, isLoading } = useQuery({ queryKey: ['admin', 'log', page], queryFn: () => apiFetch<Paginated<LogRow>>('/api/admin/moderation-log', { query: { page } }), placeholderData: keepPreviousData });
  if (isLoading) return <Skeleton className="h-40" />;
  if (!data?.data.length) return <EmptyState icon={Shield} title="No moderation actions yet." />;
  return (
    <div>
      <div className="overflow-x-auto rounded-[10px] border border-border" id="list-top">
        <table className="w-full text-sm">
          <thead className="bg-surface-2 text-left text-xs text-muted"><tr><th className="px-3 py-2 font-medium">When</th><th className="px-3 py-2 font-medium">Moderator</th><th className="px-3 py-2 font-medium">Action</th><th className="px-3 py-2 font-medium">Target</th><th className="px-3 py-2 font-medium">Reason</th></tr></thead>
          <tbody>
            {data.data.map((r) => (
              <tr key={r.id} className="border-t border-border bg-surface">
                <td className="px-3 py-2 font-mono text-xs text-muted"><TimeAgo iso={r.created_at} /></td>
                <td className="px-3 py-2">{r.actor?.username ?? '—'}</td>
                <td className="px-3 py-2"><Badge className="border border-border">{humanize(r.action)}</Badge></td>
                <td className="px-3 py-2 font-mono text-xs">{r.target_type} · {r.target_id.slice(0, 8)}</td>
                <td className="px-3 py-2 text-muted">{r.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pagination meta={data.meta} onPage={setPage} />
    </div>
  );
}
