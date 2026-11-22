import { ArrowBigUp, Bookmark, Hand, Share2 } from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/cn';
import { useToggle } from '@/lib/api/queries';
import { useAuthAction } from '@/hooks/useAuthAction';
import type { TargetType } from '@/lib/modules';
import type { Viewer } from '@/lib/api/types';

const base =
  'inline-flex h-9 items-center gap-1.5 rounded-[6px] border px-3 text-sm font-medium transition-colors duration-150 cursor-pointer disabled:cursor-not-allowed disabled:opacity-60';

export function VoteButton({ t, id, count, viewer, color, label = 'Upvote' }: { t: TargetType; id: string; count: number; viewer: Viewer; color: string; label?: string }) {
  const m = useToggle(t, id, 'upvote');
  const guard = useAuthAction();
  const own = viewer.is_owner;
  return (
    <button
      type="button"
      className={cn(base, viewer.has_voted ? 'border-transparent text-bg' : 'border-border bg-surface hover:bg-surface-2')}
      style={viewer.has_voted ? { background: color } : undefined}
      aria-pressed={viewer.has_voted}
      aria-label={`${label}, ${count} ${count === 1 ? 'vote' : 'votes'}`}
      title={own ? "You can't vote on your own post" : undefined}
      disabled={own || m.isPending}
      onClick={() => guard(() => m.mutate(!viewer.has_voted))}
    >
      <ArrowBigUp size={17} fill={viewer.has_voted ? 'currentColor' : 'none'} aria-hidden />
      <span className="font-mono">{count}</span>
    </button>
  );
}

export function InterestButton({ id, count, viewer }: { id: string; count: number; viewer: Viewer }) {
  const m = useToggle('idea', id, 'interest');
  const guard = useAuthAction();
  const on = !!viewer.has_interest;
  return (
    <button
      type="button"
      className={cn(base, on ? 'border-idea bg-idea-soft text-idea' : 'border-border bg-surface hover:bg-surface-2')}
      aria-pressed={on}
      aria-label={`I'm interested, ${count} interested`}
      disabled={viewer.is_owner || m.isPending}
      onClick={() => guard(() => m.mutate(!on))}
    >
      <Hand size={15} aria-hidden /> I'm interested <span className="font-mono text-muted">{count}</span>
    </button>
  );
}

export function BookmarkButton({ t, id, viewer }: { t: TargetType; id: string; viewer: Viewer }) {
  const m = useToggle(t, id, 'bookmark');
  const guard = useAuthAction();
  return (
    <button
      type="button"
      className={cn(base, 'border-border bg-surface hover:bg-surface-2')}
      aria-pressed={viewer.has_bookmarked}
      aria-label={viewer.has_bookmarked ? 'Remove bookmark' : 'Bookmark'}
      disabled={m.isPending}
      onClick={() => guard(() => m.mutate(!viewer.has_bookmarked), { requireVerified: false })}
    >
      <Bookmark size={15} fill={viewer.has_bookmarked ? 'currentColor' : 'none'} aria-hidden />
      <span className="hidden sm:inline">{viewer.has_bookmarked ? 'Saved' : 'Save'}</span>
    </button>
  );
}

export function ShareButton({ title }: { title: string }) {
  return (
    <button
      type="button"
      className={cn(base, 'border-border bg-surface hover:bg-surface-2')}
      aria-label="Share"
      onClick={async () => {
        const url = window.location.href;
        if (navigator.share && matchMedia('(pointer: coarse)').matches) {
          await navigator.share({ title, url }).catch(() => undefined);
        } else {
          await navigator.clipboard.writeText(url);
          toast.success('Link copied');
        }
      }}
    >
      <Share2 size={15} aria-hidden />
    </button>
  );
}
