/**
 * Framework-agnostic session module (spec §8.2).
 * The access token lives only in memory. The refresh token is an httpOnly cookie we never touch.
 */
import type { MeProfile } from '@/lib/api/types';

const API_BASE = import.meta.env.VITE_API_BASE_URL || window.location.origin;

let accessToken: string | null = null;
let expiresAt = 0;
let refreshing: Promise<boolean> | null = null;
let refreshTimer: number | undefined;
const listeners = new Set<(user: MeProfile | null) => void>();
const channel = typeof BroadcastChannel !== 'undefined' ? new BroadcastChannel('dc-auth') : null;

export const getAccessToken = () => accessToken;

export function onSessionUser(fn: (user: MeProfile | null) => void) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}
const emit = (u: MeProfile | null) => listeners.forEach((l) => l(u));

function scheduleRefresh() {
  window.clearTimeout(refreshTimer);
  const wait = Math.max(5_000, expiresAt - Date.now() - 60_000);
  refreshTimer = window.setTimeout(() => {
    if (document.visibilityState === 'visible') void refreshSession();
  }, wait);
}

export function setSession(token: string, expiresInSec: number, user?: MeProfile) {
  accessToken = token;
  expiresAt = Date.now() + expiresInSec * 1000;
  scheduleRefresh();
  if (user) emit(user);
}

export function clearSession(broadcast = true) {
  accessToken = null;
  expiresAt = 0;
  window.clearTimeout(refreshTimer);
  emit(null);
  if (broadcast) channel?.postMessage({ type: 'signed_out' });
}

export function authFetch(path: string, init: RequestInit = {}) {
  return fetch(new URL(path, API_BASE), {
    ...init,
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'devcommons', ...init.headers },
  });
}

async function doRefresh(): Promise<boolean> {
  try {
    for (let attempt = 0; attempt < 2; attempt++) {
      const res = await authFetch('/api/auth/refresh', { method: 'POST' });
      if (res.ok) {
        const { data } = await res.json();
        setSession(data.access_token, data.expires_in, data.user);
        return true;
      }
      if (res.status === 409) continue; // another tab rotated first
      break;
    }
  } catch {
    /* network failure: treat as signed out for now */
  }
  clearSession(false);
  return false;
}

/** Single-flight refresh, shared across tabs with Web Locks when available. */
export function refreshSession(): Promise<boolean> {
  refreshing ??= (async () => {
    try {
      return navigator.locks ? await navigator.locks.request('dc-refresh', doRefresh) : await doRefresh();
    } finally {
      refreshing = null;
    }
  })();
  return refreshing;
}

export async function ensureFreshAccessToken() {
  if (accessToken && expiresAt - Date.now() < 60_000) await refreshSession();
}

export function broadcastSignedIn() {
  channel?.postMessage({ type: 'signed_in' });
}

if (channel) {
  channel.onmessage = (e) => {
    if (e.data?.type === 'signed_out') clearSession(false);
    if (e.data?.type === 'signed_in') void refreshSession();
  };
}

document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible' && accessToken && expiresAt - Date.now() < 60_000) void refreshSession();
});
