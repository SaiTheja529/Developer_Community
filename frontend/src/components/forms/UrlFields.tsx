import { useEffect, useState } from 'react';
import { Link } from 'react-router';
import { AlertTriangle, Archive, Check, Loader2, Scale, Star } from 'lucide-react';
import { getData, ApiError } from '@/lib/api/client';
import { useDebouncedValue } from '@/hooks/useDebouncedValue';
import type { HarnessSummary, ResourceSummary } from '@/lib/api/types';
import { compact } from '@/lib/format';
import { TimeAgo } from '@/components/common/Meta';
import { inputClass } from './Field';
import { cn } from '@/lib/cn';

export interface RepoPreview {
  owner: string; repo: string; canonical_url: string; description: string | null; stars: number | null; language: string | null;
  license: string | null; topics: string[]; pushed_at: string | null; archived: boolean; already_listed: HarnessSummary | null;
}

const GH = /^https?:\/\/(www\.)?github\.com\/[\w.-]+\/[\w.-]+\/?$/i;

/** Local format check, then /api/github/repo-preview debounced 500 ms (spec §10). */
export function RepoUrlField({ id, value, onChange, onPreview, checkDuplicate = true, invalid, describedBy }: {
  id: string; value: string; onChange: (v: string) => void; onPreview?: (p: RepoPreview | null) => void; checkDuplicate?: boolean; invalid?: boolean; describedBy?: string;
}) {
  const dv = useDebouncedValue(value.trim(), 500);
  const [st, setSt] = useState<{ loading?: boolean; preview?: RepoPreview; error?: string }>({});
  useEffect(() => {
    if (!dv) { setSt({}); onPreview?.(null); return; }
    if (!GH.test(dv)) { setSt({ error: 'Use a repository URL like https://github.com/owner/repo' }); onPreview?.(null); return; }
    let live = true;
    setSt({ loading: true });
    getData<RepoPreview>('/api/github/repo-preview', { url: dv })
      .then((p) => { if (live) { setSt({ preview: p }); onPreview?.(p); } })
      .catch((e) => { if (live) { setSt({ error: e instanceof ApiError && e.code === 'repo_unavailable' ? "We couldn't read that repository. It may be private or not exist." : e instanceof ApiError ? e.message : 'Could not check the repository.' }); onPreview?.(null); } });
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dv]);
  const p = st.preview;
  return (
    <div>
      <div className="relative">
        <input id={id} type="url" inputMode="url" value={value} onChange={(e) => onChange(e.target.value)} aria-invalid={invalid || !!st.error} aria-describedby={describedBy} placeholder="https://github.com/owner/repo" className={cn(inputClass, 'h-10 pr-9 font-mono text-sm')} />
        <span className="absolute top-1/2 right-3 -translate-y-1/2" aria-hidden>
          {st.loading ? <Loader2 size={15} className="animate-spin text-muted" /> : p ? <Check size={15} className="text-success" /> : null}
        </span>
      </div>
      <div aria-live="polite">
        {st.error && <p className="mt-1.5 flex items-center gap-1 text-sm text-danger"><AlertTriangle size={14} aria-hidden /> {st.error}</p>}
        {p && (
          <div className="stripe-harness mt-2 rounded-[10px] border border-border bg-bg p-3 text-sm">
            <p className="font-mono font-medium">{p.owner}/{p.repo}</p>
            {p.description && <p className="mt-0.5 text-muted">{p.description}</p>}
            <p className="mt-2 flex flex-wrap gap-x-4 gap-y-1 font-mono text-xs text-muted">
              <span className="inline-flex items-center gap-1"><Star size={12} aria-hidden /> {compact(p.stars)}</span>
              {p.language && <span>{p.language}</span>}
              {p.license && <span className="inline-flex items-center gap-1"><Scale size={12} aria-hidden /> {p.license}</span>}
              {p.pushed_at && <span>last push <TimeAgo iso={p.pushed_at} /></span>}
            </p>
            {p.archived && <p className="mt-2 flex items-center gap-1.5 text-warning"><Archive size={13} aria-hidden /> This repository is archived on GitHub.</p>}
            {checkDuplicate && p.already_listed && (
              <p className="mt-2 rounded-[6px] bg-warning-soft px-2.5 py-2">
                This repo is already on DevCommons. <Link to={`/harnesses/${p.already_listed.id}/${p.already_listed.slug}`} className="font-medium underline">View harness</Link>
                {' · '}<Link to={`/harnesses/${p.already_listed.id}/${p.already_listed.slug}?tab=reviews`} className="font-medium underline">Write a review instead</Link>
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export interface CheckUrl { valid: boolean; normalized: string | null; duplicate: ResourceSummary | null; blocked_reason?: string | null; domain?: string; official_domain?: boolean }

export function ResourceUrlField({ id, value, onChange, onChecked, invalid, describedBy, skipDuplicateId }: {
  id: string; value: string; onChange: (v: string) => void; onChecked?: (c: CheckUrl | null) => void; invalid?: boolean; describedBy?: string; skipDuplicateId?: string;
}) {
  const dv = useDebouncedValue(value.trim(), 500);
  const [st, setSt] = useState<{ loading?: boolean; res?: CheckUrl; error?: string }>({});
  useEffect(() => {
    if (!dv) { setSt({}); onChecked?.(null); return; }
    let live = true;
    setSt({ loading: true });
    getData<CheckUrl>('/api/resources/check-url', { url: dv })
      .then((r) => { if (live) { setSt({ res: r }); onChecked?.(r); } })
      .catch((e) => live && setSt({ error: e instanceof ApiError ? e.message : 'Could not check that URL.' }));
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dv]);
  const r = st.res;
  const dup = r?.duplicate && r.duplicate.id !== skipDuplicateId ? r.duplicate : null;
  return (
    <div>
      <input id={id} type="url" inputMode="url" value={value} onChange={(e) => onChange(e.target.value)} aria-invalid={invalid} aria-describedby={describedBy} placeholder="https://docs.example.com/guide" className={cn(inputClass, 'h-10 font-mono text-sm')} />
      <div aria-live="polite" className="text-sm">
        {st.loading && <p className="mt-1.5 text-muted">Checking…</p>}
        {st.error && <p className="mt-1.5 text-danger">{st.error}</p>}
        {r && !r.valid && <p className="mt-1.5 flex items-center gap-1 text-danger"><AlertTriangle size={14} aria-hidden /> {r.blocked_reason ? `This URL can't be added: ${r.blocked_reason}.` : 'Enter a full http(s) URL.'}</p>}
        {r?.valid && r.domain && !dup && <p className="mt-1.5 font-mono text-xs text-muted">Domain: {r.domain}{r.official_domain ? ' · trusted official domain' : ''}</p>}
        {dup && (
          <p className="mt-2 rounded-[6px] bg-warning-soft px-2.5 py-2">
            Already in the Knowledge Hub: <Link to={`/resources/${dup.id}`} className="font-medium underline">{dup.name}</Link>
          </p>
        )}
      </div>
    </div>
  );
}

