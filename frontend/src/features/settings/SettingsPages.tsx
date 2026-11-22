import { useEffect, useRef, useState } from 'react';
import { NavLink, Outlet, useNavigate, useSearchParams } from 'react-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { Check, Laptop, Plus, Trash2, X } from 'lucide-react';
import { apiFetch, ApiError, getData } from '@/lib/api/client';
import { qk } from '@/lib/queryKeys';
import type { AIToday, MeProfile } from '@/lib/api/types';
import { useAuth } from '@/features/auth/AuthProvider';
import { authFetch, clearSession, setSession } from '@/features/auth/session';
import { oauthErrorMessage, PROVIDER_LABEL, ProviderMark, startLink, useProviders, type Provider } from '@/features/auth/oauth';
import { useDebouncedValue } from '@/hooks/useDebouncedValue';
import { Field, TextArea, TextInput, inputClass } from '@/components/forms/Field';
import { TagInput } from '@/components/forms/TagInput';
import { Button } from '@/components/common/Button';
import { ConfirmDialog } from '@/components/common/ConfirmDialog';
import { Skeleton } from '@/components/common/States';
import { TimeAgo } from '@/components/common/Meta';
import { cn } from '@/lib/cn';

type FullMe = MeProfile & { website_url: string | null; github_username: string | null; contact_links: { label: string; url: string }[]; contact_visibility: 'hidden' | 'collaborators' | 'public' };
const useFullMe = () => useQuery({ queryKey: qk.me, queryFn: () => getData<FullMe>('/api/users/me'), staleTime: 0 });

function usePatchMe() {
  const qc = useQueryClient();
  return async (body: Record<string, unknown>) => {
    const r = await apiFetch<{ data: FullMe }>('/api/users/me', { method: 'PATCH', body });
    qc.setQueryData(qk.me, r.data);
    void qc.invalidateQueries({ queryKey: ['users'] });
    return r.data;
  };
}

export function SettingsLayout() {
  const link = ({ isActive }: { isActive: boolean }) => cn('block rounded-[6px] px-3 py-2 text-sm', isActive ? 'bg-surface-2 font-medium' : 'text-muted hover:text-text');
  return (
    <div className="mx-auto max-w-[1000px] px-4 py-8 md:px-8">
      <h1 className="text-[28px]">Settings</h1>
      <div className="mt-6 grid gap-8 md:grid-cols-[200px_minmax(0,1fr)]">
        <nav aria-label="Settings" className="flex gap-1 overflow-x-auto md:block md:space-y-1">
          <NavLink to="/settings/profile" className={link}>Profile</NavLink>
          <NavLink to="/settings/privacy" className={link}>Privacy and contact</NavLink>
          <NavLink to="/settings/ai" className={link}>AI usage</NavLink>
          <NavLink to="/settings/account" className={link}>Account</NavLink>
        </nav>
        <div className="min-w-0"><Outlet /></div>
      </div>
    </div>
  );
}

const Card = ({ title, children, danger }: { title: string; children: React.ReactNode; danger?: boolean }) => (
  <section className={cn('rounded-[10px] border bg-surface p-5 md:p-6', danger ? 'border-danger' : 'border-border')}>
    <h2 className={cn('text-lg', danger && 'text-danger')}>{title}</h2>
    <div className="mt-4 space-y-4">{children}</div>
  </section>
);

export function ProfileSettingsPage() {
  const { data: me } = useFullMe();
  const patch = usePatchMe();
  const [v, setV] = useState<null | { display_name: string; username: string; bio: string; skills: string[]; interests: string[]; website_url: string; github_username: string }>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const du = useDebouncedValue(v?.username ?? '', 400);
  const [avail, setAvail] = useState<null | { available: boolean; reason?: string }>(null);
  useEffect(() => {
    if (me && !v) setV({ display_name: me.display_name, username: me.username, bio: me.bio ?? '', skills: me.skills ?? [], interests: me.interests ?? [], website_url: me.website_url ?? '', github_username: me.github_username ?? '' });
  }, [me, v]);
  useEffect(() => {
    if (!me || !du || du === me.username || du.length < 3) { setAvail(null); return; }
    getData<{ available: boolean; reason?: string }>('/api/users/check-username', { username: du }).then(setAvail).catch(() => setAvail(null));
  }, [du, me]);
  if (!v || !me) return <Skeleton className="h-96" />;
  return (
    <>
      <title>Profile settings · DevCommons</title>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setErrors({});
          try {
            await patch({ ...v, bio: v.bio || null, website_url: v.website_url.trim() || null, github_username: v.github_username.trim() || null, ...(v.username === me.username ? { username: undefined } : {}) });
            toast.success('Profile saved');
          } catch (err) {
            if (err instanceof ApiError && err.details?.fields) setErrors(err.details.fields as Record<string, string>);
            else toast.error(err instanceof ApiError ? err.message : 'Could not save.');
          } finally {
            setBusy(false);
          }
        }}
      >
        <Card title="Profile">
          <Field label="Display name" required error={errors.display_name}>{(p) => <TextInput {...p} value={v.display_name} maxLength={60} onChange={(e) => setV({ ...v, display_name: e.target.value })} />}</Field>
          <Field label="Username" required error={errors.username} hint={v.username !== me.username ? (avail ? (avail.available ? <span className="text-success">Available. Old links to your profile will stop working.</span> : <span className="text-danger">{avail.reason === 'reserved' ? 'Reserved' : avail.reason === 'invalid' ? '3–30 lowercase letters, numbers, - or _' : 'Taken'}</span>) : 'Checking…') : undefined}>
            {(p) => <TextInput {...p} value={v.username} maxLength={30} onChange={(e) => setV({ ...v, username: e.target.value.toLowerCase() })} className="font-mono" autoComplete="username" />}
          </Field>
          <Field label="Bio" error={errors.bio} counter={{ n: v.bio.length, max: 500 }}>{(p) => <TextArea {...p} rows={3} value={v.bio} onChange={(e) => setV({ ...v, bio: e.target.value })} />}</Field>
          <Field label="Skills">{(p) => <TagInput id={p.id} value={v.skills} onChange={(x) => setV({ ...v, skills: x })} max={15} />}</Field>
          <Field label="Interests">{(p) => <TagInput id={p.id} value={v.interests} onChange={(x) => setV({ ...v, interests: x })} max={15} />}</Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Website" error={errors.website_url}>{(p) => <TextInput {...p} type="url" value={v.website_url} onChange={(e) => setV({ ...v, website_url: e.target.value })} placeholder="https://" />}</Field>
            <Field label="GitHub username" error={errors.github_username}>{(p) => <TextInput {...p} value={v.github_username} maxLength={39} onChange={(e) => setV({ ...v, github_username: e.target.value })} className="font-mono" />}</Field>
          </div>
          <div className="flex justify-end"><Button type="submit" variant="primary" disabled={busy}>{busy ? 'Saving…' : 'Save profile'}</Button></div>
        </Card>
      </form>
    </>
  );
}

export function PrivacySettingsPage() {
  const { data: me } = useFullMe();
  const patch = usePatchMe();
  const [links, setLinks] = useState<{ label: string; url: string }[] | null>(null);
  const [vis, setVis] = useState<FullMe['contact_visibility']>('hidden');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<Record<string, string>>({});
  useEffect(() => { if (me && !links) { setLinks(me.contact_links ?? []); setVis(me.contact_visibility); } }, [me, links]);
  if (!me || !links) return <Skeleton className="h-80" />;
  return (
    <>
      <title>Privacy settings · DevCommons</title>
      <Card title="Privacy and contact">
        <p className="rounded-[6px] bg-surface-2 p-3 text-sm">Your email is never shown on your profile. It's only shared with a collaborator if you tick “share my contact details” on a specific request.</p>
        <fieldset>
          <legend className="text-sm font-medium">Who can see your contact links</legend>
          <div className="mt-2 space-y-1">
            {([['hidden', 'Hidden', 'Nobody, unless you share them on a collaboration request.'], ['collaborators', 'Only people I collaborate with', 'Shown to accepted collaborators.'], ['public', 'Public', 'Shown on your profile.']] as const).map(([val, label, desc]) => (
              <label key={val} className="flex cursor-pointer items-start gap-2.5 rounded-[6px] px-2 py-1.5 hover:bg-surface-2">
                <input type="radio" name="vis" className="mt-1 size-4" checked={vis === val} onChange={() => setVis(val)} />
                <span><span className="text-sm font-medium">{label}</span><span className="block text-xs text-muted">{desc}</span></span>
              </label>
            ))}
          </div>
        </fieldset>
        <div>
          <p className="text-sm font-medium">Contact links <span className="font-normal text-muted">(up to 5)</span></p>
          <ul className="mt-2 space-y-2">
            {links.map((l, i) => (
              <li key={i} className="flex flex-wrap gap-2">
                <input aria-label={`Link ${i + 1} label`} value={l.label} maxLength={40} onChange={(e) => setLinks(links.map((x, k) => (k === i ? { ...x, label: e.target.value } : x)))} placeholder="LinkedIn" className={cn(inputClass, 'h-9 w-36 text-sm')} />
                <input aria-label={`Link ${i + 1} URL`} value={l.url} onChange={(e) => setLinks(links.map((x, k) => (k === i ? { ...x, url: e.target.value } : x)))} placeholder="https://" className={cn(inputClass, 'h-9 min-w-48 flex-1 font-mono text-sm')} aria-invalid={!!err[`contact_links.${i}.url`]} />
                <button type="button" onClick={() => setLinks(links.filter((_, k) => k !== i))} className="grid size-9 cursor-pointer place-items-center rounded-[6px] text-muted hover:bg-surface-2" aria-label={`Remove link ${i + 1}`}><Trash2 size={15} /></button>
                {err[`contact_links.${i}.url`] && <p className="w-full text-sm text-danger">{err[`contact_links.${i}.url`]}</p>}
              </li>
            ))}
          </ul>
          <Button size="sm" className="mt-2" disabled={links.length >= 5} onClick={() => setLinks([...links, { label: '', url: '' }])}><Plus size={14} aria-hidden /> Add link</Button>
        </div>
        <div className="flex justify-end">
          <Button variant="primary" disabled={busy} onClick={async () => {
            setBusy(true); setErr({});
            try { await patch({ contact_links: links.filter((l) => l.label.trim() && l.url.trim()), contact_visibility: vis }); toast.success('Privacy settings saved'); }
            catch (e) { if (e instanceof ApiError && e.details?.fields) setErr(e.details.fields as Record<string, string>); else toast.error(e instanceof ApiError ? e.message : 'Could not save.'); }
            finally { setBusy(false); }
          }}>{busy ? 'Saving…' : 'Save'}</Button>
        </div>
      </Card>
    </>
  );
}

export function AISettingsPage() {
  const { data } = useQuery({ queryKey: ['ai', 'usage'], queryFn: () => getData<{ today: AIToday; daily: { date: string; tokens: number; requests: number }[] }>('/api/ai/usage', { days: 30 }) });
  if (!data) return <Skeleton className="h-80" />;
  const t = data.today;
  const pct = Math.min(100, (t.tokens / t.limit_tokens) * 100);
  const max = Math.max(1, ...data.daily.map((d) => d.requests));
  const days = Array.from({ length: 30 }, (_, i) => {
    const d = new Date(Date.now() - (29 - i) * 86_400_000).toISOString().slice(0, 10);
    return data.daily.find((x) => x.date === d) ?? { date: d, tokens: 0, requests: 0 };
  });
  return (
    <>
      <title>AI usage · DevCommons</title>
      <Card title="AI usage">
        <div>
          <div className="flex items-baseline justify-between text-sm"><span className="font-medium">Tokens today</span><span className="font-mono">{t.tokens.toLocaleString()} / {t.limit_tokens.toLocaleString()}</span></div>
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-surface-2" role="progressbar" aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100} aria-label="Tokens used today"><div className="h-full rounded-full bg-ai" style={{ width: `${pct}%` }} /></div>
          <div className="mt-3 flex items-baseline justify-between text-sm"><span className="font-medium">Generations today</span><span className="font-mono">{t.generations} / {t.limit_generations}</span></div>
          <p className="mt-2 text-xs text-muted">Limits reset at 00:00 UTC (<TimeAgo iso={t.resets_at} />). Chat counts toward tokens; drafts and refinements count as generations.</p>
        </div>
        <div>
          <p className="text-sm font-medium">Requests per day, last 30 days</p>
          <div className="mt-3 flex h-32 items-end gap-[3px]" role="img" aria-label={`Requests per day over 30 days. Total ${data.daily.reduce((a, d) => a + d.requests, 0)}.`}>
            {days.map((d) => (
              <div key={d.date} className="group relative flex-1">
                <div className="w-full rounded-t-[2px] bg-ai" style={{ height: `${Math.max(d.requests ? 4 : 1, (d.requests / max) * 120)}px`, opacity: d.requests ? 1 : 0.2 }} />
                <span className="pointer-events-none absolute bottom-full left-1/2 mb-1 hidden -translate-x-1/2 rounded bg-text px-1.5 py-0.5 font-mono text-[10px] whitespace-nowrap text-bg group-hover:block">{d.date.slice(5)} · {d.requests} req · {d.tokens} tok</span>
              </div>
            ))}
          </div>
          <div className="mt-1 flex justify-between font-mono text-[11px] text-muted"><span>{days[0].date.slice(5)}</span><span>today</span></div>
        </div>
      </Card>
    </>
  );
}

interface SessionRow { id: string; device_label: string; created_at: string; last_used_at: string; is_current: boolean }

interface Connections {
  has_password: boolean;
  providers: Record<Provider, boolean>;
  accounts: { provider: Provider; label: string; email: string | null; login: string | null; created_at: string; last_used_at: string }[];
}

function ConnectedAccounts() {
  const qc = useQueryClient();
  const { data: enabled } = useProviders();
  const conns = useQuery({ queryKey: ['auth', 'connections'], queryFn: () => getData<Connections>('/api/auth/connections') });
  const [busy, setBusy] = useState<Provider | null>(null);
  const [sp, setSp] = useSearchParams();
  const handled = useRef<string | null>(null);

  // Result of a connect round-trip: /settings/account?linked=github or ?oauth_error=...
  useEffect(() => {
    const linked = sp.get('linked') as Provider | null;
    const err = oauthErrorMessage(sp.get('oauth_error'), sp.get('provider'));
    if (!linked && !err) return;
    if (handled.current === sp.toString()) return; // StrictMode runs effects twice
    handled.current = sp.toString();
    if (linked) toast.success(`${PROVIDER_LABEL[linked]} connected. You can now sign in with it.`);
    if (err) toast.error(err);
    setSp({}, { replace: true });
    void qc.invalidateQueries({ queryKey: ['auth', 'connections'] });
  }, [sp, setSp, qc]);

  const rows = (['github', 'google'] as Provider[]).filter((p) => enabled?.[p] || conns.data?.accounts.some((a) => a.provider === p));
  if (!conns.isLoading && !rows.length) return null;
  const linkedCount = conns.data?.accounts.length ?? 0;
  return (
    <Card title="Connected accounts">
      <p className="text-sm text-muted">Sign in with these instead of your password. Connecting one also verifies your email.</p>
      {conns.isLoading ? <Skeleton className="h-20" /> : (
        <ul className="divide-y divide-border">
          {rows.map((p) => {
            const acct = conns.data?.accounts.find((a) => a.provider === p);
            const onlyWay = !!acct && !conns.data?.has_password && linkedCount === 1;
            return (
              <li key={p} className="flex items-center gap-3 py-3 text-sm">
                <span className="grid size-8 place-items-center rounded-full border border-border bg-bg"><ProviderMark provider={p} /></span>
                <div className="min-w-0 flex-1">
                  <p className="font-medium">{PROVIDER_LABEL[p]}</p>
                  <p className="truncate text-xs text-muted">
                    {acct ? <>{acct.login ? `@${acct.login} · ` : ''}{acct.email ?? 'Connected'} · last used <TimeAgo iso={acct.last_used_at} /></> : 'Not connected'}
                  </p>
                </div>
                {acct ? (
                  <ConfirmDialog
                    trigger={<Button size="sm" disabled={onlyWay} title={onlyWay ? 'Set a password or connect another account first' : undefined}>Disconnect</Button>}
                    title={`Disconnect ${PROVIDER_LABEL[p]}?`}
                    description={`You won't be able to sign in with ${PROVIDER_LABEL[p]} until you connect it again.`}
                    confirmLabel="Disconnect"
                    onConfirm={async () => {
                      try {
                        await apiFetch(`/api/auth/connections/${p}`, { method: 'DELETE' });
                        toast(`${PROVIDER_LABEL[p]} disconnected`);
                        void conns.refetch();
                      } catch (e) {
                        toast.error(e instanceof ApiError ? e.message : 'Could not disconnect.');
                        throw e;
                      }
                    }}
                  />
                ) : (
                  <Button size="sm" disabled={busy !== null || !enabled?.[p]} onClick={async () => {
                    setBusy(p);
                    try { await startLink(p); } catch (e) { setBusy(null); toast.error(e instanceof ApiError ? e.message : 'Could not start connecting.'); }
                  }}>{busy === p ? 'Opening…' : 'Connect'}</Button>
                )}
              </li>
            );
          })}
        </ul>
      )}
      {conns.data && !conns.data.has_password && linkedCount === 1 && (
        <p className="text-xs text-muted">This is your only way to sign in. Set a password below or connect another account before disconnecting it.</p>
      )}
    </Card>
  );
}

export function AccountSettingsPage() {
  const { data: me } = useFullMe();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { signOut } = useAuth();
  const sessions = useQuery({ queryKey: ['auth', 'sessions'], queryFn: () => getData<SessionRow[]>('/api/auth/sessions') });
  const [email, setEmail] = useState({ new_email: '', password: '' });
  const [pw, setPw] = useState({ current_password: '', new_password: '', confirm: '' });
  const [delPw, setDelPw] = useState('');
  const [errs, setErrs] = useState<Record<string, string>>({});
  if (!me) return <Skeleton className="h-96" />;
  const hasPw = me.has_password !== false;
  const reauthHint = 'No password on this account, so you must have signed in within the last 15 minutes.';
  return (
    <div className="space-y-6">
      <title>Account settings · DevCommons</title>
      <Card title="Email">
        <p className="text-sm">{me.email} {me.email_verified ? <span className="ml-1 inline-flex items-center gap-1 text-success"><Check size={13} aria-hidden /> verified</span> : <span className="ml-1 inline-flex items-center gap-1 text-warning"><X size={13} aria-hidden /> not verified</span>}</p>
        <form className={cn('grid gap-3 sm:items-end', hasPw ? 'sm:grid-cols-[1fr_1fr_auto]' : 'sm:grid-cols-[1fr_auto]')} onSubmit={async (e) => {
          e.preventDefault(); setErrs({});
          try { await apiFetch('/api/users/me/email', { method: 'POST', body: hasPw ? email : { new_email: email.new_email } }); toast.success('Check your new inbox to confirm.'); setEmail({ new_email: '', password: '' }); }
          catch (err) { setErrs(err instanceof ApiError && err.details?.fields ? (err.details.fields as Record<string, string>) : { new_email: err instanceof ApiError ? err.message : 'Could not change email.' }); }
        }}>
          <Field label="New email" error={errs.new_email}>{(p) => <TextInput {...p} type="email" autoComplete="email" value={email.new_email} onChange={(e) => setEmail({ ...email, new_email: e.target.value })} />}</Field>
          {hasPw && <Field label="Current password" error={errs.password}>{(p) => <TextInput {...p} type="password" autoComplete="current-password" value={email.password} onChange={(e) => setEmail({ ...email, password: e.target.value })} />}</Field>}
          <Button type="submit" disabled={!email.new_email || (hasPw && !email.password)}>Change email</Button>
        </form>
      </Card>
      <ConnectedAccounts />
      <Card title={hasPw ? 'Password' : 'Set a password'}>
        {!hasPw && <p className="text-sm text-muted">You sign in with GitHub or Google. Add a password to also sign in with your email. {reauthHint}</p>}
        <form className="space-y-3" onSubmit={async (e) => {
          e.preventDefault(); setErrs({});
          if (pw.new_password !== pw.confirm) { setErrs({ confirm: "Passwords don't match." }); return; }
          try {
            const r = await apiFetch<{ data: { access_token?: string; expires_in?: number } }>('/api/users/me/password', { method: 'POST', body: hasPw ? { current_password: pw.current_password, new_password: pw.new_password } : { new_password: pw.new_password } });
            if (r?.data?.access_token) setSession(r.data.access_token, r.data.expires_in ?? 900);
            toast.success(hasPw ? 'Password changed. Other devices were signed out.' : 'Password set. You can now also sign in with your email.');
            if (!hasPw) void qc.invalidateQueries({ queryKey: qk.me });
            void qc.invalidateQueries({ queryKey: ['auth', 'connections'] });
            setPw({ current_password: '', new_password: '', confirm: '' });
            void sessions.refetch();
          } catch (err) { setErrs(err instanceof ApiError && err.details?.fields ? (err.details.fields as Record<string, string>) : { current_password: err instanceof ApiError ? err.message : 'Could not change password.' }); }
        }}>
          {hasPw && <Field label="Current password" error={errs.current_password}>{(p) => <TextInput {...p} type="password" autoComplete="current-password" value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} />}</Field>}
          {!hasPw && errs.current_password && <p role="alert" className="text-sm text-danger">{errs.current_password}</p>}
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="New password" hint="At least 10 characters." error={errs.new_password}>{(p) => <TextInput {...p} type="password" autoComplete="new-password" value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} />}</Field>
            <Field label="Confirm new password" error={errs.confirm}>{(p) => <TextInput {...p} type="password" autoComplete="new-password" value={pw.confirm} onChange={(e) => setPw({ ...pw, confirm: e.target.value })} />}</Field>
          </div>
          <div className="flex justify-end"><Button type="submit" disabled={(hasPw && !pw.current_password) || !pw.new_password}>{hasPw ? 'Change password' : 'Set password'}</Button></div>
        </form>
      </Card>
      <Card title="Active sessions">
        {sessions.isLoading ? <Skeleton className="h-24" /> : (
          <ul className="divide-y divide-border">
            {(sessions.data ?? []).map((s) => (
              <li key={s.id} className="flex items-center gap-3 py-2.5 text-sm">
                <Laptop size={16} className="text-muted" aria-hidden />
                <div className="min-w-0 flex-1">
                  <p className="font-medium">{s.device_label} {s.is_current && <span className="ml-1 rounded bg-surface-2 px-1.5 py-0.5 font-mono text-[11px]">This device</span>}</p>
                  <p className="font-mono text-xs text-muted">last active <TimeAgo iso={s.last_used_at} /></p>
                </div>
                {!s.is_current && <Button size="sm" onClick={async () => { await apiFetch(`/api/auth/sessions/${s.id}`, { method: 'DELETE' }); void sessions.refetch(); toast('Signed out that session'); }}>Sign out</Button>}
              </li>
            ))}
          </ul>
        )}
        <ConfirmDialog
          trigger={<Button>Sign out everywhere</Button>}
          title="Sign out of every device?"
          description="Including this one. You'll need to sign in again."
          confirmLabel="Sign out everywhere"
          onConfirm={async () => { await apiFetch('/api/auth/logout-all', { method: 'POST' }); clearSession(); qc.clear(); navigate('/sign-in'); }}
        />
      </Card>
      <Card title="Delete account" danger>
        <p className="text-sm text-muted">Your profile is anonymized and AI chats are deleted. Your public posts remain, attributed to “Deleted user”.</p>
        <ConfirmDialog
          trigger={<Button variant="danger">Delete my account</Button>}
          title="Delete your account?"
          description={hasPw ? "This can't be undone. Enter your password to confirm." : `This can't be undone. ${reauthHint}`}
          confirmLabel="Delete account"
          onConfirm={async () => {
            try {
              await apiFetch('/api/users/me', { method: 'DELETE', body: hasPw ? { password: delPw } : {} });
              await authFetch('/api/auth/logout', { method: 'POST' }).catch(() => undefined);
              await signOut();
              toast('Your account was deleted.');
              navigate('/');
            } catch (e) {
              toast.error(e instanceof ApiError ? e.message : 'Could not delete the account.');
              throw e;
            }
          }}
        >
          {hasPw && <>
            <label htmlFor="del-pw" className="mt-4 block text-sm font-medium">Password</label>
            <input id="del-pw" type="password" autoComplete="current-password" value={delPw} onChange={(e) => setDelPw(e.target.value)} className={cn(inputClass, 'mt-1 h-10')} />
          </>}
        </ConfirmDialog>
      </Card>
    </div>
  );
}
