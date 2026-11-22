# DevCommons — LinkedIn post and deployment checklist

- [Part 1: LinkedIn post](#part-1-linkedin-post) (ready to copy)
- [Part 2: What you need to deploy it](#part-2-what-you-need-to-deploy-it)

---

## Part 1: LinkedIn post

### Full version

**I built DevCommons: a community platform for developers who build with AI coding agents.** 🧱

Coding agents work best with a good harness: instruction files, hooks, MCP servers, sub-agents and workflows. Today those setups live in scattered repos and threads. DevCommons gives them a home.

**What you can do**
🔧 **Harness Lab:** share and discover agent harnesses, with GitHub repo previews, votes, reviews and testing reports
💡 **Project Ideas:** post ideas, gather feedback and find collaborators
📚 **Knowledge Hub:** a curated library of docs and tutorials, with verified official sources and automatic broken-link checks
✨ **AI Workspace:** chat that uses the page you're on as context, plus generators that turn a GitHub repo into harness docs, suggest project ideas or build a learning path

One rule shaped the whole design: **AI assists, you decide what gets published.** Everything the AI writes lands as an editable draft, clearly labeled, and nothing goes live until you submit it.

**The part I enjoyed most:** the home page is a live 3D "paper city" built from real data. Harnesses are towers that grow with votes and GitHub stars, ideas are glowing beacons, resources are stacks of books, and an AI core orbits above. It's fully accessible, with an HTML fallback.

**Under the hood**
• React 19, TypeScript, Vite, Tailwind, TanStack Query, three.js / React Three Fiber
• Flask, PostgreSQL, Redis and the OpenAI API, with streaming responses
• Sign in with email, GitHub or Google
• Rotating sessions with reuse detection, rate limiting and server-side link safety checks
• 130+ automated backend tests

Next up: drag-and-drop collections and a frontend test suite.

I'd love feedback from anyone building with Claude Code, Cursor or Copilot agents. What would you want from a place like this? 👇

#AI #AgenticAI #DeveloperTools #React #Python #ThreeJS #OpenSource #BuildInPublic

### Short version

Built **DevCommons**, a home for developers working with AI coding agents. Share agent harnesses (instruction files, hooks, MCP servers), post project ideas and find collaborators, and keep a library of docs with automatic broken-link checks. An AI workspace drafts harness write-ups from GitHub repos and suggests ideas, but you review everything before it's published. The home page is a live 3D city built from real community data.

React · TypeScript · three.js · Flask · PostgreSQL · OpenAI · GitHub/Google sign-in

Feedback welcome! #AgenticAI #DeveloperTools #BuildInPublic

### Before you post

- Add a link: the live site once deployed (Part 2), the GitHub repo if it's public, or both.
- Attach a short screen recording of the 3D home page. A video gets far more reach than text alone.
- "130+ tests" counts backend tests only (132 today). There's no frontend test suite yet, so keep that wording.

---

## Part 2: What you need to deploy it

DevCommons has two parts that deploy separately:

| Part | What it is | Typical host |
|---|---|---|
| **Frontend** (`frontend/`) | Static files built by `npm run build` | Vercel (a `vercel.json` is included), Netlify, Cloudflare Pages |
| **Backend** (`backend/`) | Flask API in Docker, plus PostgreSQL and Redis | Any Docker host: Render, Railway, Fly.io, Google Cloud Run, a VPS |

### 1. Accounts and services to set up

| # | What | Why | Notes |
|---|---|---|---|
| 1 | **A domain you own**, e.g. `devcommons.dev` | **Required.** The sign-in cookie only works when the frontend and API share one domain | Use `devcommons.dev` for the frontend and `api.devcommons.dev` for the API. Free hosting subdomains such as `*.vercel.app` and `*.onrender.com` count as **different sites**, so users would be signed out on every reload |
| 2 | **Frontend host** | Serves the React app | Connect the repo, set the root to `frontend/` |
| 3 | **Backend host that runs Docker** | Runs the API | Must allow long-lived HTTP responses (AI chat streams for up to 90 s) |
| 4 | **PostgreSQL 16** | Main database | Managed options: Neon, Supabase, Render, RDS. Must allow the `citext` and `pg_trgm` extensions, which the first migration creates |
| 5 | **Redis** | Shared rate limits across server processes | Upstash, Render or Railway Redis. Without it, each process counts limits separately |
| 6 | **Email provider (SMTP)** | Verification, password reset and security emails | Brevo, Resend, SendGrid, Mailgun, or Gmail for low volume. Verify your sending domain (SPF/DKIM) so emails don't land in spam |
| 7 | **OpenAI API key** | AI chat and generation | Set a monthly spending limit in the OpenAI dashboard as well as `AI_MONTHLY_BUDGET_USD` |
| 8 | **GitHub OAuth app** (optional) | "Continue with GitHub" | Create a **separate production app** with the production callback URL (below) |
| 9 | **Google OAuth client** (optional) | "Continue with Google" | Add the production redirect URI. Publish the consent screen; while it's in "Testing", only listed test users can sign in |
| 10 | **GitHub personal access token** (optional) | Raises GitHub API limits from 60 to 5,000 requests/hour for repo previews | Fine-grained, public repositories, read-only |
| 11 | **A scheduler** (cron) | Runs maintenance jobs (section 5) | GitHub Actions on a schedule, your host's cron jobs, or cron-job.org |
| 12 | **Sentry** (optional) | Error reports | Set `SENTRY_DSN` |

### 2. Backend environment variables (production)

Set these in your backend host's settings. **Never commit them.** Generate each secret with:

```bash
python3 -c "import secrets,base64;print(base64.b64encode(secrets.token_bytes(32)).decode())"
```

```dotenv
# Core
APP_ENV=production
SECRET_KEY=<random secret>
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME
CORS_ORIGINS=https://devcommons.dev
FRONTEND_URL=https://devcommons.dev
API_PUBLIC_URL=https://api.devcommons.dev
COOKIE_SECURE=true

# Sign-in tokens
JWT_SIGNING_KEYS={"k1":"<random secret>"}
JWT_ACTIVE_KID=k1
JOB_SECRET=<random secret>

# Email
EMAIL_PROVIDER=smtp
EMAIL_FROM=DevCommons <no-reply@devcommons.dev>
SMTP_HOST=<provider host>
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_USERNAME=<provider username>
SMTP_PASSWORD=<provider password or API key>

# AI
AI_ENABLED=true
AI_PROVIDER=openai
OPENAI_API_KEY=<key>
OPENAI_MODEL=<exact model id from the OpenAI docs>
AI_MODEL_LABEL=<the model name users see>
AI_PRICING_JSON={"<model id>":{"input_per_1m":0,"cached_input_per_1m":0,"output_per_1m":0}}
AI_MONTHLY_BUDGET_USD=50

# GitHub / Google sign-in (optional)
GITHUB_OAUTH_CLIENT_ID=
GITHUB_OAUTH_CLIENT_SECRET=
GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=
GITHUB_TOKEN=

# Infrastructure
RATELIMIT_STORAGE_URI=redis://default:PASSWORD@HOST:6379
TRUST_PROXY_HOPS=1
SENTRY_DSN=
LOG_LEVEL=INFO
```

Things to get right:

- **Set `AI_PRICING_JSON` to your model's real prices** (from the OpenAI pricing page). The monthly budget is calculated from it, so zeros mean the budget never trips.
- **`TRUST_PROXY_HOPS=1`** when the host puts a load balancer in front of the app (Render, Railway, Fly, Cloud Run all do). Without it, every user looks like the same IP address and rate limits hit everyone at once.
- **`CORS_ORIGINS`** must exactly match the frontend address: `https`, no trailing slash. Add `https://www.devcommons.dev` too if you serve `www`.
- The server refuses to start in production if `COOKIE_SECURE` isn't `true`, if `SMTP_SECURITY=none`, or if a required value is missing. The error names the variable.
- Don't copy `DEV_API_TARGET` / `DEV_API_ORIGIN`. They're for local development only.

### 3. Deploy the backend

1. Point your host at `backend/` and build with the included **Dockerfile**. The container listens on port **8080**, runs database migrations on start, and serves with Gunicorn threads (needed for streaming chat). Tune with `GUNICORN_WORKERS` (default 2) and `GUNICORN_THREADS` (default 16).
2. Add the environment variables from section 2.
3. Point `api.devcommons.dev` at the service, with HTTPS on.
4. Check it:
   ```bash
   curl https://api.devcommons.dev/api/health         # {"data":{"status":"ok"}}
   curl https://api.devcommons.dev/api/health/ready   # also checks the database
   curl https://api.devcommons.dev/api/auth/providers # which social sign-ins are on
   ```
5. Create your account through the site, then make yourself an admin from the host's shell:
   ```bash
   flask --app wsgi users set-role <your-username> admin
   ```
   Don't run `seed --demo` in production. It creates demo accounts with a public password.

### 4. Deploy the frontend

1. Point your host at `frontend/`. Build command: `npm run build`. Output folder: `dist`. Node 20.19+ or 22.12+.
2. Set **`VITE_API_BASE_URL=https://api.devcommons.dev`** before building. It's baked into the build, so rebuild after changing it.
3. **Edit `frontend/vercel.json`**: in the `Content-Security-Policy` header, replace `https://api.devcommons.app` in `connect-src` with your API address. Otherwise the browser blocks every API call.
4. Point `devcommons.dev` at the site, with HTTPS on. `vercel.json` already handles page routing and the security headers. On another host, copy its rewrite rule (all paths serve `index.html`) and the headers.

### 5. Scheduled jobs

Call these with a scheduler. Each is a `POST` with the job secret:

```bash
curl -X POST -H "X-Job-Secret: $JOB_SECRET" https://api.devcommons.dev/api/internal/jobs/link-check
```

| Job | What it does | Suggested schedule |
|---|---|---|
| `link-check` | Checks up to 50 Knowledge Hub links per run (new links first, then the longest unchecked); links broken for 7 days are hidden | Every 15 minutes |
| `refresh-repos` | Refreshes GitHub stars and metadata for up to 200 harnesses; flags archived or deleted repos | Daily |
| `cleanup` | Permanently removes content deleted over 90 days ago, deleted chats and discarded AI drafts over 30 days old, and old sessions, tokens and cache | Daily |
| `rebuild-counters` | Recomputes vote, comment and bookmark counts | Weekly |

### 6. GitHub and Google sign-in in production

| Provider | Setting | Production value |
|---|---|---|
| GitHub OAuth app | Homepage URL | `https://devcommons.dev` |
| GitHub OAuth app | Authorization callback URL | `https://api.devcommons.dev/api/auth/oauth/github/callback` |
| Google OAuth client | Authorized redirect URI | `https://api.devcommons.dev/api/auth/oauth/google/callback` |
| Google consent screen | Publishing status | **In production**, with app name, logo, privacy policy and terms links (`/privacy`, `/terms`) |

### 7. Before you share the link

- [ ] Sign up with a real email address: the verification email arrives and its link opens your domain
- [ ] Reload the page: you stay signed in (if not, re-check the shared domain, `COOKIE_SECURE` and `CORS_ORIGINS`)
- [ ] "Continue with GitHub" and "Continue with Google" both work
- [ ] Send an AI chat message: the reply streams word by word, not all at once at the end
- [ ] Generate a harness from a public GitHub repo
- [ ] The 3D home page loads on a phone
- [ ] Settings → Account → Active sessions shows your device
- [ ] OpenAI dashboard: a usage limit is set
- [ ] Database backups are turned on at your Postgres provider
- [ ] Privacy and Terms pages reflect how you handle data (emails, AI chats sent to OpenAI)

### Rough monthly cost for a small launch

| Item | Cost |
|---|---|
| Domain | About $10–15 per year |
| Frontend hosting | Free tier is usually enough |
| Backend, Postgres, Redis | Free to about $25/month on small paid plans. Free databases often pause or expire, so check the limits |
| Email | Free tiers cover a few hundred emails per day |
| OpenAI | Depends on usage. It's capped by `AI_MONTHLY_BUDGET_USD` and the per-user daily limits (`AI_DAILY_TOKEN_LIMIT`, `AI_DAILY_GENERATION_LIMIT`) |
