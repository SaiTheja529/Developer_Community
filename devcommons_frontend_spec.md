# DevCommons — Frontend Implementation Spec

> **Source:** `devcommons_modified_idea.md` (product concept).
> **Depends on:** `devcommons_backend_spec.md`. Every endpoint, field name, enum, limit, and error code used here is defined there. When the two disagree, the backend spec wins. Fix this document to match.
> **Build order:** after the backend milestone with the same number (F2 after B2, and so on). F0 can start in parallel using mocked APIs.

**How to read this document**

- §2–§8 are foundations: stack, structure, design system, data layer. Build these first.
- §9–§12 specify every page and shared component.
- §13–§18 cover cross-cutting quality: states, accessibility, performance, security, testing, deployment.
- §19 is the build plan with acceptance criteria.
- **Verify** marks items to check against current vendor docs.

---

## 1. Product Surface

DevCommons is an independent community platform with four modules. Each module has its own color and URL namespace, while sharing one shell and one component system.

| Module | Tagline (concept §15) | Routes |
|---|---|---|
| Harness Lab | Explore. Test. Improve. Share. | `/harnesses/*` |
| Project Ideas | Share. Discuss. Collaborate. Build. | `/ideas/*` |
| Knowledge Hub | Discover. Learn. Curate. Share. | `/resources/*`, `/collections/*` |
| AI Workspace | Ask. Generate. Refine. Create. | `/ai/*`, plus the "Ask AI" side panel on detail pages |

**Non-negotiable product rules** that show up throughout the UI:

1. AI output is always labeled and visually distinct from community content (concept §10.2).
2. AI never publishes. Users always land on a normal, editable form before anything goes public (concept §4.4 C).
3. Email and contact details are never shown unless the backend returns them (concept §5).
4. Ratings and reviews are labeled as community opinion, not objective guarantees (concept §4.1).
5. Links show their verification state. Official documentation is visually distinct from community resources (concept §4.3).

---

## 2. Technology Stack

| Concern | Choice | Notes |
|---|---|---|
| Build | Vite (current major) + TypeScript (strict) | |
| UI library | React 19 | Uses native `<title>`/`<meta>` hoisting for per-page metadata |
| Routing | React Router v7 (declarative/data mode, SPA) | `createBrowserRouter`, lazy route modules |
| Server state | TanStack Query v5 | All API data. No API data in global stores |
| Client UI state | React state + `zustand` (only for the AI panel and the chat stream) | |
| Auth | In-house, against the backend's JWT API (backend §6) | No auth SDK. Access token in memory, refresh token in an `httpOnly` cookie the frontend never reads. See §8 |
| Styling | Tailwind CSS v4 with CSS-variable design tokens | |
| Components | shadcn/ui (Radix primitives), copied into `src/components/ui` and restyled | Gives accessible dialogs, menus, tabs, popovers |
| Icons | `lucide-react` | |
| Forms | `react-hook-form` + `zod` + `@hookform/resolvers` | |
| Markdown | `react-markdown` + `remark-gfm` + `rehype-sanitize` + `rehype-highlight` (lazy-loaded) | Raw HTML is disabled |
| Drag and drop | `@dnd-kit/core` + `@dnd-kit/sortable` | With the keyboard sensor, for collection ordering |
| Dates | `date-fns` | |
| Toasts | `sonner` | |
| Class utils | `clsx` + `tailwind-merge` (`cn()`) | |
| Testing | Vitest, Testing Library, MSW, Playwright | |
| Lint/format | ESLint (typescript-eslint, react-hooks, jsx-a11y), Prettier | |

**Decision:** no global Redux-style store. Server state lives in TanStack Query, URL state (filters, page, tabs) lives in the URL, and everything else is component state.

---

## 3. Project Structure

```text
frontend/
├── index.html
├── vite.config.ts
├── tsconfig.json
├── .env.example
├── vercel.json
├── public/
│   ├── favicon.svg
│   └── og-default.png
└── src/
    ├── main.tsx                 # QueryClientProvider → AuthProvider → RouterProvider
    ├── router.tsx               # route table (§9), lazy imports
    ├── styles/
    │   └── globals.css          # Tailwind import, @theme tokens, light/dark variables
    ├── lib/
    │   ├── api/
    │   │   ├── client.ts        # apiFetch(): base URL, auth header, envelope unwrap, ApiError
    │   │   ├── sse.ts           # streamSSE(): POST + ReadableStream parser
    │   │   ├── types.ts         # TS mirrors of backend schemas
    │   │   └── endpoints/       # one file per module: harnesses.ts, ideas.ts, ai.ts, ...
    │   ├── queryKeys.ts
    │   ├── queryClient.ts
    │   ├── format.ts            # numbers, dates, relative time
    │   ├── markdown.tsx         # MarkdownView config (sanitize schema, link renderer)
    │   ├── draftMappers.ts      # AI draft output → create-form values (§11.6)
    │   └── cn.ts
    ├── hooks/
    │   ├── useMe.ts             # GET /api/users/me (enabled when signed in)
    │   ├── useConfig.ts         # GET /api/meta/config (categories, enums, limits)
    │   ├── useAuthAction.ts     # run an action, or prompt sign-in / email verification
    │   ├── useDebouncedValue.ts
    │   ├── useUnsavedChangesGuard.ts
    │   ├── useFormAutosave.ts   # localStorage draft per form
    │   └── useListParams.ts     # read/write filters + page in the URL
    ├── components/
    │   ├── ui/                  # shadcn primitives (button, dialog, dropdown-menu, tabs, ...)
    │   ├── layout/              # AppShell, TopNav, MobileNav, Footer, PageHeader, ModuleHero
    │   ├── common/              # §10 shared components
    │   └── feedback/            # CommentThread, SuggestionList, ReviewCard, ...
    ├── features/
    │   ├── home/
    │   ├── search/
    │   ├── harnesses/           # pages/, components/, api.ts (query hooks), schema.ts (zod)
    │   ├── ideas/
    │   ├── collaborations/
    │   ├── resources/
    │   ├── collections/
    │   ├── ai/                  # chat/, generate/, drafts/, panel/ (AskAIPanel), store.ts
    │   ├── auth/                # AuthProvider, session store, sign-in/up, verify, reset pages, guards
    │   ├── users/               # profile, settings
    │   ├── notifications/
    │   └── admin/
    └── test/
        ├── msw/handlers.ts      # mock API for dev (VITE_USE_MOCKS=true) and tests
        ├── fixtures/
        └── setup.ts
```

Each feature folder owns its pages, feature components, query hooks (`useHarnessList`, `useCreateHarness`, ...), and zod form schemas. Shared components never import from `features/`.

---

## 4. Configuration

| Variable | Example | Purpose |
|---|---|---|
| `VITE_API_BASE_URL` | `https://api.devcommons.app` (prod), `http://localhost:5000` (dev) | |
| `VITE_APP_NAME` | `DevCommons` | Working name. Used in titles and copy, so rebranding is a config change |
| `VITE_USE_MOCKS` | `false` | `true` starts the MSW browser worker, so the UI runs without the backend |
| `VITE_SENTRY_DSN` | optional | |

**Never** put the OpenAI key, JWT signing keys, or any other secret in the frontend (concept §10). The frontend holds no keys at all.

---

## 5. Design System

### 5.1 Identity

Concept §11 asks for "a distinct identity and visual language". The direction is **"workbench"**: a calm, paper-like reading surface for long technical content, monospace metadata that feels native to developers, and one accent color per module. It must not look like the creator's portfolio or a generic SaaS template.

Signature elements:

- **Monospace metadata line** under every title, for example `claude_code · agent-orchestration · ★ 120 · updated 3d ago`.
- **Module stripe:** a 3 px top border in the module color on cards and page headers.
- **AI surfaces** use a dashed violet border, a sparkle icon, and an explicit text label. Community content never uses dashed borders.
- A subtle dot-grid background appears only in module heroes on the home and landing pages.

### 5.2 Tokens

Defined as CSS variables in `globals.css` and mapped into Tailwind via `@theme`. Light is the default. Dark follows `prefers-color-scheme` and can be overridden by a toggle stored in `localStorage` (`data-theme` on `<html>`).

| Token | Light | Dark | Use |
|---|---|---|---|
| `--bg` | `#FAFAF7` | `#0E1013` | Page background |
| `--surface` | `#FFFFFF` | `#161A20` | Cards, panels |
| `--surface-2` | `#F3F3EE` | `#1D222A` | Inset areas, code blocks |
| `--border` | `#E4E4DE` | `#2A3038` | |
| `--text` | `#16181D` | `#E8EAED` | Body |
| `--text-muted` | `#5B6170` | `#9AA1AD` | Metadata (≥ 4.5:1 on `--bg` in both themes) |
| `--focus` | `#2563EB` | `#93C5FD` | 2 px focus ring + 2 px offset |
| `--harness` | `#0F766E` | `#5EEAD4` | Harness Lab |
| `--idea` | `#B45309` | `#FCD34D` | Project Ideas |
| `--knowledge` | `#4F46E5` | `#A5B4FC` | Knowledge Hub |
| `--ai` | `#7C3AED` | `#C4B5FD` | AI Workspace and all AI labels |
| `--success` | `#15803D` | `#86EFAC` | Verified links, accepted |
| `--warning` | `#B45309` | `#FCD34D` | Unverified links, pending |
| `--danger` | `#B91C1C` | `#FCA5A5` | Broken links, destructive actions |

Each accent also has a `-soft` variant at 10% opacity over `--surface`, for badge backgrounds and selected states. All accent colors above meet WCAG AA (4.5:1) as text on `--surface` in their theme. Verify with a contrast checker after any change.

| Scale | Values |
|---|---|
| Font, UI | IBM Plex Sans (400, 500, 600), loaded from Google Fonts with `display=swap` |
| Font, mono | IBM Plex Mono (400, 500) for code, metadata lines, tags, counts |
| Type sizes | 12 / 14 / 16 (body) / 18 / 20 / 24 / 30 / 36 px. Line height 1.6 for prose, 1.3 for headings |
| Spacing | 4 px base: 4, 8, 12, 16, 24, 32, 48, 64 |
| Radius | 6 (inputs, badges), 10 (cards), 14 (dialogs, panels) |
| Shadow | `0 1px 2px rgb(0 0 0 / .06)` for cards. Dialogs one step stronger. No heavy drop shadows |
| Content width | Prose max 72ch. Page container max 1200 px. Gutters 16 px mobile, 24 px tablet, 32 px desktop |
| Breakpoints | `sm 640`, `md 768`, `lg 1024`, `xl 1280` |
| Motion | 150–200 ms ease-out for hover and expand. Disabled under `prefers-reduced-motion`. No information conveyed only through motion (concept §11) |

### 5.3 Badge vocabulary

Badges always carry text, and usually an icon. Color is never the only signal.

| Badge | Look | When |
|---|---|---|
| `AI-generated` | `--ai` dashed outline + sparkle | Chat replies, drafts, AI feedback suggestions |
| `AI-assisted` | `--ai` soft fill + sparkle | Published content with `ai_assisted=true` |
| `Official docs ✓` | `--success` soft + shield-check | `resource_type='official_docs'` and `official_verified=true` |
| `Official docs (unverified)` | neutral outline + shield | `official_docs` but not verified |
| `Link OK · checked 2d ago` | `--success` text + dot | `link.status` `ok` |
| `Redirects` | neutral + arrow icon | `redirected`. The tooltip shows the final URL |
| `Link pending check` | neutral + clock | `pending` |
| `Possibly broken` | `--danger` + alert | `broken` / `unreachable`, or open reports > 0 |
| `Looking for collaborators` | `--idea` soft + users icon | `collaboration_status='seeking_collaborators'` |
| `Team formed` | neutral | `team_formed` |
| `Featured` | module color soft + star | `is_featured` |
| `Hidden by moderators` | `--warning` banner (not a badge) | Owner viewing their own hidden content |
| Suggestion status | neutral or colored per status | `open`, `acknowledged`, `planned`, `implemented` (success), `declined` |
| Tool chips | mono text, `--surface-2` | `claude_code` is shown as "Claude Code" via the config label map |

### 5.4 Writing style

- Sentence case for headings, buttons, and labels.
- Buttons are verbs: "Submit harness", "Request to collaborate", "Add to collection".
- Destructive confirmations say exactly what goes away: "Delete this harness? Comments and reviews will be hidden too."
- AI copy is honest about limits: "Based on the README and 4 files we could read", not "Analyzed your repository".

---

## 6. App Shell and Navigation

### 6.1 Layout

```text
┌──────────────────────────────────────────────────────────────────────────┐
│ [Logo] DevCommons   Harness Lab  Ideas  Knowledge Hub  AI Workspace      │
│                         [ Search (⌘K) .................. ]  [+ New ▾] 🔔 (U) │
├──────────────────────────────────────────────────────────────────────────┤
│  <Outlet />                                                   │ AskAI   │
│                                                               │ panel   │
│                                                               │ (when   │
│                                                               │  open)  │
├──────────────────────────────────────────────────────────────────────────┤
│ Footer: About · Community guidelines · Privacy · Terms · Content license │
└──────────────────────────────────────────────────────────────────────────┘
```

- **Top nav (≥ md):** logo, four module links (the active one is underlined in its module color), a search trigger, a "+ New" menu, the notification bell with unread count, and the user menu. Signed-out users see "Sign in" and "Join" in place of the bell and user menu.
- **"+ New" menu:** Submit a harness, Share a project idea, Add a resource, Create a collection, Generate with AI.
- **User menu:** Profile, Bookmarks, Collaborations, AI drafts, Settings, Admin (moderators only), Theme toggle, Sign out.
- **Mobile (< md):** the top bar keeps the logo, search icon, bell, and avatar. A bottom tab bar holds Home, Harnesses, Ideas, Knowledge, and AI. "+ New" becomes a floating button on list pages.
- **Skip link** "Skip to content" is the first focusable element.
- **Global banners** (stacked above `<Outlet/>`): the suspended-account notice, the "Verify your email to start posting" reminder (with a Resend button), and an "AI is temporarily unavailable" notice when `/api/ai/status` says so.

### 6.2 Command palette search

- Opens with `⌘K` / `Ctrl+K`, or by clicking the search field.
- It is a Radix Dialog with a combobox. Input is debounced by 250 ms, then calls `GET /api/search?q=&limit=5`. Results are grouped by module, each with its module icon.
- `Enter` on "See all results for …" goes to `/search?q=`.
- Recent searches (the last 5) are kept in `localStorage`.

### 6.3 Ask AI panel

- Opened by an "Ask AI about this" button on harness, idea, resource, and collection detail pages, and by "Ask AI" in the AI nav for a context-free panel.
- A right-side sheet, 420 px wide on desktop and full-screen on mobile. It does not block the page; the page stays scrollable at ≥ lg.
- It starts a **new conversation** with `context: {type, id}` (the backend locks context per conversation). Its header shows a context chip: `Context: Harness · Spec-First Claude Harness`.
- It contains the same chat components as `/ai` (§11.1), plus an "Open in AI Workspace" link to `/ai/c/:conversationId`.
- Panel state (open, context, conversation ID) lives in `features/ai/store.ts` (zustand), so it survives route changes within the same context.
- Signed-out users see a short explanation and a "Sign in to use AI" button.

---

## 7. Data Layer

### 7.1 API client

```ts
// lib/api/client.ts
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,              // backend §5.3 codes
    message: string,
    public details?: Record<string, unknown>,
    public requestId?: string,
  ) { super(message); }
}

import { getAccessToken, refreshSession } from '@/features/auth/session';  // §8.2

export async function apiFetch<T>(path: string, init: RequestInit & { query?: Record<string, unknown> } = {}): Promise<T> {
  const url = new URL(path, import.meta.env.VITE_API_BASE_URL);
  for (const [k, v] of Object.entries(init.query ?? {})) {
    if (v === undefined || v === null || v === '' || (Array.isArray(v) && v.length === 0)) continue;
    url.searchParams.set(k, Array.isArray(v) ? v.join(',') : String(v));
  }
  const send = () => {
    const token = getAccessToken();
    return fetch(url, {
      ...init,
      headers: {
        Accept: 'application/json',
        ...(init.body ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...init.headers,
      },
    });
  };
  let res = await send();
  // Expired or missing access token: refresh once (single-flight), then retry once.
  if (res.status === 401 && getAccessToken() !== null && (await refreshSession())) {
    res = await send();
  }
  if (res.status === 204) return undefined as T;
  const json = await res.json().catch(() => null);
  if (!res.ok) {
    const e = json?.error;
    throw new ApiError(res.status, e?.code ?? 'internal_error', e?.message ?? 'Something went wrong.', e?.details, e?.request_id);
  }
  return json as T;  // { data, meta? }; endpoint functions unwrap .data
}
```

`/api/auth/*` calls do not go through `apiFetch`. They use the auth module's own `authFetch`, which adds `credentials: 'include'` and the `X-Requested-With: devcommons` header (§8.2).

Endpoint modules return typed results, for example `listHarnesses(params): Promise<Paginated<HarnessSummary>>` and `getHarness(id): Promise<HarnessDetail>`.

### 7.2 Types

`lib/api/types.ts` mirrors the backend schemas by hand. Key shapes:

```ts
export type UUID = string;
export interface Paginated<T> { data: T[]; meta: { page: number; page_size: number; total: number; total_pages: number } }
export interface UserSummary { id: UUID; username: string; display_name: string; avatar_url: string | null; is_deleted: boolean }
export interface Category { slug: string; name: string }
export interface Viewer { is_owner: boolean; has_voted: boolean; has_interest?: boolean; has_bookmarked: boolean; can_edit: boolean; can_moderate: boolean }
export type ContentStatus = 'published' | 'hidden' | 'removed';

export interface HarnessSummary {
  id: UUID; slug: string; name: string; short_description: string;
  tools: string[]; category: Category; tags: string[]; author: UserSummary;
  repo: { url: string; owner: string; name: string; stars: number | null; language: string | null };
  counts: { votes: number; comments: number; suggestions: number; reviews: number; bookmarks: number };
  ai_assisted: boolean; is_featured: boolean; created_at: string; updated_at: string; viewer: Viewer;
}
export interface HarnessComponent { type: string; name: string; description: string }
export interface HarnessDetail extends HarnessSummary {
  detailed_explanation: string; architecture: string | null; components: HarnessComponent[];
  setup_instructions: string | null; limitations: string | null; accepts_collaboration: boolean;
  repo: HarnessSummary['repo'] & { forks: number | null; license: string | null; topics: string[]; pushed_at: string | null; archived: boolean; fetched_at: string | null };
  rating_summary: RatingSummary | null; status: ContentStatus;
}

export type LinkStatus = 'pending' | 'ok' | 'redirected' | 'broken' | 'unreachable' | 'blocked';
export type VerificationStatus = 'verified_hub' | 'verified_official_domain' | 'reachable_unverified';

export type ChatEvent =
  | { event: 'meta'; data: { conversation_id: UUID; user_message_id: UUID; assistant_message_id: UUID; context_sources: ContextSource[] } }
  | { event: 'delta'; data: { text: string } }
  | { event: 'done'; data: { assistant_message_id: UUID; status: 'complete'; usage: { input_tokens: number; output_tokens: number }; conversation_title?: string } }
  | { event: 'error'; data: { code: string; message: string } };

export interface ContextSource { kind: 'platform' | 'github'; label: string; url?: string; status: 'included' | 'failed' | 'unavailable' | 'stale'; truncated?: boolean; reason?: string }
```

Add the rest (ideas, resources, collections, comments, suggestions, reviews, collaborations, notifications, drafts, config) the same way, field-for-field from backend §8–§9.

**Optional later:** generate these types from an OpenAPI document if the backend adds one. Until then, an MSW fixture per type keeps them honest in tests.

### 7.3 TanStack Query conventions

```ts
// lib/queryKeys.ts
export const qk = {
  config: ['meta', 'config'] as const,
  me: ['users', 'me'] as const,
  aiStatus: ['ai', 'status'] as const,
  list: (module: string, params: object) => [module, 'list', params] as const,
  detail: (module: string, id: string) => [module, 'detail', id] as const,
  comments: (targetType: string, id: string, sort: string) => ['comments', targetType, id, sort] as const,
  suggestions: (targetType: string, id: string, filters: object) => ['suggestions', targetType, id, filters] as const,
  reviews: (harnessId: string, sort: string) => ['reviews', harnessId, sort] as const,
  conversations: ['ai', 'conversations'] as const,
  conversation: (id: string) => ['ai', 'conversation', id] as const,
  drafts: (filters: object) => ['ai', 'drafts', filters] as const,
  draft: (id: string) => ['ai', 'draft', id] as const,
  unreadCount: ['notifications', 'unread'] as const,
  notifications: (filters: object) => ['notifications', 'list', filters] as const,
};
```

| Data | `staleTime` | Notes |
|---|---|---|
| `/api/meta/config` | 1 h | Prefetched at app start. Blocks form rendering only |
| `/api/users/me` | 5 min | Refetched after profile edits |
| Lists | 30 s | `placeholderData: keepPreviousData` so pagination doesn't flash |
| Details | 60 s | Prefetch on card hover/focus (`queryClient.prefetchQuery`) |
| Unread count | — | `refetchInterval: 60_000` only while `document.visibilityState === 'visible'` |

Global `QueryClient` defaults: `retry` up to 2 times for network errors and 5xx, never for 4xx. `refetchOnWindowFocus` is on for details and off for lists.

### 7.4 Mutations and optimistic updates

- **Votes, interest, and bookmarks are optimistic.** `onMutate` toggles `viewer.has_*` and adjusts the count in the detail cache and in every list cache containing that ID (`setQueriesData({queryKey: [module, 'list']}, ...)`). Roll back on error. On success, set the count to the server's `{count}`.
- **Comments:** append the server-returned comment on success (not optimistic, so moderation and validation errors show properly). Invalidate the target's detail query to refresh counts.
- **Creates:** on success, `navigate` to the new detail page and invalidate that module's lists.
- **Deletes:** confirm with a dialog, then navigate to the list and show a toast. Undo is not offered (soft delete is server-side only).

### 7.5 Global error handling

A `QueryCache`/`MutationCache` `onError` and a route `errorElement` map `ApiError.code` to behavior:

| Code | Behavior |
|---|---|
| `unauthenticated`, `token_expired`, `session_revoked` (after the automatic refresh also failed) | Clear the session and navigate to `/sign-in?next=<current path>`, with the toast "Your session ended. Please sign in again." |
| `email_not_verified` | Open the `VerifyEmailDialog`: "Check your inbox to verify your email before posting", with a Resend button |
| `account_suspended` | Show the global suspended banner. Disable write controls |
| `forbidden` | Toast: "You don't have permission to do that." |
| `not_found` | Detail pages render the 404 state |
| `validation_error` | Forms map `details.fields` onto react-hook-form `setError`. Never toast |
| `duplicate` | Forms show an inline callout with a link to `details.existing_id` |
| `rate_limited` | Toast: "Slow down a little. Try again in N seconds." N comes from `Retry-After` |
| `ai_quota_exceeded` | AI surfaces show an inline quota card with the reset time |
| `ai_unavailable` | AI surfaces show an "AI is unavailable right now" card. The rest of the app keeps working |
| 5xx / network | Error state with a "Try again" button and "Reference: req_…" for support |

### 7.6 URL state for lists

`useListParams(defaults)` reads and writes `q, category, tags, tools, tech, resource_type, level, official, collaboration_status, sort, page` via `useSearchParams`.

- Changing any filter resets `page` to 1.
- Filters are shareable via URL. Back and forward navigation works.
- Arrays are comma-separated, matching backend §5.4.

### 7.7 SSE streaming client

`EventSource` cannot send an `Authorization` header or a POST body, so the chat uses `fetch` with a streamed body:

```ts
// lib/api/sse.ts
export async function streamSSE(path: string, body: unknown, opts: { signal: AbortSignal; onEvent: (e: ChatEvent) => void }) {
  await ensureFreshAccessToken();                     // refresh first if the token expires within 60 s
  const token = getAccessToken();
  const res = await fetch(new URL(path, import.meta.env.VITE_API_BASE_URL), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify(body),
    signal: opts.signal,
  });
  if (!res.ok || !res.headers.get('content-type')?.includes('text/event-stream')) {
    throw await toApiError(res);                     // quota, auth, validation come back as JSON errors
  }
  const reader = res.body!.pipeThrough(new TextDecoderStream()).getReader();
  let buf = '';
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += value.replace(/\r\n/g, '\n');
    let i: number;
    while ((i = buf.indexOf('\n\n')) !== -1) {
      const block = buf.slice(0, i); buf = buf.slice(i + 2);
      let event = 'message'; const data: string[] = [];
      for (const line of block.split('\n')) {
        if (line.startsWith(':')) continue;                          // keepalive comment
        if (line.startsWith('event:')) event = line.slice(6).trim();
        else if (line.startsWith('data:')) data.push(line.slice(5).trimStart());
      }
      if (data.length) opts.onEvent({ event, data: JSON.parse(data.join('\n')) } as ChatEvent);
    }
  }
}
```

- **Stop button:** `abortController.abort()`. The backend saves the partial reply as `cancelled`. The UI marks the message "Stopped".
- If the stream ends without a `done` or `error` event, treat it as an error: "Connection lost. Your message was saved. Regenerate to try again."
- Throttle UI updates: append deltas to a ref and flush to state once per animation frame.

---

## 8. Authentication

The backend owns authentication with email + password and JWTs (backend §6). The frontend has no auth SDK.

### 8.1 Token handling rules

| Rule | Why |
|---|---|
| The access token (15 min JWT) lives **only in memory**, in the auth module, never in `localStorage`, `sessionStorage`, or a readable cookie | An XSS bug cannot read a stored long-lived credential |
| The refresh token is an `httpOnly` cookie set by the API. **Frontend code never sees or handles it** | Same |
| Every `/api/auth/*` call (register, login, refresh, logout, and the rest) goes through `authFetch`, which sends `credentials: 'include'` and the header `X-Requested-With: devcommons`. All other API calls omit credentials | The browser only stores the refresh cookie from register and login when credentials are included. Refresh and logout also need the header for the backend's CSRF rules (backend §6.5) |
| Never decode the JWT to make security decisions. Read the user from `GET /api/users/me` | The backend re-checks role and status on every request anyway |
| A page reload loses the access token by design. The app restores it silently with one refresh call on startup | |

### 8.2 Session module (`features/auth/session.ts`)

A small framework-agnostic module, so the API client can use it outside React:

```ts
let accessToken: string | null = null;
let expiresAt = 0;                       // ms epoch
let refreshing: Promise<boolean> | null = null;
const channel = new BroadcastChannel('dc-auth');   // cross-tab sync

export const getAccessToken = () => accessToken;

export function setSession(token: string, expiresInSec: number) {
  accessToken = token;
  expiresAt = Date.now() + expiresInSec * 1000;
}

export function clearSession(broadcast = true) {
  accessToken = null; expiresAt = 0;
  if (broadcast) channel.postMessage({ type: 'signed_out' });
}

/** Single-flight refresh, shared across tabs with the Web Locks API. Returns true if a new token was obtained. */
export function refreshSession(): Promise<boolean> {
  refreshing ??= navigator.locks.request('dc-refresh', async () => {
    try {
      for (let attempt = 0; attempt < 2; attempt++) {
        const res = await authFetch('/api/auth/refresh', { method: 'POST' });
        if (res.ok) {
          const { data } = await res.json();
          setSession(data.access_token, data.expires_in);
          queryClient.setQueryData(qk.me, data.user);
          return true;
        }
        if (res.status === 409) continue;      // refresh_conflict: another tab just rotated; retry once
        break;
      }
      clearSession();
      return false;
    } finally {
      refreshing = null;
    }
  });
  return refreshing;
}

export async function ensureFreshAccessToken() {
  if (accessToken && expiresAt - Date.now() < 60_000) await refreshSession();
}

export function authFetch(path: string, init: RequestInit = {}) {
  return fetch(new URL(path, import.meta.env.VITE_API_BASE_URL), {
    ...init,
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'devcommons', ...init.headers },
  });
}

channel.onmessage = (e) => {
  if (e.data?.type === 'signed_out') { clearSession(false); queryClient.clear(); }
  if (e.data?.type === 'signed_in') { void refreshSession(); }   // pick up the new cookie
};
```

- **Proactive refresh:** a timer refreshes about 60 s before `expiresAt`, but only while the tab is visible. Hidden tabs refresh lazily when they next make a request.
- **Startup:** `AuthProvider` calls `refreshSession()` once on mount. Until it settles, the auth status is `loading`, and guarded routes show a full-page skeleton instead of redirecting.
- **Browser support:** if `navigator.locks` is missing, fall back to the in-tab single-flight promise alone. The backend's 409 + retry handles cross-tab races.

### 8.3 `AuthProvider` and `useAuth()`

```ts
type AuthStatus = 'loading' | 'signed_out' | 'signed_in';
interface AuthContext {
  status: AuthStatus;
  user: MeProfile | null;          // from GET /api/users/me (cached as qk.me)
  isVerified: boolean;             // user.email_verified
  signIn(email: string, password: string): Promise<void>;
  signUp(input: { email: string; password: string; username: string; display_name: string }): Promise<void>;
  signOut(): Promise<void>;        // POST /api/auth/logout, clearSession(), queryClient.clear(), navigate('/')
  signOutEverywhere(): Promise<void>;
}
```

- `signIn` and `signUp` call the endpoint, `setSession(...)`, seed `qk.me` with the returned `user`, and broadcast `signed_in` to other tabs.
- On sign-out, clear the whole TanStack Query cache, so no private data remains in memory.

### 8.4 Guards

- `<RequireAuth>` waits while `status === 'loading'`, then redirects signed-out users to `/sign-in?next=<path>`.
- `<RequireVerified>` renders a "Verify your email" screen in place of the page, not a redirect. The screen shows the address, a Resend button, and "Wrong email? Change it in account settings".
- `<RequireRole role="moderator">` renders 404 for non-moderators. It does not reveal that admin pages exist.
- **Action guards on public pages:** `useAuthAction()` wraps vote, bookmark, comment, and similar actions. Signed out, it navigates to `/sign-in?next=<current path>`. Signed in but unverified, it opens `VerifyEmailDialog`. Otherwise it runs the action.
- `next` must be a same-origin relative path starting with `/`. Anything else falls back to `/`, to prevent open redirects.

### 8.5 Auth pages

All auth pages use a centered single-column card layout without the module nav, with the logo linking home.

| Page | Fields and behavior |
|---|---|
| `/sign-in` | Email, password (show/hide toggle), "Forgot password?" link, submit "Sign in", link to sign-up. On 401 `invalid_credentials`: "Email or password is incorrect." On 429 `too_many_attempts`: "Too many attempts. Try again in N minutes." On success, navigate to `next` |
| `/sign-up` | Email, username (live availability via `/api/users/check-username`, debounced 400 ms, inline ✓/✗ with reason), display name, password with a strength hint (length meter and the backend's rules: 10+ characters, not a common password), and a terms and guidelines checkbox. On success, navigate to `/check-email` |
| `/check-email` | "We sent a verification link to a•••@example.com." Resend button with a 60 s cooldown. A "Continue browsing" link. The user is already signed in, but unverified |
| `/verify-email?token=` | On mount: read the token, `history.replaceState` to remove it from the URL, POST `/api/auth/verify-email`. Success: "Email verified" + continue button, and refetch `qk.me`. On 400 `invalid_token`: "This link is invalid or expired" + Resend (if signed in) |
| `/forgot-password` | Email field. Always shows the same result: "If an account exists for that email, we've sent a reset link." |
| `/reset-password?token=` | Strip the token from the URL on mount. New password + confirm. On success: "Password updated. Sign in with your new password." All other sessions were signed out. `invalid_token` shows a link to request a new one |
| `/welcome` | Optional, shown once after the first verification: bio, skills, interests, with a "Skip for now" option. Saves through `PATCH /api/users/me` |

Accessibility for auth forms:

- Use `autocomplete` attributes: `email`, `current-password`, `new-password`, `username`.
- Never block paste into password fields.
- Errors are announced through `aria-live`.

Auth pages set `<meta name="referrer" content="no-referrer">` so tokens in URLs cannot leak.

---

## 9. Routes

All pages are lazy-loaded. "Auth" means `<RequireAuth><RequireVerified>`. "Signed in" means `<RequireAuth>` only (unverified users allowed).

| Path | Page | Auth | Main data |
|---|---|---|---|
| `/` | Home | — | `/api/home` |
| `/search?q=` | Search results | — | `/api/search` + per-module "see all" links |
| `/harnesses` | Harness list | — | `GET /api/harnesses` |
| `/harnesses/new` | Harness form (create; `?draft=<id>` prefills) | Auth | config, draft |
| `/harnesses/:id/:slug?` | Harness detail | — | detail, reviews, suggestions, comments |
| `/harnesses/:id/edit` | Harness form (edit) | Owner | detail |
| `/ideas` | Idea list | — | `GET /api/ideas` |
| `/ideas/new` | Idea form (`?draft=<id>&index=<n>`) | Auth | |
| `/ideas/:id/:slug?` | Idea detail | — | |
| `/ideas/:id/edit` | Idea form (edit) | Owner | |
| `/ideas/:id/requests` | Collaboration requests for this idea | Owner | `GET /api/ideas/:id/collaboration-requests` |
| `/resources` | Resource list | — | `GET /api/resources` |
| `/resources/new` | Resource form (`?draft=<id>&index=<n>` or `?url=`) | Auth | |
| `/resources/:id` | Resource detail | — | |
| `/resources/:id/edit` | Resource form | Owner | |
| `/collections` | Collection list | — | |
| `/collections/new` | Collection form | Auth | |
| `/collections/:id/:slug?` | Collection detail | — (private: owner) | |
| `/collections/:id/edit` | Collection editor (metadata + items) | Owner | |
| `/ai` | AI Workspace: new chat | Auth | conversations, status |
| `/ai/c/:conversationId` | Chat | Auth | conversation |
| `/ai/generate` | Generation task picker | Auth | |
| `/ai/generate/:task` | Task form (`harness`, `project-idea`, `resources`) | Auth | |
| `/ai/drafts` | Drafts list | Auth | |
| `/ai/drafts/:id` | Draft review and refine | Auth | |
| `/u/:username` | Public profile (tabs via `?tab=`) | — | profile, contributions |
| `/me/bookmarks` | Bookmarks | Auth | |
| `/me/collaborations` | Collaboration inbox/outbox | Auth | |
| `/notifications` | Notifications | Auth | |
| `/settings/profile` | Edit profile | Signed in | |
| `/settings/privacy` | Contact visibility and links | Signed in | |
| `/settings/ai` | AI usage and quota | Signed in | `/api/ai/usage` |
| `/settings/account` | Email, password, active sessions, delete account | Signed in | `/api/auth/sessions` |
| `/sign-in`, `/sign-up` | Auth pages (§8.5). Signed-in users are redirected to `next` or `/` | — | |
| `/check-email`, `/welcome` | Post-sign-up pages | Signed in | |
| `/verify-email`, `/forgot-password`, `/reset-password` | Token pages | — | |
| `/admin`, `/admin/reports`, `/admin/users`, `/admin/trusted-domains`, `/admin/log` | Moderation | Moderator / admin | |
| `/about`, `/guidelines`, `/privacy`, `/terms` | Static pages (Markdown files) | — | |
| `*` | 404 | — | |

Detail URLs include the slug for readability. If the slug is missing or stale, `replace`-navigate to the canonical slug once the data loads.

---

## 10. Shared Components

| Component | Responsibility |
|---|---|
| `PageHeader` | Module stripe, breadcrumb, title, metadata line, primary actions slot |
| `ModuleHero` | Module tagline, short explainer, primary CTA, dot-grid background (list pages, first page only) |
| `FilterBar` | Search input (debounced 300 ms), category select, tag multi-select, module-specific filters, sort select, "Clear filters". On mobile it collapses into a "Filters" sheet with an applied-count badge |
| `ContentCard` (variants: harness, idea, resource, collection) | Module stripe, title link, short description (3-line clamp), metadata line, badges, counts row (votes, comments, ...), author chip, relative time. The whole card is not a single link; the title is the link, so inner buttons stay accessible |
| `Pagination` | Prev/next + page numbers, `aria-current="page"`, scrolls to the list top on change |
| `MarkdownView` | `react-markdown` + GFM + sanitize + lazy highlight. Links get `target="_blank" rel="noopener noreferrer nofollow ugc"` and an external icon. Headings get anchor IDs. Images are disabled in v1 (shown as links) to avoid tracking pixels and layout shifts |
| `MarkdownEditor` | Textarea with Write/Preview tabs, a small toolbar (bold, italic, code, link, list, heading), a character counter (`n / max` from config limits, amber at 90%, red over), and an "Improve with AI" menu (§11.5) |
| `TagInput` | Chips. `Enter`/`,` adds, `Backspace` removes. Normalized like the backend (lowercase, spaces become `-`, allowed chars only). Autocomplete from `/api/tags?module=`. Enforces the max count |
| `ToolSelect` | Multi-select of `TOOLS` with labels from config |
| `ComponentListEditor` | `useFieldArray` rows of `{type, name, description}` with add, remove, and move up/down |
| `FeatureListEditor` | `{title, detail}` rows (idea expected features) |
| `RepoUrlField` | Validates the GitHub URL format locally, then calls `/api/github/repo-preview` (debounced 500 ms). Shows a repo card (stars, language, license, last push, archived warning). If `already_listed`, shows "This repo is already on DevCommons" with links "View harness" and "Write a review instead" |
| `ResourceUrlField` | Calls `/api/resources/check-url`. Shows the normalized domain, a duplicate callout, or the blocked reason. It does not prefill the name, because v1 never fetches page content |
| `UserChip` | Avatar + display name linking to `/u/:username`. "Deleted user" is rendered as plain text |
| `TimeAgo` | Relative time with the full date in a `title` and `<time dateTime>` |
| `VoteButton` | Arrow-up + count. `aria-pressed`. Disabled with a tooltip on own content. Uses `useAuthAction` |
| `InterestButton` | "I'm interested" + count (ideas only, `kind=interest`) |
| `BookmarkButton` | Toggle with `aria-pressed` and toast "Saved to bookmarks" |
| `ShareButton` | Copies the canonical URL. Uses `navigator.share` on mobile |
| `ReportDialog` | Reason radio group (filtered by target type: AI targets show `inaccurate_ai`, `unsafe_ai`, `other`; resources show `broken_link`, `outdated`, `misleading`, ...), optional details, submit to `POST /api/reports`. Success: "Thanks. Moderators will review it." A 409 shows "You've already reported this." |
| `ConfirmDialog` | For deletes and declines. The destructive button uses `--danger` |
| `AIBadge` | Variants `generated` and `assisted` (§5.3), with a tooltip explaining what it means |
| `LinkStatusBadge`, `OfficialBadge`, `VerificationBadge` | §5.3 |
| `EmptyState` | Icon, one-sentence explanation, optional CTA |
| `ErrorState` | Message, "Try again", request ID |
| `Skeleton*` | Card, detail, comment, and chat-message skeletons matching final layout sizes |
| `OwnerToolbar` | On detail pages for owners: Edit, Delete, and module-specific actions. Shows the hidden-content banner when relevant |
| `ModeratorMenu` | For moderators on any content: Hide, Restore, Remove, Feature/Unfeature, with a reason prompt. Calls `POST /api/admin/moderate` |

### 10.1 Feedback components

| Component | Spec |
|---|---|
| `CommentThread` | Sort tabs (Oldest / Newest / Top). Top-level comments with up to 3 inline replies and "Show N more replies" (`/api/comments/:id/replies`). Deleted comments render as "[deleted]" placeholders. Each comment has a vote button, Reply, and a ⋯ menu (Edit within 7 days for the author, Delete for the author or target owner, Report). Edited comments show "(edited)" |
| `CommentComposer` | MarkdownEditor (compact), "Post" button, "Be constructive" hint linking to the guidelines. Signed-out users see "Sign in to join the discussion" |
| `SuggestionList` | Kind filter chips (labels per target, from config) and status filter. Cards show kind badge, title, body excerpt, votes, status badge, and owner response (quoted, labeled "Owner response"). Owners get a status dropdown and "Respond" |
| `SuggestionForm` | Kind select (per target), title, body. Kind-specific extras: component type and name for `component_recommendation`, technology tags for `tech_stack`, a resource picker or URL for `alternative_resource` |
| `ReviewForm` | The concept's four structured questions as labeled fields: "What did you test?" (required), "What worked well?", "What did not work as expected?", "What improvements would you recommend?". Then "Environment" and an optional collapsible "Ratings" section with five 1–5 star inputs (radio groups, keyboard operable, "Not rated" default) |
| `ReviewCard` | Author, environment, the four answers as labeled sections, ratings (if any), votes. Footer text: "Community opinion based on this reviewer's testing." |
| `RatingSummary` | Per-dimension average with a count ("Setup 3.7 · 3 ratings"). Hidden when no ratings. Always captioned "Community opinions, not guarantees." |

---

## 11. Page Specifications

Each page lists its purpose, layout, data, interactions, and states. Loading, empty, and error states follow §13 unless noted.

### 11.0 Home `/`

- **Hero:** name, one-line positioning (concept header), primary CTAs "Explore harnesses" and "Share an idea", secondary "Ask AI".
- **Four module tiles:** module color, tagline, live count from `/api/home` stats, link.
- **Sections:** "Trending harnesses" (3–5 cards), "Ideas looking for collaborators", "Recently added resources", "Featured collections". Each has "See all →" linking to the list with the right filter or sort.
- **Signed-in extras:** "Continue where you left off" (last 3 AI conversations and drafts) and the unread notifications count.
- **Empty platform state:** module tiles say "Be the first to …".

### 11.1 Harness Lab

**List `/harnesses`**

- `ModuleHero` (page 1 only), then `FilterBar` with these filters: search, category, tools (multi), tags, sort (`recent` default, `popular`, `trending`, `most_reviewed`, `most_discussed`), and a "Featured only" toggle.
- Grid: 1 column on mobile, 2 on md, 3 on xl. Cards show name, short description, tool chips, category, stars, and counts (votes, reviews, suggestions).
- Empty with filters: "No harnesses match these filters." + "Clear filters". Empty without filters: "No harnesses yet. Submit the first one."

**Detail `/harnesses/:id/:slug?`**

```text
PageHeader: name · AIBadge(assisted?) · Featured?
  metadata: claude_code, cursor · agent-orchestration · by @ada · updated 3d ago
  actions: [Vote 42] [Bookmark] [Share] [Ask AI about this] [⋯ Report / Owner / Mod]
┌────────────────────────────────────────────┬───────────────────────────┐
│ Tabs: Overview | Reviews (3) |             │ Repo card                 │
│       Suggestions (5) | Discussion (12)    │  owner/name ★120 TS MIT    │
│                                            │  last push · Open on GitHub│
│ Overview:                                  │ Rating summary (if any)   │
│  Short description (lead)                  │ Tags                      │
│  How it works (detailed_explanation)       │ Contributor card          │
│  Architecture                              │ [Request to collaborate]  │
│  Components (table: type · name · desc)    │  (if accepts_collaboration)│
│  Setup                                     │ [Get AI suggestions]      │
│  Known limitations                         │                           │
└────────────────────────────────────────────┴───────────────────────────┘
```

- Tabs are synced to `?tab=`. The sidebar moves below the content on mobile.
- The components table is grouped by type, with an icon per type.
- **Reviews tab:** `RatingSummary`, "Write a testing report" (hidden for the owner, replaced by "Edit your report" if the user already submitted one), and a list of `ReviewCard`s sorted Helpful or Recent.
- **Suggestions tab:** `SuggestionList` with kinds Improvement / Bug report / Component recommendation, plus a "Suggest an improvement" button.
- **Discussion tab:** `CommentThread`.
- **Archived repo:** a warning callout, "This repository is archived on GitHub."
- **Get AI suggestions (signed-in):** calls `POST /api/ai/feedback-suggestions`. Results render in an `AIFeedbackPanel` (§11.5) with a dashed violet border, the heading "AI-generated suggestions, not a community review", and a `based_on` source list.

**Form `/harnesses/new` and `/harnesses/:id/edit`**

Sections, as a single long page with a sticky section nav on desktop:

1. **Repository:** `RepoUrlField`. Name prefills from the repo name, and the short description from the repo description if empty. A button "Draft documentation with AI" goes to `/ai/generate/harness?repo=<url>`.
2. **Basics:** name, short description (counter to 280), category, tools, tags.
3. **How it works:** detailed explanation (MarkdownEditor).
4. **Architecture and components:** architecture (MarkdownEditor), `ComponentListEditor`.
5. **Setup and limitations:** setup instructions, limitations.
6. **Collaboration:** "Allow collaboration requests" switch.

Behavior:

- zod schema built from `config.limits`, validated on blur and on submit. The first invalid field gets focus on submit.
- Autosaves to `localStorage` every 2 s while dirty (`useFormAutosave('harness-new')`). On return, it shows "Restore your unsaved draft?".
- `useUnsavedChangesGuard` blocks navigation when there are unsaved changes.
- **Draft prefill:** with `?draft=<id>`, load the draft and map it through `draftMappers.harnessFromDraft` (§11.6). Show a violet banner: "Prefilled from an AI draft. Review every section before publishing; you are the author." Also show a collapsible "Gaps the AI couldn't determine" list from `gaps_and_uncertainties`. Submit includes `source_draft_id`.
- Submit button: "Publish harness". On 409 `duplicate`, show the callout with a link.
- Edit mode: a "Danger zone" section at the bottom with Delete.

### 11.2 Project Ideas

**List `/ideas`**

- Filters: search, category, tech (tags input against `tech_stack`), tags, collaboration status (All / Looking for collaborators / Just sharing / Team formed), sort (`recent`, `popular`, `trending`, `most_interest`, `most_discussed`).
- Cards show title, problem statement excerpt, tech chips (max 4 + "+N"), collaboration badge, and counts (votes, interest, comments).

**Detail `/ideas/:id/:slug?`**

- Header actions: Vote, "I'm interested", Bookmark, Share, Ask AI, ⋯.
- Content sections: Problem, Proposed solution, Details (description), Expected features (checklist-style list), Suggested tech stack (chips), GitHub link (if any).
- **Sidebar collaboration card:**
  - Status badge and collaborator count.
  - Visitor, when `seeking_collaborators`: a "Request to collaborate" button opens `CollaborationRequestDialog`. It contains a message (20–2000 chars), skills (TagInput), the checkbox "Share my email and contact links with the owner if they accept" (unchecked by default), and the privacy note "Your contact details stay private unless you choose to share them."
  - If `viewer_request` exists: "Request pending" with "Withdraw", or "Accepted" with "View details".
  - Owner: "Manage requests (N pending)" linking to `/ideas/:id/requests`, and a status switcher.
- Tabs: Suggestions (kinds Feature / Tech stack / Architecture), Discussion.
- "Get AI suggestions" works the same as for harnesses.

**Form** has the same patterns as the harness form. Sections: Basics (title, category, tags, collaboration status), Problem and solution, Details, Expected features (`FeatureListEditor`), Tech stack (TagInput), GitHub link (optional, with `RepoUrlField` in a lighter mode that accepts any public repo and shows no duplicate check). The "Generate an idea with AI" link goes to `/ai/generate/project-idea`.

**Requests `/ideas/:id/requests` (owner)**

- Tabs: Pending / Accepted / Declined.
- Each request card shows the requester chip, skills, message, and date.
- Pending cards have "Accept" and "Decline". Accept opens a dialog with an optional message and the checkbox "Share my email and contact links with this person". Decline opens a dialog with an optional message.
- Accepted cards show the revealed `counterpart_contact` when present, otherwise "They chose not to share contact details. You can reply via comments on the idea."

**Collaborations `/me/collaborations`**

- Tabs: Received / Sent, with a status filter. The same cards, plus a target link.
- Sent pending requests have "Withdraw".

### 11.3 Knowledge Hub

**Resource list `/resources`**

- Filters: search, category, resource type, level, language, "Official docs only" toggle, tags, sort.
- A list layout (not a grid) suits link directories. Each row shows the type icon, name (internal link to detail), domain in mono, `OfficialBadge`, `LinkStatusBadge`, level chip, a two-line description, and counts.
- A primary "Open ↗" external link sits on each row. External links show the domain before the click.
- A toggle "Include possibly broken links" maps to `include_broken`.

**Resource detail `/resources/:id`**

- Header: name, the badges, domain, and a big "Open resource ↗" button.
- Link health panel: status, HTTP status, last checked, final URL if redirected, open reports count. "Report broken or outdated" opens `ReportDialog` with those reasons preselected. Owners and moderators also get "Re-check now".
- Description, category, type, level, language, submitter.
- "In collections": up to 5 collection chips.
- Actions: Recommend (vote), Bookmark, "Add to collection" (popover listing own collections from `/api/users/me/collections?resource_id=` with checkmarks, plus "New collection…"), Share, Ask AI.
- Tabs: "How people used it" (comments, with the composer placeholder "How did this resource help you?") and "Alternatives and corrections" (suggestions).
- Copy under the link panel: "A working link doesn't guarantee the content is accurate or current."

**Resource form**

- Fields: URL (`ResourceUrlField`) first, then name, description, category, resource type, level, language, tags.
- When the type is `official_docs` and the domain is not trusted, an info note says: "We'll show this as 'Official docs (unverified)' until a moderator confirms the domain."
- After submit, the detail page shows "Link pending check".

**Collection list `/collections`**

- Cards show title, item count, category, creator, the first 3 resource domains as mono chips, and votes.

**Collection detail `/collections/:id`**

- Header: title, description, creator, item count, actions (Vote, Bookmark, Share, Ask AI).
- An ordered list of items: number, resource row (as in the list), and the curator's note in a quote style.
- Unavailable items show "This resource is no longer available" (and "Remove" for the owner).
- A Discussion tab holds comments.
- Private collections show a lock badge, "Only you can see this collection".

**Collection editor `/collections/new` and `/collections/:id/edit`**

- Metadata form: title, description, category, tags, visibility.
- Items panel:
  - A search combobox over `/api/resources?q=` adds items.
  - The list is sortable with dnd-kit (drag handle plus keyboard: focus the handle, `Space` to lift, arrows to move, `Space` to drop, with announcements).
  - Each item has an inline note field (≤ 500) and "Remove".
- Saves:
  - Metadata saves with "Save".
  - Item add and remove call their endpoints immediately.
  - Order saves with `PUT /items/order`, debounced by 800 ms after the last move. A "Saved" indicator confirms it.
- A counter shows `n / 100 items`.

### 11.4 AI Workspace: Chat `/ai`, `/ai/c/:conversationId`

```text
┌───────────────┬──────────────────────────────────────────────────────┐
│ [+ New chat]  │ Header: title (editable) · Context chip (if any)     │
│ Search chats  │         Usage: 45k / 200k today  · ⋯ (Rename, Delete)│
│               ├──────────────────────────────────────────────────────┤
│ Today         │  (user)  How can I tighten the hooks?                │
│  • Hooks q…   │  (AI ✦)  ┆ Here are three ways…                       │
│ Yesterday     │          ┆ ▸ Context used (4)                         │
│  • LangGraph… │          ┆ [Copy] [Regenerate] [Report]               │
│               ├──────────────────────────────────────────────────────┤
│               │ [ Ask about harnesses, ideas, docs…        ] [Send]  │
│               │ AI can be wrong. Check important details.            │
└───────────────┴──────────────────────────────────────────────────────┘
```

**Conversation sidebar**

- Paginated `GET /api/ai/conversations`, grouped by Today, Yesterday, Previous 7 days, and Older.
- Each item shows a context icon if the conversation has context.
- On mobile it becomes a drawer.

**Empty `/ai`**

- Greeting plus 4–6 example prompts from concept §4.4 A, as buttons that fill the input.
- A secondary card links to "Generate content".

**Messages**

- User messages: right-aligned, neutral surface.
- Assistant messages: left, with the AI style (violet left rule, sparkle avatar, "AI-generated" in the accessible name). Content renders with `MarkdownView`. Code blocks get a copy button.
- **Context used:** a disclosure under each assistant message, listing `context_sources` with status icons (included ✓, truncated ⋯, failed ✕ with reason, unavailable). This implements concept §4.4 A, "make it clear what context it used".
- Message actions: Copy, Regenerate (last assistant message only, calls `POST /api/ai/conversations/:id/regenerate`), Report (`ReportDialog` with `target_type: 'ai_message'`).
- `status: 'cancelled'` messages show "Stopped". `status: 'error'` messages show an error line and "Regenerate".

**Composer**

- Auto-growing textarea. `Enter` sends, `Shift+Enter` adds a newline.
- Counter near the limit (`AI_MAX_INPUT_CHARS` from config).
- Send is disabled while streaming. A Stop button replaces it during streaming.
- Disclaimer line: "AI can be wrong. Check important details."

**Streaming flow**

1. Append the user message locally and an empty assistant message with `status: 'streaming'`.
2. Call `streamSSE('/api/ai/chat', {conversation_id, message, context})`.
3. On `meta`: set the real IDs. If this was a new chat, `navigate('/ai/c/' + id, { replace: true })` without remounting the stream (keep the stream in the zustand store).
4. On `delta`: append text.
5. On `done`: set `complete`, update the title from `conversation_title`, invalidate the `qk.conversations` list and the `qk.aiStatus` usage.
6. On `error`: set `error` with the message.

**Accessibility while streaming**

- Do not announce every token. Use an `aria-live="polite"` region that announces "Response complete" (or the error) on `done` or `error`.
- Show a visual typing indicator before the first token.

**Quota and availability**

- A usage meter appears in the header.
- When the quota is exceeded, the composer is replaced by a card: "You've reached today's AI limit. It resets at 00:00 UTC (in 5h 12m)."
- When AI is unavailable, show "AI is unavailable right now." Chat history stays readable.

### 11.5 AI Workspace: Generation

**Task picker `/ai/generate`**

Five cards, each with a description of input and output:

| Card | Leads to |
|---|---|
| Document a harness from a GitHub repo | `/ai/generate/harness` |
| Generate project ideas | `/ai/generate/project-idea` |
| Find learning resources | `/ai/generate/resources` |
| Improve existing text | Explains that the "Improve with AI" button lives in every editor |
| Get feedback on a harness or idea | Explains that it lives on detail pages |

**Task forms**

| Task | Inputs |
|---|---|
| harness | Repo URL (`RepoUrlField`, `?repo=` prefill), additional context (optional, ≤ 4000) |
| project-idea | Domain, problem, tech preferences (tags), interests, count (1–3). At least one of domain, problem, or interests is required |
| resources | Topic (required), goal, level |

- **Submit state:** generation is a synchronous request of up to about 60 s. Show an honest progress card: "Generating… this usually takes 20–40 seconds", with an elapsed-time counter and a Cancel button (aborts the fetch). **Do not fake step-by-step progress.**
- **Success:** navigate to `/ai/drafts/:id`.
- **Errors:** 422 `repo_unavailable` shows inline on the repo field. Quota and unavailability use the standard AI cards.

**Draft review `/ai/drafts/:id`**

Common layout:

- A violet banner: "AI-generated draft. Nothing is published until you review and submit it."
- Header actions: Regenerate (optional extra context), History (dropdown of previous versions with "Restore"), Discard, Report.
- Then the task-specific body.

| Task | Body |
|---|---|
| `harness_doc` | One card per field (name, short description, problem, explanation, architecture, components table, setup, limitations, tools, category, tags). Each card has Edit (inline editor, saves via `PATCH /api/ai/drafts/:id`) and Refine (popover with instruction input and quick chips "Shorter", "More detail", "Clearer steps", calling `refine-section`). A prominent **"Gaps and uncertainties"** callout lists what the AI couldn't determine. Components show `evidence_path` as "Seen in `.claude/hooks/x.sh`" or "Inferred". Primary CTA: "Continue to publish" → `/harnesses/new?draft=:id` |
| `project_idea` | 1–3 idea cards side by side (stacked on mobile), each with all fields and per-field Edit/Refine. Each card has "Use this idea" → `/ideas/new?draft=:id&index=n` |
| `resource_recommendations` | Learning path notes, then an ordered list. Each item shows name, URL, domain, description, type, level, and a `VerificationBadge`. `verified_hub` items link to the hub entry and offer "Bookmark" and "Add to collection". Other items offer "Add to Knowledge Hub" → `/resources/new?draft=:id&index=n`. A collapsed "Omitted links (couldn't be reached)" section lists `omitted`, with the copy "Removed because we couldn't verify these links." Footer action: "Create a collection from hub items" (enabled when at least 1 item is `verified_hub`) → `/collections/new?draft=:id` |
| `feedback_suggestions` | The list shown in `AIFeedbackPanel` (below) |

**`AIFeedbackPanel`** (on detail pages and in feedback drafts)

- Heading "AI-generated suggestions, not a community review".
- Suggestions grouped by category, each with title, detail, a confidence chip, and a "Based on" list.
- Per suggestion, "Post as my suggestion" opens `SuggestionForm` prefilled with the kind mapped from the category (`missing_feature`→`feature`/`improvement`, `testing`→`improvement`, ...). The submission sends `ai_assisted: true`, and the form has a note: "You're posting this as yourself. Edit it to reflect your own view."

**"Improve with AI" in every `MarkdownEditor`**

- A menu with Improve clarity, Rewrite, Expand, Organize into sections, Improve setup steps (setup fields only), Complete the proposal (idea fields only), Refine architecture explanation (architecture fields only), and Custom instruction….
- It calls `POST /api/ai/refine` with `{text, action, instruction?, field}`.
- It opens a **compare dialog**: original vs suggestion side by side (stacked on mobile), the `change_summary`, and the buttons "Replace", "Insert below", "Try again", and "Cancel".
- After "Replace" or "Insert below", the form sends `ai_assisted: true` with its submission, so the published item gets the AI-assisted badge.
- It is disabled when the field is empty, with a tooltip.

**Drafts list `/ai/drafts`**

- Filter by task and status (Draft, Published, Discarded).
- Rows show the task icon, title, updated time, and status.
- Published drafts link to the published item.

### 11.6 Draft → form mapping (`lib/draftMappers.ts`)

The mappers are pure functions with unit tests.

| Draft task | Form | Mapping |
|---|---|---|
| `harness_doc` | Harness form | `name`, `short_description`, `detailed_explanation` = `"## Problem\n" + problem_addressed + "\n\n" + detailed_explanation`, `architecture`, `components` (drop `evidence_path`), `setup_instructions`, `limitations`, `tools` = `suggested_tools`, `category` = `suggested_category`, `tags` = `suggested_tags`, `repo_url` = `draft.input.repo_url` |
| `project_idea` (`index`) | Idea form | `title`, `problem_statement`, `proposed_solution`, `description` = summary + "## Target users" + "## Architecture" + "## Milestones" (list) + "## Challenges" (list), `expected_features`, `tech_stack`, `category`, `tags`. `collaboration_status` defaults to `sharing` |
| `resource_recommendations` (`index`) | Resource form | `url`, `name`, `description`, `resource_type`, `category`, `level` |
| `resource_recommendations` | Collection form | `items` = the `verified_hub` items' `hub_resource_id` in order. Title = `"Learning " + input.topic` |

Every form opened from a draft sends `source_draft_id` on submit.

### 11.7 Profiles and settings

**Public profile `/u/:username`**

- Header: avatar, display name, `@username`, bio, skills and interests chips, website and GitHub links, and contact links only if the API returns them. "Joined Nov 2026".
- Stat tabs: Harnesses, Ideas, Resources, Collections, Reviews, using `/contributions?type=`, paginated, with the same cards as the lists.
- Own profile: an "Edit profile" button.

**Settings**

| Page | Contents |
|---|---|
| `/settings/profile` | Display name, username (with availability check and a warning that old links will break), bio, skills, interests, website, GitHub username |
| `/settings/privacy` | Contact links editor (≤ 5 `{label, url}`). Visibility radio: Hidden (default), Only people I collaborate with, Public. Explanatory copy: "Your email is never shown on your profile. It's only shared with a collaborator if you tick 'share my contact details' on a specific request." |
| `/settings/ai` | Today's usage meter, a 30-day bar chart (requests and tokens per day), and a line explaining limits |
| `/settings/account` | **Email:** current address with verified status. "Change email" asks for the new address and the current password (`POST /api/users/me/email`), then shows "Check your new inbox to confirm". **Password:** current, new, and confirm fields (`POST /api/users/me/password`), then "Password changed. Other devices were signed out." **Sessions:** a list from `GET /api/auth/sessions` (device label, last active, "This device" tag) with "Sign out" per row and "Sign out everywhere". **Delete account:** a danger-zone dialog requiring the password (`DELETE /api/users/me`). The notice explains what happens to content (backend §6.8): "Your profile is anonymized and AI chats are deleted. Your public posts remain, attributed to 'Deleted user'." |

### 11.8 Notifications and bookmarks

**Bell (top nav):** the unread count badge (capped at "9+") opens a popover with the 10 latest notifications. Each row shows an icon per type, the text from `data` (e.g. "**Ada** suggested an improvement on **Spec-First Harness**", with "and 3 others" when `count > 1`), and the relative time. Clicking a row marks it read and navigates to `data.url_path`. The popover also has "Mark all as read" and "See all".

**`/notifications`:** a full list with an Unread/All toggle and pagination.

**`/me/bookmarks`:** type tabs (All, Harnesses, Ideas, Resources, Collections) using the module cards, sorted by bookmarked date.

### 11.9 Moderation `/admin/*` (moderators and admins)

| Page | Contents |
|---|---|
| Reports queue | Status and type filters. Each row: target preview (title, snippet, author, current status), reason, details, reporter, date, report count for the same target. Row actions: Open target, Hide, Remove, Restore, Resolve, Dismiss (with a note). AI reports show the reported message or draft content inline |
| Users (admin) | Search, role and status filters. Actions: Suspend/Unsuspend and Change role, each with a reason and confirmation |
| Trusted domains (admin) | Table plus an add form (domain, kind, label) and delete |
| Moderation log | Read-only table of `moderation_actions` |
| Overview (admin) | Stat tiles from `/api/admin/stats`, including AI cost month-to-date vs budget |

### 11.10 Static pages

About, Community guidelines (constructive feedback, no spam, AI-labeling expectations, collaboration etiquette), Privacy, and Terms. They are Markdown files in `src/content/` rendered with `MarkdownView`. The footer shows the content license chosen by product (backend §18).

---

## 12. Forms: Common Rules

- One zod schema per form in `features/<module>/schema.ts`, created by a factory that reads `config.limits` and enum lists, so limits never drift from the backend.
- Labels are always visible (no placeholder-only fields). Required fields are marked with "(required)" in text, not only an asterisk.
- Help text sits under the label. Errors appear under the field in `--danger` with an icon, linked through `aria-describedby`.
- On submit failure, focus the first invalid field and show an error summary at the top for long forms.
- Map backend `validation_error.details.fields` with `setError(field, {message})`. Unknown field keys go to the summary.
- Disable the submit button only while submitting (with a spinner). Never disable it for validation; show the errors instead.
- Autosave long forms (harness, idea, collection) to `localStorage` under `form:<module>:<id|new>`. Clear it on successful submit.
- Unsaved-changes guard on all create and edit forms (React Router `useBlocker` + `beforeunload`).

---

## 13. Loading, Empty, Error, and Success States

Concept §11 requires all four for every surface.

| Surface | Loading | Empty | Error |
|---|---|---|---|
| Lists | 6 card skeletons | `EmptyState` with a module-specific CTA, or "No matches" + "Clear filters" | `ErrorState` replacing the grid. Filters stay usable |
| Detail | Header + body skeleton | — | 404 page: "This harness doesn't exist or was removed." Other errors use `ErrorState` |
| Comments, suggestions, reviews | 3 skeleton rows | "No comments yet. Start the discussion." / "No suggestions yet." / "No testing reports yet. Tried it? Share what happened." | Inline error with retry. The rest of the page keeps working |
| Chat | Message skeletons when opening a conversation | Example prompts | Inline error under the failed message |
| Generation | Progress card with elapsed time | — | Inline error card with "Try again" |
| Forms | Skeleton until config and (for edit) the entity load | — | Field-level and summary errors |

**Success feedback:** toasts for quick actions (saved, bookmarked, reported, copied). Creates and other big actions navigate to the result. Long saves use an inline "Saved ✓" indicator.

---

## 14. Accessibility (WCAG 2.1 AA)

- Semantic landmarks: `header`, `nav`, `main`, `aside`, `footer`. One `h1` per page, with an ordered heading hierarchy.
- Everything reachable and operable by keyboard. A visible focus ring (`--focus`, 2 px). No keyboard traps; Radix handles focus inside dialogs, which return focus on close.
- Toggle buttons (vote, bookmark, interest) use `aria-pressed`. Counts are included in the accessible name: "Upvote, 42 votes".
- Tabs use the Radix Tabs pattern, synced to the URL.
- Drag-and-drop has a full keyboard alternative and screen-reader announcements (dnd-kit `announcements`).
- Star rating inputs are radio groups with labels ("3 of 5").
- Color contrast ≥ 4.5:1 for text and ≥ 3:1 for UI boundaries and icons, in both themes.
- Status is never conveyed by color alone: badges have text, and link status has an icon and a label.
- `prefers-reduced-motion` disables transitions and the typing animation.
- Touch targets ≥ 44×44 px on mobile.
- Language attribute `lang="en"`. Resource language chips use `lang` on the label.
- Run `eslint-plugin-jsx-a11y` in CI, plus `@axe-core/playwright` checks on key pages in E2E tests.

---

## 15. Performance and SEO

- Route-level code splitting. Markdown highlighting, dnd-kit, and admin pages load lazily.
- **Budget:** the initial JS for the home route stays ≤ 200 KB gzipped. Check it with `rollup-plugin-visualizer` in CI.
- Prefetch details on card hover or focus. Prefetch `/api/meta/config` and `/api/users/me` at startup.
- Fonts: preconnect to Google Fonts, load only the weights used, `font-display: swap`.
- Avatars: `loading="lazy"`, fixed dimensions to avoid layout shift.
- Chat: virtualize the message list only if a conversation exceeds about 200 messages (not needed in v1).
- **SEO:** set a per-page `<title>` ("Spec-First Claude Harness · Harness Lab · DevCommons") and `<meta name="description">` using React 19 metadata hoisting. Set Open Graph tags on detail pages. **Limitation:** as an SPA, crawlers that do not run JS see only the shell. If organic search becomes important, move to React Router framework mode with SSR or prerendering for public detail pages. That is listed as a later enhancement, not v1.

---

## 16. Frontend Security

- No secrets in the bundle. The only configuration is the API URL and app name.
- Never store the access token outside memory, and never log it. The refresh token is `httpOnly` and invisible to code (§8.1).
- Auth pages and the verify and reset pages remove tokens from the URL immediately and use `no-referrer`.
- Never use `dangerouslySetInnerHTML`. Markdown goes through `rehype-sanitize` with the default schema, and raw HTML is disabled.
- Render user-provided URLs only if they are `http:` or `https:` (re-check on the client as defence in depth). External links get `rel="noopener noreferrer nofollow ugc"`.
- Show the destination domain next to external links in user content.
- Don't log tokens or AI content to the console in production. The Sentry `beforeSend` scrubs request bodies.
- **Content Security Policy** via `vercel.json` headers. Without a third-party auth provider, the policy can stay strict:

  ```text
  default-src 'self';
  script-src 'self';
  connect-src 'self' https://api.<domain>;
  img-src 'self' https: data:;
  style-src 'self' 'unsafe-inline' https://fonts.googleapis.com;
  font-src https://fonts.gstatic.com;
  frame-src 'none';
  frame-ancestors 'none'; base-uri 'self'; form-action 'self';
  ```

- Also set `Referrer-Policy: strict-origin-when-cross-origin`, `X-Content-Type-Options: nosniff`, and a `Permissions-Policy` that disables the camera, microphone, and geolocation.

---

## 17. Testing

| Layer | Tooling | Must cover |
|---|---|---|
| Unit | Vitest | Session module: single-flight refresh, 409 retry, `clearSession` broadcast, `next` path sanitizing; `streamSSE` parser (split chunks, CRLF, keepalive comments, multi-line data), `draftMappers`, tag normalization, zod schema factories, `useListParams` |
| Component | Vitest + Testing Library + MSW | VoteButton optimistic update and rollback, CommentThread (reply, edit, deleted placeholder), ReportDialog reason filtering, RepoUrlField states (valid, duplicate, unavailable), MarkdownView strips `<script>` and `javascript:` links, AI badges present on all AI surfaces |
| E2E | Playwright + `@axe-core/playwright` | (1) sign up → open the verification link → submit harness → see it in the list; (2) comment, suggest, review on someone else's harness; (3) request collaboration → owner accepts with contact sharing → requester sees contact; (4) add a resource → add it to a new collection → reorder by keyboard; (5) AI chat streams, Stop works, history persists after reload; (6) generate harness draft → refine a section → publish → AI-assisted badge visible; (7) a signed-out user is prompted to sign in on vote; (8) reload keeps the session, sign-out in one tab signs out the other, and an expired access token refreshes transparently; (9) forgot password → reset → old sessions are signed out |
| Visual | Playwright screenshots (light and dark) for home, list, detail, chat | Catch token regressions |

E2E runs against a staging backend seeded with `flask seed --demo`. Seeded test users already have verified emails. For sign-up and reset flows, the staging backend uses a test email provider whose messages the tests can read (for example a Mailpit container or SES sandbox to a test inbox).

---

## 18. Local Development and Deployment

### 18.1 Local

```bash
cd frontend
cp .env.example .env.local        # VITE_API_BASE_URL=http://localhost:5000
npm install
npm run dev                       # http://localhost:5173
# UI-only work without the backend:
VITE_USE_MOCKS=true npm run dev
```

- Scripts: `dev`, `build` (`tsc -b && vite build`), `preview`, `lint`, `typecheck`, `test`, `test:e2e`.
- Add `http://localhost:5173` to the backend `CORS_ORIGINS`. Use `localhost` for both apps, not `127.0.0.1` for one of them, or the refresh cookie will be cross-site. The backend's console email provider prints verification and reset links to its log.

### 18.2 Vercel

`vercel.json`:

```json
{
  "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }],
  "headers": [
    { "source": "/assets/(.*)", "headers": [{ "key": "Cache-Control", "value": "public, max-age=31536000, immutable" }] },
    { "source": "/(.*)", "headers": [
      { "key": "Content-Security-Policy", "value": "<see §16>" },
      { "key": "Referrer-Policy", "value": "strict-origin-when-cross-origin" },
      { "key": "X-Content-Type-Options", "value": "nosniff" },
      { "key": "Permissions-Policy", "value": "camera=(), microphone=(), geolocation=()" }
    ]}
  ]
}
```

- **Environments:** Production serves `devcommons.app` and talks to `api.devcommons.app`. Staging serves `staging.devcommons.app` and talks to `api-staging.devcommons.app`.
- **Preview URLs:** `*.vercel.app` preview URLs are cross-site to the API, so the `SameSite=Strict` refresh cookie is never sent and sign-in will not survive a reload or token expiry. Use a stable branch alias on your own domain (`staging.devcommons.app`) for anything that needs auth. Plain previews are fine for signed-out pages.
- **CI (GitHub Actions):** lint, typecheck, unit and component tests, build, and bundle-size check on every PR. Run E2E against staging on merge to `main` before promoting.

---

## 19. Build Milestones

Each frontend milestone starts once the backend milestone with the same number is merged. F0 can use MSW mocks.

### F0. Foundations (with B0)

- Vite + TS + Tailwind tokens + shadcn base components, light/dark theme, AppShell (top nav, mobile nav, footer, skip link), router with lazy routes and 404, API client, error mapping, QueryClient, MSW setup, static pages, CI.
- **Accept:** the shell renders on mobile and desktop in both themes. Lighthouse accessibility ≥ 95 on the empty shell. CI is green.

### F1. Auth and profiles (with B1)

- Session module, `AuthProvider`, all §8.5 auth pages, guards, `useAuthAction`, `VerifyEmailDialog`, `useMe`, `useConfig`, public profile (empty contributions), settings for profile, privacy, and account (email, password, sessions, delete).
- **Accept:** E2E flows 8 and 9 pass. A new user signs up, verifies, and lands back on the page they came from. Unverified users see the verify prompt on writes. No token is ever written to `localStorage` (assert in a test).

### F2. Harness Lab (with B2)

- Harness list with filters and URL state, detail with tabs, form with RepoUrlField, components editor, autosave, and unsaved guard. Shared CommentThread, SuggestionList and form, ReviewForm and card, RatingSummary, Vote/Bookmark/Share, ReportDialog, OwnerToolbar. Home trending section.
- **Accept:** E2E flows 1, 2, and 7 pass. A duplicate repo shows the callout. Optimistic votes roll back on failure.

### F3. Project Ideas and collaboration (with B3)

- Idea list, detail, and form. Interest button, collaboration request dialog, owner requests page, `/me/collaborations`, notification bell and page.
- **Accept:** E2E flow 3 passes. Contact details appear only when the API returns them.

### F4. Knowledge Hub (with B4)

- Resource list, detail, and form with the URL check. Link, official, and verification badges. Collections list, detail, and editor with keyboard-accessible reordering. "Add to collection" popover. Bookmarks page.
- **Accept:** E2E flow 4 passes. Official and unverified badges render correctly for both cases.

### F5. Moderation UI (with B5)

- ModeratorMenu on content, the admin pages, the hidden-content banner for owners, and the suspended banner.
- **Accept:** a moderator can hide content and the owner sees the banner. Non-moderators get 404 on `/admin`.

### F6. AI chat (with B6)

- `streamSSE`, the chat page, the conversation sidebar, Context used, Stop, Regenerate, Report, the Ask AI panel on all detail pages, the usage meter, and the quota and unavailable cards.
- **Accept:** E2E flow 5 passes. Opening chat from a harness shows the correct context chip and sources. Screen readers hear "Response complete", not each token.

### F7. AI generation (with B7)

- Task picker, task forms, honest progress card, draft review pages for all tasks, `refine-section`, history and restore, `draftMappers`, form prefill banners, "Improve with AI" compare dialog in MarkdownEditor, AIFeedbackPanel with "Post as my suggestion", drafts list, `/settings/ai`.
- **Accept:** E2E flow 6 passes. No AI content is posted without an explicit user submit on a normal form. Unreachable AI links never render as recommendations.

### F8. Polish (with B8)

- axe checks on all key pages, bundle budget, visual regression baseline, empty-state and error-state copy review, cross-browser check (latest Chrome, Firefox, Safari, plus iOS Safari and Android Chrome).
- **Accept:** zero axe violations on key pages. All §13 states exist for every surface.

---

## 20. Verify List

| Item | Notes |
|---|---|
| Web Locks API and `BroadcastChannel` support in target browsers (fallback described) | §8.2 |
| Final domain layout keeps the frontend and API on one registrable domain | §8.1, §18.2 |
| React Router v7 `useBlocker` behavior in SPA mode | §12 |
| Tailwind v4 `@theme` syntax with CSS variables for runtime dark mode | §5.2 |
| Final brand name, logo, and domain | Affects `VITE_APP_NAME`, CSP, OG images |
| Content license text for the footer and submit forms | Backend §18 |
