import type { ChatEvent } from './types';
import { API_BASE, toApiError } from './client';
import { ensureFreshAccessToken, getAccessToken } from '@/features/auth/session';

/** POST + streamed body SSE parser (spec §7.7). EventSource can't send auth headers. */
export async function streamSSE(path: string, body: unknown, opts: { signal: AbortSignal; onEvent: (e: ChatEvent) => void }) {
  await ensureFreshAccessToken();
  const token = getAccessToken();
  const res = await fetch(new URL(path, API_BASE), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify(body),
    signal: opts.signal,
  });
  if (!res.ok || !res.headers.get('content-type')?.includes('text/event-stream')) throw await toApiError(res);

  const reader = res.body!.pipeThrough(new TextDecoderStream()).getReader();
  let buf = '';
  let terminal = false;
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += value.replace(/\r\n/g, '\n');
    let i: number;
    while ((i = buf.indexOf('\n\n')) !== -1) {
      const block = buf.slice(0, i);
      buf = buf.slice(i + 2);
      let event = 'message';
      const data: string[] = [];
      for (const line of block.split('\n')) {
        if (line.startsWith(':')) continue;
        if (line.startsWith('event:')) event = line.slice(6).trim();
        else if (line.startsWith('data:')) data.push(line.slice(5).trimStart());
      }
      if (!data.length) continue;
      if (event === 'done' || event === 'error') terminal = true;
      opts.onEvent({ event, data: JSON.parse(data.join('\n')) } as ChatEvent);
    }
  }
  if (!terminal) {
    opts.onEvent({ event: 'error', data: { code: 'connection_lost', message: 'Connection lost. Your message was saved. Regenerate to try again.' } });
  }
}
