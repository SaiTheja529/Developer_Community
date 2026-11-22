import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { ArrowDown, ArrowUp, Check, Plus, Search, Trash2 } from 'lucide-react';
import { apiFetch, ApiError } from '@/lib/api/client';
import { useCollection } from '@/lib/api/queries';
import { useDraft } from '@/lib/api/ai';
import { useConfig } from '@/hooks/useConfig';
import { useDebouncedValue } from '@/hooks/useDebouncedValue';
import { useForm, useUnsavedChangesGuard } from '@/hooks/useForm';
import type { CollectionDetail, CollectionItem, Paginated, Recommendation, ResourceSummary } from '@/lib/api/types';
import { ErrorSummary, Field, FormSection, SelectInput, TextArea, TextInput, inputClass } from '@/components/forms/Field';
import { TagInput } from '@/components/forms/TagInput';
import { DraftPrefillBanner, FormShell, SubmitBar } from '@/components/forms/FormShell';
import { ConfirmDialog } from '@/components/common/ConfirmDialog';
import { Button } from '@/components/common/Button';
import { DetailSkeleton } from '@/components/common/States';
import { cn } from '@/lib/cn';

interface V extends Record<string, unknown> { title: string; description: string; category: string; tags: string[]; visibility: 'public' | 'private'; ai_assisted: boolean }
const EMPTY: V = { title: '', description: '', category: '', tags: [], visibility: 'public', ai_assisted: false };

export default function CollectionFormPage() {
  const { id } = useParams();
  const editing = !!id;
  const [sp] = useSearchParams();
  const draftId = sp.get('draft');
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { data: config } = useConfig();
  const existing = useCollection(id);
  const draft = useDraft(editing ? null : draftId);
  const f = useForm<V>(EMPTY);
  const [loaded, setLoaded] = useState(!editing && !draftId);
  const [busy, setBusy] = useState(false);
  const bypass = useUnsavedChangesGuard(f.dirty && !busy);
  const [draftItems, setDraftItems] = useState<{ resource_id: string; name: string }[]>([]);

  useEffect(() => {
    if (loaded) return;
    if (editing && existing.data) {
      const c = existing.data;
      f.reset({ title: c.title, description: c.description ?? '', category: c.category.slug, tags: c.tags, visibility: c.visibility, ai_assisted: c.ai_assisted });
      setLoaded(true);
    }
    if (!editing && draft.data) {
      const recs = (draft.data.output as { recommendations?: Recommendation[] }).recommendations ?? [];
      const hub = recs.filter((r) => r.verification.status === 'verified_hub' && r.hub_resource_id);
      setDraftItems(hub.map((r) => ({ resource_id: r.hub_resource_id!, name: r.name })));
      f.reset({ ...EMPTY, title: `Learning ${String(draft.data.input.topic ?? '')}`.slice(0, 120), ai_assisted: true });
      setLoaded(true);
    }
  }, [editing, existing.data, draft.data, loaded, f]);

  if ((editing && existing.isLoading) || (draftId && draft.isLoading) || !config) return <DetailSkeleton />;
  if (editing && existing.data && !existing.data.viewer.can_edit) return <div className="mx-auto max-w-[720px] px-4 py-20 text-center"><h1 className="text-2xl">You can only edit your own collections.</h1></div>;
  const v = f.values;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const errs: Record<string, string> = {};
    if (v.title.trim().length < 3) errs.title = 'Use at least 3 characters.';
    if (!v.category) errs.category = 'Choose a category.';
    if (Object.keys(errs).length) { f.setErrors(errs); return; }
    setBusy(true);
    const body = { ...v, description: v.description || null, ...(editing ? {} : { source_draft_id: draftId, items: draftItems.map((d) => ({ resource_id: d.resource_id })) }) };
    try {
      const res = await apiFetch<{ data: CollectionDetail }>(editing ? `/api/collections/${id}` : '/api/collections', { method: editing ? 'PATCH' : 'POST', body });
      bypass();
      await qc.invalidateQueries({ queryKey: ['collections'] });
      toast.success(editing ? 'Collection saved' : 'Collection created. Add resources next.');
      navigate(editing ? `/collections/${res.data.id}/${res.data.slug}` : `/collections/${res.data.id}/edit`, { replace: true });
    } catch (err) {
      if (!f.applyApiError(err)) toast.error(err instanceof ApiError ? err.message : 'Could not save. Try again.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <FormShell
      module="knowledge"
      title={editing ? `Edit ${existing.data?.title ?? 'collection'}` : 'Create a collection'}
      sections={[{ id: 'meta', label: 'Details' }, ...(editing ? [{ id: 'items', label: 'Resources' }, { id: 'danger', label: 'Danger zone' }] : [])]}
      banner={draftId && !editing ? <DraftPrefillBanner /> : undefined}
    >
      <form onSubmit={submit} noValidate className="space-y-5">
        <ErrorSummary errors={f.errors} labels={{ title: 'Title', category: 'Category', description: 'Description' }} />
        <FormSection id="meta" title="Details">
          <Field label="Title" required error={f.errors.title} counter={{ n: v.title.length, max: 120 }}>
            {(p) => <TextInput {...p} value={v.title} maxLength={120} onChange={(e) => f.set('title', e.target.value)} />}
          </Field>
          <Field label="Description" hint="Who is this learning path for?" counter={{ n: v.description.length, max: 5000 }}>
            {(p) => <TextArea {...p} rows={3} value={v.description} onChange={(e) => f.set('description', e.target.value)} />}
          </Field>
          <div className="grid gap-5 sm:grid-cols-2">
            <Field label="Category" required error={f.errors.category}>
              {(p) => <SelectInput {...p} value={v.category} onChange={(e) => f.set('category', e.target.value)} placeholder="Choose a category" options={(config.categories.collection ?? []).map((c) => ({ value: c.slug, label: c.name }))} />}
            </Field>
            <Field label="Visibility">
              {(p) => <SelectInput {...p} value={v.visibility} onChange={(e) => f.set('visibility', e.target.value as V['visibility'])} options={[{ value: 'public', label: 'Public' }, { value: 'private', label: 'Private (only you)' }]} />}
            </Field>
          </div>
          <Field label="Tags">{(p) => <TagInput id={p.id} value={v.tags} onChange={(x) => f.set('tags', x)} module="collection" />}</Field>
          {draftItems.length > 0 && (
            <div className="rounded-[10px] bg-surface-2 p-3 text-sm">
              <p className="font-medium">{draftItems.length} Knowledge Hub resources from the AI draft will be added:</p>
              <ol className="mt-1 list-decimal pl-5">{draftItems.map((d) => <li key={d.resource_id}>{d.name}</li>)}</ol>
            </div>
          )}
        </FormSection>
        <SubmitBar busy={busy} label={editing ? 'Save' : 'Create collection'} onCancel={() => navigate(-1)} />
      </form>
      {editing && existing.data && <ItemsPanel c={existing.data} />}
      {editing && id && (
        <section id="danger" className="rounded-[10px] border border-danger p-5">
          <h2 className="text-lg text-danger">Danger zone</h2>
          <ConfirmDialog
            trigger={<Button variant="danger" className="mt-3">Delete collection</Button>}
            title="Delete this collection?"
            description="The resources stay in the Knowledge Hub. Comments on the collection will be hidden."
            confirmLabel="Delete collection"
            onConfirm={async () => { await apiFetch(`/api/collections/${id}`, { method: 'DELETE' }); bypass(); await qc.invalidateQueries({ queryKey: ['collections'] }); toast.success('Collection deleted'); navigate('/collections', { replace: true }); }}
          />
        </section>
      )}
    </FormShell>
  );
}

/** Items: add via search, inline notes, keyboard-accessible reordering, debounced order save (spec §11.3). */
function ItemsPanel({ c }: { c: CollectionDetail }) {
  const qc = useQueryClient();
  const [items, setItems] = useState<CollectionItem[]>(() => [...c.items].sort((a, b) => a.position - b.position));
  const [q, setQ] = useState('');
  const dq = useDebouncedValue(q, 300);
  const [results, setResults] = useState<ResourceSummary[]>([]);
  const [saved, setSaved] = useState<'idle' | 'saving' | 'saved'>('idle');
  const [announce, setAnnounce] = useState('');
  const orderTimer = useRef<number | undefined>(undefined);
  const refresh = () => qc.invalidateQueries({ queryKey: ['collections'] });

  useEffect(() => {
    if (dq.trim().length < 2) { setResults([]); return; }
    let live = true;
    apiFetch<Paginated<ResourceSummary>>('/api/resources', { query: { q: dq, page_size: 6 } }).then((r) => live && setResults(r.data)).catch(() => undefined);
    return () => { live = false; };
  }, [dq]);

  const ids = new Set(items.map((i) => i.resource_id ?? i.resource?.id));
  const add = async (r: ResourceSummary) => {
    try {
      await apiFetch(`/api/collections/${c.id}/items`, { method: 'POST', body: { resource_id: r.id } });
      setItems((s) => [...s, { position: s.length, note: null, resource: r, resource_id: r.id }]);
      setQ('');
      setAnnounce(`${r.name} added`);
      void refresh();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : 'Could not add.');
    }
  };
  const remove = async (rid: string, name: string) => {
    await apiFetch(`/api/collections/${c.id}/items/${rid}`, { method: 'DELETE' });
    setItems((s) => s.filter((i) => (i.resource_id ?? i.resource?.id) !== rid));
    setAnnounce(`${name} removed`);
    void refresh();
  };
  const saveNote = async (rid: string, note: string) => {
    await apiFetch(`/api/collections/${c.id}/items/${rid}`, { method: 'PATCH', body: { note: note || null } });
    setSaved('saved');
  };
  const move = (i: number, d: number) => {
    const j = i + d;
    if (j < 0 || j >= items.length) return;
    const n = [...items];
    [n[i], n[j]] = [n[j], n[i]];
    setItems(n);
    setAnnounce(`${n[j].resource?.name ?? 'Item'} moved to position ${j + 1} of ${n.length}`);
    setSaved('saving');
    window.clearTimeout(orderTimer.current);
    orderTimer.current = window.setTimeout(async () => {
      try {
        await apiFetch(`/api/collections/${c.id}/items/order`, { method: 'PUT', body: { resource_ids: n.map((x) => x.resource_id ?? x.resource?.id) } });
        setSaved('saved');
        void refresh();
      } catch {
        toast.error('Could not save the new order.');
        setSaved('idle');
      }
    }, 800);
    requestAnimationFrame(() => document.getElementById(`move-${d < 0 ? 'up' : 'down'}-${j}`)?.focus());
  };

  return (
    <FormSection id="items" title="Resources" description="Changes here save immediately.">
      <div aria-live="polite" className="sr-only">{announce}</div>
      <div className="flex items-center justify-between text-sm">
        <span className="font-mono text-muted">{items.length} / 100 items</span>
        {saved !== 'idle' && <span className="inline-flex items-center gap-1 text-muted">{saved === 'saving' ? 'Saving…' : <><Check size={14} className="text-success" aria-hidden /> Saved</>}</span>}
      </div>
      <div className="relative">
        <label className="sr-only" htmlFor="add-res">Search the Knowledge Hub to add a resource</label>
        <Search size={15} className="pointer-events-none absolute top-3 left-3 text-muted" aria-hidden />
        <input id="add-res" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search the Knowledge Hub to add…" className={cn(inputClass, 'h-10 pl-9')} disabled={items.length >= 100} />
        {results.length > 0 && (
          <ul className="absolute inset-x-0 top-11 z-20 rounded-[10px] border border-border bg-surface p-1 shadow-[var(--shadow-dialog)]">
            {results.map((r) => (
              <li key={r.id}>
                <button type="button" disabled={ids.has(r.id)} onClick={() => add(r)} className="flex w-full cursor-pointer items-center gap-2 rounded-[6px] px-2.5 py-2 text-left text-sm hover:bg-surface-2 disabled:cursor-default disabled:opacity-50">
                  {ids.has(r.id) ? <Check size={14} aria-hidden /> : <Plus size={14} aria-hidden />}
                  <span className="truncate">{r.name}</span>
                  <span className="ml-auto shrink-0 font-mono text-xs text-muted">{r.domain}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      {items.length === 0 ? (
        <p className="rounded-[10px] border border-dashed border-border px-4 py-6 text-center text-sm text-muted">No resources yet. Search above to add the first one.</p>
      ) : (
        <ol className="space-y-2">
          {items.map((it, i) => {
            const rid = (it.resource_id ?? it.resource?.id)!;
            const name = it.resource?.name ?? 'Unavailable resource';
            return (
              <li key={rid} className="rounded-[10px] border border-border bg-bg p-3">
                <div className="flex items-center gap-2">
                  <span className="w-6 text-right font-mono text-sm text-muted">{i + 1}</span>
                  <div className="min-w-0 flex-1">
                    {it.resource ? <Link to={`/resources/${rid}`} className="font-medium hover:underline">{name}</Link> : <span className="text-muted">This resource is no longer available.</span>}
                    {it.resource && <span className="ml-2 font-mono text-xs text-muted">{it.resource.domain}</span>}
                  </div>
                  <button id={`move-up-${i}`} type="button" className="grid size-8 cursor-pointer place-items-center rounded-[6px] text-muted hover:bg-surface-2 disabled:opacity-30" disabled={i === 0} onClick={() => move(i, -1)} aria-label={`Move ${name} up`}><ArrowUp size={15} /></button>
                  <button id={`move-down-${i}`} type="button" className="grid size-8 cursor-pointer place-items-center rounded-[6px] text-muted hover:bg-surface-2 disabled:opacity-30" disabled={i === items.length - 1} onClick={() => move(i, 1)} aria-label={`Move ${name} down`}><ArrowDown size={15} /></button>
                  <button type="button" className="grid size-8 cursor-pointer place-items-center rounded-[6px] text-muted hover:bg-surface-2 hover:text-danger" onClick={() => remove(rid, name)} aria-label={`Remove ${name}`}><Trash2 size={15} /></button>
                </div>
                <label className="mt-2 block pl-8">
                  <span className="sr-only">Curator note for {name}</span>
                  <input defaultValue={it.note ?? ''} maxLength={500} onBlur={(e) => e.target.value !== (it.note ?? '') && void saveNote(rid, e.target.value)} placeholder="Add a note: why this, and what to focus on" className={cn(inputClass, 'h-9 text-sm')} />
                </label>
              </li>
            );
          })}
        </ol>
      )}
    </FormSection>
  );
}
