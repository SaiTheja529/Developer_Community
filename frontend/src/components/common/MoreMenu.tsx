import { useState } from 'react';
import { useNavigate } from 'react-router';
import * as Dropdown from '@radix-ui/react-dropdown-menu';
import * as Dialog from '@radix-ui/react-dialog';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { Eye, EyeOff, Flag, MoreHorizontal, Pencil, Star, StarOff, Trash2, XOctagon } from 'lucide-react';
import { apiFetch, ApiError } from '@/lib/api/client';
import { useAuth } from '@/features/auth/AuthProvider';
import { useAuthAction } from '@/hooks/useAuthAction';
import type { ContentStatus, Viewer } from '@/lib/api/types';
import { ReportDialog, type ReportTarget } from './ReportDialog';
import { Button } from './Button';
import { inputClass } from '@/components/forms/Field';

type ModAction = 'hide' | 'restore' | 'remove' | 'feature' | 'unfeature';
const item = 'flex cursor-pointer items-center gap-2 rounded-[6px] px-2.5 py-2 text-sm outline-none data-[highlighted]:bg-surface-2';

/** ⋯ menu on detail pages: Report, owner Edit, and moderator actions (spec §10 OwnerToolbar / ModeratorMenu). */
export function MoreMenu({ targetType, id, viewer, status, isFeatured, editPath, plural }: {
  targetType: Exclude<ReportTarget, 'ai_message' | 'ai_draft' | 'user' | 'comment' | 'suggestion' | 'review'>;
  id: string; viewer: Viewer; status: ContentStatus; isFeatured: boolean; editPath: string; plural: string;
}) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const guard = useAuthAction();
  const { user } = useAuth();
  const [report, setReport] = useState(false);
  const [mod, setMod] = useState<ModAction | null>(null);
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const canMod = viewer.can_moderate || user?.role === 'moderator' || user?.role === 'admin';

  const run = async (action: ModAction) => {
    setBusy(true);
    try {
      await apiFetch('/api/admin/moderate', { method: 'POST', body: { target_type: targetType, target_id: id, action, reason: reason.trim() || null } });
      toast.success({ hide: 'Hidden', restore: 'Restored', remove: 'Removed', feature: 'Featured', unfeature: 'No longer featured' }[action]);
      await qc.invalidateQueries({ queryKey: [plural] });
      void qc.invalidateQueries({ queryKey: ['home'] });
      setMod(null);
      setReason('');
      if (action === 'remove') navigate(`/${plural}`);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : 'Action failed.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Dropdown.Root>
        <Dropdown.Trigger className="grid size-9 cursor-pointer place-items-center rounded-[6px] border border-border bg-surface hover:bg-surface-2" aria-label="More actions">
          <MoreHorizontal size={16} />
        </Dropdown.Trigger>
        <Dropdown.Portal>
          <Dropdown.Content align="end" sideOffset={6} className="z-50 min-w-[200px] rounded-[10px] border border-border bg-surface p-1 shadow-[var(--shadow-dialog)]">
            {viewer.can_edit && <Dropdown.Item className={item} onSelect={() => navigate(editPath)}><Pencil size={14} /> Edit</Dropdown.Item>}
            {!viewer.is_owner && <Dropdown.Item className={item} onSelect={() => guard(() => setReport(true), { requireVerified: false })}><Flag size={14} /> Report</Dropdown.Item>}
            {canMod && (
              <>
                <Dropdown.Separator className="my-1 h-px bg-border" />
                <Dropdown.Label className="px-2.5 py-1 text-xs text-muted">Moderation</Dropdown.Label>
                {status === 'published' ? <Dropdown.Item className={item} onSelect={() => setMod('hide')}><EyeOff size={14} /> Hide</Dropdown.Item> : <Dropdown.Item className={item} onSelect={() => setMod('restore')}><Eye size={14} /> Restore</Dropdown.Item>}
                {isFeatured ? <Dropdown.Item className={item} onSelect={() => void run('unfeature')}><StarOff size={14} /> Unfeature</Dropdown.Item> : <Dropdown.Item className={item} onSelect={() => void run('feature')}><Star size={14} /> Feature</Dropdown.Item>}
                <Dropdown.Item className={`${item} text-danger`} onSelect={() => setMod('remove')}><XOctagon size={14} /> Remove</Dropdown.Item>
              </>
            )}
            {viewer.can_edit && !canMod && <Dropdown.Item className={`${item} text-danger`} onSelect={() => navigate(`${editPath}#danger`)}><Trash2 size={14} /> Delete…</Dropdown.Item>}
          </Dropdown.Content>
        </Dropdown.Portal>
      </Dropdown.Root>
      {report && <ReportDialog targetType={targetType} targetId={id} open={report} onOpenChange={setReport} preselect={targetType === 'resource' ? 'broken_link' : undefined} />}
      <Dialog.Root open={!!mod} onOpenChange={(o) => !o && setMod(null)}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-black/30" />
          <Dialog.Content className="fixed top-1/2 left-1/2 z-50 w-[min(92vw,420px)] -translate-x-1/2 -translate-y-1/2 rounded-[14px] border border-border bg-surface p-6 shadow-[var(--shadow-dialog)]">
            <Dialog.Title className="text-lg font-semibold capitalize">{mod} this {targetType}?</Dialog.Title>
            <Dialog.Description className="mt-1 text-sm text-muted">
              {mod === 'hide' ? 'Only the owner and moderators will see it. The owner is notified.' : mod === 'remove' ? 'It is removed for everyone. The owner is notified.' : 'It becomes visible to everyone again.'}
            </Dialog.Description>
            <label htmlFor="mod-reason" className="mt-4 block text-sm font-medium">Reason (shown in the moderation log)</label>
            <textarea id="mod-reason" rows={3} maxLength={1000} value={reason} onChange={(e) => setReason(e.target.value)} className={`${inputClass} mt-1 py-2 text-sm`} />
            <div className="mt-4 flex justify-end gap-2">
              <Dialog.Close asChild><Button>Cancel</Button></Dialog.Close>
              <Button variant={mod === 'restore' ? 'primary' : 'danger'} disabled={busy} onClick={() => mod && void run(mod)} className="capitalize">{busy ? 'Working…' : mod}</Button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </>
  );
}
