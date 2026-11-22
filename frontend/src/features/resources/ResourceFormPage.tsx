import { useEffect, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { Info } from 'lucide-react';
import { apiFetch, ApiError } from '@/lib/api/client';
import { useResource } from '@/lib/api/queries';
import { useDraft } from '@/lib/api/ai';
import { useConfig } from '@/hooks/useConfig';
import { useForm, useUnsavedChangesGuard } from '@/hooks/useForm';
import type { Recommendation, ResourceDetail } from '@/lib/api/types';
import { ErrorSummary, Field, FormSection, SelectInput, TextArea, TextInput } from '@/components/forms/Field';
import { TagInput } from '@/components/forms/TagInput';
import { ResourceUrlField, type CheckUrl } from '@/components/forms/UrlFields';
import { DraftPrefillBanner, FormShell, SubmitBar } from '@/components/forms/FormShell';
import { ConfirmDialog } from '@/components/common/ConfirmDialog';
import { Button } from '@/components/common/Button';
import { DetailSkeleton } from '@/components/common/States';
import { humanize } from '@/lib/format';

interface V extends Record<string, unknown> {
  url: string; name: string; description: string; category: string; resource_type: string; level: string; language: string; tags: string[]; ai_assisted: boolean;
}
const EMPTY: V = { url: '', name: '', description: '', category: '', resource_type: '', level: '', language: 'en', tags: [], ai_assisted: false };
const LABELS: Record<string, string> = { url: 'URL', name: 'Name', description: 'Description', category: 'Category', resource_type: 'Type', level: 'Level', language: 'Language', tags: 'Tags' };

export default function ResourceFormPage() {
  const { id } = useParams();
  const editing = !!id;
  const [sp] = useSearchParams();
  const draftId = sp.get('draft');
  const index = Number(sp.get('index') ?? 0);
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { data: config } = useConfig();
  const existing = useResource(id);
  const draft = useDraft(editing ? null : draftId);
  const f = useForm<V>({ ...EMPTY, url: sp.get('url') ?? '' });
  const [loaded, setLoaded] = useState(!editing && !draftId);
  const [busy, setBusy] = useState(false);
  const [check, setCheck] = useState<CheckUrl | null>(null);
  const bypass = useUnsavedChangesGuard(f.dirty && !busy);

  useEffect(() => {
    if (loaded) return;
    if (editing && existing.data) {
      const r = existing.data;
      f.reset({ url: r.url, name: r.name, description: r.description, category: r.category.slug, resource_type: r.resource_type, level: r.level ?? '', language: r.language ?? 'en', tags: r.tags, ai_assisted: r.ai_assisted });
      setLoaded(true);
    }
    if (!editing && draft.data) {
      const rec = ((draft.data.output as { recommendations?: Recommendation[] }).recommendations ?? [])[index];
      if (rec) f.reset({ ...EMPTY, url: rec.url, name: rec.name, description: rec.description, resource_type: rec.resource_type, category: rec.category ?? '', level: rec.level ?? '', ai_assisted: true });
      setLoaded(true);
    }
  }, [editing, existing.data, draft.data, loaded, f, index]);

  if ((editing && existing.isLoading) || (draftId && draft.isLoading) || !config) return <DetailSkeleton />;
  if (editing && existing.data && !existing.data.viewer.can_edit) return <div className="mx-auto max-w-[720px] px-4 py-20 text-center"><h1 className="text-2xl">You can only edit resources you added.</h1></div>;
  const v = f.values;
  const types = (config.enums.resource_types as string[]) ?? [];
  const levels = (config.enums.resource_levels as string[]) ?? [];

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const errs: Record<string, string> = {};
    if (!/^https?:\/\//i.test(v.url.trim())) errs.url = 'Enter a full http(s) URL.';
    if (v.name.trim().length < 3) errs.name = 'Use at least 3 characters.';
    if (v.description.trim().length < 20) errs.description = 'Describe it in at least 20 characters.';
    if (!v.category) errs.category = 'Choose a category.';
    if (!v.resource_type) errs.resource_type = 'Choose a type.';
    if (Object.keys(errs).length) { f.setErrors(errs); requestAnimationFrame(() => document.getElementById('error-summary')?.focus()); return; }
    setBusy(true);
    const body = { ...v, url: v.url.trim(), level: v.level || null, language: v.language || null, ...(editing ? {} : { source_draft_id: draftId }) };
    try {
      const res = await apiFetch<{ data: ResourceDetail }>(editing ? `/api/resources/${id}` : '/api/resources', { method: editing ? 'PATCH' : 'POST', body });
      bypass();
      await qc.invalidateQueries({ queryKey: ['resources'] });
      void qc.invalidateQueries({ queryKey: ['home'] });
      toast.success(editing ? 'Resource updated' : 'Resource added. We’ll check the link shortly.');
      navigate(`/resources/${res.data.id}`, { replace: true });
    } catch (err) {
      if (err instanceof ApiError && err.code === 'duplicate') f.setErrors({ url: 'This link is already in the Knowledge Hub.' });
      else if (!f.applyApiError(err)) toast.error(err instanceof ApiError ? err.message : 'Could not save. Try again.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <FormShell
      module="knowledge"
      title={editing ? `Edit ${existing.data?.name ?? 'resource'}` : 'Add a resource'}
      sections={[{ id: 'link', label: 'Link' }, { id: 'about', label: 'About it' }, ...(editing ? [{ id: 'danger', label: 'Danger zone' }] : [])]}
      banner={draftId && !editing ? <DraftPrefillBanner /> : undefined}
    >
      <form onSubmit={submit} noValidate className="space-y-5">
        <ErrorSummary errors={f.errors} labels={LABELS} />
        <FormSection id="link" title="Link" description="We never fetch page content, only whether the link works.">
          <Field label="URL" required error={f.errors.url}>
            {(p) => <ResourceUrlField id={p.id} value={v.url} onChange={(x) => f.set('url', x)} onChecked={setCheck} invalid={p['aria-invalid']} describedBy={p['aria-describedby']} skipDuplicateId={id} />}
          </Field>
        </FormSection>
        <FormSection id="about" title="About it">
          <Field label="Name" required error={f.errors.name} counter={{ n: v.name.length, max: 150 }}>
            {(p) => <TextInput {...p} value={v.name} maxLength={150} onChange={(e) => f.set('name', e.target.value)} />}
          </Field>
          <Field label="Description" required hint="What does it cover, and who is it for?" error={f.errors.description} counter={{ n: v.description.length, max: 3000 }}>
            {(p) => <TextArea {...p} rows={4} value={v.description} onChange={(e) => f.set('description', e.target.value)} />}
          </Field>
          <div className="grid gap-5 sm:grid-cols-2">
            <Field label="Category" required error={f.errors.category}>
              {(p) => <SelectInput {...p} value={v.category} onChange={(e) => f.set('category', e.target.value)} placeholder="Choose a category" options={(config.categories.resource ?? []).map((c) => ({ value: c.slug, label: c.name }))} />}
            </Field>
            <Field label="Type" required error={f.errors.resource_type}>
              {(p) => <SelectInput {...p} value={v.resource_type} onChange={(e) => f.set('resource_type', e.target.value)} placeholder="Choose a type" options={types.map((t) => ({ value: t, label: humanize(t) }))} />}
            </Field>
            <Field label="Level">
              {(p) => <SelectInput {...p} value={v.level} onChange={(e) => f.set('level', e.target.value)} placeholder="Any level" options={levels.map((t) => ({ value: t, label: humanize(t) }))} />}
            </Field>
            <Field label="Language" hint="Two-letter code, e.g. en, de, ja.">
              {(p) => <TextInput {...p} value={v.language} maxLength={10} onChange={(e) => f.set('language', e.target.value.toLowerCase())} className="font-mono" />}
            </Field>
          </div>
          {v.resource_type === 'official_docs' && check && !check.official_domain && (
            <p className="flex items-start gap-2 rounded-[10px] bg-surface-2 p-3 text-sm"><Info size={15} className="mt-0.5 shrink-0" aria-hidden /> We'll show this as "Official docs (unverified)" until a moderator confirms the domain.</p>
          )}
          <Field label="Tags">
            {(p) => <TagInput id={p.id} value={v.tags} onChange={(x) => f.set('tags', x)} module="resource" />}
          </Field>
        </FormSection>
        <SubmitBar busy={busy} label={editing ? 'Save changes' : 'Add resource'} onCancel={() => navigate(-1)} />
      </form>
      {editing && id && (
        <section id="danger" className="rounded-[10px] border border-danger p-5">
          <h2 className="text-lg text-danger">Danger zone</h2>
          <ConfirmDialog
            trigger={<Button variant="danger" className="mt-3">Delete resource</Button>}
            title="Delete this resource?"
            description="It will disappear from collections that include it, and its comments will be hidden."
            confirmLabel="Delete resource"
            onConfirm={async () => { await apiFetch(`/api/resources/${id}`, { method: 'DELETE' }); bypass(); await qc.invalidateQueries({ queryKey: ['resources'] }); toast.success('Resource deleted'); navigate('/resources', { replace: true }); }}
          />
        </section>
      )}
    </FormShell>
  );
}
