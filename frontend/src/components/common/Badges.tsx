import type { ReactNode } from 'react';
import { AlertTriangle, ArrowRightLeft, Clock, Lock, ShieldCheck, Shield, Sparkles, Star, Users } from 'lucide-react';
import { cn } from '@/lib/cn';
import { timeAgo } from '@/lib/format';
import type { CollaborationStatus, ResourceSummary } from '@/lib/api/types';
import { TOOL_LABELS } from '@/lib/modules';

export function Badge({ className, children, title }: { className?: string; children: ReactNode; title?: string }) {
  return (
    <span title={title} className={cn('inline-flex items-center gap-1 rounded-[6px] px-1.5 py-0.5 text-xs font-medium leading-5 whitespace-nowrap', className)}>
      {children}
    </span>
  );
}

export function AIBadge({ variant }: { variant: 'generated' | 'assisted' }) {
  return variant === 'generated' ? (
    <Badge className="border border-dashed border-ai text-ai" title="Written by AI. Check it before relying on it.">
      <Sparkles size={12} aria-hidden /> AI-generated
    </Badge>
  ) : (
    <Badge className="bg-ai-soft text-ai" title="The author used AI to help write this, then reviewed and published it.">
      <Sparkles size={12} aria-hidden /> AI-assisted
    </Badge>
  );
}

export const FeaturedBadge = ({ color = 'var(--text)' }: { color?: string }) => (
  <Badge className="border border-border" >
    <Star size={12} aria-hidden style={{ color }} fill="currentColor" /> Featured
  </Badge>
);

export function OfficialBadge({ r }: { r: Pick<ResourceSummary, 'resource_type' | 'official_verified'> }) {
  if (r.resource_type !== 'official_docs') return null;
  return r.official_verified ? (
    <Badge className="bg-success-soft text-success"><ShieldCheck size={12} aria-hidden /> Official docs</Badge>
  ) : (
    <Badge className="border border-border text-muted"><Shield size={12} aria-hidden /> Official docs (unverified)</Badge>
  );
}

export function LinkStatusBadge({ link }: { link: ResourceSummary['link'] }) {
  if (link.open_reports > 0 || link.status === 'broken' || link.status === 'unreachable')
    return <Badge className="bg-danger-soft text-danger"><AlertTriangle size={12} aria-hidden /> Possibly broken</Badge>;
  if (link.status === 'ok')
    return (
      <Badge className="text-success">
        <span className="size-1.5 rounded-full bg-success" aria-hidden /> Link OK{link.last_checked_at ? ` · checked ${timeAgo(link.last_checked_at)}` : ''}
      </Badge>
    );
  if (link.status === 'redirected')
    return <Badge className="border border-border text-muted" title={link.final_url ?? undefined}><ArrowRightLeft size={12} aria-hidden /> Redirects</Badge>;
  if (link.status === 'blocked') return <Badge className="bg-danger-soft text-danger"><AlertTriangle size={12} aria-hidden /> Blocked</Badge>;
  return <Badge className="border border-border text-muted"><Clock size={12} aria-hidden /> Link pending check</Badge>;
}

export function CollabBadge({ status }: { status: CollaborationStatus }) {
  if (status === 'seeking_collaborators') return <Badge className="bg-idea-soft text-idea"><Users size={12} aria-hidden /> Looking for collaborators</Badge>;
  if (status === 'team_formed') return <Badge className="border border-border text-muted">Team formed</Badge>;
  return null;
}

export const PrivateBadge = () => (
  <Badge className="border border-border text-muted"><Lock size={12} aria-hidden /> Private</Badge>
);

export function Chip({ children, lang }: { children: ReactNode; lang?: string }) {
  return (
    <span lang={lang} className="inline-flex items-center rounded-[6px] bg-surface-2 px-1.5 py-0.5 font-mono text-xs text-muted">
      {children}
    </span>
  );
}

export const ToolChip = ({ tool }: { tool: string }) => <Chip>{TOOL_LABELS[tool] ?? tool}</Chip>;
