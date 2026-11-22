# DevCommons Backend — Quick Start

Flask 3 + PostgreSQL 16 API that implements `devcommons_backend_spec.md`.
Everything lives in this `backend/` folder.

---

## 1. What you need (one time)

| Tool | Check it works |
|---|---|
| Docker Desktop (running) | `docker ps` |
| uv (Python package manager) | `uv --version` — install with `curl -LsSf https://astral.sh/uv/install.sh \| sh` |

uv downloads Python 3.12 for you, so you don't need to install Python separately.

---

## 2. First-time setup (about 2 minutes)

```bash
cd backend

# 1. Start Postgres (port 5433) and Redis (port 6380) in Docker
docker compose up -d

# 2. Install Python dependencies
uv sync

# 3. Create your config file (a ready-to-use .env is already here; skip this if it exists)
cp .env.example .env
#    Then put real random values in SECRET_KEY, JOB_SECRET and JWT_SIGNING_KEYS.
#    Generate one with:
#    python3 -c "import secrets,base64;print(base64.b64encode(secrets.token_bytes(32)).decode())"

# 4. Create the database tables (also seeds categories and trusted domains)
uv run flask --app wsgi db upgrade

# 5. (Optional) Add sample harnesses, ideas, resources and collections
uv run flask --app wsgi seed --demo
```

---

## 3. Start the backend (every day)

```bash
cd backend
docker compose up -d                          # make sure Postgres and Redis are running
uv run flask --app wsgi db upgrade            # only needed after pulling new migrations
uv run flask --app wsgi run --port 5001 --debug
```

Leave this terminal open; the server runs until you press `Ctrl+C`. `--debug` reloads on code changes.

> **Changed `.env`? Restart the server.** Settings (including `AI_PROVIDER` and `OPENAI_API_KEY`) are read
> once at startup. Code changes reload automatically; `.env` changes don't.

The API is now at **http://localhost:5001/api**. Check it:

```bash
curl http://localhost:5001/api/health         # {"data":{"status":"ok"}}
curl http://localhost:5001/api/health/ready   # also checks the database
```

> **Why port 5001?** On macOS, port 5000 is used by AirPlay Receiver.
> To use 5000 instead, turn off *System Settings → General → AirDrop & Handoff → AirPlay Receiver*.

To run it the production way (Gunicorn with threads, needed for streaming chat):

```bash
GUNICORN_BIND=127.0.0.1:5001 uv run gunicorn -c gunicorn.conf.py wsgi:app
```

Stop everything with `Ctrl+C`, then `docker compose stop`.

---

## 4. Sign in

**Demo accounts** (after `seed --demo`), all with password `devcommons-demo-password`:

| Email | Role |
|---|---|
| `ada@demo.devcommons.local` | admin |
| `grace@demo.devcommons.local` | moderator |
| `linus@demo.devcommons.local` | user |

**Your own account:** register through the frontend or the API. With the default `EMAIL_PROVIDER=console`,
emails are **printed in the terminal** where the backend runs, so copy the verification link from there. To
receive them in your inbox, see [section 7](#7-send-real-email). To skip email verification:

```bash
uv run flask --app wsgi users verify-email <username>
uv run flask --app wsgi users set-role <username> admin     # make yourself an admin
```

---

## 5. Connect the frontend

With the backend running on port 5001, start the frontend in a second terminal:

```bash
cd frontend
npm install          # first time only
npm run dev          # prints the URL, usually http://localhost:5173
```

Full frontend instructions are in [`../frontend/README.md`](../frontend/README.md). How the two connect in development:

- The frontend's dev server forwards every `/api/*` request to `http://localhost:5001` (set by `DEV_API_TARGET`
  in `frontend/.env.local`). You don't configure an API URL in the browser.
- It sends `Origin: http://localhost:5173` (`DEV_API_ORIGIN`), which is already in `CORS_ORIGINS` in `.env`.
  This works even when the frontend itself runs on another port, such as 5174.
- If you run the backend on a different port, change `DEV_API_TARGET` and restart the frontend.
- If you change `DEV_API_ORIGIN`, add the same value to `CORS_ORIGINS` here and restart the backend.
- The refresh cookie only works when the frontend and the API share a site, so open the app on `localhost`,
  not `127.0.0.1`.
- `/api/auth/refresh` and `/api/auth/logout` require the header `X-Requested-With: devcommons`. The frontend
  sends it automatically.

---

## 6. AI features

`.env.example` ships with `AI_PROVIDER=fake`, which returns placeholder answers ("Here is a sample answer…")
so you can build the UI without an API key. To use OpenAI for real, set these in `.env`:

```dotenv
AI_PROVIDER=openai
OPENAI_API_KEY=sk-...
# Check the exact model id on the OpenAI docs before setting this
OPENAI_MODEL=<model-id>
AI_PRICING_JSON={"<model-id>":{"input_per_1m":0,"cached_input_per_1m":0,"output_per_1m":0}}
```

Then **stop the server (`Ctrl+C`) and start it again**. A server that was already running keeps using the fake
client until it's restarted. Check which one is active with a quick chat in the AI Workspace: placeholder text
means the fake client is still loaded.

Set `AI_ENABLED=false` to switch AI off completely. Add a `GITHUB_TOKEN` (read-only, public repos) to raise
GitHub's rate limit from 60 to 5,000 requests per hour.

---

## 7. Send real email

By default (`EMAIL_PROVIDER=console`) no email leaves your machine: each message, with its link, is printed
in the backend terminal. To send real email, use any SMTP provider. Set these in `.env`, then **restart the
server**:

```dotenv
EMAIL_PROVIDER=smtp
EMAIL_FROM=DevCommons <you@gmail.com>
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_USERNAME=you@gmail.com
SMTP_PASSWORD=your-16-letter-app-password
```

| Provider | `SMTP_HOST` | Port / security | Username / password |
|---|---|---|---|
| Gmail | `smtp.gmail.com` | 587 `starttls` (or 465 `ssl`) | Your address / an [App Password](https://myaccount.google.com/apppasswords) (needs 2-Step Verification). Your normal password won't work |
| Outlook / Microsoft 365 | `smtp.office365.com` | 587 `starttls` | Your address / your password (SMTP AUTH must be enabled) |
| Brevo | `smtp-relay.brevo.com` | 587 `starttls` | From Brevo → SMTP & API |
| Resend | `smtp.resend.com` | 465 `ssl` | `resend` / your API key |
| SendGrid | `smtp.sendgrid.net` | 587 `starttls` | `apikey` / your API key |
| Mailtrap (testing inbox) | from your Mailtrap inbox | 587 `starttls` | from your Mailtrap inbox |

- `EMAIL_FROM` must be an address the provider lets you send from. Gmail replaces any other sender with your
  own address; Resend, SendGrid and Brevo need a verified domain or sender.
- Use `SMTP_SECURITY=ssl` for port 465 and `starttls` for 587. `none` is only for a local test server and is
  refused when `APP_ENV=production`.
- The server refuses to start if `SMTP_HOST` is missing, or if only one of `SMTP_USERNAME` / `SMTP_PASSWORD`
  is set.
- If sending fails, the user's action (sign-up, password reset) still succeeds, and the backend terminal logs
  `email_send_failed` with the reason.

**Try it:** sign up through the frontend with your real address, or use *Resend email* on the yellow banner.

---

## 8. Sign in with GitHub and Google

Optional, alongside email + password. A button appears on the sign-in and sign-up pages once that provider's
ID and secret are set in `.env` (restart the server after setting them). Accounts created this way start
**already verified**, so the app doesn't need to send them a verification email.

**GitHub** — github.com → Settings → Developer settings → OAuth Apps → **New OAuth App**

| Field | Value (local development) |
|---|---|
| Homepage URL | `http://localhost:5173` |
| Authorization callback URL | `http://localhost:5001/api/auth/oauth/github/callback` |

Copy the Client ID, click **Generate a new client secret**, and put both in `GITHUB_OAUTH_CLIENT_ID` /
`GITHUB_OAUTH_CLIENT_SECRET`.

**Google** — console.cloud.google.com → APIs & Services → **OAuth consent screen** (External; add yourself as
a test user while it's in Testing), then **Credentials → Create credentials → OAuth client ID → Web application**

| Field | Value (local development) |
|---|---|
| Authorized redirect URIs | `http://localhost:5001/api/auth/oauth/google/callback` |

Put the client ID and secret in `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET`.

How it behaves:

- The callback goes straight to this API (`API_PUBLIC_URL`, default `http://localhost:5001`), not through the
  frontend, so the registered URL stays the same whichever port the frontend runs on. In production set
  `API_PUBLIC_URL=https://api.your-domain` and register that callback URL instead.
- **New email** → a new account, with a username taken from the GitHub login or the email (changeable in
  Settings → Profile).
- **Email of an existing verified account** → the provider is connected to that account.
- **Email of an existing *unverified* account** → the provider proves who owns the address, so that account
  is claimed: it becomes verified, its old password is removed and its sessions are signed out (protects
  against someone who registered with another person's email).
- Only verified provider emails are accepted. Later sign-ins match on the provider's account ID, not the email.
- Users connect or disconnect providers in **Settings → Account → Connected accounts**. The last way to sign in
  can't be removed. Accounts without a password can set one there, and confirm sensitive changes (email,
  password, deletion) by having signed in within the last 15 minutes.
- Security: state + PKCE in a signed, 10-minute, HttpOnly cookie; redirects only to known frontend origins
  (any `http://localhost:<port>` in development); provider tokens are used once and never stored.

---

## 9. Run the tests

```bash
docker compose up -d          # tests use a separate database: devcommons_test
uv run pytest                 # 132 tests
uv run pytest --cov=app       # with coverage
uv run ruff check app tests   # lint
```

> If you created the Docker database **before** `scripts/init-test-db.sql` existed, create the test DB once:
> `docker compose exec db createdb -U devcommons devcommons_test`

---

## 10. Handy commands

| Command | What it does |
|---|---|
| `uv run flask --app wsgi db upgrade` | Apply database migrations |
| `uv run flask --app wsgi db migrate -m "msg"` | Create a migration after changing models (review it by hand) |
| `uv run flask --app wsgi seed [--demo]` | Seed reference data (and sample content) |
| `uv run flask --app wsgi counters rebuild` | Recompute all vote/comment/... counters |
| `uv run flask --app wsgi jobs run link-check` | Run a scheduled job once (`link-check`, `refresh-repos`, `cleanup`, `rebuild-counters`) |
| `docker compose down -v` | **Delete** the local database and start fresh |
| `docker build -t devcommons-api .` | Build the production image (migrates on start, serves on port 8080) |

In production, scheduled jobs are triggered with
`POST /api/internal/jobs/<name>` and the header `X-Job-Secret: <JOB_SECRET>`.

---

## 11. Troubleshooting

| Problem | Fix |
|---|---|
| `ValidationError ... Settings` on start | A required `.env` value is missing or invalid. The message names the variable |
| `connection refused` on port 5433 | Start Docker Desktop, then run `docker compose up -d` |
| Port 5433 or 6380 already in use | `DB_PORT=5434 docker compose up -d`, and update `DATABASE_URL` to match |
| Login keeps returning 429 | 5 wrong passwords lock the account for 15 minutes (by design) |
| Every request returns 429 | Rate limits are in memory. Restart the server, or set `RATELIMIT_ENABLED=false` while developing |
| AI answers are placeholder text | `AI_PROVIDER` is `fake`, or you edited `.env` without restarting the server |
| `Address already in use` on port 5001 | Another backend is still running. Find it with `lsof -iTCP:5001 -sTCP:LISTEN` and stop it, or use another port and update the frontend's `DEV_API_TARGET` |
| No GitHub / Google button | Both the provider's `..._CLIENT_ID` and `..._CLIENT_SECRET` must be set, then restart the backend. Check with `curl localhost:5001/api/auth/providers` |
| GitHub says "redirect_uri is not associated with this application" | The callback URL in the OAuth app must be exactly `<API_PUBLIC_URL>/api/auth/oauth/github/callback` |
| Google says `redirect_uri_mismatch` or "access blocked" | Add the exact callback URL under Authorized redirect URIs, and add yourself as a test user on the consent screen |
| Back on the sign-in page with "took too long" | The sign-in must finish within 10 minutes in the same browser. Also open the app on `localhost`, not `127.0.0.1` |
| Email links open `localhost:5173` but the frontend runs on another port | Links are built from `FRONTEND_URL`. Set it to the frontend's real address (e.g. `http://localhost:5174`) and restart. Leave `CORS_ORIGINS` alone |
| Verification email never arrives | With `EMAIL_PROVIDER=console` it's printed in the backend terminal, not sent. Switch to `smtp` (section 7) and restart |
| `email_send_failed` / `SMTPAuthenticationError` in the log | Wrong username or password. Gmail needs an App Password, not your normal password |
| Email sent but lands in spam | Send from a domain you've verified with the provider (SPF/DKIM), not a free address |
| Frontend shows "Origin not allowed" (403) | The frontend's `DEV_API_ORIGIN` isn't in `CORS_ORIGINS`. Add it and restart |

---

## 12. Where things are

```text
app/
  __init__.py        create_app(), blueprints, JSON format
  config.py          every setting (read from .env)
  auth/              register, login, JWT, refresh cookies, email, GitHub/Google sign-in (oauth.py)
  common/            errors, validation, pagination, SSRF-safe URL checks, search helpers
  integrations/      GitHub API + link checker
  modules/<name>/    models.py, schemas.py, service.py, routes.py per feature
    ai/              chat (SSE), generation, drafts, prompts/*.md, quotas
migrations/          Alembic migrations (0001 schema, 0002 seed data, 0003 oauth_accounts)
tests/               unit + API tests (real Postgres, real JWTs)
```

**Small additions to the spec** (each one is commented in the code):

- `users.last_failed_login_at`: tracks the 15-minute window for the login lockout.
- `resources.link_broken_since`: tracks the 7-day "hide broken links" rule.
- `AI_PROVIDER=fake`: an offline AI client for development and tests.
- Sign in with GitHub / Google: new `oauth_accounts` table (migration `0003`), see section 8.
- Email is sent over SMTP (`EMAIL_PROVIDER=smtp`, any provider) instead of AWS SES, so `boto3` is no longer a dependency.
- The AI output-token limit is split into `AI_MAX_OUTPUT_TOKENS_CHAT` and `AI_MAX_OUTPUT_TOKENS_GENERATION`.
- Tests clean the database between runs with `TRUNCATE` instead of rolling back transactions.
