import { useState } from 'react';
import { Lightbulb, Quote } from 'lucide-react';
import * as Dialog from '@radix-ui/react-dialog';
import { usePostSuggestion, useSuggestions } from '@/lib/api/queries';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { apiFetch } from '@/lib/api/client';
import type { Suggestion } from '@/lib/api/types';
import type { TargetType } from '@/lib/modules';
import { useAuthAction } from '@/hooks/useAuthAction';
import { ApiError } from '@/lib/api/client';
import { humanize } from '@/lib/format';
import { Badge, AIBadge } from '@/components/common/Badges';
import { TimeAgo, UserChip } from '@/components/common/Meta';
import { MarkdownView } from '@/components/common/MarkdownView';
import { Button } from '@/components/common/Button';
import { EmptyState, ErrorState, Skeleton } from '@/components/common/States';
import { fieldClass } from '@/components/common/FilterBar';
import { cn } from '@/lib/cn';

const STATUS_STYLE: Record<string, string> = {
  open: 'border border-border text-muted', acknowledged: 'border border-border text-text', planned: 'bg-knowledge-soft text-knowledge',
  implemented: 'bg-success-soft text-success', declined: 'border border-border text-muted line-through',
};

export function SuggestDialog({ t, id, kinds, open, onOpenChange, initial, aiAssisted }: {
  t: TargetType; id: string; kinds: string[]; open: boolean; onOpenChange: (o: boolean) => void;
  initial?: { kind?: string; title?: string; body?: string }; aiAssisted?: boolean;
}) {
  const [kind, setKind] = useState(initial?.kind ?? kinds[0]);
  const [title, setTitle] = useState(initial?.title ?? '');
  const [body, setBody] = useState(initial?.body ?? '');
  const [err, setErr] = useState<Record<string, string>>({});
  const post = usePostSuggestion(t, id);
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/30" />
        <Dialog.Content className="fixed top-1/2 left-1/2 z-50 max-h-[90dvh] w-[min(94vw,560px)] -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-[14px] border border-border bg-surface p-6 shadow-[var(--shadow-dialog)]">
          <Dialog.Title className="text-lg font-semibold">Suggest an improvement</Dialog.Title>
          <Dialog.Description className="mt-1 text-sm text-muted">The owner can mark it planned, implemented or declined.</Dialog.Description>
          {aiAssisted && <p className="ai-surface mt-3 rounded-[6px] px-3 py-2 text-sm">You're posting this as yourself. Edit it to reflect your own view. It will carry an "AI-assisted" label.</p>}
          <form
            className="mt-5 space-y-4"
            onSubmit={(e) => {
              e.preventDefault();
              post.mutate({ kind, title, body, ai_assisted: !!aiAssisted }, {
                onSuccess: () => { onOpenChange(false); setTitle(''); setBody(''); setErr({}); },
                onError: (e) => {
                  const f = e instanceof ApiError ? (e.details?.fields as Record<string, string> | undefined) : undefined;
                  setErr(f ?? { _: e instanceof ApiError ? e.message : 'Could not post.' });
                },
              });
            }}
          >
            <label className="flex flex-col gap-1.5">
              <span className="text-sm font-medium">Kind (required)</span>
              <select value={kind} onChange={(e) => setKind(e.target.value)} className={fieldClass}>
                {kinds.map((k) => <option key={k} value={k}>{humanize(k)}</option>)}
              </select>
            </label>
            <label className="flex flex-col gap-1.5">
              <span className="text-sm font-medium">Title (required)</span>
              <input value={title} onChange={(e) => setTitle(e.target.value)} className={fieldClass} aria-invalid={!!err.title} aria-describedby={err.title ? 'st-err' : undefined} />
              {err.title && <span id="st-err" className="text-sm text-danger">{err.title}</span>}
            </label>
            <label className="flex flex-col gap-1.5">
              <span className="text-sm font-medium">Details (required)</span>
              <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={5} className={cn(fieldClass, 'h-auto py-2')} aria-invalid={!!err.body} aria-describedby={err.body ? 'sb-err' : undefined} />
              {err.body && <span id="sb-err" className="text-sm text-danger">{err.body}</span>}
            </label>
            {err._ && <p role="alert" className="text-sm text-danger">{err._}</p>}
            <div className="flex justify-end gap-2">
              <Dialog.Close asChild><Button type="button">Cancel</Button></Dialog.Close>
              <Button type="submit" variant="primary" disabled={post.isPending}>{post.isPending ? 'Posting…' : 'Post suggestion'}</Button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function OwnerControls({ s, t, id }: { s: Suggestion; t: TargetType; id: string }) {
  const qc = useQueryClient();
  const [responding, setResponding] = useState(false);
  const [text, setText] = useState(s.owner_response ?? '');
  const save = async (body: Record<string, unknown>) => {
    try {
      await apiFetch(`/api/suggestions/${s.id}`, { method: 'PATCH', body });
      void qc.invalidateQueries({ queryKey: ['suggestions', t, id] });
      toast.success('Suggestion updated');
      setResponding(false);
    } catch (e) { toast.error(e instanceof ApiError ? e.message : 'Could not update.'); }
  };
  return (
    <div className="mt-3 border-t border-border pt-3">
      <div className="flex flex-wrap items-center gap-2">
        <label className="text-xs font-medium text-muted" htmlFor={`st-${s.id}`}>Status</label>
        <select id={`st-${s.id}`} value={s.status} onChange={(e) => save({ status: e.target.value })} className={cn(fieldClass, 'h-8 text-sm')}>
          {['open', 'acknowledged', 'planned', 'implemented', 'declined'].map((x) => <option key={x} value={x}>{humanize(x)}</option>)}
        </select>
        <Button size="sm" variant="ghost" onClick={() => setResponding((r) => !r)}>{s.owner_response ? 'Edit response' : 'Respond'}</Button>
      </div>
      {responding && (
        <form className="mt-2" onSubmit={(e) => { e.preventDefault(); void save({ owner_response: text.trim() || null }); }}>
          <label className="sr-only" htmlFor={`resp-${s.id}`}>Owner response</label>
          <textarea id={`resp-${s.id}`} rows={3} maxLength={2000} value={text} onChange={(e) => setText(e.target.value)} className={cn(fieldClass, 'h-auto w-full py-2')} />
          <div className="mt-2 flex justify-end gap-2"><Button size="sm" type="button" onClick={() => setResponding(false)}>Cancel</Button><Button size="sm" variant="primary" type="submit">Save response</Button></div>
        </form>
      )}
    </div>
  );
}

export function SuggestionList({ t, id, kinds, isOwner }: { t: TargetType; id: string; kinds: string[]; isOwner: boolean }) {
  const [kind, setKind] = useState<string>('');
  const [open, setOpen] = useState(false);
  const guard = useAuthAction();
  const { data, isLoading, error, refetch } = useSuggestions(t, id, { kind: kind || undefined, sort: 'top' });
  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-1" role="group" aria-label="Filter by kind">
          {['', ...kinds].map((k) => (
            <button key={k || 'all'} type="button" aria-pressed={kind === k} onClick={() => setKind(k)} className={cn('h-8 cursor-pointer rounded-full border px-3 text-sm', kind === k ? 'border-text bg-text text-bg' : 'border-border hover:bg-surface-2')}>
              {k ? humanize(k) : 'All'}
            </button>
          ))}
        </div>
        {!isOwner && <Button variant="primary" onClick={() => guard(() => setOpen(true))}><Lightbulb size={15} aria-hidden /> Suggest an improvement</Button>}
      </div>
      <SuggestDialog t={t} id={id} kinds={kinds} open={open} onOpenChange={setOpen} />
      <div className="mt-5">
        {isLoading ? <div className="space-y-3">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-20" />)}</div>
          : error ? <ErrorState error={error} onRetry={() => refetch()} />
          : !data?.data.length ? <EmptyState icon={Lightbulb} title="No suggestions yet." />
          : (
            <ul className="space-y-3">
              {data.data.map((s) => (
                <li key={s.id} className="rounded-[10px] border border-border bg-surface p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge className="bg-surface-2">{humanize(s.kind)}</Badge>
                    <Badge className={STATUS_STYLE[s.status] ?? ''}>{humanize(s.status)}</Badge>
                    {s.ai_assisted && <AIBadge variant="assisted" />}
                    <span className="ml-auto font-mono text-xs text-muted">▲ {s.counts?.votes ?? 0}</span>
                  </div>
                  <h3 className="mt-2 font-semibold">{s.title}</h3>
                  <MarkdownView source={s.body} className="mt-1 text-sm text-muted" />
                  {s.owner_response && (
                    <blockquote className="mt-3 rounded-[6px] bg-surface-2 p-3 text-sm">
                      <p className="mb-1 flex items-center gap-1 text-xs font-medium text-muted"><Quote size={12} aria-hidden /> Owner response</p>
                      {s.owner_response}
                    </blockquote>
                  )}
                  <div className="mt-3 flex items-center gap-2 text-xs text-muted"><UserChip user={s.author} size={18} className="text-xs" /> · <TimeAgo iso={s.created_at} /></div>
                  {isOwner && <OwnerControls s={s} t={t} id={id} />}
                </li>
              ))}
            </ul>
          )}
      </div>
    </div>
  );
}
