import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router';
import { Check, ChevronRight, Copy, Minus, RotateCcw, Sparkles, Square, SendHorizonal, X, AlertTriangle, Clock } from 'lucide-react';
import { toast } from 'sonner';
import { useAI, useSession } from './store';
import type { ChatMessage, ContextSource } from '@/lib/api/types';
import { MarkdownView } from '@/components/common/MarkdownView';
import { Button } from '@/components/common/Button';
import { cn } from '@/lib/cn';
import { useAuth } from '@/features/auth/AuthProvider';
import { ReportButton } from '@/components/common/ReportDialog';

export const EXAMPLE_PROMPTS = [
  'How can I create an effective AI coding harness?',
  'Which MCP servers could be useful for a code-review workflow?',
  'What should I consider before publishing this harness?',
  'Recommend documentation for learning LangGraph.',
  'What improvements would you suggest for a project idea?',
  'Explain how PreToolUse hooks work in Claude Code.',
];

const SOURCE_ICON: Record<ContextSource['status'], typeof Check> = { included: Check, failed: X, unavailable: Minus, stale: Clock };

function ContextUsed({ sources }: { sources: ContextSource[] }) {
  const [open, setOpen] = useState(false);
  if (!sources.length) return null;
  return (
    <div className="mt-2">
      <button type="button" className="inline-flex cursor-pointer items-center gap-1 font-mono text-xs text-muted hover:text-text" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        <ChevronRight size={13} className={cn('transition-transform', open && 'rotate-90')} aria-hidden /> Context used ({sources.length})
      </button>
      {open && (
        <ul className="mt-1.5 space-y-1 pl-4 text-xs">
          {sources.map((s, i) => {
            const Icon = SOURCE_ICON[s.status];
            return (
              <li key={i} className="flex items-start gap-1.5">
                <Icon size={13} className={cn('mt-0.5 shrink-0', s.status === 'included' ? 'text-success' : s.status === 'failed' ? 'text-danger' : 'text-muted')} aria-hidden />
                <span>
                  <span className="sr-only">{s.status}: </span>
                  {s.url ? <a href={s.url} target="_blank" rel="noopener noreferrer nofollow" className="underline">{s.label}</a> : s.label}
                  {s.truncated && <span className="text-muted"> (truncated)</span>}
                  {s.reason && <span className="text-muted"> — {s.reason}</span>}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

function Message({ m, isLast, onRegenerate }: { m: ChatMessage; isLast: boolean; onRegenerate: () => void }) {
  if (m.role === 'user')
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-[14px] rounded-br-[4px] border border-border bg-surface-2 px-3.5 py-2.5 text-[15px] whitespace-pre-wrap">{m.content}</div>
      </div>
    );
  const waiting = m.status === 'streaming' && !m.content;
  return (
    <article className="flex gap-3" aria-label="AI-generated reply">
      <span className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-full bg-ai-soft text-ai" aria-hidden>
        <Sparkles size={14} />
      </span>
      <div className="min-w-0 flex-1 border-l-2 border-dashed border-ai pl-3.5">
        <p className="mb-1 font-mono text-[11px] text-ai">AI-generated</p>
        {waiting ? (
          <span className="inline-flex gap-1 py-2" aria-label="Thinking">
            {[0, 1, 2].map((i) => <span key={i} className="typing-dot size-1.5 rounded-full bg-ai" />)}
          </span>
        ) : (
          <MarkdownView source={m.content} className="text-[15px]" />
        )}
        {m.status === 'cancelled' && <p className="mt-1 font-mono text-xs text-muted">Stopped</p>}
        {m.status === 'error' && (
          <p className="mt-2 flex items-center gap-1.5 text-sm text-danger" role="alert">
            <AlertTriangle size={14} aria-hidden /> {m.error ?? 'Something went wrong.'}
          </p>
        )}
        {m.context_sources && <ContextUsed sources={m.context_sources} />}
        {m.status !== 'streaming' && (
          <div className="mt-2 flex gap-1">
            <button
              type="button"
              className="inline-flex h-7 cursor-pointer items-center gap-1 rounded-[6px] px-1.5 text-xs text-muted hover:bg-surface-2 hover:text-text"
              onClick={async () => {
                await navigator.clipboard.writeText(m.content);
                toast.success('Copied');
              }}
            >
              <Copy size={13} aria-hidden /> Copy
            </button>
            {isLast && (
              <button type="button" className="inline-flex h-7 cursor-pointer items-center gap-1 rounded-[6px] px-1.5 text-xs text-muted hover:bg-surface-2 hover:text-text" onClick={onRegenerate}>
                <RotateCcw size={13} aria-hidden /> Regenerate
              </button>
            )}
            {!m.id.startsWith('tmp-') && <ReportButton targetType="ai_message" targetId={m.id} size="sm" className="h-7 gap-1 px-1.5 text-xs font-normal text-muted hover:text-text" />}
          </div>
        )}
      </div>
    </article>
  );
}

function BlockingCard({ code, message }: { code: string; message: string }) {
  const title = code === 'ai_quota_exceeded' ? "You've reached today's AI limit." : code === 'ai_unavailable' ? 'AI is unavailable right now.' : message;
  return (
    <div className="ai-surface rounded-[10px] p-4 text-sm" role="status">
      <p className="font-medium">{title}</p>
      <p className="mt-1 text-muted">
        {code === 'ai_quota_exceeded' ? 'It resets at 00:00 UTC. Your chat history stays readable.' : code === 'ai_unavailable' ? 'The rest of DevCommons keeps working. Try again in a few minutes.' : 'Verify your email to use AI.'}
      </p>
    </div>
  );
}

export function ChatView({ sessionKey, compact = false }: { sessionKey: string; compact?: boolean }) {
  const s = useSession(sessionKey);
  const { send, stop, regenerate } = useAI();
  const { status } = useAuth();
  const [text, setText] = useState('');
  const listRef = useRef<HTMLDivElement>(null);
  const taRef = useRef<HTMLTextAreaElement>(null);
  const MAX = 8000;

  useEffect(() => {
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [s.messages]);

  useEffect(() => {
    const ta = taRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = `${Math.min(ta.scrollHeight, 200)}px`;
  }, [text]);

  if (status !== 'signed_in')
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3 p-8 text-center">
        <Sparkles className="text-ai" aria-hidden />
        <p className="max-w-xs text-sm text-muted">AI chat uses your account's daily quota, so you need to be signed in.</p>
        <Link to={`/sign-in?next=${encodeURIComponent(location.pathname)}`} className="inline-flex h-9 items-center rounded-[6px] bg-text px-3.5 text-sm font-medium text-bg">
          Sign in to use AI
        </Link>
      </div>
    );

  const submit = () => {
    if (!text.trim() || s.streaming || text.length > MAX) return;
    void send(sessionKey, text.trim());
    setText('');
  };
  const lastAssistant = [...s.messages].reverse().find((m) => m.role === 'assistant');

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div ref={listRef} className={cn('min-h-0 flex-1 overflow-y-auto', compact ? 'px-4 py-4' : 'px-4 py-6 md:px-8')}>
        <div className={cn('mx-auto flex flex-col gap-6', !compact && 'max-w-[760px]')}>
          {s.messages.length === 0 && (
            <div className="py-6">
              <p className="text-lg font-semibold">{s.context ? `Ask about ${s.context.title}` : 'What are you working on?'}</p>
              <p className="mt-1 text-sm text-muted">
                {s.context ? 'Answers use this page as context. You can see exactly what was used under each reply.' : 'Ask about harnesses, ideas, or docs. Pick a starter or write your own.'}
              </p>
              <div className={cn('mt-4 grid gap-2', !compact && 'sm:grid-cols-2')}>
                {(s.context ? ['Summarize what this does and who it is for.', 'What are the weak spots or risks?', 'How would I set this up step by step?'] : EXAMPLE_PROMPTS).map((p) => (
                  <button key={p} type="button" onClick={() => { setText(p); taRef.current?.focus(); }} className="cursor-pointer rounded-[10px] border border-border bg-surface px-3 py-2.5 text-left text-sm hover:border-ai">
                    {p}
                  </button>
                ))}
              </div>
            </div>
          )}
          {s.messages.map((m) => (
            <Message key={m.id} m={m} isLast={m.id === lastAssistant?.id && !!s.conversationId} onRegenerate={() => void regenerate(sessionKey)} />
          ))}
        </div>
      </div>
      <div aria-live="polite" className="sr-only">{s.announce}</div>
      <div className={cn('border-t border-border bg-surface', compact ? 'p-3' : 'px-4 py-3 md:px-8')}>
        <div className={cn('mx-auto', !compact && 'max-w-[760px]')}>
          {s.blocking ? (
            <BlockingCard {...s.blocking} />
          ) : (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                submit();
              }}
              className="flex items-end gap-2 rounded-[10px] border border-border bg-bg p-1.5 focus-within:border-ai"
            >
              <label htmlFor={`composer-${sessionKey}`} className="sr-only">Message</label>
              <textarea
                id={`composer-${sessionKey}`}
                ref={taRef}
                rows={1}
                value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    submit();
                  }
                }}
                placeholder="Ask about harnesses, ideas, docs…"
                className="max-h-[200px] min-h-9 flex-1 resize-none bg-transparent px-2 py-1.5 text-[15px] outline-none placeholder:text-muted"
              />
              {s.streaming ? (
                <Button type="button" variant="secondary" size="md" onClick={() => stop(sessionKey)} aria-label="Stop generating">
                  <Square size={13} fill="currentColor" aria-hidden /> Stop
                </Button>
              ) : (
                <Button type="submit" variant="primary" size="md" disabled={!text.trim() || text.length > MAX} aria-label="Send">
                  <SendHorizonal size={15} aria-hidden />
                </Button>
              )}
            </form>
          )}
          <div className="mt-1.5 flex justify-between px-1 text-xs text-muted">
            <span>AI can be wrong. Check important details.</span>
            {text.length > MAX * 0.9 && <span className={cn('font-mono', text.length > MAX && 'text-danger')}>{text.length} / {MAX}</span>}
          </div>
        </div>
      </div>
    </div>
  );
}
