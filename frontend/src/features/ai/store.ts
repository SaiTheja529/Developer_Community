import { create } from 'zustand';
import { streamSSE } from '@/lib/api/sse';
import { ApiError } from '@/lib/api/client';
import type { ChatEvent, ChatMessage, ContextType } from '@/lib/api/types';
import { queryClient } from '@/lib/queryClient';
import { qk } from '@/lib/queryKeys';

export interface ChatContext { type: ContextType; id: string; title: string }
export interface ChatSession {
  conversationId: string | null;
  title: string | null;
  context: ChatContext | null;
  messages: ChatMessage[];
  streaming: boolean;
  /** Text for the polite live region: only "Response complete" or the error (spec §11.4). */
  announce: string;
  blocking: null | { code: string; message: string };
}

const empty = (context: ChatContext | null = null): ChatSession => ({
  conversationId: null, title: null, context, messages: [], streaming: false, announce: '', blocking: null,
});

interface AIState {
  sessions: Record<string, ChatSession>;
  panel: { open: boolean; context: ChatContext | null };
  openPanel(context: ChatContext | null): void;
  closePanel(): void;
  reset(key: string, context?: ChatContext | null): void;
  load(key: string, data: { id: string; title: string | null; context: ChatContext | null; messages: ChatMessage[] }): void;
  send(key: string, text: string): Promise<void>;
  regenerate(key: string): Promise<void>;
  stop(key: string): void;
}

const controllers = new Map<string, AbortController>();
const tmpId = () => `tmp-${Math.random().toString(36).slice(2)}`;

export const useAI = create<AIState>((set, get) => {
  const patch = (key: string, fn: (s: ChatSession) => Partial<ChatSession>) =>
    set((st) => {
      const cur = st.sessions[key] ?? empty();
      return { sessions: { ...st.sessions, [key]: { ...cur, ...fn(cur) } } };
    });
  const patchMsg = (key: string, id: string, fn: (m: ChatMessage) => Partial<ChatMessage>) =>
    patch(key, (s) => ({ messages: s.messages.map((m) => (m.id === id ? { ...m, ...fn(m) } : m)) }));

  async function run(key: string, path: string, body: unknown, assistantTmp: string, userTmp?: string) {
    const ctrl = new AbortController();
    controllers.set(key, ctrl);
    let assistantId = assistantTmp;
    let buffer = '';
    let raf = 0;
    const flush = () => {
      raf = 0;
      if (!buffer) return;
      const chunk = buffer;
      buffer = '';
      patchMsg(key, assistantId, (m) => ({ content: m.content + chunk }));
    };
    const onEvent = (e: ChatEvent) => {
      switch (e.event) {
        case 'meta': {
          const realA = e.data.assistant_message_id;
          patch(key, (s) => ({
            conversationId: e.data.conversation_id,
            messages: s.messages.map((m) =>
              m.id === assistantId ? { ...m, id: realA, context_sources: e.data.context_sources } : userTmp && m.id === userTmp ? { ...m, id: e.data.user_message_id } : m,
            ),
          }));
          assistantId = realA;
          break;
        }
        case 'delta':
          buffer += e.data.text;
          if (!raf) raf = requestAnimationFrame(flush);
          break;
        case 'done':
          cancelAnimationFrame(raf);
          flush();
          patchMsg(key, assistantId, () => ({ status: 'complete' }));
          patch(key, (s) => ({ streaming: false, announce: 'Response complete', title: e.data.conversation_title ?? s.title }));
          void queryClient.invalidateQueries({ queryKey: qk.conversations });
          void queryClient.invalidateQueries({ queryKey: qk.aiStatus });
          break;
        case 'error':
          cancelAnimationFrame(raf);
          flush();
          patchMsg(key, assistantId, () => ({ status: 'error', error: e.data.message }));
          patch(key, () => ({ streaming: false, announce: e.data.message }));
          break;
      }
    };
    try {
      await streamSSE(path, body, { signal: ctrl.signal, onEvent });
    } catch (err) {
      cancelAnimationFrame(raf);
      flush();
      if (ctrl.signal.aborted) {
        patchMsg(key, assistantId, () => ({ status: 'cancelled' }));
        patch(key, () => ({ streaming: false, announce: 'Stopped' }));
      } else if (err instanceof ApiError && ['ai_quota_exceeded', 'ai_unavailable', 'email_not_verified', 'unauthenticated'].includes(err.code)) {
        // Request never reached the model: drop the placeholders and show a blocking card.
        patch(key, (s) => ({
          streaming: false,
          messages: s.messages.filter((m) => m.id !== assistantId && m.id !== userTmp),
          blocking: { code: err.code, message: err.message },
          announce: err.message,
        }));
      } else {
        const msg = err instanceof ApiError ? err.message : 'Connection lost. Your message was saved. Regenerate to try again.';
        patchMsg(key, assistantId, () => ({ status: 'error', error: msg }));
        patch(key, () => ({ streaming: false, announce: msg }));
      }
    } finally {
      controllers.delete(key);
    }
  }

  return {
    sessions: {},
    panel: { open: false, context: null },
    openPanel: (context) => {
      const cur = get().sessions.panel;
      const same = cur && cur.context?.id === context?.id && cur.context?.type === context?.type;
      if (!same && !cur?.streaming) set((st) => ({ sessions: { ...st.sessions, panel: empty(context) } }));
      set({ panel: { open: true, context } });
    },
    closePanel: () => set((st) => ({ panel: { ...st.panel, open: false } })),
    reset: (key, context = null) => {
      controllers.get(key)?.abort();
      set((st) => ({ sessions: { ...st.sessions, [key]: empty(context) } }));
    },
    load: (key, d) =>
      set((st) => ({
        sessions: {
          ...st.sessions,
          [key]: { ...empty(d.context), conversationId: d.id, title: d.title, messages: d.messages },
        },
      })),
    send: async (key, text) => {
      const s = get().sessions[key] ?? empty();
      if (s.streaming || !text.trim()) return;
      const now = new Date().toISOString();
      const u: ChatMessage = { id: tmpId(), role: 'user', content: text, status: 'complete', created_at: now };
      const a: ChatMessage = { id: tmpId(), role: 'assistant', content: '', status: 'streaming', created_at: now };
      patch(key, (x) => ({ messages: [...x.messages, u, a], streaming: true, announce: '', blocking: null }));
      const body: Record<string, unknown> = { conversation_id: s.conversationId, message: text };
      if (!s.conversationId && s.context) body.context = { type: s.context.type, id: s.context.id };
      await run(key, '/api/ai/chat', body, a.id, u.id);
    },
    regenerate: async (key) => {
      const s = get().sessions[key];
      if (!s?.conversationId || s.streaming) return;
      const lastA = [...s.messages].reverse().find((m) => m.role === 'assistant');
      const a: ChatMessage = { id: tmpId(), role: 'assistant', content: '', status: 'streaming', created_at: new Date().toISOString() };
      patch(key, (x) => ({ messages: [...x.messages.filter((m) => m.id !== lastA?.id), a], streaming: true, announce: '' }));
      await run(key, `/api/ai/conversations/${s.conversationId}/regenerate`, {}, a.id);
    },
    stop: (key) => controllers.get(key)?.abort(),
  };
});

export const useSession = (key: string) => useAI((s) => s.sessions[key] ?? EMPTY);
const EMPTY = empty();
