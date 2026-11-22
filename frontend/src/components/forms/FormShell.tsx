import type { ReactNode } from 'react';
import { RotateCcw, Sparkles } from 'lucide-react';
import { Button } from '@/components/common/Button';
import { MODULES, type ModuleKey } from '@/lib/modules';
import { cn } from '@/lib/cn';

/** Long-form page: sticky section nav on desktop, module stripe, optional banners (spec §11.1). */
export function FormShell({ module, title, sections, children, banner }: { module: ModuleKey; title: string; sections: { id: string; label: string }[]; children: ReactNode; banner?: ReactNode }) {
  const m = MODULES[module];
  return (
    <div className="mx-auto max-w-[1200px] px-4 py-8 md:px-8">
      <title>{`${title} · ${m.name} · DevCommons`}</title>
      <p className="font-mono text-sm" style={{ color: m.color }}>{m.name}</p>
      <h1 className="mt-1 text-[28px]">{title}</h1>
      <div className="mt-6 grid gap-8 lg:grid-cols-[200px_minmax(0,1fr)]">
        <nav aria-label="Form sections" className="hidden lg:block">
          <ol className={cn('sticky top-20 space-y-1 border-l-2 pl-3 text-sm')} style={{ borderColor: m.color }}>
            {sections.map((s) => (
              <li key={s.id}><a href={`#${s.id}`} className="block py-1 text-muted hover:text-text">{s.label}</a></li>
            ))}
          </ol>
        </nav>
        <div className="min-w-0 max-w-[780px] space-y-5">
          {banner}
          {children}
        </div>
      </div>
    </div>
  );
}

export function RestoreBanner({ onRestore, onDiscard }: { onRestore: () => void; onDiscard: () => void }) {
  return (
    <div role="status" className="flex flex-wrap items-center gap-3 rounded-[10px] border border-border bg-surface-2 px-4 py-3 text-sm">
      <RotateCcw size={15} aria-hidden /> You have an unsaved draft of this form.
      <div className="ml-auto flex gap-2">
        <Button size="sm" variant="primary" type="button" onClick={onRestore}>Restore it</Button>
        <Button size="sm" type="button" onClick={onDiscard}>Discard</Button>
      </div>
    </div>
  );
}

export function DraftPrefillBanner({ gaps }: { gaps?: string[] }) {
  return (
    <div className="ai-surface rounded-[10px] p-4 text-sm" role="note">
      <p className="flex items-center gap-2 font-medium text-ai"><Sparkles size={15} aria-hidden /> Prefilled from an AI draft</p>
      <p className="mt-1">Review every section before publishing; you are the author. The published post will carry an "AI-assisted" label.</p>
      {gaps && gaps.length > 0 && (
        <details className="mt-2">
          <summary className="cursor-pointer font-medium">Gaps the AI couldn't determine ({gaps.length})</summary>
          <ul className="mt-2 list-disc space-y-1 pl-5">{gaps.map((g, i) => <li key={i}>{g}</li>)}</ul>
        </details>
      )}
    </div>
  );
}

export function SubmitBar({ busy, label, onCancel }: { busy: boolean; label: string; onCancel?: () => void }) {
  return (
    <div className="sticky bottom-[60px] z-10 flex items-center justify-end gap-2 rounded-[10px] border border-border bg-surface/95 p-3 backdrop-blur md:bottom-3">
      {onCancel && <Button type="button" onClick={onCancel}>Cancel</Button>}
      <Button type="submit" variant="primary" size="lg" disabled={busy}>{busy ? 'Saving…' : label}</Button>
    </div>
  );
}
