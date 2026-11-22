import { formatDistanceToNowStrict, format } from 'date-fns';

export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return '';
  const d = new Date(iso);
  const diff = Date.now() - d.getTime();
  if (diff < 60_000) return 'just now';
  const s = formatDistanceToNowStrict(d);
  return (
    s
      .replace(/ seconds?/, 's')
      .replace(/ minutes?/, 'm')
      .replace(/ hours?/, 'h')
      .replace(/ days?/, 'd')
      .replace(/ months?/, 'mo')
      .replace(/ years?/, 'y') + ' ago'
  );
}

export const fullDate = (iso: string) => format(new Date(iso), 'PPP p');
export const monthYear = (iso: string) => format(new Date(iso), 'MMM yyyy');

export function compact(n: number | null | undefined): string {
  if (n == null) return '–';
  if (n < 1000) return String(n);
  if (n < 1_000_000) return `${(n / 1000).toFixed(n < 10_000 ? 1 : 0).replace(/\.0$/, '')}k`;
  return `${(n / 1_000_000).toFixed(1).replace(/\.0$/, '')}M`;
}

/** Only http(s) URLs are ever rendered as links (spec §16). */
export function safeUrl(u: string | null | undefined): string | null {
  if (!u) return null;
  try {
    const url = new URL(u);
    return url.protocol === 'http:' || url.protocol === 'https:' ? url.toString() : null;
  } catch {
    return null;
  }
}

export function domainOf(u: string): string {
  try {
    return new URL(u).hostname.replace(/^www\./, '');
  } catch {
    return u;
  }
}

/** `next` must be a same-origin relative path (spec §8.4). */
export function sanitizeNext(next: string | null | undefined): string {
  if (!next || !next.startsWith('/') || next.startsWith('//') || next.startsWith('/\\')) return '/';
  return next;
}

export const humanize = (s: string) => s.replace(/[_-]+/g, ' ').replace(/^\w/, (c) => c.toUpperCase());
