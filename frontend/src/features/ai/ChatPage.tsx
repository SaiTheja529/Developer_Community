import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { isToday, isYesterday, subDays } from 'date-fns';
import { MessageSquare, MoreHorizontal, PanelLeft, Plus, Sparkles, Wrench, Lightbulb, BookOpen, Library, Wand2, FileText } from 'lucide-react';
import * as Dropdown from '@radix-ui/react-dropdown-menu';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { apiFetch } from '@/lib/api/client';
import { useAIStatus } from '@/lib/api/ai';
import { getData } from '@/lib/api/client';
import { qk } from '@/lib/queryKeys';
import type { ConversationDetail, ConversationSummary } from '@/lib/api/types';
import { useAI, useSession } from './store';
import { ChatView } from './ChatView';
import { useAuth } from '@/features/auth/AuthProvider';
import { Skeleton } from '@/components/common/States';
import { cn } from '@/lib/cn';
import { TARGET } from '@/lib/modules';

const CTX_ICON = { harness: Wrench, idea: Lightbulb, resource: BookOpen, collection: Library } as const;

function group(list: ConversationSummary[]) {
  const g: Record<string, ConversationSummary[]> = { Today: [], Yesterday: [], 'Previous 7 days': [], Older: [] };
  const week = subDays(new Date(), 7);
  for (const c of list) {
    const d = c.last_message_at ? new Date(c.last_message_at) : new Date(0);
    if (isToday(d)) g.Today.push(c);
    else if (isYesterday(d)) g.Yesterday.push(c);
    else if (d > week) g['Previous 7 days'].push(c);
    else g.Older.push(c);
  }
  return Object.entries(g).filter(([, v]) => v.length);
}

function Sidebar({ activeId, onPick }: { activeId?: string; onPick: () => void }) {
  const { status } = useAuth();
  const [q, setQ] = useState('');
  const { data, isLoading } = useQuery({
    queryKey: qk.conversations,
    queryFn: () => getData<ConversationSummary[]>('/api/ai/conversations'),
    enabled: status === 'signed_in',
  });
  const filtered = useMemo(() => (data ?? []).filter((c) => (c.title ?? '').toLowerCase().includes(q.toLowerCase())), [data, q]);
  return (
    <div className="flex h-full flex-col">
      <div className="space-y-2 p-3">
        <Link to="/ai" onClick={onPick} className="flex h-9 items-center justify-center gap-1.5 rounded-[6px] border border-dashed border-ai bg-ai-soft text-sm font-medium text-ai">
          <Plus size={15} aria-hidden /> New chat
        </Link>
        <div className="grid grid-cols-2 gap-1.5">
          <Link to="/ai/generate" onClick={onPick} className="flex h-8 items-center justify-center gap-1 rounded-[6px] border border-border text-xs font-medium hover:bg-surface-2"><Wand2 size={13} aria-hidden /> Generate</Link>
          <Link to="/ai/drafts" onClick={onPick} className="flex h-8 items-center justify-center gap-1 rounded-[6px] border border-border text-xs font-medium hover:bg-surface-2"><FileText size={13} aria-hidden /> Drafts</Link>
        </div>
        <label className="block">
          <span className="sr-only">Search chats</span>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search chats" className="h-9 w-full rounded-[6px] border border-border bg-surface px-2.5 text-sm placeholder:text-muted" />
        </label>
      </div>
      <nav aria-label="Conversations" className="min-h-0 flex-1 overflow-y-auto px-2 pb-4">
        {isLoading && <div className="space-y-2 p-1">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-8" />)}</div>}
        {!isLoading && !filtered.length && <p className="px-2 py-4 text-sm text-muted">{q ? 'No chats match.' : 'Your chats will show up here.'}</p>}
        {group(filtered).map(([label, items]) => (
          <div key={label} className="mt-3">
            <p className="px-2 pb-1 text-xs font-medium text-muted">{label}</p>
            <ul>
              {items.map((c) => {
                const Icon = c.context ? CTX_ICON[c.context.type] : MessageSquare;
                return (
                  <li key={c.id}>
                    <Link to={`/ai/c/${c.id}`} onClick={onPick} aria-current={activeId === c.id ? 'page' : undefined} className={cn('flex items-center gap-2 rounded-[6px] px-2 py-1.5 text-sm', activeId === c.id ? 'bg-surface-2 font-medium' : 'hover:bg-surface-2')}>
                      <Icon size={14} className={c.context ? 'shrink-0 text-ai' : 'shrink-0 text-muted'} aria-label={c.context ? `${TARGET[c.context.type].label} context` : undefined} />
                      <span className="truncate">{c.title ?? 'Untitled chat'}</span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>
    </div>
  );
}

function UsageMeter() {
  const { data } = useAIStatus();
  const t = data?.today;
  if (!t) return null;
  const pct = Math.min(100, (t.tokens / t.limit_tokens) * 100);
  return (
    <Link to="/settings/ai" className="ml-auto hidden items-center gap-2 font-mono text-xs text-muted hover:text-text md:flex" title="AI usage today">
      <span className="h-1.5 w-20 overflow-hidden rounded-full bg-surface-2"><span className="block h-full rounded-full bg-ai" style={{ width: `${Math.max(pct, 1)}%` }} /></span>
      {Math.round(t.tokens / 1000)}k / {Math.round(t.limit_tokens / 1000)}k today
    </Link>
  );
}

function ConversationMenu({ id, title }: { id: string; title: string | null }) {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const item = 'flex cursor-pointer items-center gap-2 rounded-[6px] px-2.5 py-2 text-sm outline-none data-[highlighted]:bg-surface-2';
  return (
    <Dropdown.Root>
      <Dropdown.Trigger className="grid size-9 shrink-0 cursor-pointer place-items-center rounded-[6px] hover:bg-surface-2 md:ml-0" aria-label="Conversation actions"><MoreHorizontal size={16} /></Dropdown.Trigger>
      <Dropdown.Portal>
        <Dropdown.Content align="end" sideOffset={6} className="z-50 min-w-[180px] rounded-[10px] border border-border bg-surface p-1 shadow-[var(--shadow-dialog)]">
          <Dropdown.Item className={item} onSelect={async () => {
            const next = window.prompt('Rename this chat', title ?? '');
            if (!next?.trim()) return;
            await apiFetch(`/api/ai/conversations/${id}`, { method: 'PATCH', body: { title: next.trim().slice(0, 120) } });
            useAI.setState((st) => ({ sessions: { ...st.sessions, page: { ...st.sessions.page, title: next.trim() } } }));
            void qc.invalidateQueries({ queryKey: qk.conversations });
            toast.success('Renamed');
          }}>Rename</Dropdown.Item>
          <Dropdown.Item className={`${item} text-danger`} onSelect={async () => {
            if (!window.confirm('Delete this chat? It is removed from your history.')) return;
            await apiFetch(`/api/ai/conversations/${id}`, { method: 'DELETE' });
            void qc.invalidateQueries({ queryKey: qk.conversations });
            toast('Chat deleted');
            navigate('/ai');
          }}>Delete</Dropdown.Item>
        </Dropdown.Content>
      </Dropdown.Portal>
    </Dropdown.Root>
  );
}

export default function ChatPage() {
  const { conversationId } = useParams();
  const navigate = useNavigate();
  const s = useSession('page');
  const { reset, load } = useAI();
  const [drawer, setDrawer] = useState(false);

  // Fresh chat at /ai, unless a stream for a new conversation is in flight.
  useEffect(() => {
    if (!conversationId && !s.streaming) reset('page');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversationId]);

  // Once the server assigns an ID to a new chat, move the URL without remounting the stream.
  useEffect(() => {
    if (s.conversationId && s.conversationId !== conversationId) navigate(`/ai/c/${s.conversationId}`, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [s.conversationId]);

  const needsLoad = !!conversationId && s.conversationId !== conversationId;
  const { data, isLoading, error } = useQuery({
    queryKey: qk.conversation(conversationId ?? ''),
    queryFn: () => getData<ConversationDetail>(`/api/ai/conversations/${conversationId}`),
    enabled: needsLoad,
  });
  useEffect(() => {
    if (data && needsLoad) load('page', { id: data.id, title: data.title, context: data.context, messages: data.messages });
  }, [data, needsLoad, load]);

  return (
    <div className="flex h-[calc(100dvh-56px-52px)] md:h-[calc(100dvh-56px)]">
      <title>{`${s.title ?? 'AI Workspace'} · DevCommons`}</title>
      <aside className="hidden w-[260px] shrink-0 border-r border-border bg-surface md:block">
        <Sidebar activeId={conversationId} onPick={() => undefined} />
      </aside>
      {drawer && (
        <div className="fixed inset-0 z-50 md:hidden" role="dialog" aria-label="Conversations">
          <button className="absolute inset-0 bg-black/30" aria-label="Close" onClick={() => setDrawer(false)} />
          <div className="absolute inset-y-0 left-0 w-[80%] max-w-[300px] bg-surface"><Sidebar activeId={conversationId} onPick={() => setDrawer(false)} /></div>
        </div>
      )}
      <section className="stripe-ai flex min-w-0 flex-1 flex-col" aria-label="Chat">
        <header className="flex items-center gap-2 border-b border-border px-4 py-2.5 md:px-8">
          <button type="button" className="grid size-9 cursor-pointer place-items-center rounded-[6px] hover:bg-surface-2 md:hidden" onClick={() => setDrawer(true)} aria-label="Show conversations">
            <PanelLeft size={17} />
          </button>
          <Sparkles size={16} className="text-ai" aria-hidden />
          <h1 className="truncate text-[15px] font-semibold">{s.title ?? (conversationId ? 'Chat' : 'New chat')}</h1>
          {s.context && <span className="ml-1 hidden truncate rounded-[6px] bg-ai-soft px-2 py-0.5 font-mono text-xs text-ai sm:inline">Context: {TARGET[s.context.type].label} · {s.context.title}</span>}
          <UsageMeter />
          {s.conversationId && <ConversationMenu id={s.conversationId} title={s.title} />}
        </header>
        {needsLoad && isLoading ? (
          <div className="mx-auto w-full max-w-[760px] space-y-6 p-8">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-16" />)}</div>
        ) : error ? (
          <p className="p-8 text-sm text-danger" role="alert">This chat couldn't be loaded. It may have been deleted.</p>
        ) : (
          <ChatView sessionKey="page" />
        )}
      </section>
    </div>
  );
}
