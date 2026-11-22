import { useState } from 'react';
import { Sparkles } from 'lucide-react';
import { apiFetch, ApiError } from '@/lib/api/client';
import type { AIDraft, FeedbackSuggestionOut } from '@/lib/api/types';
import { Button } from '@/components/common/Button';
import { Badge } from '@/components/common/Badges';
import { SuggestDialog } from '@/components/feedback/SuggestionList';
import { useAuthAction } from '@/hooks/useAuthAction';
import { humanize } from '@/lib/format';

const KIND_MAP: Record<'harness' | 'idea', Record<string, string>> = {
  harness: { missing_feature: 'improvement', architecture: 'improvement', testing: 'improvement', documentation: 'improvement', security: 'bug_report', maintainability: 'improvement' },
  idea: { missing_feature: 'feature', architecture: 'architecture', testing: 'feature', documentation: 'feature', security: 'architecture', maintainability: 'architecture' },
};

export function FeedbackList({ suggestions, target }: { suggestions: FeedbackSuggestionOut[]; target?: { type: 'harness' | 'idea'; id: string; kinds: string[] } }) {
  const [posting, setPosting] = useState<FeedbackSuggestionOut | null>(null);
  const groups = suggestions.reduce<Record<string, FeedbackSuggestionOut[]>>((acc, s) => ((acc[s.category] ??= []).push(s), acc), {});
  return (
    <div className="space-y-5">
      {Object.entries(groups).map(([cat, items]) => (
        <section key={cat}>
          <h3 className="mb-2 text-sm font-semibold">{humanize(cat)}</h3>
          <ul className="space-y-2.5">
            {items.map((s, i) => (
              <li key={i} className="rounded-[10px] border border-border bg-surface p-3.5">
                <div className="flex flex-wrap items-start gap-2">
                  <p className="font-medium">{s.title}</p>
                  <Badge className="ml-auto border border-border font-mono text-muted">{s.confidence} confidence</Badge>
                </div>
                <p className="mt-1 text-sm text-muted">{s.detail}</p>
                {s.based_on.length > 0 && <p className="mt-2 font-mono text-xs text-muted">Based on: {s.based_on.join(' · ')}</p>}
                {target && <Button size="sm" className="mt-3" onClick={() => setPosting(s)}>Post as my suggestion</Button>}
              </li>
            ))}
          </ul>
        </section>
      ))}
      {target && posting && (
        <SuggestDialog
          key={posting.title}
          t={target.type}
          id={target.id}
          kinds={target.kinds}
          open
          onOpenChange={(o) => !o && setPosting(null)}
          aiAssisted
          initial={{ kind: KIND_MAP[target.type][posting.category] ?? target.kinds[0], title: posting.title.slice(0, 150), body: posting.detail }}
        />
      )}
    </div>
  );
}

/** "Get AI suggestions" on harness and idea pages (spec §11.1, §11.5). */
export function AIFeedbackPanel({ type, id, kinds }: { type: 'harness' | 'idea'; id: string; kinds: string[] }) {
  const [state, setState] = useState<{ loading?: boolean; draft?: AIDraft; error?: string }>({});
  const guard = useAuthAction();
  const run = () =>
    guard(async () => {
      setState({ loading: true });
      try {
        const r = await apiFetch<{ data: AIDraft }>('/api/ai/feedback-suggestions', { method: 'POST', body: { target_type: type, target_id: id } });
        setState({ draft: r.data });
      } catch (e) {
        setState({ error: e instanceof ApiError ? (e.code === 'ai_quota_exceeded' ? "You've reached today's AI limit." : e.message) : 'AI is unavailable right now.' });
      }
    });
  const out = state.draft?.output as { label?: string; suggestions?: FeedbackSuggestionOut[] } | undefined;
  return (
    <div className="ai-surface rounded-[10px] p-4">
      <p className="flex items-center gap-2 text-sm font-semibold"><Sparkles size={15} className="text-ai" aria-hidden /> AI-generated suggestions, not a community review</p>
      {!state.draft && !state.loading && (
        <>
          <p className="mt-1 text-sm text-muted">Get ideas for improvements based on this page, its repository and existing feedback.</p>
          <Button variant="ai" size="sm" className="mt-3" onClick={run}>Get AI suggestions</Button>
        </>
      )}
      {state.loading && <p className="mt-2 text-sm text-muted" role="status">Generating… this usually takes 15–30 seconds.</p>}
      {state.error && <p className="mt-2 text-sm text-danger" role="alert">{state.error}</p>}
      {out?.suggestions && (
        <div className="mt-4">
          {state.draft?.context_sources && state.draft.context_sources.length > 0 && (
            <p className="mb-3 font-mono text-xs text-muted">Sources: {state.draft.context_sources.map((s) => s.label).join(' · ')}</p>
          )}
          <FeedbackList suggestions={out.suggestions} target={{ type, id, kinds }} />
        </div>
      )}
    </div>
  );
}
