import { useState } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { Lock } from 'lucide-react';
import { apiFetch, ApiError } from '@/lib/api/client';
import { Button } from '@/components/common/Button';
import { Field, TextArea } from '@/components/forms/Field';
import { TagInput } from '@/components/forms/TagInput';

export function CollabRequestDialog({ target, id, title, open, onOpenChange }: { target: 'idea' | 'harness'; id: string; title: string; open: boolean; onOpenChange: (o: boolean) => void }) {
  const qc = useQueryClient();
  const [message, setMessage] = useState('');
  const [skills, setSkills] = useState<string[]>([]);
  const [share, setShare] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/30" />
        <Dialog.Content className="fixed top-1/2 left-1/2 z-50 max-h-[92dvh] w-[min(94vw,540px)] -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-[14px] border border-border bg-surface p-6 shadow-[var(--shadow-dialog)]">
          <Dialog.Title className="text-lg font-semibold">Request to collaborate</Dialog.Title>
          <Dialog.Description className="mt-1 text-sm text-muted">On “{title}”. The owner gets a notification and can accept or decline.</Dialog.Description>
          <form
            className="mt-5 space-y-4"
            onSubmit={async (e) => {
              e.preventDefault();
              if (message.trim().length < 20) { setErr('Tell the owner a bit more (at least 20 characters).'); return; }
              setBusy(true);
              try {
                await apiFetch(`/api/${target === 'idea' ? 'ideas' : 'harnesses'}/${id}/collaboration-requests`, { method: 'POST', body: { message: message.trim(), skills, share_contact: share } });
                toast.success('Request sent');
                void qc.invalidateQueries({ queryKey: [target === 'idea' ? 'ideas' : 'harnesses', 'detail', id] });
                void qc.invalidateQueries({ queryKey: ['collaborations'] });
                onOpenChange(false);
              } catch (e2) {
                setErr(e2 instanceof ApiError ? (e2.status === 409 ? 'You already have a request for this.' : e2.message) : 'Could not send.');
              } finally {
                setBusy(false);
              }
            }}
          >
            <Field label="Message" required hint="What you'd work on, and why you're a good fit." error={err ?? undefined} counter={{ n: message.length, max: 2000 }}>
              {(p) => <TextArea {...p} rows={5} value={message} maxLength={2000} onChange={(e) => { setMessage(e.target.value); setErr(null); }} />}
            </Field>
            <Field label="Your skills">{(p) => <TagInput id={p.id} value={skills} onChange={setSkills} max={10} placeholder="react, fastapi…" />}</Field>
            <label className="flex cursor-pointer items-start gap-2.5 text-sm">
              <input type="checkbox" checked={share} onChange={(e) => setShare(e.target.checked)} className="mt-0.5 size-4" />
              <span>Share my email and contact links with the owner if they accept</span>
            </label>
            <p className="flex items-start gap-2 rounded-[6px] bg-surface-2 px-3 py-2 text-xs text-muted"><Lock size={13} className="mt-0.5 shrink-0" aria-hidden /> Your contact details stay private unless you choose to share them.</p>
            <div className="flex justify-end gap-2">
              <Dialog.Close asChild><Button type="button">Cancel</Button></Dialog.Close>
              <Button type="submit" variant="primary" disabled={busy}>{busy ? 'Sending…' : 'Send request'}</Button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
