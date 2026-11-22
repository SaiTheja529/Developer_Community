import { useEffect, useState } from 'react';
import { useNavigate, useParams, useSearchParams, Link } from 'react-router';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { Sparkles } from 'lucide-react';
import { apiFetch, ApiError } from '@/lib/api/client';
import { useIdea } from '@/lib/api/queries';
import { useDraft } from '@/lib/api/ai';
import { useConfig } from '@/hooks/useConfig';
import { useForm, useFormAutosave, useUnsavedChangesGuard } from '@/hooks/useForm';
import type { CollaborationStatus, IdeaDetail, IdeaPrefill } from '@/lib/api/types';
import { ErrorSummary, Field, FormSection, SelectInput, TextArea, TextInput } from '@/components/forms/Field';
import { TagInput } from '@/components/forms/TagInput';
import { MarkdownEditor } from '@/components/forms/MarkdownEditor';
import { FeatureListEditor, type FeatureRow } from '@/components/forms/ListEditors';
import { RepoUrlField } from '@/components/forms/UrlFields';
import { DraftPrefillBanner, FormShell, RestoreBanner, SubmitBar } from '@/components/forms/FormShell';
import { ConfirmDialog } from '@/components/common/ConfirmDialog';
import { Button, buttonClass } from '@/components/common/Button';
import { DetailSkeleton } from '@/components/common/States';

interface V extends Record<string, unknown> {
  title: string; category: string; tags: string[]; collaboration_status: CollaborationStatus; problem_statement: string; proposed_solution: string;
  description: string; expected_features: FeatureRow[]; tech_stack: string[]; github_url: string; ai_assisted: boolean;
}
const EMPTY: V = { title: '', category: '', tags: [], collaboration_status: 'sharing', problem_statement: '', proposed_solution: '', description: '', expected_features: [], tech_stack: [], github_url: '', ai_assisted: false };
const LABELS: Record<string, string> = { title: 'Title', category: 'Category', problem_statement: 'Problem', proposed_solution: 'Proposed solution', description: 'Details', expected_features: 'Expected features', tech_stack: 'Tech stack', github_url: 'GitHub link', tags: 'Tags' };

function validate(v: V) {
  const e: Record<string, string> = {};
  if (v.title.trim().length < 5) e.title = 'Use at least 5 characters.';
  if (!v.category) e.category = 'Choose a category.';
  if (v.problem_statement.trim().length < 20) e.problem_statement = 'Describe the problem in at least 20 characters.';
  if (v.proposed_solution.trim().length < 20) e.proposed_solution = 'Describe the solution in at least 20 characters.';
  if (v.expected_features.some((x) => !x.title.trim())) e.expected_features = 'Every feature needs a title, or remove empty rows.';
  return e;
}

export default function IdeaFormPage() {
  const { id } = useParams();
  const editing = !!id;
  const [sp] = useSearchParams();
  const draftId = sp.get('draft');
  const index = Number(sp.get('index') ?? 0);
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { data: config } = useConfig();
  const existing = useIdea(id);
  const draft = useDraft(editing ? null : draftId);
  const f = useForm<V>(EMPTY);
  const [loaded, setLoaded] = useState(!editing && !draftId);
  const [busy, setBusy] = useState(false);
  const auto = useFormAutosave(`idea:${id ?? 'new'}`, f.values, f.dirty, !draftId);
  const [showRestore, setShowRestore] = useState(!!auto.saved);
  const bypass = useUnsavedChangesGuard(f.dirty && !busy);

  useEffect(() => {
    if (loaded) return;
    if (editing && existing.data) {
      const i = existing.data;
      f.reset({ title: i.title, category: i.category.slug, tags: i.tags, collaboration_status: i.collaboration_status, problem_statement: i.problem_statement, proposed_solution: i.proposed_solution, description: i.description ?? '', expected_features: i.expected_features.map((x) => ({ title: x.title, detail: x.detail ?? '' })), tech_stack: i.tech_stack, github_url: i.github_url ?? '', ai_assisted: i.ai_assisted });
      setLoaded(true);
    }
    if (!editing && draft.data) {
      const p = ((draft.data.prefill as IdeaPrefill[]) ?? [])[index];
      if (p) f.reset({ ...EMPTY, title: p.title, problem_statement: p.problem_statement ?? '', proposed_solution: p.proposed_solution ?? '', description: p.description ?? '', expected_features: (p.expected_features ?? []).map((x) => ({ title: x.title, detail: x.detail ?? '' })), tech_stack: p.tech_stack ?? [], category: p.category ?? '', tags: p.tags ?? [], ai_assisted: true });
      setLoaded(true);
    }
  }, [editing, existing.data, draft.data, loaded, f, index]);

  if ((editing && existing.isLoading) || (draftId && draft.isLoading) || !config) return <DetailSkeleton />;
  if (editing && existing.data && !existing.data.viewer.can_edit) return <div className="mx-auto max-w-[720px] px-4 py-20 text-center"><h1 className="text-2xl">You can only edit your own idea.</h1></div>;
  const v = f.values;
  const aiApplied = () => f.set('ai_assisted', true);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const errs = validate(v);
    if (Object.keys(errs).length) { f.setErrors(errs); requestAnimationFrame(() => document.getElementById('error-summary')?.focus()); return; }
    setBusy(true);
    const body = {
      ...v, description: v.description || null, github_url: v.github_url.trim() || null,
      expected_features: v.expected_features.map((x) => ({ title: x.title, detail: x.detail || null })),
      ...(editing ? {} : { source_draft_id: draftId }),
    };
    try {
      const res = await apiFetch<{ data: IdeaDetail }>(editing ? `/api/ideas/${id}` : '/api/ideas', { method: editing ? 'PATCH' : 'POST', body });
      auto.clear();
      bypass();
      await qc.invalidateQueries({ queryKey: ['ideas'] });
      void qc.invalidateQueries({ queryKey: ['home'] });
      toast.success(editing ? 'Idea updated' : 'Idea published');
      navigate(`/ideas/${res.data.id}/${res.data.slug}`, { replace: true });
    } catch (err) {
      if (!f.applyApiError(err)) toast.error(err instanceof ApiError ? err.message : 'Could not save. Try again.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <FormShell
      module="idea"
      title={editing ? `Edit ${existing.data?.title ?? 'idea'}` : 'Share a project idea'}
      sections={[{ id: 'basics', label: 'Basics' }, { id: 'problem', label: 'Problem and solution' }, { id: 'details', label: 'Details' }, { id: 'features', label: 'Expected features' }, { id: 'tech', label: 'Tech stack and repo' }, ...(editing ? [{ id: 'danger', label: 'Danger zone' }] : [])]}
      banner={<>
        {draftId && !editing && <DraftPrefillBanner />}
        {showRestore && auto.saved && !draftId && <RestoreBanner onRestore={() => { f.setValues(auto.saved as V); f.setDirty(true); setShowRestore(false); }} onDiscard={() => { auto.clear(); setShowRestore(false); }} />}
        {!editing && !draftId && (
          <Link to="/ai/generate/project-idea" className={buttonClass('ai', 'md')}><Sparkles size={15} aria-hidden /> Generate an idea with AI</Link>
        )}
      </>}
    >
      <form onSubmit={submit} noValidate className="space-y-5">
        <ErrorSummary errors={f.errors} labels={LABELS} />
        <FormSection id="basics" title="Basics">
          <Field label="Title" required error={f.errors.title} counter={{ n: v.title.length, max: 120 }}>
            {(p) => <TextInput {...p} value={v.title} maxLength={120} onChange={(e) => f.set('title', e.target.value)} />}
          </Field>
          <div className="grid gap-5 sm:grid-cols-2">
            <Field label="Category" required error={f.errors.category}>
              {(p) => <SelectInput {...p} value={v.category} onChange={(e) => f.set('category', e.target.value)} placeholder="Choose a category" options={(config.categories.idea ?? []).map((c) => ({ value: c.slug, label: c.name }))} />}
            </Field>
            <Field label="Collaboration" hint="You can change this later.">
              {(p) => <SelectInput {...p} value={v.collaboration_status} onChange={(e) => f.set('collaboration_status', e.target.value as CollaborationStatus)} options={[{ value: 'sharing', label: 'Just sharing for feedback' }, { value: 'seeking_collaborators', label: 'Looking for collaborators' }, { value: 'team_formed', label: 'Team formed' }]} />}
            </Field>
          </div>
          <Field label="Tags" error={f.errors.tags}>
            {(p) => <TagInput id={p.id} value={v.tags} onChange={(x) => f.set('tags', x)} module="idea" />}
          </Field>
        </FormSection>
        <FormSection id="problem" title="Problem and solution">
          <Field label="Problem" required hint="Who has this problem, and why does it matter?" error={f.errors.problem_statement} counter={{ n: v.problem_statement.length, max: 5000 }}>
            {(p) => <TextArea {...p} rows={4} value={v.problem_statement} onChange={(e) => f.set('problem_statement', e.target.value)} />}
          </Field>
          <Field label="Proposed solution" required error={f.errors.proposed_solution} counter={{ n: v.proposed_solution.length, max: 5000 }}>
            {(p) => <MarkdownEditor id={p.id} value={v.proposed_solution} onChange={(x) => f.set('proposed_solution', x)} max={5000} field="proposed_solution" kind="idea" rows={5} onAIApplied={aiApplied} invalid={p['aria-invalid']} describedBy={p['aria-describedby']} />}
          </Field>
        </FormSection>
        <FormSection id="details" title="Details" description="Target users, architecture, milestones, open questions.">
          <Field label="Description" counter={{ n: v.description.length, max: 20000 }}>
            {(p) => <MarkdownEditor id={p.id} value={v.description} onChange={(x) => f.set('description', x)} max={20000} field="description" kind="idea" rows={8} onAIApplied={aiApplied} />}
          </Field>
        </FormSection>
        <FormSection id="features" title="Expected features">
          <FeatureListEditor value={v.expected_features} onChange={(x) => f.set('expected_features', x)} />
          {f.errors.expected_features && <p className="text-sm text-danger">{f.errors.expected_features}</p>}
        </FormSection>
        <FormSection id="tech" title="Tech stack and repository">
          <Field label="Suggested tech stack" hint="Up to 20, e.g. python, react, postgresql.">
            {(p) => <TagInput id={p.id} value={v.tech_stack} onChange={(x) => f.set('tech_stack', x)} max={20} placeholder="Add a technology" />}
          </Field>
          <Field label="GitHub link (optional)" error={f.errors.github_url}>
            {(p) => <RepoUrlField id={p.id} value={v.github_url} onChange={(x) => f.set('github_url', x)} checkDuplicate={false} invalid={p['aria-invalid']} />}
          </Field>
        </FormSection>
        <SubmitBar busy={busy} label={editing ? 'Save changes' : 'Publish idea'} onCancel={() => navigate(-1)} />
      </form>
      {editing && id && (
        <section id="danger" className="rounded-[10px] border border-danger p-5">
          <h2 className="text-lg text-danger">Danger zone</h2>
          <ConfirmDialog
            trigger={<Button variant="danger" className="mt-3">Delete idea</Button>}
            title="Delete this idea?"
            description="Comments and suggestions will be hidden too, and pending collaboration requests will be withdrawn."
            confirmLabel="Delete idea"
            onConfirm={async () => { await apiFetch(`/api/ideas/${id}`, { method: 'DELETE' }); bypass(); await qc.invalidateQueries({ queryKey: ['ideas'] }); toast.success('Idea deleted'); navigate('/ideas', { replace: true }); }}
          />
        </section>
      )}
    </FormShell>
  );
}
