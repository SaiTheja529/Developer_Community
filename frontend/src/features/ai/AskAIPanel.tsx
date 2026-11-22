import { useEffect, useRef } from 'react';
import { Link } from 'react-router';
import { ExternalLink, Sparkles, X } from 'lucide-react';
import { useAI, useSession } from './store';
import { ChatView } from './ChatView';
import { TARGET } from '@/lib/modules';

/** Non-blocking right-side sheet (spec §6.3). The page stays scrollable at ≥ lg. */
export function AskAIPanel() {
  const { open, context } = useAI((s) => s.panel);
  const close = useAI((s) => s.closePanel);
  const s = useSession('panel');
  const ref = useRef<HTMLElement>(null);

  useEffect(() => {
    if (!open) return;
    ref.current?.querySelector<HTMLElement>('textarea, button')?.focus();
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && close();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, close]);

  if (!open) return null;
  return (
    <aside
      ref={ref}
      aria-label="Ask AI"
      className="fixed inset-0 z-50 flex flex-col border-l border-border bg-surface shadow-[var(--shadow-dialog)] md:inset-y-0 md:right-0 md:left-auto md:w-[420px]"
    >
      <header className="stripe-ai flex items-start justify-between gap-2 border-b border-border px-4 py-3">
        <div className="min-w-0">
          <p className="flex items-center gap-1.5 font-semibold"><Sparkles size={15} className="text-ai" aria-hidden /> Ask AI</p>
          {context ? (
            <p className="mt-1 truncate font-mono text-xs text-muted">Context: {TARGET[context.type].label} · {context.title}</p>
          ) : (
            <p className="mt-1 font-mono text-xs text-muted">No page context</p>
          )}
          {s.conversationId && (
            <Link to={`/ai/c/${s.conversationId}`} onClick={close} className="mt-1 inline-flex items-center gap-1 text-xs text-ai hover:underline">
              Open in AI Workspace <ExternalLink size={11} aria-hidden />
            </Link>
          )}
        </div>
        <button type="button" onClick={close} className="grid size-9 cursor-pointer place-items-center rounded-[6px] hover:bg-surface-2" aria-label="Close Ask AI panel">
          <X size={17} />
        </button>
      </header>
      <ChatView sessionKey="panel" compact />
    </aside>
  );
}

export function AskAIButton({ context }: { context: { type: keyof typeof TARGET; id: string; title: string } }) {
  const openPanel = useAI((s) => s.openPanel);
  return (
    <button
      type="button"
      onClick={() => openPanel(context)}
      className="inline-flex h-9 cursor-pointer items-center gap-1.5 rounded-[6px] border border-dashed border-ai bg-ai-soft px-3 text-sm font-medium text-ai"
    >
      <Sparkles size={15} aria-hidden /> Ask AI about this
    </button>
  );
}
