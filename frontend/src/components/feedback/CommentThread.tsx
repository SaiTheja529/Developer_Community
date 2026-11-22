import { useState } from 'react';
import { Link } from 'react-router';
import { MessageSquare, Reply } from 'lucide-react';
import { useComments, usePostComment } from '@/lib/api/queries';
import type { Comment } from '@/lib/api/types';
import type { TargetType } from '@/lib/modules';
import { useAuth } from '@/features/auth/AuthProvider';
import { useAuthAction } from '@/hooks/useAuthAction';
import { ApiError } from '@/lib/api/client';
import { MarkdownView } from '@/components/common/MarkdownView';
import { AIBadge } from '@/components/common/Badges';
import { TimeAgo, UserChip } from '@/components/common/Meta';
import { Button } from '@/components/common/Button';
import { EmptyState, ErrorState, Skeleton } from '@/components/common/States';
import { cn } from '@/lib/cn';

function Composer({ t, id, parentId, placeholder, onDone, autoFocus }: { t: TargetType; id: string; parentId?: string; placeholder: string; onDone?: () => void; autoFocus?: boolean }) {
  const [body, setBody] = useState('');
  const [err, setErr] = useState<string | null>(null);
  const post = usePostComment(t, id);
  const guard = useAuthAction();
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (!body.trim()) return;
        guard(() =>
          post.mutate(
            { body: body.trim(), parent_id: parentId },
            {
              onSuccess: () => { setBody(''); setErr(null); onDone?.(); },
              onError: (e) => setErr(e instanceof ApiError ? e.message : 'Could not post. Try again.'),
            },
          ),
        );
      }}
    >
      <label className="sr-only" htmlFor={`c-${parentId ?? 'root'}`}>{placeholder}</label>
      <textarea
        id={`c-${parentId ?? 'root'}`}
        value={body}
        autoFocus={autoFocus}
        onChange={(e) => setBody(e.target.value)}
        placeholder={placeholder}
        rows={parentId ? 2 : 3}
        className="w-full resize-y rounded-[6px] border border-border bg-surface px-3 py-2 text-[15px] placeholder:text-muted"
        aria-describedby={err ? `ce-${parentId ?? 'root'}` : undefined}
      />
      {err && <p id={`ce-${parentId ?? 'root'}`} role="alert" className="mt-1 text-sm text-danger">{err}</p>}
      <div className="mt-2 flex items-center justify-between gap-2">
        <p className="text-xs text-muted">Markdown works. <Link to="/guidelines" className="underline">Be constructive.</Link></p>
        <div className="flex gap-2">
          {onDone && <Button type="button" variant="ghost" size="sm" onClick={onDone}>Cancel</Button>}
          <Button type="submit" variant="primary" size="sm" disabled={post.isPending || !body.trim()}>{post.isPending ? 'Posting…' : 'Post'}</Button>
        </div>
      </div>
    </form>
  );
}

function CommentItem({ c, t, id, depth = 0 }: { c: Comment; t: TargetType; id: string; depth?: number }) {
  const [replying, setReplying] = useState(false);
  if (c.deleted) return <li className={cn('py-3 text-sm text-muted italic', depth && 'pl-4')}>[deleted]</li>;
  return (
    <li className={cn('py-3', depth > 0 && 'border-l border-border pl-4')}>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <UserChip user={c.author} />
        <span className="font-mono text-xs text-muted"><TimeAgo iso={c.created_at} />{c.edited_at && ' (edited)'}</span>
        {c.ai_assisted && <AIBadge variant="assisted" />}
      </div>
      <MarkdownView source={c.body} className="mt-1.5 text-[15px]" />
      {depth === 0 && (
        <button type="button" onClick={() => setReplying((r) => !r)} className="mt-1.5 inline-flex cursor-pointer items-center gap-1 text-xs text-muted hover:text-text">
          <Reply size={13} aria-hidden /> Reply
        </button>
      )}
      {replying && <div className="mt-2"><Composer t={t} id={id} parentId={c.id} placeholder="Write a reply" autoFocus onDone={() => setReplying(false)} /></div>}
      {!!c.replies?.length && (
        <ul className="mt-2">{c.replies.map((r) => <CommentItem key={r.id} c={r} t={t} id={id} depth={1} />)}</ul>
      )}
      {c.reply_count > (c.replies?.length ?? 0) && depth === 0 && (
        <p className="mt-1 pl-4 font-mono text-xs text-muted">{c.reply_count - (c.replies?.length ?? 0)} more replies</p>
      )}
    </li>
  );
}

export function CommentThread({ t, id, placeholder = 'Add to the discussion' }: { t: TargetType; id: string; placeholder?: string }) {
  const [sort, setSort] = useState('oldest');
  const { status } = useAuth();
  const { data, isLoading, error, refetch } = useComments(t, id, sort);
  return (
    <div className="max-w-[72ch]">
      {status === 'signed_in' ? (
        <Composer t={t} id={id} placeholder={placeholder} />
      ) : (
        <p className="rounded-[10px] border border-border bg-surface-2 px-4 py-3 text-sm">
          <Link to={`/sign-in?next=${encodeURIComponent(location.pathname + location.search)}`} className="font-medium underline">Sign in</Link> to join the discussion.
        </p>
      )}
      <div className="mt-6 flex items-center gap-1" role="group" aria-label="Sort comments">
        {['oldest', 'newest', 'top'].map((s) => (
          <button key={s} type="button" aria-pressed={sort === s} onClick={() => setSort(s)} className={cn('h-8 cursor-pointer rounded-[6px] px-2.5 text-sm capitalize', sort === s ? 'bg-surface-2 font-medium' : 'text-muted hover:text-text')}>
            {s}
          </button>
        ))}
      </div>
      {isLoading ? (
        <div className="mt-4 space-y-4">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-14" />)}</div>
      ) : error ? (
        <div className="mt-4"><ErrorState error={error} onRetry={() => refetch()} title="Comments didn't load." /></div>
      ) : !data?.data.length ? (
        <div className="mt-4"><EmptyState icon={MessageSquare} title="No comments yet. Start the discussion." /></div>
      ) : (
        <ul className="mt-2 divide-y divide-border">{data.data.map((c) => <CommentItem key={c.id} c={c} t={t} id={id} />)}</ul>
      )}
    </div>
  );
}
