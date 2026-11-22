import { useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router';
import { useQueryClient } from '@tanstack/react-query';
import * as Popover from '@radix-ui/react-popover';
import * as Dropdown from '@radix-ui/react-dropdown-menu';
import { toast } from 'sonner';
import { AlertTriangle, BookOpen, Check, ChevronDown, ExternalLink, FileText, History, Lightbulb, MessageSquareText, Pencil, RotateCcw, Sparkles, Trash2, Wand2 } from 'lucide-react';
import { apiFetch, ApiError } from '@/lib/api/client';
import { draftKey, useDraft, useDrafts } from '@/lib/api/ai';
import type { AIDraft, DraftTask, FeedbackSuggestionOut, HarnessDocOutput, IdeaDraftOutput, Recommendation } from '@/lib/api/types';
import { Button, buttonClass } from '@/components/common/Button';
import { Badge, Chip } from '@/components/common/Badges';
import { TimeAgo } from '@/components/common/Meta';
import { MarkdownView } from '@/components/common/MarkdownView';
import { ConfirmDialog } from '@/components/common/ConfirmDialog';
import { DetailSkeleton, EmptyState, ErrorState, Skeleton } from '@/components/common/States';
import { DetailError } from '@/components/common/DetailHelpers';
import { Pagination } from '@/components/common/Pagination';
import { inputClass } from '@/components/forms/Field';
import { ReportButton } from '@/components/common/ReportDialog';
import { FeedbackList } from '../AIFeedbackPanel';
import { COMPONENT_LABELS, TOOL_LABELS } from '@/lib/modules';
import { domainOf, humanize, safeUrl } from '@/lib/format';
import { cn } from '@/lib/cn';

const TASK_META: Record<DraftTask, { label: string; icon: typeof FileText }> = {
  harness_doc: { label: 'Harness documentation', icon: FileText },
  project_idea: { label: 'Project ideas', icon: Lightbulb },
  resource_recommendations: { label: 'Learning resources', icon: BookOpen },
  feedback_suggestions: { label: 'Feedback suggestions', icon: MessageSquareText },
};

export function DraftsListPage() {
  const [sp, setSp] = useSearchParams();
  const task = sp.get('task') ?? '';
  const status = sp.get('status') ?? 'draft';
  const page = Number(sp.get('page') ?? 1);
  const { data, isLoading, error, refetch } = useDrafts({ task: task || undefined, status, page });
  const set = (k: string, v: string) => setSp((p) => { const n = new URLSearchParams(p); if (v) n.set(k, v); else n.delete(k); if (k !== 'page') n.delete('page'); return n; });
  return (
    <div className="mx-auto max-w-[900px] px-4 py-8 md:px-8">
      <title>AI drafts · DevCommons</title>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="flex items-center gap-2 font-mono text-sm text-ai"><Sparkles size={15} aria-hidden /> AI Workspace</p>
          <h1 className="mt-1 text-[28px]">AI drafts</h1>
        </div>
        <Link to="/ai/generate" className={buttonClass('ai')}><Sparkles size={15} aria-hidden /> Generate</Link>
      </div>
      <div className="mt-6 flex flex-wrap gap-3">
        <label className="flex flex-col gap-1 text-xs font-medium text-muted">Task
          <select value={task} onChange={(e) => set('task', e.target.value)} className={cn(inputClass, 'h-9 text-sm text-text')}>
            <option value="">All tasks</option>
            {Object.entries(TASK_META).map(([k, m]) => <option key={k} value={k}>{m.label}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-muted">Status
          <select value={status} onChange={(e) => set('status', e.target.value)} className={cn(inputClass, 'h-9 text-sm text-text')}>
            <option value="draft">Draft</option><option value="published">Published</option><option value="discarded">Discarded</option>
          </select>
        </label>
      </div>
      <div className="mt-6" id="list-top">
        {isLoading ? <div className="space-y-2">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-16" />)}</div>
          : error ? <ErrorState error={error} onRetry={() => refetch()} />
          : !data?.data.length ? <EmptyState icon={Sparkles} title={status === 'draft' ? 'No drafts yet.' : `No ${status} drafts.`} action={<Link to="/ai/generate" className={buttonClass('ai')}>Generate a draft</Link>} />
          : (
            <ul className="divide-y divide-border rounded-[10px] border border-border bg-surface">
              {data.data.map((d) => {
                const M = TASK_META[d.task];
                const pub = d.published_target;
                return (
                  <li key={d.id} className="flex items-center gap-3 px-4 py-3">
                    <M.icon size={18} className="shrink-0 text-ai" aria-hidden />
                    <div className="min-w-0 flex-1">
                      <Link to={`/ai/drafts/${d.id}`} className="block truncate font-medium hover:underline">{d.title}</Link>
                      <p className="font-mono text-xs text-muted">{M.label} · updated <TimeAgo iso={d.updated_at} /></p>
                    </div>
                    {pub ? (
                      <Link to={`/${pub.type === 'harness' ? 'harnesses' : pub.type === 'idea' ? 'ideas' : pub.type === 'resource' ? 'resources' : 'collections'}/${pub.id}`} className="text-sm underline">View published</Link>
                    ) : (
                      <Badge className="border border-border capitalize text-muted">{d.status}</Badge>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        {data && <Pagination meta={data.meta} onPage={(p) => set('page', String(p))} />}
      </div>
    </div>
  );
}

/* ── Draft review ─────────────────────────────────────────────────────── */

function setPath(obj: Record<string, unknown>, path: string, value: unknown) {
  const out = structuredClone(obj) as Record<string, unknown>;
  const parts = path.split('.');
  let cur: Record<string, unknown> | unknown[] = out;
  for (let i = 0; i < parts.length - 1; i++) cur = (cur as Record<string, unknown>)[parts[i]] as Record<string, unknown>;
  (cur as Record<string, unknown>)[parts[parts.length - 1]] = value;
  return out;
}

function useDraftActions(d: AIDraft) {
  const qc = useQueryClient();
  const update = (next: AIDraft) => { qc.setQueryData(draftKey(d.id), (old: AIDraft | undefined) => ({ ...next, history: old?.history })); void qc.invalidateQueries({ queryKey: draftKey(d.id) }); };
  return {
    patchField: async (path: string, value: unknown) => {
      const r = await apiFetch<{ data: AIDraft }>(`/api/ai/drafts/${d.id}`, { method: 'PATCH', body: { output: setPath(d.output, path, value) } });
      update(r.data);
      toast.success('Saved');
    },
    refine: async (path: string, instruction: string) => {
      const r = await apiFetch<{ data: AIDraft }>(`/api/ai/drafts/${d.id}/refine-section`, { method: 'POST', body: { field: path, instruction } });
      update(r.data);
      toast.success('Section refined. The previous version is in History.');
    },
  };
}

/** One text field of a draft: read view, inline edit (PATCH), and Refine (refine-section). */
function DraftField({ d, path, label, value, markdown = true, multiline = true }: { d: AIDraft; path: string; label: string; value: string; markdown?: boolean; multiline?: boolean }) {
  const { patchField, refine } = useDraftActions(d);
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(value);
  const [busy, setBusy] = useState(false);
  const [instr, setInstr] = useState('');
  const [open, setOpen] = useState(false);
  const locked = d.status !== 'draft';
  const doRefine = async (instruction: string) => {
    setBusy(true);
    setOpen(false);
    try { await refine(path, instruction); } catch (e) { toast.error(e instanceof ApiError ? e.message : 'Refine failed.'); } finally { setBusy(false); }
  };
  return (
    <section className="rounded-[10px] border border-border bg-surface p-4" aria-busy={busy}>
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-sm font-semibold">{label}</h3>
        {!locked && !editing && (
          <div className="ml-auto flex gap-1">
            <Button size="sm" variant="ghost" onClick={() => { setText(value); setEditing(true); }}><Pencil size={13} aria-hidden /> Edit</Button>
            <Popover.Root open={open} onOpenChange={setOpen}>
              <Popover.Trigger asChild><Button size="sm" variant="ghost" className="text-ai" disabled={busy}><Wand2 size={13} aria-hidden /> {busy ? 'Refining…' : 'Refine'}</Button></Popover.Trigger>
              <Popover.Portal>
                <Popover.Content align="end" sideOffset={6} className="z-50 w-[300px] rounded-[10px] border border-border bg-surface p-3 shadow-[var(--shadow-dialog)]">
                  <p className="text-xs font-medium text-muted">Quick refinements</p>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {['Shorter', 'More detail', 'Clearer steps'].map((c) => (
                      <button key={c} type="button" onClick={() => doRefine(c)} className="cursor-pointer rounded-full border border-dashed border-ai px-2.5 py-1 text-xs text-ai hover:bg-ai-soft">{c}</button>
                    ))}
                  </div>
                  <form className="mt-3" onSubmit={(e) => { e.preventDefault(); if (instr.trim()) void doRefine(instr.trim()); }}>
                    <label className="text-xs font-medium text-muted" htmlFor={`ri-${path}`}>Or tell AI what to change</label>
                    <input id={`ri-${path}`} value={instr} onChange={(e) => setInstr(e.target.value)} maxLength={500} className={cn(inputClass, 'mt-1 h-9 text-sm')} placeholder="e.g. mention the PreToolUse hook" />
                    <Button type="submit" size="sm" variant="ai" className="mt-2 w-full" disabled={!instr.trim()}>Refine</Button>
                  </form>
                </Popover.Content>
              </Popover.Portal>
            </Popover.Root>
          </div>
        )}
      </div>
      {editing ? (
        <form className="mt-2" onSubmit={async (e) => { e.preventDefault(); setBusy(true); try { await patchField(path, text); setEditing(false); } catch (err) { toast.error(err instanceof ApiError ? err.message : 'Could not save.'); } finally { setBusy(false); } }}>
          {multiline ? <textarea value={text} onChange={(e) => setText(e.target.value)} rows={Math.min(16, Math.max(4, text.split('\n').length + 1))} className={cn(inputClass, 'py-2 font-mono text-sm')} aria-label={label} autoFocus />
            : <input value={text} onChange={(e) => setText(e.target.value)} className={cn(inputClass, 'h-10')} aria-label={label} autoFocus />}
          <div className="mt-2 flex justify-end gap-2">
            <Button type="button" size="sm" onClick={() => setEditing(false)}>Cancel</Button>
            <Button type="submit" size="sm" variant="primary" disabled={busy}>Save</Button>
          </div>
        </form>
      ) : value ? (
        markdown ? <MarkdownView source={value} className="mt-2 text-[15px]" /> : <p className="mt-2">{value}</p>
      ) : (
        <p className="mt-2 text-sm text-muted italic">Empty</p>
      )}
    </section>
  );
}

function HarnessDraftBody({ d }: { d: AIDraft }) {
  const o = d.output as unknown as HarnessDocOutput;
  return (
    <div className="space-y-4">
      {o.gaps_and_uncertainties?.length > 0 && (
        <div className="rounded-[10px] border border-warning bg-warning-soft p-4" role="note">
          <p className="flex items-center gap-2 font-semibold"><AlertTriangle size={16} className="text-warning" aria-hidden /> Gaps and uncertainties</p>
          <p className="mt-1 text-sm text-muted">What the AI couldn't determine from the repository. Fill these in yourself.</p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">{o.gaps_and_uncertainties.map((g, i) => <li key={i}>{g}</li>)}</ul>
        </div>
      )}
      <DraftField d={d} path="name" label="Name" value={o.name} markdown={false} multiline={false} />
      <DraftField d={d} path="short_description" label="Short description" value={o.short_description} markdown={false} />
      <DraftField d={d} path="problem_addressed" label="Problem addressed" value={o.problem_addressed} />
      <DraftField d={d} path="detailed_explanation" label="How it works" value={o.detailed_explanation} />
      <DraftField d={d} path="architecture" label="Architecture" value={o.architecture} />
      <section className="rounded-[10px] border border-border bg-surface p-4">
        <h3 className="text-sm font-semibold">Components ({o.components.length})</h3>
        <div className="mt-2 overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-muted"><tr><th className="py-1.5 pr-3 font-medium">Type</th><th className="py-1.5 pr-3 font-medium">Name</th><th className="py-1.5 pr-3 font-medium">What it does</th><th className="py-1.5 font-medium">Evidence</th></tr></thead>
            <tbody>
              {o.components.map((c, i) => (
                <tr key={i} className="border-t border-border align-top">
                  <td className="py-2 pr-3 whitespace-nowrap text-muted">{COMPONENT_LABELS[c.type]?.replace(/s$/, '') ?? c.type}</td>
                  <td className="py-2 pr-3 font-mono text-[13px]">{c.name}</td>
                  <td className="py-2 pr-3">{c.description}</td>
                  <td className="py-2 text-xs text-muted">{c.evidence_path ? <>Seen in <code className="font-mono">{c.evidence_path}</code></> : 'Inferred'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <DraftField d={d} path="setup_instructions" label="Setup" value={o.setup_instructions} />
      <DraftField d={d} path="limitations" label="Limitations" value={o.limitations} />
      <section className="rounded-[10px] border border-border bg-surface p-4 text-sm">
        <h3 className="font-semibold">Suggested metadata</h3>
        <dl className="mt-2 space-y-2">
          <div className="flex flex-wrap items-center gap-1.5"><dt className="w-20 text-muted">Tools</dt>{o.suggested_tools.map((t) => <Chip key={t}>{TOOL_LABELS[t] ?? t}</Chip>)}</div>
          <div className="flex flex-wrap items-center gap-1.5"><dt className="w-20 text-muted">Category</dt><Chip>{o.suggested_category}</Chip></div>
          <div className="flex flex-wrap items-center gap-1.5"><dt className="w-20 text-muted">Tags</dt>{o.suggested_tags.map((t) => <Chip key={t}>#{t}</Chip>)}</div>
        </dl>
      </section>
      {d.status === 'draft' && (
        <Link to={`/harnesses/new?draft=${d.id}`} className={buttonClass('primary', 'lg')}>Continue to publish</Link>
      )}
    </div>
  );
}

function IdeaDraftBody({ d }: { d: AIDraft }) {
  const ideas = (d.output as { ideas: IdeaDraftOutput[] }).ideas ?? [];
  return (
    <div className={cn('grid gap-4', ideas.length > 1 && 'xl:grid-cols-2')}>
      {ideas.map((idea, n) => (
        <article key={n} className="stripe-idea space-y-3 rounded-[10px] border border-border bg-bg p-3">
          <p className="px-1 font-mono text-xs text-muted">Idea {n + 1} of {ideas.length}</p>
          <DraftField d={d} path={`ideas.${n}.title`} label="Title" value={idea.title} markdown={false} multiline={false} />
          <DraftField d={d} path={`ideas.${n}.summary`} label="Summary" value={idea.summary} />
          <DraftField d={d} path={`ideas.${n}.problem_statement`} label="Problem" value={idea.problem_statement} />
          <DraftField d={d} path={`ideas.${n}.proposed_solution`} label="Proposed solution" value={idea.proposed_solution} />
          <DraftField d={d} path={`ideas.${n}.target_users`} label="Target users" value={idea.target_users} />
          <DraftField d={d} path={`ideas.${n}.architecture`} label="Architecture" value={idea.architecture} />
          <section className="space-y-3 rounded-[10px] border border-border bg-surface p-4 text-sm">
            <div><h3 className="font-semibold">Expected features</h3><ul className="mt-1 list-disc pl-5">{idea.expected_features.map((f, i) => <li key={i}><span className="font-medium">{f.title}</span> — {f.detail}</li>)}</ul></div>
            <div><h3 className="font-semibold">Milestones</h3><ol className="mt-1 list-decimal pl-5">{idea.milestones.map((m, i) => <li key={i}>{m}</li>)}</ol></div>
            <div><h3 className="font-semibold">Challenges</h3><ul className="mt-1 list-disc pl-5">{idea.challenges.map((c, i) => <li key={i}>{c}</li>)}</ul></div>
            <div className="flex flex-wrap gap-1.5">{idea.tech_stack.map((t) => <Chip key={t}>{t}</Chip>)}</div>
          </section>
          {d.status === 'draft' && <Link to={`/ideas/new?draft=${d.id}&index=${n}`} className={buttonClass('primary', 'md', 'w-full')}>Use this idea</Link>}
        </article>
      ))}
    </div>
  );
}

function VerificationBadge({ v }: { v: Recommendation['verification'] }) {
  if (v.status === 'verified_hub') return <Badge className="bg-success-soft text-success"><Check size={12} aria-hidden /> In the Knowledge Hub</Badge>;
  if (v.status === 'verified_official_domain') return <Badge className="bg-success-soft text-success"><Check size={12} aria-hidden /> Official domain · link works</Badge>;
  return <Badge className="border border-border text-muted">Link works · not verified</Badge>;
}

function ResourcesDraftBody({ d }: { d: AIDraft }) {
  const o = d.output as { learning_path_notes: string; recommendations: Recommendation[]; omitted?: { name: string; url: string; reason: string }[] };
  const hubCount = o.recommendations.filter((r) => r.verification.status === 'verified_hub').length;
  return (
    <div className="space-y-4">
      <DraftField d={d} path="learning_path_notes" label="Learning path notes" value={o.learning_path_notes} />
      <ol className="space-y-3">
        {o.recommendations.map((r, i) => {
          const url = safeUrl(r.url);
          return (
            <li key={i} className="rounded-[10px] border border-border bg-surface p-4">
              <div className="flex flex-wrap items-start gap-2">
                <span className="font-mono text-sm text-muted">{i + 1}.</span>
                <div className="min-w-0 flex-1">
                  <p className="font-semibold">{r.name}</p>
                  {url && <a href={url} target="_blank" rel="noopener noreferrer nofollow" className="inline-flex items-center gap-1 font-mono text-xs text-muted underline">{domainOf(url)} <ExternalLink size={11} aria-hidden /></a>}
                </div>
                <VerificationBadge v={r.verification} />
              </div>
              <p className="mt-2 text-sm">{r.description}</p>
              <div className="mt-2 flex flex-wrap gap-1.5"><Chip>{humanize(r.resource_type)}</Chip>{r.level && <Chip>{r.level}</Chip>}</div>
              <div className="mt-3">
                {r.verification.status === 'verified_hub' && r.hub_resource_id ? (
                  <Link to={`/resources/${r.hub_resource_id}`} className={buttonClass('secondary', 'sm')}>Open in Knowledge Hub</Link>
                ) : d.status === 'draft' ? (
                  <Link to={`/resources/new?draft=${d.id}&index=${i}`} className={buttonClass('secondary', 'sm')}>Add to Knowledge Hub</Link>
                ) : null}
              </div>
            </li>
          );
        })}
      </ol>
      {!!o.omitted?.length && (
        <details className="rounded-[10px] border border-border bg-surface p-4 text-sm">
          <summary className="cursor-pointer font-medium">Omitted links (couldn't be reached) · {o.omitted.length}</summary>
          <p className="mt-2 text-muted">Removed because we couldn't verify these links.</p>
          <ul className="mt-2 list-disc pl-5">{o.omitted.map((x, i) => <li key={i}>{x.name} <span className="font-mono text-xs text-muted">({x.reason})</span></li>)}</ul>
        </details>
      )}
      {d.status === 'draft' && (
        hubCount > 0 ? <Link to={`/collections/new?draft=${d.id}`} className={buttonClass('primary', 'lg')}>Create a collection from {hubCount} hub {hubCount === 1 ? 'item' : 'items'}</Link>
          : <p className="text-sm text-muted">None of these are in the Knowledge Hub yet, so a collection can't be created from this draft.</p>
      )}
    </div>
  );
}

export function DraftReviewPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { data: d, isLoading, error, refetch } = useDraft(id);
  const [regenOpen, setRegenOpen] = useState(false);
  const [extra, setExtra] = useState('');
  const [regenBusy, setRegenBusy] = useState(false);
  if (isLoading) return <DetailSkeleton />;
  if (error || !d) return <DetailError error={error} retry={() => refetch()} noun="draft" listPath="/ai/drafts" />;
  const M = TASK_META[d.task];
  const refresh = (next: AIDraft) => { qc.setQueryData(draftKey(d.id), next); void qc.invalidateQueries({ queryKey: draftKey(d.id) }); void qc.invalidateQueries({ queryKey: ['ai', 'drafts'] }); };

  return (
    <div className="mx-auto max-w-[1100px] px-4 py-8 md:px-8">
      <title>{`${d.title} · AI draft · DevCommons`}</title>
      <Link to="/ai/drafts" className="text-sm text-muted hover:underline">AI drafts</Link>
      <div className="ai-surface mt-3 flex items-start gap-2 rounded-[10px] px-4 py-3 text-sm" role="note">
        <Sparkles size={16} className="mt-0.5 shrink-0 text-ai" aria-hidden />
        <p>{d.status === 'published' ? 'This draft has been published. Edits here no longer change the published post.' : d.status === 'discarded' ? 'This draft was discarded.' : 'AI-generated draft. Nothing is published until you review and submit it.'}</p>
      </div>
      <header className="mt-5 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div className="min-w-0">
          <p className="flex items-center gap-2 font-mono text-sm text-ai"><M.icon size={15} aria-hidden /> {M.label}</p>
          <h1 className="mt-1 text-[26px]">{d.title}</h1>
          <p className="mt-1 font-mono text-xs text-muted">revision {d.revision} · {d.model} · updated <TimeAgo iso={d.updated_at} /></p>
        </div>
        {d.status === 'draft' && (
          <div className="flex flex-wrap gap-2">
            {d.task !== 'feedback_suggestions' && (
              <Popover.Root open={regenOpen} onOpenChange={setRegenOpen}>
                <Popover.Trigger asChild><Button variant="ai" disabled={regenBusy}><RotateCcw size={15} aria-hidden /> {regenBusy ? 'Regenerating…' : 'Regenerate'}</Button></Popover.Trigger>
                <Popover.Portal>
                  <Popover.Content align="end" sideOffset={6} className="z-50 w-[320px] rounded-[10px] border border-border bg-surface p-3 shadow-[var(--shadow-dialog)]">
                    <form onSubmit={async (e) => {
                      e.preventDefault(); setRegenOpen(false); setRegenBusy(true);
                      try { const r = await apiFetch<{ data: AIDraft }>(`/api/ai/drafts/${d.id}/regenerate`, { method: 'POST', body: { additional_context: extra.trim() || null } }); refresh(r.data); toast.success('Regenerated. The previous version is in History.'); }
                      catch (err) { toast.error(err instanceof ApiError ? err.message : 'Regenerate failed.'); }
                      finally { setRegenBusy(false); }
                    }}>
                      <label htmlFor="regen-extra" className="text-sm font-medium">Extra context (optional)</label>
                      <textarea id="regen-extra" rows={3} maxLength={4000} value={extra} onChange={(e) => setExtra(e.target.value)} className={cn(inputClass, 'mt-1 py-2 text-sm')} />
                      <Button type="submit" variant="ai" size="sm" className="mt-2 w-full">Regenerate draft</Button>
                    </form>
                  </Popover.Content>
                </Popover.Portal>
              </Popover.Root>
            )}
            <Dropdown.Root>
              <Dropdown.Trigger asChild><Button disabled={!d.history?.length}><History size={15} aria-hidden /> History <ChevronDown size={13} aria-hidden /></Button></Dropdown.Trigger>
              <Dropdown.Portal>
                <Dropdown.Content align="end" sideOffset={6} className="z-50 min-w-[240px] rounded-[10px] border border-border bg-surface p-1 shadow-[var(--shadow-dialog)]">
                  {(d.history ?? []).map((h, i) => (
                    <Dropdown.Item key={i} className="flex cursor-pointer items-center justify-between gap-3 rounded-[6px] px-2.5 py-2 text-sm outline-none data-[highlighted]:bg-surface-2"
                      onSelect={async () => {
                        try { const r = await apiFetch<{ data: AIDraft }>(`/api/ai/drafts/${d.id}/restore`, { method: 'POST', body: { history_index: i } }); refresh(r.data); toast.success(`Restored revision ${h.revision}`); }
                        catch (err) { toast.error(err instanceof ApiError ? err.message : 'Restore failed.'); }
                      }}>
                      <span>Restore revision {h.revision}</span><span className="font-mono text-xs text-muted"><TimeAgo iso={h.saved_at} /></span>
                    </Dropdown.Item>
                  ))}
                </Dropdown.Content>
              </Dropdown.Portal>
            </Dropdown.Root>
            <ConfirmDialog
              trigger={<Button><Trash2 size={15} aria-hidden /> Discard</Button>}
              title="Discard this draft?"
              description="It moves to Discarded and is deleted after 30 days. Nothing was published from it."
              confirmLabel="Discard draft"
              onConfirm={async () => { await apiFetch(`/api/ai/drafts/${d.id}/discard`, { method: 'POST' }); void qc.invalidateQueries({ queryKey: ['ai'] }); toast('Draft discarded'); navigate('/ai/drafts'); }}
            />
            <ReportButton targetType="ai_draft" targetId={d.id} />
          </div>
        )}
      </header>
      {d.context_sources && d.context_sources.length > 0 && (
        <details className="mt-4 text-sm">
          <summary className="cursor-pointer font-mono text-xs text-muted">Based on {d.context_sources.filter((s) => s.status === 'included').length} sources we could read</summary>
          <ul className="mt-2 space-y-1 pl-4 text-xs">{d.context_sources.map((s, i) => <li key={i}>{s.status === 'included' ? '✓' : '✕'} {s.label}{s.reason ? ` — ${s.reason}` : ''}</li>)}</ul>
        </details>
      )}
      <div className="mt-6">
        {d.task === 'harness_doc' && <HarnessDraftBody d={d} />}
        {d.task === 'project_idea' && <IdeaDraftBody d={d} />}
        {d.task === 'resource_recommendations' && <ResourcesDraftBody d={d} />}
        {d.task === 'feedback_suggestions' && (
          <div className="ai-surface rounded-[10px] p-4">
            <p className="mb-3 text-sm font-semibold">{d.label ?? 'AI-generated suggestions, not a community review'}</p>
            <FeedbackList suggestions={(d.output as { suggestions: FeedbackSuggestionOut[] }).suggestions ?? []} />
          </div>
        )}
      </div>
    </div>
  );
}
