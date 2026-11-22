import { Link } from 'react-router';
import * as Popover from '@radix-ui/react-popover';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { Check, FolderPlus, Plus } from 'lucide-react';
import { apiFetch, ApiError, getData } from '@/lib/api/client';
import { useAuth } from '@/features/auth/AuthProvider';
import { useAuthAction } from '@/hooks/useAuthAction';

interface MyCollection { id: string; slug: string; title: string; item_count: number; contains_resource: boolean; visibility: string }

/** Popover listing own collections with checkmarks (spec §11.3). */
export function AddToCollection({ resourceId }: { resourceId: string }) {
  const { status } = useAuth();
  const guard = useAuthAction();
  const qc = useQueryClient();
  const key = ['users', 'me', 'collections', resourceId];
  const { data, refetch } = useQuery({ queryKey: key, queryFn: () => getData<MyCollection[]>('/api/users/me/collections', { resource_id: resourceId }), enabled: false });
  const toggle = async (c: MyCollection) => {
    try {
      if (c.contains_resource) await apiFetch(`/api/collections/${c.id}/items/${resourceId}`, { method: 'DELETE' });
      else await apiFetch(`/api/collections/${c.id}/items`, { method: 'POST', body: { resource_id: resourceId } });
      toast.success(c.contains_resource ? `Removed from ${c.title}` : `Added to ${c.title}`);
      void refetch();
      void qc.invalidateQueries({ queryKey: ['collections'] });
      void qc.invalidateQueries({ queryKey: ['resources', 'detail', resourceId] });
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : 'Could not update the collection.');
    }
  };
  return (
    <Popover.Root onOpenChange={(o) => o && status === 'signed_in' && void refetch()}>
      <Popover.Trigger asChild>
        <button type="button" onClick={(e) => { if (status !== 'signed_in') { e.preventDefault(); guard(() => undefined); } }} className="inline-flex h-9 cursor-pointer items-center gap-1.5 rounded-[6px] border border-border bg-surface px-3 text-sm font-medium hover:bg-surface-2">
          <FolderPlus size={15} aria-hidden /> <span className="hidden sm:inline">Add to collection</span>
        </button>
      </Popover.Trigger>
      {status === 'signed_in' && (
        <Popover.Portal>
          <Popover.Content align="end" sideOffset={6} className="z-50 w-[280px] rounded-[10px] border border-border bg-surface p-1.5 shadow-[var(--shadow-dialog)]">
            <p className="px-2 py-1.5 text-xs font-medium text-muted">Your collections</p>
            {!data ? <p className="px-2 py-3 text-sm text-muted">Loading…</p> : data.length === 0 ? <p className="px-2 py-3 text-sm text-muted">You don't have any collections yet.</p> : (
              <ul>
                {data.map((c) => (
                  <li key={c.id}>
                    <button type="button" role="menuitemcheckbox" aria-checked={c.contains_resource} onClick={() => toggle(c)} className="flex w-full cursor-pointer items-center gap-2 rounded-[6px] px-2 py-2 text-left text-sm hover:bg-surface-2">
                      <span className="grid size-4 place-items-center rounded border border-border">{c.contains_resource && <Check size={12} aria-hidden />}</span>
                      <span className="truncate">{c.title}</span>
                      <span className="ml-auto font-mono text-xs text-muted">{c.item_count}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <Popover.Close asChild>
              <Link to="/collections/new" className="mt-1 flex items-center gap-2 rounded-[6px] border-t border-border px-2 py-2 text-sm hover:bg-surface-2"><Plus size={14} aria-hidden /> New collection…</Link>
            </Popover.Close>
          </Popover.Content>
        </Popover.Portal>
      )}
    </Popover.Root>
  );
}
