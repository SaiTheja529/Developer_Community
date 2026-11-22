import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Link, Navigate, Outlet, useNavigate, useSearchParams } from 'react-router';
import { Check, Eye, EyeOff, X } from 'lucide-react';
import { useAuth } from './AuthProvider';
import { ApiError } from '@/lib/api/client';
import { authFetch } from './session';
import { resendVerification } from './resend';
import { oauthErrorMessage, PROVIDER_LABEL, SocialSignIn, type Provider } from './oauth';
import { toast } from 'sonner';
import { sanitizeNext } from '@/lib/format';
import { Button } from '@/components/common/Button';
import { fieldClass } from '@/components/common/FilterBar';
import { Logo } from '@/components/layout/AppShell';
import { useDebouncedValue } from '@/hooks/useDebouncedValue';
import { getData } from '@/lib/api/client';
import { cn } from '@/lib/cn';

export function AuthLayout() {
  return (
    <div className="dot-grid flex min-h-dvh flex-col items-center px-4 py-10">
      <meta name="referrer" content="no-referrer" />
      <Logo />
      <main id="main" className="mt-8 w-full max-w-[400px] rounded-[14px] border border-border bg-surface p-6 shadow-[var(--shadow-card)] sm:p-8">
        <Outlet />
      </main>
    </div>
  );
}

function Field({ label, hint, error, children, id }: { label: string; hint?: ReactNode; error?: string; children: ReactNode; id: string }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-medium">{label}</label>
      {children}
      {hint && !error && <p id={`${id}-hint`} className="text-xs text-muted">{hint}</p>}
      {error && <p id={`${id}-err`} className="text-sm text-danger">{error}</p>}
    </div>
  );
}

function PasswordInput({ id, value, onChange, autoComplete, invalid }: { id: string; value: string; onChange: (v: string) => void; autoComplete: string; invalid?: boolean }) {
  const [show, setShow] = useState(false);
  return (
    <div className="relative">
      <input id={id} type={show ? 'text' : 'password'} value={value} onChange={(e) => onChange(e.target.value)} autoComplete={autoComplete} aria-invalid={invalid} className={cn(fieldClass, 'h-10 w-full pr-10')} required />
      <button type="button" onClick={() => setShow((s) => !s)} className="absolute top-1/2 right-1 grid size-8 -translate-y-1/2 cursor-pointer place-items-center rounded text-muted hover:text-text" aria-label={show ? 'Hide password' : 'Show password'}>
        {show ? <EyeOff size={16} /> : <Eye size={16} />}
      </button>
    </div>
  );
}

function useRedirectIfSignedIn() {
  const { status } = useAuth();
  const [sp] = useSearchParams();
  return status === 'signed_in' ? <Navigate to={sanitizeNext(sp.get('next'))} replace /> : null;
}

export function SignInPage() {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const [sp] = useSearchParams();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const redirect = useRedirectIfSignedIn();
  const oauthErr = oauthErrorMessage(sp.get('oauth_error'), sp.get('provider'));
  if (redirect && !busy) return redirect;
  return (
    <>
      <title>Sign in · DevCommons</title>
      <h1 className="text-2xl">Sign in</h1>
      <p className="mt-1 text-sm text-muted">Welcome back.</p>
      {oauthErr && <p role="alert" className="mt-4 rounded-[6px] bg-danger-soft px-3 py-2 text-sm text-danger">{oauthErr}</p>}
      <SocialSignIn next={sp.get('next')} />
      <form
        className="mt-6 space-y-4"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setErr(null);
          try {
            await signIn(email, password);
            navigate(sanitizeNext(sp.get('next')), { replace: true });
          } catch (e) {
            const code = e instanceof ApiError ? e.code : '';
            setErr(code === 'invalid_credentials' ? 'Email or password is incorrect.' : code === 'too_many_attempts' ? `Too many attempts. Try again in ${Math.ceil(((e as ApiError).retryAfter ?? 900) / 60)} minutes.` : code === 'account_suspended' ? 'This account is suspended.' : 'Sign-in failed. Check your connection and try again.');
            setBusy(false);
          }
        }}
      >
        <Field label="Email" id="email"><input id="email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} className={cn(fieldClass, 'h-10')} required /></Field>
        <Field label="Password" id="password" hint={<Link to="/forgot-password" className="underline">Forgot password?</Link>}>
          <PasswordInput id="password" value={password} onChange={setPassword} autoComplete="current-password" />
        </Field>
        <div aria-live="assertive">{err && <p className="rounded-[6px] bg-danger-soft px-3 py-2 text-sm text-danger">{err}</p>}</div>
        <Button type="submit" variant="primary" size="lg" className="w-full" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</Button>
      </form>
      <p className="mt-6 text-center text-sm text-muted">New here? <Link to={`/sign-up${sp.get('next') ? `?next=${encodeURIComponent(sp.get('next')!)}` : ''}`} className="font-medium text-text underline">Create an account</Link></p>
    </>
  );
}

export function SignUpPage() {
  const { signUp } = useAuth();
  const navigate = useNavigate();
  const [sp] = useSearchParams();
  const [f, setF] = useState({ email: '', username: '', display_name: '', password: '' });
  const [agree, setAgree] = useState(false);
  const [errs, setErrs] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const du = useDebouncedValue(f.username, 400);
  const [avail, setAvail] = useState<null | { available: boolean; reason?: string }>(null);
  const redirect = useRedirectIfSignedIn();

  useEffect(() => {
    if (du.length < 3) { setAvail(null); return; }
    let live = true;
    getData<{ available: boolean; reason?: string }>('/api/users/check-username', { username: du }).then((r) => live && setAvail(r)).catch(() => live && setAvail(null));
    return () => { live = false; };
  }, [du]);

  if (redirect && !busy) return redirect;
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: k === 'username' ? e.target.value.toLowerCase() : e.target.value });
  const strength = Math.min(4, Math.floor(f.password.length / 4));
  return (
    <>
      <title>Join · DevCommons</title>
      <h1 className="text-2xl">Create your account</h1>
      <p className="mt-1 text-sm text-muted">Share harnesses, ideas and the docs that helped you.</p>
      <SocialSignIn next={sp.get('next')} />
      <form
        className="mt-6 space-y-4"
        onSubmit={async (e) => {
          e.preventDefault();
          if (!agree) { setErrs({ agree: 'Please accept the terms and community guidelines.' }); return; }
          setBusy(true);
          setErrs({});
          try {
            await signUp(f);
            navigate('/check-email', { replace: true });
          } catch (e) {
            const err = e as ApiError;
            const fields = (err.details?.fields as Record<string, string>) ?? {};
            if (err.code === 'email_taken') fields.email = 'An account with this email already exists.';
            if (err.code === 'username_taken') fields.username = 'That username is taken.';
            setErrs(Object.keys(fields).length ? fields : { _: err.message ?? 'Sign-up failed.' });
            setBusy(false);
          }
        }}
      >
        <Field label="Email" id="su-email" error={errs.email}><input id="su-email" type="email" autoComplete="email" value={f.email} onChange={set('email')} className={cn(fieldClass, 'h-10')} required /></Field>
        <Field label="Username" id="su-user" error={errs.username} hint={avail && (
          <span className={cn('inline-flex items-center gap-1', avail.available ? 'text-success' : 'text-danger')}>
            {avail.available ? <Check size={12} aria-hidden /> : <X size={12} aria-hidden />}
            {avail.available ? 'Available' : avail.reason === 'reserved' ? 'Reserved' : avail.reason === 'invalid' ? '3–30 lowercase letters, numbers, - or _' : 'Taken'}
          </span>
        )}>
          <input id="su-user" autoComplete="username" value={f.username} onChange={set('username')} className={cn(fieldClass, 'h-10 font-mono')} required aria-describedby="su-user-hint" />
        </Field>
        <Field label="Display name" id="su-name" error={errs.display_name}><input id="su-name" autoComplete="name" value={f.display_name} onChange={set('display_name')} className={cn(fieldClass, 'h-10')} required /></Field>
        <Field label="Password" id="su-pass" error={errs.password} hint="At least 10 characters. Common passwords are rejected.">
          <PasswordInput id="su-pass" value={f.password} onChange={(v) => setF({ ...f, password: v })} autoComplete="new-password" />
          <div className="flex gap-1" aria-hidden>{[0, 1, 2, 3].map((i) => <span key={i} className={cn('h-1 flex-1 rounded-full', i < strength ? (f.password.length >= 10 ? 'bg-success' : 'bg-warning') : 'bg-surface-2')} />)}</div>
        </Field>
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} className="mt-1 size-4" />
          <span>I agree to the <Link to="/terms" className="underline">terms</Link> and <Link to="/guidelines" className="underline">community guidelines</Link>.</span>
        </label>
        <div aria-live="assertive">{(errs.agree || errs._) && <p className="text-sm text-danger">{errs.agree ?? errs._}</p>}</div>
        <Button type="submit" variant="primary" size="lg" className="w-full" disabled={busy}>{busy ? 'Creating account…' : 'Create account'}</Button>
      </form>
      <p className="mt-3 text-xs text-muted">Signing up with GitHub or Google means you agree to the <Link to="/terms" className="underline">terms</Link> and <Link to="/guidelines" className="underline">community guidelines</Link>.</p>
      <p className="mt-6 text-center text-sm text-muted">Already have an account? <Link to="/sign-in" className="font-medium text-text underline">Sign in</Link></p>
    </>
  );
}

export function CheckEmailPage() {
  const { user } = useAuth();
  const [cool, setCool] = useState(0);
  useEffect(() => {
    if (!cool) return;
    const t = setTimeout(() => setCool((c) => c - 1), 1000);
    return () => clearTimeout(t);
  }, [cool]);
  const masked = user?.email.replace(/^(.)[^@]*/, '$1•••') ?? 'your inbox';
  return (
    <>
      <title>Check your email · DevCommons</title>
      <h1 className="text-2xl">Check your email</h1>
      <p className="mt-3 text-sm">We sent a verification link to <span className="font-mono">{masked}</span>. You can browse while you wait; posting unlocks once you verify.</p>
      <div className="mt-6 flex flex-col gap-2">
        <Button disabled={cool > 0} onClick={async () => { const r = await resendVerification(); (r.ok ? toast.success : toast.error)(r.message); if (r.ok) setCool(60); }}>{cool ? `Resend in ${cool}s` : 'Resend email'}</Button>
        <Link to="/" className="text-center text-sm underline">Continue browsing</Link>
      </div>
    </>
  );
}

export function VerifyEmailPage() {
  const [sp] = useSearchParams();
  const token = useRef(sp.get('token'));
  const [state, setState] = useState<'working' | 'ok' | 'bad'>('working');
  useEffect(() => {
    history.replaceState(null, '', '/verify-email');
    if (!token.current) { setState('bad'); return; }
    authFetch('/api/auth/verify-email', { method: 'POST', body: JSON.stringify({ token: token.current }) }).then((r) => setState(r.ok ? 'ok' : 'bad')).catch(() => setState('bad'));
  }, []);
  return (
    <>
      <title>Verify email · DevCommons</title>
      {state === 'working' && <p className="text-sm text-muted">Verifying…</p>}
      {state === 'ok' && <><h1 className="text-2xl">Email verified</h1><p className="mt-2 text-sm text-muted">You can post, review and use AI now.</p><Link to="/" className="mt-6 inline-flex h-10 items-center rounded-[6px] bg-text px-4 text-sm font-medium text-bg">Continue</Link></>}
      {state === 'bad' && <><h1 className="text-2xl">This link is invalid or expired</h1><p className="mt-2 text-sm text-muted">Sign in and use “Resend email” in the banner to get a new one.</p><Link to="/sign-in" className="mt-6 inline-flex text-sm underline">Sign in</Link></>}
    </>
  );
}

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  return (
    <>
      <title>Reset password · DevCommons</title>
      <h1 className="text-2xl">Reset your password</h1>
      {sent ? (
        <p className="mt-3 text-sm" role="status">If an account exists for that email, we've sent a reset link.</p>
      ) : (
        <form className="mt-6 space-y-4" onSubmit={async (e) => { e.preventDefault(); await authFetch('/api/auth/forgot-password', { method: 'POST', body: JSON.stringify({ email }) }).catch(() => undefined); setSent(true); }}>
          <Field label="Email" id="fp-email"><input id="fp-email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} className={cn(fieldClass, 'h-10')} required /></Field>
          <Button type="submit" variant="primary" size="lg" className="w-full">Send reset link</Button>
        </form>
      )}
      <p className="mt-6 text-center text-sm"><Link to="/sign-in" className="underline">Back to sign in</Link></p>
    </>
  );
}

export function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  if (status === 'loading') return <div className="mx-auto max-w-[1200px] px-4 py-10" aria-busy="true"><div className="h-8 w-1/3 animate-pulse rounded bg-surface-2" /></div>;
  if (status === 'signed_out') return <Navigate to={`/sign-in?next=${encodeURIComponent(location.pathname + location.search)}`} replace />;
  return <>{children}</>;
}

export function ResetPasswordPage() {
  const [sp] = useSearchParams();
  const token = useRef(sp.get('token'));
  const [pw, setPw] = useState('');
  const [confirm, setConfirm] = useState('');
  const [state, setState] = useState<'form' | 'done' | 'bad'>('form');
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    history.replaceState(null, '', '/reset-password');
    if (!token.current) setState('bad');
  }, []);
  return (
    <>
      <title>Choose a new password · DevCommons</title>
      {state === 'done' ? (
        <><h1 className="text-2xl">Password updated</h1><p className="mt-2 text-sm text-muted">Sign in with your new password. All other sessions were signed out.</p><Link to="/sign-in" className="mt-6 inline-flex h-10 items-center rounded-[6px] bg-text px-4 text-sm font-medium text-bg">Sign in</Link></>
      ) : state === 'bad' ? (
        <><h1 className="text-2xl">This link is invalid or expired</h1><Link to="/forgot-password" className="mt-4 inline-flex text-sm underline">Request a new reset link</Link></>
      ) : (
        <>
          <h1 className="text-2xl">Choose a new password</h1>
          <form className="mt-6 space-y-4" onSubmit={async (e) => {
            e.preventDefault();
            if (pw !== confirm) { setErr("Passwords don't match."); return; }
            setBusy(true); setErr(null);
            const r = await authFetch('/api/auth/reset-password', { method: 'POST', body: JSON.stringify({ token: token.current, new_password: pw }) }).catch(() => null);
            setBusy(false);
            if (r?.ok) setState('done');
            else {
              const j = await r?.json().catch(() => null);
              if (j?.error?.code === 'invalid_token') setState('bad');
              else setErr(j?.error?.details?.fields?.new_password ?? j?.error?.message ?? 'Could not reset the password.');
            }
          }}>
            <Field label="New password" id="rp-new" hint="At least 10 characters. Common passwords are rejected."><PasswordInput id="rp-new" value={pw} onChange={setPw} autoComplete="new-password" /></Field>
            <Field label="Confirm new password" id="rp-confirm" error={err ?? undefined}><PasswordInput id="rp-confirm" value={confirm} onChange={setConfirm} autoComplete="new-password" invalid={!!err} /></Field>
            <Button type="submit" variant="primary" size="lg" className="w-full" disabled={busy}>{busy ? 'Saving…' : 'Set new password'}</Button>
          </form>
        </>
      )}
    </>
  );
}


/** Landing page after GitHub/Google. The backend already set the refresh cookie; AuthProvider's startup refresh signs us in. */
export function AuthCallbackPage() {
  const { status, user } = useAuth();
  const [sp] = useSearchParams();
  const navigate = useNavigate();
  const done = useRef(false);
  const provider = PROVIDER_LABEL[sp.get('provider') as Provider] ?? 'your account';

  useEffect(() => {
    if (status !== 'signed_in' || done.current) return;
    done.current = true;
    if (sp.get('password_removed'))
      toast.warning('Your email is now verified. The old password on this account was removed for your security. Set a new one in Settings → Account if you want one.', { duration: 12_000 });
    if (sp.get('new'))
      toast.success(`Welcome to DevCommons, ${user?.display_name ?? ''}! Your username is @${user?.username}.`, {
        duration: 10_000,
        action: { label: 'Change it', onClick: () => navigate('/settings/profile') },
      });
    navigate(sanitizeNext(sp.get('next')), { replace: true });
  }, [status, sp, user, navigate]);

  if (status === 'signed_out')
    return (
      <>
        <title>Sign-in didn't finish · DevCommons</title>
        <h1 className="text-2xl">Sign-in didn't finish</h1>
        <p className="mt-3 text-sm">We couldn't start your session after {provider}. Your browser may be blocking cookies for this site, or the app is open on a different address than the one you signed in from.</p>
        <Link to="/sign-in" className="mt-6 inline-flex h-10 w-full items-center justify-center rounded-[6px] bg-text text-sm font-medium text-bg">Back to sign in</Link>
      </>
    );
  return (
    <>
      <title>Signing in · DevCommons</title>
      <p className="py-6 text-center text-sm text-muted" role="status">Signing you in with {provider}…</p>
    </>
  );
}
