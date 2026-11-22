# DevCommons

A community platform for developers who build with AI coding agents.

I started this because I kept running into the same problem. The setups that make coding agents actually useful (instruction files, hooks, MCP servers, sub-agents, custom workflows) are scattered across random repos, gists and threads. There's no good place to share them, compare them, or see what's working for other people. So I built one.

DevCommons is a place to share those agent "harnesses", post project ideas and find people to build them with, and keep a curated library of docs and tutorials. There's also an AI workspace that helps you write and improve content, but it never publishes anything on your behalf.

## What's in it

**Harness Lab.** Share your agent setup and see how others have built theirs. Link a GitHub repo and it pulls in a preview (stars, description, whether it's archived). People can vote, leave reviews, and post testing reports with ratings.

**Project Ideas.** Post an idea, get feedback and suggestions, and mark it as looking for collaborators. Others can send a collaboration request, and contact details are shared only if both sides agree.

**Knowledge Hub.** A library of docs, tutorials and articles that the community curates. Official sources get a verified badge, and a background job checks links regularly so dead ones get flagged and eventually hidden. You can group resources into collections.

**AI Workspace.** A chat assistant that uses the page you're on as context, plus a few generators:
- point it at a GitHub repo and it drafts a harness write-up
- get project idea suggestions
- build a learning path from resources

One rule I stuck to the whole way through: **the AI assists, you decide what gets published.** Anything it writes shows up as an editable draft with an "AI-assisted" label, and nothing goes live until you submit it yourself.

**The 3D home page.** This was my favourite part to build. The home page is a little isometric "paper city" rendered from live data. Harnesses are towers that grow taller with votes and GitHub stars, ideas are beacons that light up when they're looking for collaborators, resources are stacks of books, and an AI core floats above everything. It's lazy-loaded, respects reduced-motion settings, and everything in the scene is also listed in plain HTML underneath, so it works without WebGL and with screen readers.

Other things that are in there:
- Sign in with email and password, GitHub, or Google
- Comments with replies, bookmarks, notifications, user profiles
- Search across everything, plus a ⌘K command palette
- Moderation tools: reports, hide/remove/feature, trusted domains, and a moderation log
- Light and dark themes

## Tech stack

| | |
|---|---|
| **Frontend** | React 19, TypeScript, Vite, Tailwind CSS v4, TanStack Query, Zustand, React Router, Radix UI |
| **3D** | three.js with React Three Fiber and drei |
| **Backend** | Python 3.12, Flask 3, SQLAlchemy 2, Pydantic, Alembic |
| **Data** | PostgreSQL 16, Redis (for rate limiting) |
| **AI** | OpenAI API with streaming responses (Server-Sent Events) |
| **Auth** | Short-lived JWTs plus rotating refresh cookies, Argon2 passwords, GitHub and Google OAuth with PKCE |
| **Tooling** | uv, pytest, Ruff, Docker, Gunicorn |

## Project structure

```text
.
├── backend/            Flask API
│   ├── app/
│   │   ├── auth/           sign-up, login, sessions, email, OAuth
│   │   ├── common/         validation, pagination, errors, URL safety checks
│   │   ├── integrations/   GitHub API and the link checker
│   │   └── modules/        one folder per feature (harnesses, ideas, resources, ai, ...)
│   ├── migrations/     Alembic migrations
│   └── tests/          unit and API tests
├── frontend/           React app
│   └── src/
│       ├── components/     shared UI
│       ├── features/       pages grouped by feature (incl. three/ for the 3D scenes)
│       └── lib/            API client, query setup, helpers
└── devcommons_*.md     the product idea and the specs I wrote before building
```

## Running it locally

You'll need **Docker**, **[uv](https://docs.astral.sh/uv/)** and **Node.js 20.19+** (or 22.12+).

**1. Start the backend**

```bash
cd backend
docker compose up -d                       # Postgres on 5433, Redis on 6380
uv sync
cp .env.example .env                       # then fill in the secrets (see the comments in the file)
uv run flask --app wsgi db upgrade
uv run flask --app wsgi seed --demo        # optional: sample content and demo accounts
uv run flask --app wsgi run --port 5001 --debug
```

**2. Start the frontend** (in a second terminal)

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Then open **http://localhost:5173**. Use `localhost` rather than `127.0.0.1`, otherwise the sign-in cookie won't stick.

If you ran the demo seed, you can sign in as `ada@demo.devcommons.local` (admin), `grace@demo.devcommons.local` (moderator) or `linus@demo.devcommons.local` (regular user). They all use the password `devcommons-demo-password`.

A few things worth knowing:
- Out of the box, AI runs on a **fake provider** that returns placeholder text, so you can work on the UI without an API key. Set `AI_PROVIDER=openai` and `OPENAI_API_KEY` in `backend/.env` to use the real thing, then restart the backend.
- Emails (verification, password reset) are **printed in the backend terminal** by default instead of being sent. Switch to SMTP if you want them in your inbox.
- GitHub and Google sign-in buttons only show up once you've added their client ID and secret.

The detailed guides cover all of this, plus troubleshooting:
- [backend/README.md](backend/README.md): setup, email, OAuth, AI config, CLI commands
- [frontend/README.md](frontend/README.md): dev server, env variables, the 3D layer

## Tests

```bash
cd backend
uv run pytest                  # 130+ tests against a real Postgres test database
uv run ruff check app tests
```

```bash
cd frontend
npm run typecheck
```

## Some decisions I made along the way

- **Security got more attention than I expected it would.** Refresh tokens rotate on every use and the server detects if an old one is reused. Logins lock for 15 minutes after repeated failed attempts. Any URL the server fetches goes through SSRF checks first. And there's rate limiting on all the endpoints that can be abused.
- **AI usage has hard limits.** Each user gets a daily token and generation allowance, and there's a monthly budget for the whole site, worked out from the model's actual pricing. That way a single person can't run up the bill.
- **Background jobs are plain HTTP endpoints.** Link checking, refreshing repo metadata, cleanup and counter rebuilds are all `POST` endpoints protected by a secret. Any cron service can call them, and I didn't need to run a separate worker.
- **Each feature module has the same shape:** `models.py`, `schemas.py`, `service.py`, `routes.py`. Once you know one module, you know them all.

## What's next

- Drag-and-drop reordering for collections (right now it uses accessible up/down buttons)
- A frontend test suite
- Deploying it publicly

## Feedback

If you build with Claude Code, Cursor, Copilot or any other coding agent, I'd love to hear what you'd want from a place like this. Feel free to open an issue or reach out.
