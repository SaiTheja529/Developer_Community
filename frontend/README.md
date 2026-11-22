# DevCommons — Frontend

React 19 + Vite + TypeScript + Tailwind v4, built from `../devcommons_frontend_spec.md`,
talking to the Flask API in `../backend`.

## 1. What you need (one time)

| Tool | Check it works |
|---|---|
| Node.js 20.19+ or 22.12+ (Vite 8 requirement) | `node -v` |
| npm (comes with Node) | `npm -v` |
| The backend, set up once | Follow sections 1–2 of [`../backend/README.md`](../backend/README.md) |

## 2. First-time setup

```bash
cd frontend
npm install
cp .env.example .env.local     # skip if .env.local already exists
```

The defaults in `.env.local` work as-is for local development:

| Variable | Default | What it does |
|---|---|---|
| `VITE_API_BASE_URL` | *(empty)* | Empty means the browser calls `/api` on the frontend's own address, and the Vite dev server forwards it to Flask. Set it to the API origin only for production builds, e.g. `https://api.devcommons.app` |
| `DEV_API_TARGET` | `http://localhost:5001` | Where the dev server forwards `/api` requests (your Flask server) |
| `DEV_API_ORIGIN` | `http://localhost:5173` | The `Origin` header sent to Flask. Must be listed in the backend's `CORS_ORIGINS`, so the frontend works on any port without changing backend config |

## 3. Start it (every day)

Start the backend first, then the frontend, in two terminals:

```bash
# Terminal 1 — backend (API on http://localhost:5001)
cd backend
docker compose up -d
uv run flask --app wsgi run --port 5001 --debug
```

```bash
# Terminal 2 — frontend
cd frontend
npm run dev
```

Open the URL that `npm run dev` prints, usually **http://localhost:5173**. If port 5173 is busy
(another app is using it), Vite picks the next free port, such as 5174, and prints that instead.
To choose the port yourself: `npm run dev -- --port 5174`.

Stop the frontend with `Ctrl+C` in its terminal.

**Sign in** with a demo account (after `uv run flask --app wsgi seed --demo` in the backend):

| Email | Password | Role |
|---|---|---|
| `ada@demo.devcommons.local` | `devcommons-demo-password` | admin |
| `grace@demo.devcommons.local` | `devcommons-demo-password` | moderator |
| `linus@demo.devcommons.local` | `devcommons-demo-password` | user |

**Check it's connected:** the home page shows the 3D board with live counts. If it shows an error
instead, the backend isn't reachable on `DEV_API_TARGET`.

## 4. Other commands

| Command | What it does |
|---|---|
| `npm run dev` | Dev server with hot reload and the `/api` proxy |
| `npm run typecheck` | TypeScript check, no output files |
| `npm run build` | Typecheck, then build static files into `dist/` |
| `npm run preview` | Serve the `dist/` build locally (uses the same `/api` proxy) |

**Production:** set `VITE_API_BASE_URL` to the API's origin *before* `npm run build`, deploy `dist/`
(see `vercel.json` for the SPA rewrite and security headers), and add the site's origin to the
backend's `CORS_ORIGINS`. Keep the frontend and API on the same registrable domain so the
refresh cookie works.

## 5. Troubleshooting

| Problem | Fix |
|---|---|
| AI replies say "Here is a sample answer…" | The backend is using the fake AI client. Set `AI_PROVIDER=openai` and your key in `backend/.env`, then **restart the backend**. It reads `.env` only at startup |
| Pages show "This didn't load" / network errors | The backend isn't running, or it's on a different port than `DEV_API_TARGET` |
| Sign-in or refresh fails with "Origin not allowed" | `DEV_API_ORIGIN` must exactly match an entry in the backend's `CORS_ORIGINS` |
| Verification / reset email never arrives | With `EMAIL_PROVIDER=console` (the default in `backend/.env`), emails aren't sent. They're printed in the backend's terminal. To get real email, set up SMTP (backend README, section 7) and restart the backend |
| No "Continue with GitHub / Google" buttons | The backend hides a provider until its client ID and secret are set. See section 8 of the backend README, then restart the backend |
| Signed out after every reload | Open the app on `localhost`, not `127.0.0.1`, so the refresh cookie stays same-site |
| Changed `.env.local` but nothing changed | Restart `npm run dev`; env files are read at startup |
| 3D board doesn't appear | Your browser has WebGL turned off. Everything on the board is also listed below it |
| `npm install` fails on peer dependencies | Check `node -v` meets the requirement above, then delete `node_modules` and run `npm install` again |

## 6. The 3D layer

| Where | What it shows |
|---|---|
| Home hero — `features/three/CommonsDiorama.tsx` | An isometric paper model of the community built from `/api/home`. Harnesses are towers (floors = votes + GitHub stars, featured = white cap), ideas are beacons (lantern glows when seeking collaborators), resources are book stacks (one book per recommendation; green ribbon = verified official docs; tilted/grey = possibly broken), collections are shelves (one spine per resource), and the AI core floats in a dashed orbit with dashed threads to every district. Hover for details, click to open. |
| Harness detail — `features/three/HarnessAssembly.tsx` | An exploded view of the harness's components, one layer per component type from foundation (instruction files, rules) to runtime (hooks, MCP servers, workflows). |

Both scenes are lazy-loaded (three.js stays out of the initial bundle, which is ~188 KB gzipped),
pause rendering when scrolled off-screen, respect `prefers-reduced-motion`, follow the light/dark
theme tokens, fall back gracefully without WebGL, and duplicate everything they show in normal,
accessible HTML (legend, cards, components table). Labels and tooltips are plain DOM nodes
projected from 3D anchors (`features/three/Overlay.tsx`), not drei `<Html>`.

## 7. What's built

Every route in spec §9 is implemented against the live Flask API:

- **Browse and discuss** — home (3D board), search + ⌘K palette, lists with URL filters, detail pages with tabs, optimistic votes / interest / bookmarks, comments with replies, suggestions (owners set status and respond), testing reports with ratings, link health, collections.
- **Create and edit** — harness, idea, resource and collection forms with client + server validation, error summary, autosave/restore, unsaved-changes guard, GitHub repo preview with duplicate detection, URL checks, tag autocomplete, component/feature list editors, collection item search / notes / keyboard reordering, danger-zone deletes.
- **AI** — streaming chat (Stop, Regenerate, Context used, rename/delete, usage meter, report), Ask AI side panel with page context, generation (harness doc, project ideas, learning resources) with an honest elapsed-time card, draft review with per-field Edit / Refine, History restore, Regenerate, Discard, "Improve with AI" compare dialog in every editor, "Get AI suggestions" on harness/idea pages with "Post as my suggestion", draft → form prefill with the AI-assisted label.
- **People** — collaboration requests (with opt-in contact sharing), owner requests page, inbox/outbox, notifications bell + page, bookmarks, profile, settings (profile, privacy, AI usage, account: email, password, sessions, delete).
- **Moderation** — ⋯ menu (edit, report, hide/restore/remove/feature), report dialog for content and AI output, admin overview, reports queue, users, trusted domains, moderation log (non-moderators get a 404).
- **Auth** — sign in/up with email + password or **Continue with GitHub / Google** (`features/auth/oauth.tsx`, landing page `/auth/callback`), Settings → Account → Connected accounts (connect, disconnect, set a first password), verify email, forgot/reset password, silent refresh, cross-tab sign-out.

Known gaps: collection reordering uses accessible up/down buttons rather than drag and drop; no automated frontend test suite yet.
