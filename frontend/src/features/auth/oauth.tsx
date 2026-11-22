import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { API_BASE, apiFetch, getData } from '@/lib/api/client';
import { sanitizeNext } from '@/lib/format';
import { cn } from '@/lib/cn';

export type Provider = 'github' | 'google';
export const PROVIDER_LABEL: Record<Provider, string> = { github: 'GitHub', google: 'Google' };

/** Which social buttons to show; the backend enables a provider once its client ID and secret are set. */
export const useProviders = () =>
  useQuery({
    queryKey: ['auth', 'providers'],
    queryFn: () => getData<Record<Provider, boolean>>('/api/auth/providers'),
    staleTime: 10 * 60_000,
  });

/**
 * Full-page redirect to the backend, which redirects to GitHub/Google. The backend sends the browser
 * back to `return_to` (this frontend's origin) at /auth/callback, or /settings/account when linking.
 */
export function startOAuth(provider: Provider, opts: { next?: string | null; linkToken?: string } = {}) {
  const url = new URL(`/api/auth/oauth/${provider}/start`, API_BASE);
  url.searchParams.set('return_to', window.location.origin);
  url.searchParams.set('next', sanitizeNext(opts.next));
  if (opts.linkToken) url.searchParams.set('link', opts.linkToken);
  window.location.assign(url.toString());
}

export async function startLink(provider: Provider) {
  const r = await apiFetch<{ data: { link_token: string } }>(`/api/auth/oauth/${provider}/link`, { method: 'POST' });
  startOAuth(provider, { next: '/settings/account', linkToken: r.data.link_token });
}

/** Messages for `?oauth_error=` codes the backend redirects back with. */
export function oauthErrorMessage(code: string | null, provider?: string | null): string | null {
  if (!code) return null;
  const p = provider === 'google' ? 'Google' : provider === 'github' ? 'GitHub' : 'that provider';
  const messages: Record<string, string> = {
    cancelled: `Signing in with ${p} was cancelled.`,
    email_not_verified: `Your ${p} account has no verified email address. Verify one there first, then try again.`,
    account_suspended: 'This account is suspended.',
    account_unavailable: 'This account no longer exists.',
    provider_not_configured: `Signing in with ${p} isn't set up on this server yet.`,
    provider_error: `Signing in with ${p} failed on their side. Try again in a moment.`,
    state_expired: 'The sign-in took too long or was opened in another browser. Try again.',
    state_mismatch: "The sign-in couldn't be verified. Try again.",
    provider_already_linked: `Your account is already connected to a different ${p} account.`,
    already_linked_elsewhere: `That ${p} account is already connected to another DevCommons account.`,
    link_expired: 'The connect request expired. Try again.',
    try_again: 'Something clashed while signing in. Try again.',
  };
  return messages[code] ?? 'Sign-in failed. Try again.';
}

function GitHubMark() {
  return (
    <svg viewBox="0 0 16 16" width="18" height="18" aria-hidden fill="currentColor">
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
    </svg>
  );
}

function GoogleMark() {
  return (
    <svg viewBox="0 0 48 48" width="18" height="18" aria-hidden>
      <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z" />
      <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" />
      <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z" />
      <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z" />
    </svg>
  );
}

export const ProviderMark = ({ provider }: { provider: Provider }) => (provider === 'github' ? <GitHubMark /> : <GoogleMark />);

/** "Continue with GitHub / Google" buttons, plus an "or" divider when there's a form below. */
export function SocialSignIn({ next, divider = true }: { next?: string | null; divider?: boolean }) {
  const { data } = useProviders();
  const [going, setGoing] = useState<Provider | null>(null);
  const enabled = (['github', 'google'] as Provider[]).filter((p) => data?.[p]);
  if (!enabled.length) return null;
  return (
    <div className="mt-6">
      <div className="grid gap-2">
        {enabled.map((p) => (
          <button
            key={p}
            type="button"
            disabled={going !== null}
            onClick={() => { setGoing(p); startOAuth(p, { next }); }}
            className={cn(
              'flex h-10 w-full cursor-pointer items-center justify-center gap-2.5 rounded-[6px] border border-border bg-bg text-sm font-medium transition-colors hover:bg-surface-2 disabled:cursor-wait disabled:opacity-70',
            )}
          >
            <ProviderMark provider={p} />
            {going === p ? `Opening ${PROVIDER_LABEL[p]}…` : `Continue with ${PROVIDER_LABEL[p]}`}
          </button>
        ))}
      </div>
      {divider && (
        <div className="mt-6 flex items-center gap-3 text-xs text-muted" role="separator">
          <span className="h-px flex-1 bg-border" /> or with email <span className="h-px flex-1 bg-border" />
        </div>
      )}
    </div>
  );
}
