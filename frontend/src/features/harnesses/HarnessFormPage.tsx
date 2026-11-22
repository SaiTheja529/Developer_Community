import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { Sparkles } from 'lucide-react';
import { apiFetch, ApiError } from '@/lib/api/client';
import { useHarness } from '@/lib/api/queries';
import { useDraft } from '@/lib/api/ai';
import { useConfig } from '@/hooks/useConfig';
import { useForm, useFormAutosave, useUnsavedChangesGuard } from '@/hooks/useForm';
import type { HarnessDetail, HarnessDocOutput, HarnessPrefill } from '@/lib/api/types';
import { Field, FormSection, SelectInput, Switch, TextInput, ErrorSummary } from '@/components/forms/Field';
import { TagInput } from '@/components/forms/TagInput';
import { MarkdownEditor } from '@/components/forms/MarkdownEditor';
import { ComponentListEditor, type ComponentRow } from '@/components/forms/ListEditors';
import { RepoUrlField } from '@/components/forms/UrlFields';
import { DraftPrefillBanner, FormShell, RestoreBanner, SubmitBar } from '@/components/forms/FormShell';
import { ConfirmDialog } from '@/components/common/ConfirmDialog';
import { Button, buttonClass } from '@/components/common/Button';
import { DetailSkeleton } from '@/components/common/States';
import { TOOL_LABELS } from '@/lib/modules';
import { cn } from '@/lib/cn';

interface V extends Record<string, unknown> {
  repo_url: string; name: string; short_description: string; category: string; tools: string[]; tags: string[];
  detailed_explanation: string; architecture: string; components: ComponentRow[]; setup_instructions: string; limitations: string;
  accepts_collaboration: boolean; ai_assisted: boolean;
}
const EMPTY: V = { repo_url: '', name: '', short_description: '', category: '', tools: [], tags: [], detailed_explanation: '', architecture: '', components: [], setup_instructions: '', limitations: '', accepts_collaboration: false, ai_assisted: false };
const LABELS: Record<string, string> = { repo_url: 'Repository', name: 'Name', short_description: 'Short description', category: 'Category', tools: 'Tools', tags: 'Tags', detailed_explanation: 'How it works', architecture: 'Architecture', components: 'Components', setup_instructions: 'Setup', limitations: 'Limitations' };

const fromDetail = (h: HarnessDetail): V => ({
  repo_url: h.repo.url, name: h.name, short_description: h.short_description, category: h.category.slug, tools: h.tools, tags: h.tags,
  detailed_explanation: h.detailed_explanation, architecture: h.architecture ?? '', setup_instructions: h.setup_instructions ?? '', limitations: h.limitations ?? '',
  components: h.components.map((c) => ({ type: c.type, name: c.name, description: c.description ?? '' })), accepts_collaboration: h.accepts_collaboration, ai_assisted: h.ai_assisted,
});
const fromPrefill = (p: HarnessPrefill): V => ({
  ...EMPTY, repo_url: p.repo_url ?? '', name: p.name, short_description: p.short_description, category: p.category ?? '', tools: p.tools ?? [], tags: p.tags ?? [],
  detailed_explanation: p.detailed_explanation ?? '', architecture: p.architecture ?? '', setup_instructions: p.setup_instructions ?? '', limitations: p.limitations ?? '',
  components: (p.components ?? []).map((c) => ({ type: c.type, name: c.name, description: c.description ?? '' })), ai_assisted: true,
});

function validate(v: V): Record<string, string> {
  const e: Record<string, string> = {};
  if (!/^https?:\/\/(www\.)?github\.com\/[\w.-]+\/[\w.-]+\/?$/i.test(v.repo_url.trim())) e.repo_url = 'Enter a GitHub repository URL.';
  if (v.name.trim().length < 3) e.name = 'Use at least 3 characters.';
  if (v.short_description.trim().length < 20) e.short_description = 'Use at least 20 characters.';
  if (v.short_description.length > 280) e.short_description = 'Keep it under 280 characters.';
  if (!v.category) e.category = 'Choose a category.';
  if (!v.tools.length) e.tools = 'Pick at least one tool.';
  if (v.detailed_explanation.trim().length < 50) e.detailed_explanation = 'Explain how it works in at least 50 characters.';
  v.components.forEach((c, i) => { if (!c.name.trim()) e[`components.${i}.name`] = 'Give this component a name.'; });
  return e;
}

export default function HarnessFormPage() {
  const { id } = useParams();
  const editing = !!id;
  const [sp] = useSearchParams();
  const draftId = sp.get('draft');
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { data: config } = useConfig();
  const existing = useHarness(id);
  const draft = useDraft(editing ? null : draftId);
  const f = useForm<V>({ ...EMPTY, repo_url: sp.get('repo') ?? '' });
  const [loaded, setLoaded] = useState(!editing && !draftId);
  const [busy, setBusy] = useState(false);
  const [duplicate, setDuplicate] = useState<string | null>(null);
  const auto = useFormAutosave(`harness:${id ?? 'new'}`, f.values, f.dirty, !draftId);
  const [showRestore, setShowRestore] = useState(!!auto.saved);
  const bypassGuard = useUnsavedChangesGuard(f.dirty && !busy);

  useEffect(() => {
    if (editing && existing.data && !loaded) { f.reset(fromDetail(existing.data)); setLoaded(true); }
    if (!editing && draft.data && !loaded) { f.reset(fromPrefill(draft.data.prefill as HarnessPrefill)); setLoaded(true); }
  }, [editing, existing.data, draft.data, loaded, f]);

  const categories = config?.categories.harness ?? [];
  const tools = (config?.enums.tools as string[] | undefined) ?? Object.keys(TOOL_LABELS);
  const types = (config?.enums.component_types as string[] | undefined) ?? ['rule'];
  const gaps = useMemo(() => (draft.data?.output as unknown as HarnessDocOutput | undefined)?.gaps_and_uncertainties, [draft.data]);

  if ((editing && existing.isLoading) || (draftId && draft.isLoading) || !config) return <DetailSkeleton />;
  if (editing && existing.data && !existing.data.viewer.can_edit) return <div className="mx-auto max-w-[720px] px-4 py-20 text-center"><h1 className="text-2xl">You can only edit your own harness.</h1></div>;

  const v = f.values;
  const aiApplied = () => f.set('ai_assisted', true);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const errs = validate(v);
    if (Object.keys(errs).length) {
      f.setErrors(errs);
      requestAnimationFrame(() => document.getElementById('error-summary')?.focus());
      return;
    }
    setBusy(true);
    setDuplicate(null);
    const body = {
      ...v,
      architecture: v.architecture || null, setup_instructions: v.setup_instructions || null, limitations: v.limitations || null,
      components: v.components.map((c) => ({ ...c, description: c.description || null })),
      ...(editing ? {} : { source_draft_id: draftId }),
    };
    try {
      const res = await apiFetch<{ data: HarnessDetail }>(editing ? `/api/harnesses/${id}` : '/api/harnesses', { method: editing ? 'PATCH' : 'POST', body });
      auto.clear();
      bypassGuard();
      await qc.invalidateQueries({ queryKey: ['harnesses'] });
      void qc.invalidateQueries({ queryKey: ['home'] });
      toast.success(editing ? 'Harness updated' : 'Harness published');
      navigate(`/harnesses/${res.data.id}/${res.data.slug}`, { replace: true });
    } catch (err) {
      if (err instanceof ApiError && err.code === 'duplicate') setDuplicate(String(err.details?.existing_id ?? ''));
      else if (err instanceof ApiError && err.code === 'repo_unavailable') f.setErrors({ repo_url: "We couldn't read that repository. It may be private or not exist." });
      else if (!f.applyApiError(err)) toast.error(err instanceof ApiError ? err.message : 'Could not save. Try again.');
    } finally {
      setBusy(false);
    }
  };

  const sections = [
    { id: 'repository', label: 'Repository' }, { id: 'basics', label: 'Basics' }, { id: 'how', label: 'How it works' },
    { id: 'architecture', label: 'Architecture' }, { id: 'setup', label: 'Setup and limitations' }, { id: 'collab', label: 'Collaboration' },
    ...(editing ? [{ id: 'danger', label: 'Danger zone' }] : []),
  ];

  return (
    <FormShell
      module="harness"
      title={editing ? `Edit ${existing.data?.name ?? 'harness'}` : 'Submit a harness'}
      sections={sections}
      banner={<>
        {draftId && !editing && <DraftPrefillBanner gaps={gaps} />}
        {showRestore && auto.saved && !draftId && <RestoreBanner onRestore={() => { f.setValues(auto.saved as V); f.setDirty(true); setShowRestore(false); }} onDiscard={() => { auto.clear(); setShowRestore(false); }} />}
      </>}
    >
      <form onSubmit={submit} noValidate className="space-y-5">
        <ErrorSummary errors={f.errors} labels={LABELS} />
        {duplicate !== null && (
          <div role="alert" className="rounded-[10px] border border-warning bg-warning-soft p-4 text-sm">
            This repository is already listed. {duplicate && <Link to={`/harnesses/${duplicate}`} className="font-medium underline">View the existing harness</Link>} and consider writing a testing report instead.
          </div>
        )}
        <FormSection id="repository" title="Repository" description="We read public metadata from GitHub: stars, language, license and last push.">
          <Field label="GitHub repository URL" required error={f.errors.repo_url}>
            {(p) => (
              <RepoUrlField
                id={p.id}
                value={v.repo_url}
                invalid={p['aria-invalid']}
                describedBy={p['aria-describedby']}
                onChange={(x) => f.set('repo_url', x)}
                onPreview={(pv) => {
                  if (!pv || editing) return;
                  if (!v.name) f.set('name', pv.repo.replace(/[-_]/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()));
                  if (!v.short_description && pv.description) f.set('short_description', pv.description.slice(0, 280));
                }}
              />
            )}
          </Field>
          {!editing && !draftId && (
            <Link to={`/ai/generate/harness${v.repo_url ? `?repo=${encodeURIComponent(v.repo_url)}` : ''}`} className={buttonClass('ai', 'md', 'self-start')}>
              <Sparkles size={15} aria-hidden /> Draft documentation with AI
            </Link>
          )}
        </FormSection>

        <FormSection id="basics" title="Basics">
          <Field label="Name" required error={f.errors.name} counter={{ n: v.name.length, max: 100 }}>
            {(p) => <TextInput {...p} value={v.name} maxLength={100} onChange={(e) => f.set('name', e.target.value)} />}
          </Field>
          <Field label="Short description" required hint="One or two sentences shown on cards." error={f.errors.short_description} counter={{ n: v.short_description.length, max: 280 }}>
            {(p) => <TextInput {...p} value={v.short_description} onChange={(e) => f.set('short_description', e.target.value)} />}
          </Field>
          <div className="grid gap-5 sm:grid-cols-2">
            <Field label="Category" required error={f.errors.category}>
              {(p) => <SelectInput {...p} value={v.category} onChange={(e) => f.set('category', e.target.value)} placeholder="Choose a category" options={categories.map((c) => ({ value: c.slug, label: c.name }))} />}
            </Field>
            <Field label="Tags" hint="Up to 8. Lowercase, dashes for spaces." error={f.errors.tags}>
              {(p) => <TagInput id={p.id} value={v.tags} onChange={(x) => f.set('tags', x)} module="harness" invalid={p['aria-invalid']} describedBy={p['aria-describedby']} />}
            </Field>
          </div>
          <fieldset aria-describedby={f.errors.tools ? 'tools-err' : undefined}>
            <legend className="text-sm font-medium">Tools it works with <span className="font-normal text-muted">(required)</span></legend>
            <div className="mt-2 flex flex-wrap gap-2">
              {tools.map((t) => {
                const on = v.tools.includes(t);
                return (
                  <label key={t} className={cn('inline-flex h-9 cursor-pointer items-center gap-2 rounded-[6px] border px-3 text-sm', on ? 'border-harness bg-harness-soft text-harness' : 'border-border hover:bg-surface-2')}>
                    <input type="checkbox" className="sr-only" checked={on} onChange={() => f.set('tools', on ? v.tools.filter((x) => x !== t) : [...v.tools, t])} />
                    {TOOL_LABELS[t] ?? t}
                  </label>
                );
              })}
            </div>
            {f.errors.tools && <p id="tools-err" className="mt-1.5 text-sm text-danger">{f.errors.tools}</p>}
          </fieldset>
        </FormSection>

        <FormSection id="how" title="How it works" description="What problem it solves and how the pieces work together. Markdown works.">
          <Field label="Detailed explanation" required error={f.errors.detailed_explanation} counter={{ n: v.detailed_explanation.length, max: 20000 }}>
            {(p) => <MarkdownEditor id={p.id} value={v.detailed_explanation} onChange={(x) => f.set('detailed_explanation', x)} max={20000} field="detailed_explanation" rows={10} onAIApplied={aiApplied} invalid={p['aria-invalid']} describedBy={p['aria-describedby']} />}
          </Field>
        </FormSection>

        <FormSection id="architecture" title="Architecture and components">
          <Field label="Architecture" counter={{ n: v.architecture.length, max: 20000 }}>
            {(p) => <MarkdownEditor id={p.id} value={v.architecture} onChange={(x) => f.set('architecture', x)} max={20000} field="architecture" kind="architecture" onAIApplied={aiApplied} />}
          </Field>
          <div>
            <p className="mb-2 text-sm font-medium">Components</p>
            <ComponentListEditor value={v.components} onChange={(x) => f.set('components', x)} types={types} errors={f.errors} />
          </div>
        </FormSection>

        <FormSection id="setup" title="Setup and limitations">
          <Field label="Setup instructions" counter={{ n: v.setup_instructions.length, max: 20000 }}>
            {(p) => <MarkdownEditor id={p.id} value={v.setup_instructions} onChange={(x) => f.set('setup_instructions', x)} max={20000} field="setup_instructions" kind="setup" rows={6} onAIApplied={aiApplied} />}
          </Field>
          <Field label="Known limitations" counter={{ n: v.limitations.length, max: 10000 }}>
            {(p) => <MarkdownEditor id={p.id} value={v.limitations} onChange={(x) => f.set('limitations', x)} max={10000} field="limitations" rows={4} onAIApplied={aiApplied} />}
          </Field>
        </FormSection>

        <FormSection id="collab" title="Collaboration">
          <Switch checked={v.accepts_collaboration} onChange={(x) => f.set('accepts_collaboration', x)} label="Allow collaboration requests" description="Others can ask to help improve this harness. You decide whether to share contact details." />
        </FormSection>

        <SubmitBar busy={busy} label={editing ? 'Save changes' : 'Publish harness'} onCancel={() => navigate(-1)} />
      </form>

      {editing && id && (
        <section id="danger" className="rounded-[10px] border border-danger p-5">
          <h2 className="text-lg text-danger">Danger zone</h2>
          <p className="mt-1 text-sm text-muted">Deleting removes the harness from DevCommons. Comments, reviews and suggestions will be hidden too.</p>
          <ConfirmDialog
            trigger={<Button variant="danger" className="mt-4">Delete harness</Button>}
            title="Delete this harness?"
            description="Comments, testing reports and suggestions will be hidden too. This can't be undone from the app."
            confirmLabel="Delete harness"
            onConfirm={async () => {
              await apiFetch(`/api/harnesses/${id}`, { method: 'DELETE' });
              bypassGuard();
              await qc.invalidateQueries({ queryKey: ['harnesses'] });
              toast.success('Harness deleted');
              navigate('/harnesses', { replace: true });
            }}
          />
        </section>
      )}
    </FormShell>
  );
}
