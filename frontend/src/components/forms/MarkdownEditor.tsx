import { useEffect, useRef, useState } from 'react';
import * as Dropdown from '@radix-ui/react-dropdown-menu';
import * as Dialog from '@radix-ui/react-dialog';
import { Bold, Code, Heading2, Italic, Link2, List, Sparkles } from 'lucide-react';
import { apiFetch, ApiError } from '@/lib/api/client';
import { MarkdownView } from '@/components/common/MarkdownView';
import { Button } from '@/components/common/Button';
import { inputClass } from './Field';
import { cn } from '@/lib/cn';
import { useAuth } from '@/features/auth/AuthProvider';

type Action = 'clarity' | 'rewrite' | 'expand' | 'organize' | 'setup_steps' | 'complete_proposal' | 'architecture' | 'custom';
const ACTIONS: { a: Action; label: string; only?: string }[] = [
  { a: 'clarity', label: 'Improve clarity' },
  { a: 'rewrite', label: 'Rewrite' },
  { a: 'expand', label: 'Expand' },
  { a: 'organize', label: 'Organize into sections' },
  { a: 'setup_steps', label: 'Improve setup steps', only: 'setup' },
  { a: 'complete_proposal', label: 'Complete the proposal', only: 'idea' },
  { a: 'architecture', label: 'Refine architecture explanation', only: 'architecture' },
];

interface Props {
  id: string; value: string; onChange: (v: string) => void; max: number; rows?: number;
  /** Backend field name sent to /api/ai/refine. */
  field: string;
  /** Which specialised actions apply: 'setup' | 'idea' | 'architecture'. */
  kind?: string;
  onAIApplied?: () => void;
  invalid?: boolean; describedBy?: string; placeholder?: string;
}

/** Write/Preview tabs, toolbar, counter (rendered by Field), and "Improve with AI" with a compare dialog (spec §10, §11.5). */
export function MarkdownEditor({ id, value, onChange, max, rows = 8, field, kind, onAIApplied, invalid, describedBy, placeholder }: Props) {
  const [tab, setTab] = useState<'write' | 'preview'>('write');
  const ta = useRef<HTMLTextAreaElement>(null);
  const [compare, setCompare] = useState<null | { action: Action; instruction?: string }>(null);
  const [customOpen, setCustomOpen] = useState(false);
  const [instruction, setInstruction] = useState('');
  const { status, isVerified } = useAuth();

  const wrap = (before: string, after = before, placeholderText = 'text') => {
    const el = ta.current;
    if (!el) return;
    const { selectionStart: s, selectionEnd: e } = el;
    const sel = value.slice(s, e) || placeholderText;
    onChange(value.slice(0, s) + before + sel + after + value.slice(e));
    requestAnimationFrame(() => { el.focus(); el.setSelectionRange(s + before.length, s + before.length + sel.length); });
  };
  const linePrefix = (prefix: string) => {
    const el = ta.current;
    if (!el) return;
    const s = value.lastIndexOf('\n', el.selectionStart - 1) + 1;
    onChange(value.slice(0, s) + prefix + value.slice(s));
    requestAnimationFrame(() => el.focus());
  };
  const tool = 'grid size-8 cursor-pointer place-items-center rounded-[6px] text-muted hover:bg-surface-2 hover:text-text';
  const aiDisabled = !value.trim() || status !== 'signed_in' || !isVerified;

  return (
    <div className={cn('rounded-[6px] border bg-surface', invalid ? 'border-danger' : 'border-border')}>
      <div className="flex flex-wrap items-center gap-1 border-b border-border px-1.5 py-1">
        <div role="tablist" className="flex">
          {(['write', 'preview'] as const).map((t) => (
            <button key={t} type="button" role="tab" aria-selected={tab === t} onClick={() => setTab(t)} className={cn('h-8 cursor-pointer rounded-[6px] px-2.5 text-sm capitalize', tab === t ? 'bg-surface-2 font-medium' : 'text-muted hover:text-text')}>{t}</button>
          ))}
        </div>
        {tab === 'write' && (
          <div className="ml-1 flex items-center border-l border-border pl-1" aria-label="Formatting">
            <button type="button" className={tool} onClick={() => wrap('**')} aria-label="Bold"><Bold size={15} /></button>
            <button type="button" className={tool} onClick={() => wrap('_')} aria-label="Italic"><Italic size={15} /></button>
            <button type="button" className={tool} onClick={() => wrap('`')} aria-label="Code"><Code size={15} /></button>
            <button type="button" className={tool} onClick={() => wrap('[', '](https://)', 'link text')} aria-label="Link"><Link2 size={15} /></button>
            <button type="button" className={tool} onClick={() => linePrefix('- ')} aria-label="List"><List size={15} /></button>
            <button type="button" className={tool} onClick={() => linePrefix('## ')} aria-label="Heading"><Heading2 size={15} /></button>
          </div>
        )}
        <div className="ml-auto">
          <Dropdown.Root>
            <Dropdown.Trigger
              disabled={aiDisabled}
              title={!value.trim() ? 'Write something first, then ask AI to improve it' : status !== 'signed_in' ? 'Sign in to use AI' : !isVerified ? 'Verify your email to use AI' : undefined}
              className="inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-[6px] border border-dashed border-ai px-2.5 text-sm font-medium text-ai disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Sparkles size={14} aria-hidden /> Improve with AI
            </Dropdown.Trigger>
            <Dropdown.Portal>
              <Dropdown.Content align="end" sideOffset={4} className="z-50 min-w-[230px] rounded-[10px] border border-border bg-surface p-1 shadow-[var(--shadow-dialog)]">
                {ACTIONS.filter((x) => !x.only || x.only === kind).map((x) => (
                  <Dropdown.Item key={x.a} onSelect={() => setCompare({ action: x.a })} className="cursor-pointer rounded-[6px] px-2.5 py-2 text-sm outline-none data-[highlighted]:bg-surface-2">{x.label}</Dropdown.Item>
                ))}
                <Dropdown.Separator className="my-1 h-px bg-border" />
                <Dropdown.Item onSelect={() => setCustomOpen(true)} className="cursor-pointer rounded-[6px] px-2.5 py-2 text-sm outline-none data-[highlighted]:bg-surface-2">Custom instruction…</Dropdown.Item>
              </Dropdown.Content>
            </Dropdown.Portal>
          </Dropdown.Root>
        </div>
      </div>
      {tab === 'write' ? (
        <textarea
          ref={ta}
          id={id}
          rows={rows}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          aria-invalid={invalid}
          aria-describedby={describedBy}
          placeholder={placeholder}
          className="block w-full resize-y rounded-b-[6px] bg-transparent px-3 py-2.5 font-mono text-[14px] leading-relaxed outline-none placeholder:font-sans placeholder:text-muted"
        />
      ) : (
        <div className="min-h-32 px-4 py-3">{value.trim() ? <MarkdownView source={value} /> : <p className="text-sm text-muted">Nothing to preview.</p>}</div>
      )}
      <span className="sr-only">Maximum {max} characters</span>

      <Dialog.Root open={customOpen} onOpenChange={setCustomOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-black/30" />
          <Dialog.Content className="fixed top-1/2 left-1/2 z-50 w-[min(94vw,460px)] -translate-x-1/2 -translate-y-1/2 rounded-[14px] border border-border bg-surface p-6 shadow-[var(--shadow-dialog)]">
            <Dialog.Title className="text-lg font-semibold">Custom instruction</Dialog.Title>
            <Dialog.Description className="mt-1 text-sm text-muted">Tell AI how to change this text. You'll compare before anything is replaced.</Dialog.Description>
            <form onSubmit={(e) => { e.preventDefault(); if (!instruction.trim()) return; setCustomOpen(false); setCompare({ action: 'custom', instruction: instruction.trim() }); }}>
              <input autoFocus value={instruction} onChange={(e) => setInstruction(e.target.value)} maxLength={500} placeholder="e.g. Make it friendlier for beginners" className={cn(inputClass, 'mt-4 h-10')} />
              <div className="mt-4 flex justify-end gap-2">
                <Dialog.Close asChild><Button type="button">Cancel</Button></Dialog.Close>
                <Button type="submit" variant="ai">Suggest</Button>
              </div>
            </form>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      {compare && (
        <CompareDialog
          original={value}
          field={field}
          action={compare.action}
          instruction={compare.instruction}
          onClose={() => setCompare(null)}
          onApply={(text, mode) => {
            onChange(mode === 'replace' ? text : `${value}\n\n${text}`);
            onAIApplied?.();
            setCompare(null);
          }}
        />
      )}
    </div>
  );
}

function CompareDialog({ original, field, action, instruction, onClose, onApply }: {
  original: string; field: string; action: Action; instruction?: string; onClose: () => void; onApply: (text: string, mode: 'replace' | 'insert') => void;
}) {
  const [state, setState] = useState<{ loading: boolean; text?: string; summary?: string; error?: string }>({ loading: true });
  const run = useRef(0);
  const go = async () => {
    const my = ++run.current;
    setState({ loading: true });
    try {
      const r = await apiFetch<{ data: { text: string; change_summary: string } }>('/api/ai/refine', { method: 'POST', body: { text: original, action, instruction, field } });
      if (my === run.current) setState({ loading: false, text: r.data.text, summary: r.data.change_summary });
    } catch (e) {
      if (my === run.current) setState({ loading: false, error: e instanceof ApiError ? (e.code === 'ai_quota_exceeded' ? "You've reached today's AI limit." : e.message) : 'AI is unavailable right now.' });
    }
  };
  const started = useRef(false);
  useEffect(() => {
    if (started.current) return; // StrictMode re-runs effects; send the AI request once.
    started.current = true;
    void go();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <Dialog.Root open onOpenChange={(o) => !o && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/30" />
        <Dialog.Content className="fixed top-1/2 left-1/2 z-50 flex max-h-[90dvh] w-[min(96vw,1000px)] -translate-x-1/2 -translate-y-1/2 flex-col rounded-[14px] border border-border bg-surface shadow-[var(--shadow-dialog)]">
          <div className="border-b border-border px-6 py-4">
            <Dialog.Title className="flex items-center gap-2 text-lg font-semibold"><Sparkles size={17} className="text-ai" aria-hidden /> Compare AI suggestion</Dialog.Title>
            <Dialog.Description className="mt-0.5 text-sm text-muted">Nothing changes until you choose Replace or Insert below.</Dialog.Description>
          </div>
          <div className="grid min-h-0 flex-1 gap-4 overflow-y-auto p-6 md:grid-cols-2">
            <div className="min-w-0">
              <p className="mb-2 text-xs font-medium text-muted">Original</p>
              <div className="rounded-[10px] border border-border bg-surface-2 p-3 font-mono text-[13px] whitespace-pre-wrap">{original}</div>
            </div>
            <div className="min-w-0">
              <p className="mb-2 font-mono text-xs text-ai">AI-generated suggestion</p>
              <div className="ai-surface min-h-24 rounded-[10px] p-3 font-mono text-[13px] whitespace-pre-wrap" aria-live="polite" aria-busy={state.loading}>
                {state.loading ? <span className="text-muted">Working on it… this usually takes a few seconds.</span> : state.error ? <span className="text-danger">{state.error}</span> : state.text}
              </div>
              {state.summary && <p className="mt-2 text-sm text-muted"><span className="font-medium text-text">What changed:</span> {state.summary}</p>}
            </div>
          </div>
          <div className="flex flex-wrap justify-end gap-2 border-t border-border px-6 py-4">
            <Button type="button" onClick={onClose}>Cancel</Button>
            <Button type="button" onClick={() => void go()} disabled={state.loading}>Try again</Button>
            <Button type="button" disabled={!state.text} onClick={() => state.text && onApply(state.text, 'insert')}>Insert below</Button>
            <Button type="button" variant="primary" disabled={!state.text} onClick={() => state.text && onApply(state.text, 'replace')}>Replace</Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
