import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { BookOpen, FileText, Lightbulb, MessageSquareText, Sparkles, Wand2, Wrench, type LucideIcon } from 'lucide-react';
import { apiFetch, ApiError } from '@/lib/api/client';
import type { AIDraft } from '@/lib/api/types';
import { Field, SelectInput, TextArea, TextInput } from '@/components/forms/Field';
import { TagInput } from '@/components/forms/TagInput';
import { RepoUrlField } from '@/components/forms/UrlFields';
import { Button } from '@/components/common/Button';
import { useAIStatus } from '@/lib/api/ai';
import { cn } from '@/lib/cn';

const TASKS: { to?: string; icon: LucideIcon; title: string; input: string; output: string; note?: string }[] = [
  { to: '/ai/generate/harness', icon: Wrench, title: 'Document a harness from a GitHub repo', input: 'A public repository URL, plus optional context.', output: 'A harness write-up: explanation, architecture, components with evidence, setup and limitations.' },
  { to: '/ai/generate/project-idea', icon: Lightbulb, title: 'Generate project ideas', input: 'A domain, a problem or your interests, and tech preferences.', output: '1–3 idea proposals with features, stack, milestones and challenges.' },
  { to: '/ai/generate/resources', icon: BookOpen, title: 'Find learning resources', input: 'A topic, your goal and level.', output: 'A learning path. Every link is checked; unreachable ones are removed.' },
  { icon: Wand2, title: 'Improve existing text', input: 'Any text field in a form.', output: 'A suggested rewrite you compare before replacing.', note: 'Use the "Improve with AI" button in any editor.' },
  { icon: MessageSquareText, title: 'Get feedback on a harness or idea', input: 'A published harness or idea.', output: 'Suggestions grouped by category, with what they were based on.', note: 'Use "Get AI suggestions" on a harness or idea page.' },
];

export function GeneratePickerPage() {
  return (
    <div className="mx-auto max-w-[1000px] px-4 py-8 md:px-8">
      <title>Generate with AI · DevCommons</title>
      <p className="flex items-center gap-2 font-mono text-sm text-ai"><Sparkles size={15} aria-hidden /> AI Workspace</p>
      <h1 className="mt-1 text-[28px]">Generate with AI</h1>
      <p className="mt-2 max-w-[60ch] text-muted">AI writes a draft. You review and edit it on a normal form, and nothing is published until you submit it yourself.</p>
      <div className="mt-6 flex gap-2 text-sm"><Link to="/ai/drafts" className="underline">Your drafts</Link><span className="text-muted">·</span><Link to="/ai" className="underline">Chat</Link></div>
      <ul className="mt-6 grid gap-4 md:grid-cols-2">
        {TASKS.map((t) => {
          const Icon = t.icon;
          const body = (
            <>
              <Icon size={20} className="text-ai" aria-hidden />
              <h2 className="mt-3 text-[17px] font-semibold">{t.title}</h2>
              <dl className="mt-2 space-y-1 text-sm">
                <div><dt className="inline font-medium">You give: </dt><dd className="inline text-muted">{t.input}</dd></div>
                <div><dt className="inline font-medium">You get: </dt><dd className="inline text-muted">{t.output}</dd></div>
              </dl>
              {t.note && <p className="mt-3 font-mono text-xs text-ai">{t.note}</p>}
            </>
          );
          return (
            <li key={t.title}>
              {t.to ? (
                <Link to={t.to} className="ai-surface block h-full rounded-[10px] p-5 hover:bg-ai-soft">{body}</Link>
              ) : (
                <div className="block h-full rounded-[10px] border border-border bg-surface p-5">{body}</div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function ProgressCard({ started, onCancel }: { started: number; onCancel: () => void }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  const s = Math.floor((now - started) / 1000);
  return (
    <div className="ai-surface rounded-[10px] p-5" role="status" aria-live="polite">
      <p className="flex items-center gap-2 font-medium"><Sparkles size={16} className="animate-pulse text-ai" aria-hidden /> Generating… this usually takes 20–40 seconds.</p>
      <p className="mt-1 font-mono text-sm text-muted">{s}s elapsed</p>
      <Button type="button" className="mt-4" onClick={onCancel}>Cancel</Button>
    </div>
  );
}

const QUOTA_MSG: Record<string, string> = {
  ai_quota_exceeded: "You've reached today's AI generation limit. It resets at 00:00 UTC.",
  ai_unavailable: 'AI is unavailable right now. Try again in a few minutes.',
  email_not_verified: 'Verify your email to use AI generation.',
};

export function GenerateTaskPage() {
  const { task } = useParams();
  const [sp] = useSearchParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const status = useAIStatus();
  const [started, setStarted] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const ctrl = useRef<AbortController | null>(null);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  // harness
  const [repo, setRepo] = useState(sp.get('repo') ?? '');
  const [extra, setExtra] = useState('');
  // idea
  const [domain, setDomain] = useState('');
  const [problem, setProblem] = useState('');
  const [tech, setTech] = useState<string[]>([]);
  const [interests, setInterests] = useState('');
  const [count, setCount] = useState('2');
  // resources
  const [topic, setTopic] = useState('');
  const [goal, setGoal] = useState('');
  const [level, setLevel] = useState('');

  if (!['harness', 'project-idea', 'resources'].includes(task ?? '')) return <div className="px-4 py-20 text-center"><h1 className="text-2xl">Unknown generation task.</h1></div>;

  const meta = {
    harness: { title: 'Document a harness', icon: FileText },
    'project-idea': { title: 'Generate project ideas', icon: Lightbulb },
    resources: { title: 'Find learning resources', icon: BookOpen },
  }[task as 'harness'];

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setFieldErrors({});
    let body: Record<string, unknown>;
    if (task === 'harness') {
      if (!repo.trim()) return setFieldErrors({ repo_url: 'Enter a GitHub repository URL.' });
      body = { repo_url: repo.trim(), additional_context: extra.trim() || null };
    } else if (task === 'project-idea') {
      if (!domain.trim() && !problem.trim() && !interests.trim()) return setError('Fill in at least one of domain, problem, or interests.');
      body = { domain: domain.trim() || null, problem: problem.trim() || null, interests: interests.trim() || null, tech_preferences: tech, count: Number(count) };
    } else {
      if (topic.trim().length < 2) return setFieldErrors({ topic: 'Enter a topic.' });
      body = { topic: topic.trim(), goal: goal.trim() || null, level: level || null };
    }
    ctrl.current = new AbortController();
    setStarted(Date.now());
    try {
      const res = await apiFetch<{ data: AIDraft }>(`/api/ai/generate/${task}`, { method: 'POST', body, signal: ctrl.current.signal });
      void qc.invalidateQueries({ queryKey: ['ai'] });
      // If the person left this page while waiting, don't yank them back: offer the draft instead.
      if (mounted.current) navigate(`/ai/drafts/${res.data.id}`);
      else toast.success('Your AI draft is ready', { action: { label: 'Open', onClick: () => navigate(`/ai/drafts/${res.data.id}`) }, duration: 15000 });
    } catch (err) {
      if (ctrl.current?.signal.aborted) setError('Cancelled. Nothing was saved.');
      else if (err instanceof ApiError && err.code === 'repo_unavailable') setFieldErrors({ repo_url: "We couldn't read that repository. It may be private or not exist." });
      else if (err instanceof ApiError && err.code === 'validation_error') setFieldErrors((err.details?.fields as Record<string, string>) ?? {});
      else if (err instanceof ApiError) setError(QUOTA_MSG[err.code] ?? err.message);
      else setError('Generation failed. Check your connection and try again.');
    } finally {
      if (mounted.current) setStarted(null);
    }
  };

  const Icon = meta.icon;
  const today = status.data?.today;
  return (
    <div className="mx-auto max-w-[720px] px-4 py-8 md:px-8">
      <title>{`${meta.title} · AI Workspace · DevCommons`}</title>
      <Link to="/ai/generate" className="text-sm text-muted hover:underline">Generate with AI</Link>
      <h1 className="mt-2 flex items-center gap-2 text-[26px]"><Icon size={22} className="text-ai" aria-hidden /> {meta.title}</h1>
      {today && <p className="mt-1 font-mono text-xs text-muted">{today.generations} / {today.limit_generations} generations used today</p>}
      {status.data && !status.data.enabled && <p className="ai-surface mt-4 rounded-[10px] p-4 text-sm">AI is unavailable right now. Everything else keeps working.</p>}
      {started ? (
        <div className="mt-6"><ProgressCard started={started} onCancel={() => ctrl.current?.abort()} /></div>
      ) : (
        <form onSubmit={submit} noValidate className="mt-6 space-y-5 rounded-[10px] border border-border bg-surface p-5 md:p-6">
          {task === 'harness' && (
            <>
              <Field label="GitHub repository URL" required error={fieldErrors.repo_url} hint="AI reads the README and a few files it can access. It tells you what it couldn't determine.">
                {(p) => <RepoUrlField id={p.id} value={repo} onChange={setRepo} invalid={p['aria-invalid']} describedBy={p['aria-describedby']} />}
              </Field>
              <Field label="Additional context" hint="Anything the repo doesn't say: how you use it, which tool it targets." counter={{ n: extra.length, max: 4000 }}>
                {(p) => <TextArea {...p} rows={4} value={extra} maxLength={4000} onChange={(e) => setExtra(e.target.value)} />}
              </Field>
            </>
          )}
          {task === 'project-idea' && (
            <>
              <p className="text-sm text-muted">Fill in at least one of domain, problem, or interests.</p>
              <Field label="Domain">{(p) => <TextInput {...p} value={domain} maxLength={300} onChange={(e) => setDomain(e.target.value)} placeholder="e.g. developer tools, healthcare" />}</Field>
              <Field label="Problem">{(p) => <TextArea {...p} rows={3} value={problem} maxLength={2000} onChange={(e) => setProblem(e.target.value)} placeholder="A problem you've noticed" />}</Field>
              <Field label="Interests">{(p) => <TextInput {...p} value={interests} maxLength={1000} onChange={(e) => setInterests(e.target.value)} placeholder="e.g. agents, offline-first, data viz" />}</Field>
              <Field label="Tech preferences">{(p) => <TagInput id={p.id} value={tech} onChange={setTech} max={15} placeholder="python, react…" />}</Field>
              <Field label="How many ideas">{(p) => <SelectInput {...p} value={count} onChange={(e) => setCount(e.target.value)} options={[{ value: '1', label: '1' }, { value: '2', label: '2' }, { value: '3', label: '3' }]} className="w-24" />}</Field>
            </>
          )}
          {task === 'resources' && (
            <>
              <Field label="Topic" required error={fieldErrors.topic}>{(p) => <TextInput {...p} value={topic} maxLength={200} onChange={(e) => setTopic(e.target.value)} placeholder="e.g. LangGraph, Rust async" />}</Field>
              <Field label="Goal">{(p) => <TextInput {...p} value={goal} maxLength={500} onChange={(e) => setGoal(e.target.value)} placeholder="What do you want to be able to do?" />}</Field>
              <Field label="Level">{(p) => <SelectInput {...p} value={level} onChange={(e) => setLevel(e.target.value)} placeholder="Any level" options={[{ value: 'beginner', label: 'Beginner' }, { value: 'intermediate', label: 'Intermediate' }, { value: 'advanced', label: 'Advanced' }]} />}</Field>
            </>
          )}
          {error && <p role="alert" className={cn('rounded-[6px] px-3 py-2 text-sm', error.startsWith('Cancelled') ? 'bg-surface-2' : 'bg-danger-soft text-danger')}>{error}</p>}
          <div className="flex justify-end">
            <Button type="submit" variant="ai" size="lg" disabled={status.data?.enabled === false}><Sparkles size={16} aria-hidden /> Generate draft</Button>
          </div>
        </form>
      )}
    </div>
  );
}
