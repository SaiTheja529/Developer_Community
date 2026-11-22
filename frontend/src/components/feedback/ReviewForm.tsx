import { useState } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { Star } from 'lucide-react';
import { apiFetch, ApiError } from '@/lib/api/client';
import { Button } from '@/components/common/Button';
import { Field, TextArea, TextInput } from '@/components/forms/Field';
import { cn } from '@/lib/cn';

const DIMS = ['overall', 'documentation', 'setup', 'coordination', 'reliability'] as const;

function StarInput({ name, value, onChange }: { name: string; value: number | null; onChange: (v: number | null) => void }) {
  return (
    <fieldset className="flex flex-wrap items-center gap-2">
      <legend className="sr-only capitalize">{name}</legend>
      <span className="w-28 text-sm capitalize">{name}</span>
      <div className="flex" role="radiogroup" aria-label={`${name} rating`}>
        {[1, 2, 3, 4, 5].map((n) => (
          <label key={n} className="cursor-pointer p-0.5" title={`${n} of 5`}>
            <input type="radio" name={name} className="peer sr-only" checked={value === n} onChange={() => onChange(n)} />
            <span className="sr-only">{n} of 5</span>
            <Star size={20} aria-hidden className={cn('rounded peer-focus-visible:outline-2 peer-focus-visible:outline-focus', value != null && n <= value ? 'fill-harness text-harness' : 'text-border')} />
          </label>
        ))}
      </div>
      <button type="button" onClick={() => onChange(null)} className={cn('cursor-pointer text-xs underline', value == null ? 'text-muted' : '')} aria-pressed={value == null}>Not rated</button>
    </fieldset>
  );
}

/** The concept's four structured testing questions + optional ratings (spec §10.1). */
export function ReviewForm({ harnessId, open, onOpenChange }: { harnessId: string; open: boolean; onOpenChange: (o: boolean) => void }) {
  const qc = useQueryClient();
  const [v, setV] = useState({ what_tested: '', worked_well: '', did_not_work: '', recommendations: '', environment: '' });
  const [ratings, setRatings] = useState<Record<string, number | null>>({ overall: null, documentation: null, setup: null, coordination: null, reliability: null });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof v) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setV({ ...v, [k]: e.target.value });

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/30" />
        <Dialog.Content className="fixed top-1/2 left-1/2 z-50 max-h-[92dvh] w-[min(96vw,640px)] -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-[14px] border border-border bg-surface p-6 shadow-[var(--shadow-dialog)]">
          <Dialog.Title className="text-lg font-semibold">Write a testing report</Dialog.Title>
          <Dialog.Description className="mt-1 text-sm text-muted">Share what you actually tried. Reports are shown as community opinion, not guarantees.</Dialog.Description>
          <form
            className="mt-5 space-y-4"
            onSubmit={async (e) => {
              e.preventDefault();
              if (v.what_tested.trim().length < 20) { setErrors({ what_tested: 'Describe what you tested in at least 20 characters.' }); return; }
              setBusy(true);
              try {
                await apiFetch(`/api/harnesses/${harnessId}/reviews`, { method: 'POST', body: { ...Object.fromEntries(Object.entries(v).map(([k, x]) => [k, x.trim() || null])), ratings } });
                toast.success('Testing report posted');
                void qc.invalidateQueries({ queryKey: ['reviews', harnessId] });
                void qc.invalidateQueries({ queryKey: ['harnesses', 'detail', harnessId] });
                onOpenChange(false);
              } catch (err) {
                if (err instanceof ApiError && err.status === 409) toast.error("You've already posted a testing report for this harness.");
                else if (err instanceof ApiError && err.code === 'validation_error') setErrors((err.details?.fields as Record<string, string>) ?? {});
                else toast.error(err instanceof ApiError ? err.message : 'Could not post.');
              } finally {
                setBusy(false);
              }
            }}
          >
            <Field label="What did you test?" required error={errors.what_tested} counter={{ n: v.what_tested.length, max: 5000 }}>{(p) => <TextArea {...p} rows={3} value={v.what_tested} onChange={set('what_tested')} />}</Field>
            <Field label="What worked well?">{(p) => <TextArea {...p} rows={2} value={v.worked_well} onChange={set('worked_well')} />}</Field>
            <Field label="What did not work as expected?">{(p) => <TextArea {...p} rows={2} value={v.did_not_work} onChange={set('did_not_work')} />}</Field>
            <Field label="What improvements would you recommend?">{(p) => <TextArea {...p} rows={2} value={v.recommendations} onChange={set('recommendations')} />}</Field>
            <Field label="Environment" hint="Tool and version, OS, repo size.">{(p) => <TextInput {...p} value={v.environment} maxLength={500} onChange={set('environment')} placeholder="Claude Code 2.x on macOS, 20k LOC TypeScript" />}</Field>
            <details className="rounded-[10px] border border-border p-3">
              <summary className="cursor-pointer text-sm font-medium">Ratings (optional)</summary>
              <div className="mt-3 space-y-2">{DIMS.map((d) => <StarInput key={d} name={d} value={ratings[d]} onChange={(x) => setRatings({ ...ratings, [d]: x })} />)}</div>
            </details>
            <div className="flex justify-end gap-2">
              <Dialog.Close asChild><Button type="button">Cancel</Button></Dialog.Close>
              <Button type="submit" variant="primary" disabled={busy}>{busy ? 'Posting…' : 'Post report'}</Button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
