import { Link } from 'react-router';
import { MarkdownView } from '@/components/common/MarkdownView';
import { MODULES } from '@/lib/modules';
import type { ModuleKey } from '@/lib/modules';

const CONTENT: Record<string, { title: string; body: string }> = {
  about: {
    title: 'About DevCommons',
    body: `DevCommons is an independent community for developers who build with AI coding agents.

It has four parts:

- **Harness Lab** — share, test and improve the rules, hooks, subagents and MCP servers that keep agents on track.
- **Project Ideas** — publish a problem worth solving, gather suggestions, and find collaborators.
- **Knowledge Hub** — docs, tutorials and guides with visible link health, plus curated collections.
- **AI Workspace** — chat with page context, or draft content you then review and publish yourself.

AI never publishes on your behalf. Anything AI wrote is labeled.`,
  },
  guidelines: {
    title: 'Community guidelines',
    body: `## Be constructive
Critique the work, not the person. Say what you tried, what happened, and what you'd change.

## No spam or self-promotion without substance
Share links because they help, not because they're yours.

## Label AI help
If AI helped you write a post, keep the "AI-assisted" label. Check AI output before you post it as your own view.

## Collaborate with care
Keep requests specific. Respect "no" — and never share someone else's contact details.`,
  },
  privacy: {
    title: 'Privacy',
    body: `Your email is never shown on your profile. It's only shared with a collaborator if you tick "share my contact details" on a specific request.

AI chats are private to you, and are deleted when you delete your account.`,
  },
  terms: {
    title: 'Terms',
    body: `Community content is licensed under CC BY 4.0 unless the author says otherwise. You keep ownership of what you post.

Ratings and reviews are community opinion, not guarantees.`,
  },
};

export function StaticPage({ page }: { page: keyof typeof CONTENT }) {
  const c = CONTENT[page];
  return (
    <div className="mx-auto max-w-[760px] px-4 py-10 md:px-8">
      <title>{`${c.title} · DevCommons`}</title>
      <h1 className="text-[30px]">{c.title}</h1>
      <MarkdownView source={c.body} className="mt-6" />
    </div>
  );
}

export function NotFoundPage() {
  return (
    <div className="mx-auto max-w-[720px] px-4 py-24 text-center">
      <title>Not found · DevCommons</title>
      <p className="font-mono text-sm text-muted">404</p>
      <h1 className="mt-2 text-2xl">There's nothing at this address.</h1>
      <Link to="/" className="mt-6 inline-flex h-9 items-center rounded-[6px] border border-border px-3.5 text-sm font-medium hover:bg-surface-2">Go home</Link>
    </div>
  );
}

/** Routes whose screens belong to later milestones (F2 forms, F3 collaboration, F5 admin, F7 generation). */
export function PendingPage({ module, title, milestone }: { module: ModuleKey; title: string; milestone: string }) {
  const m = MODULES[module];
  return (
    <div className={`mx-auto max-w-[720px] px-4 py-20 text-center`}>
      <title>{`${title} · DevCommons`}</title>
      <p className="font-mono text-sm" style={{ color: m.color }}>{m.name} · {milestone}</p>
      <h1 className="mt-2 text-2xl">{title}</h1>
      <p className="mt-3 text-muted">This screen is part of milestone {milestone} and hasn't been built yet. The API already supports it.</p>
      <Link to={m.path} className="mt-6 inline-flex h-9 items-center rounded-[6px] border border-border px-3.5 text-sm font-medium hover:bg-surface-2">Back to {m.name}</Link>
    </div>
  );
}
