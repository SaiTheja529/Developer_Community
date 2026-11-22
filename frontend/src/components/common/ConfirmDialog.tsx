import * as Dialog from '@radix-ui/react-dialog';
import { useState, type ReactNode } from 'react';
import { Button } from './Button';

/** Destructive confirmation. Says exactly what goes away (spec §5.4, §10). */
export function ConfirmDialog({ trigger, title, description, confirmLabel, onConfirm, destructive = true, children }: {
  trigger: ReactNode; title: string; description: string; confirmLabel: string; onConfirm: () => Promise<unknown> | void; destructive?: boolean; children?: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>{trigger}</Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/30" />
        <Dialog.Content className="fixed top-1/2 left-1/2 z-50 w-[min(92vw,440px)] -translate-x-1/2 -translate-y-1/2 rounded-[14px] border border-border bg-surface p-6 shadow-[var(--shadow-dialog)]">
          <Dialog.Title className="text-lg font-semibold">{title}</Dialog.Title>
          <Dialog.Description className="mt-2 text-sm text-muted">{description}</Dialog.Description>
          {children}
          <div className="mt-6 flex justify-end gap-2">
            <Dialog.Close asChild><Button type="button">Cancel</Button></Dialog.Close>
            <Button
              type="button"
              variant={destructive ? 'danger' : 'primary'}
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  await onConfirm();
                  setOpen(false);
                } catch {
                  /* the caller already surfaced the error; keep the dialog open */
                } finally {
                  setBusy(false);
                }
              }}
            >
              {busy ? 'Working…' : confirmLabel}
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
