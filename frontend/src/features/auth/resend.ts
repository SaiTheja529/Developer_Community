import { apiFetch, ApiError } from '@/lib/api/client';

/**
 * Asks the API to send a new verification email.
 * Uses apiFetch (not authFetch) because the endpoint needs the Bearer access token.
 * Returns { ok, message } so every caller shows the same wording.
 */
export async function resendVerification(): Promise<{ ok: boolean; message: string }> {
  try {
    await apiFetch('/api/auth/resend-verification', { method: 'POST' });
    return { ok: true, message: 'Verification email sent. Check your inbox.' };
  } catch (e) {
    if (e instanceof ApiError) {
      if (e.status === 409) return { ok: false, message: 'Your email is already verified. Reload the page.' };
      if (e.status === 429) return { ok: false, message: 'You can resend 3 times an hour. Try again later.' };
      if (e.status === 401) return { ok: false, message: 'Your session expired. Sign in again to resend.' };
    }
    return { ok: false, message: 'Could not send right now. Try again later.' };
  }
}
