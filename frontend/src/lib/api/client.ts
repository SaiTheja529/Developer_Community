import { getAccessToken, refreshSession } from '@/features/auth/session';

export const API_BASE = import.meta.env.VITE_API_BASE_URL || window.location.origin;

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: Record<string, unknown>,
    public requestId?: string,
    public retryAfter?: number,
  ) {
    super(message);
  }
}

type Query = Record<string, unknown>;

export function buildUrl(path: string, query?: Query) {
  const url = new URL(path, API_BASE);
  for (const [k, v] of Object.entries(query ?? {})) {
    if (v === undefined || v === null || v === '' || v === false || (Array.isArray(v) && v.length === 0)) continue;
    url.searchParams.set(k, Array.isArray(v) ? v.join(',') : String(v));
  }
  return url;
}

export async function toApiError(res: Response): Promise<ApiError> {
  const json = await res.json().catch(() => null);
  const e = json?.error;
  const ra = Number(res.headers.get('Retry-After'));
  return new ApiError(res.status, e?.code ?? 'internal_error', e?.message ?? 'Something went wrong.', e?.details, e?.request_id, Number.isFinite(ra) ? ra : undefined);
}

export async function apiFetch<T>(path: string, init: Omit<RequestInit, 'body'> & { query?: Query; body?: unknown } = {}): Promise<T> {
  const { query, body, ...rest } = init;
  const url = buildUrl(path, query);
  const send = () => {
    const token = getAccessToken();
    return fetch(url, {
      ...rest,
      body: body === undefined ? undefined : JSON.stringify(body),
      headers: {
        Accept: 'application/json',
        ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...rest.headers,
      },
    });
  };
  let res = await send();
  if (res.status === 401 && getAccessToken() !== null && (await refreshSession())) res = await send();
  if (res.status === 204) return undefined as T;
  if (!res.ok) throw await toApiError(res);
  return (await res.json()) as T;
}

/** Unwraps the `{data}` envelope. */
export const getData = async <T,>(path: string, query?: Query) => (await apiFetch<{ data: T }>(path, { query })).data;
