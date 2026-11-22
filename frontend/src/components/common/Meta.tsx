import { Link } from 'react-router';
import type { ReactNode } from 'react';
import type { UserSummary } from '@/lib/api/types';
import { fullDate, timeAgo } from '@/lib/format';
import { cn } from '@/lib/cn';

/** Monospace metadata line under titles (spec §5.1). Pieces are separated with a middle dot. */
export function MetaLine({ parts, className }: { parts: (ReactNode | null | undefined | false)[]; className?: string }) {
  const items = parts.filter(Boolean);
  return (
    <p className={cn('flex flex-wrap items-center gap-x-1.5 gap-y-0.5 font-mono text-xs text-muted', className)}>
      {items.map((p, i) => (
        <span key={i} className="inline-flex items-center gap-1.5">
          {i > 0 && <span aria-hidden className="opacity-60">·</span>}
          {p}
        </span>
      ))}
    </p>
  );
}

export function TimeAgo({ iso, prefix }: { iso: string; prefix?: string }) {
  return (
    <time dateTime={iso} title={fullDate(iso)}>
      {prefix ? `${prefix} ` : ''}
      {timeAgo(iso)}
    </time>
  );
}

function initials(name: string) {
  return name.split(/\s+/).map((s) => s[0]).slice(0, 2).join('').toUpperCase();
}

export function Avatar({ user, size = 24 }: { user: Pick<UserSummary, 'display_name' | 'avatar_url'>; size?: number }) {
  return user.avatar_url ? (
    <img src={user.avatar_url} alt="" width={size} height={size} loading="lazy" className="rounded-full object-cover" style={{ width: size, height: size }} />
  ) : (
    <span aria-hidden className="inline-grid place-items-center rounded-full bg-surface-2 font-mono text-[10px] font-medium text-muted border border-border" style={{ width: size, height: size }}>
      {initials(user.display_name)}
    </span>
  );
}

export function UserChip({ user, size = 20, className }: { user: UserSummary | null; size?: number; className?: string }) {
  if (!user || user.is_deleted) return <span className={cn('text-sm text-muted', className)}>Deleted user</span>;
  return (
    <Link to={`/u/${user.username}`} className={cn('inline-flex items-center gap-1.5 text-sm hover:underline', className)}>
      <Avatar user={user} size={size} />
      <span>{user.display_name}</span>
    </Link>
  );
}
