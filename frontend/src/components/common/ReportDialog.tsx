import { useState } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { Flag } from 'lucide-react';
import { toast } from 'sonner';
import { apiFetch, ApiError } from '@/lib/api/client';
import { useAuthAction } from '@/hooks/useAuthAction';
import { Button } from './Button';
import { inputClass } from '@/components/forms/Field';
import { cn } from '@/lib/cn';

export type ReportTarget = 'harness' | 'idea' | 'resource' | 'collection' | 'comment' | 'suggestion' | 'review' | 'user' | 'ai_message' | 'ai_draft';

const REASONS: Record<string, string> = {
  spam: 'Spam', abuse: 'Abusive or harassing', broken_link: 'Broken link', outdated: 'Outdated', misleading: 'Misleading',
  inaccurate_ai: 'Inaccurate AI output', unsafe_ai: 'Unsafe AI output', copyright: 'Copyright problem', privacy: 'Exposes private information', other: 'Something else',
};
const BY_TARGET: Record<string, string[]> = {
  ai_message: ['inaccurate_ai', 'unsafe_ai', 'other'],
  ai_draft: ['inaccurate_ai', 'unsafe_ai', 'other'],
  resource: ['broken_link', 'outdated', 'misleading', 'spam', 'copyright', 'other'],
  user: ['spam', 'abuse', 'privacy', 'other'],
};
const DEFAULT = ['spam', 'abuse', 'misleading', 'copyright', 'privacy', 'other'];

/** Reason radio group filtered by target type, optional details (spec §10). */
export function ReportDialog({ targetType, targetId, open, onOpenChange, preselect }: { targetType: ReportTarget; targetId: string; open: boolean; onOpenChange: (o: boolean) => void; preselect?: string }) {
  const reasons = BY_TARGET[targetType] ?? DEFAULT;
  const [reason, setReason] = useState(preselect ?? reasons[0]);
  const [details, setDetails] = useState('');
  const [busy, setBusy] = useState(false);
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/30" />
        <Dialog.Content className="fixed top-1/2 left-1/2 z-50 w-[min(94vw,460px)] -translate-x-1/2 -translate-y-1/2 rounded-[14px] border border-border bg-surface p-6 shadow-[var(--shadow-dialog)]">
          <Dialog.Title className="text-lg font-semibold">Report this</Dialog.Title>
          <Dialog.Description className="mt-1 text-sm text-muted">Moderators review every report. The author isn't told who reported it.</Dialog.Description>
          <form
            className="mt-4"
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy(true);
              try {
                await apiFetch('/api/reports', { method: 'POST', body: { target_type: targetType, target_id: targetId, reason, details: details.trim() || null } });
                toast.success('Thanks. Moderators will review it.');
                onOpenChange(false);
              } catch (err) {
                toast.error(err instanceof ApiError && err.status === 409 ? "You've already reported this." : err instanceof ApiError ? err.message : 'Could not send the report.');
              } finally {
                setBusy(false);
              }
            }}
          >
            <fieldset>
              <legend className="text-sm font-medium">Reason</legend>
              <div className="mt-2 space-y-1">
                {reasons.map((r) => (
                  <label key={r} className="flex cursor-pointer items-center gap-2.5 rounded-[6px] px-2 py-1.5 text-sm hover:bg-surface-2">
                    <input type="radio" name="reason" value={r} checked={reason === r} onChange={() => setReason(r)} className="size-4" /> {REASONS[r]}
                  </label>
                ))}
              </div>
            </fieldset>
            <label className="mt-3 block text-sm font-medium" htmlFor="report-details">Details (optional)</label>
            <textarea id="report-details" rows={3} maxLength={1000} value={details} onChange={(e) => setDetails(e.target.value)} className={cn(inputClass, 'mt-1 py-2 text-sm')} />
            <div className="mt-4 flex justify-end gap-2">
              <Dialog.Close asChild><Button type="button">Cancel</Button></Dialog.Close>
              <Button type="submit" variant="primary" disabled={busy}>{busy ? 'Sending…' : 'Send report'}</Button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

export function ReportButton({ targetType, targetId, label = 'Report', size = 'md', className }: { targetType: ReportTarget; targetId: string; label?: string; size?: 'sm' | 'md'; className?: string }) {
  const [open, setOpen] = useState(false);
  const guard = useAuthAction();
  return (
    <>
      <Button size={size} variant="ghost" className={className} onClick={() => guard(() => setOpen(true), { requireVerified: false })}><Flag size={size === 'sm' ? 13 : 14} aria-hidden /> {label}</Button>
      {open && <ReportDialog targetType={targetType} targetId={targetId} open={open} onOpenChange={setOpen} />}
    </>
  );
}
