# Onyx

Onyx keeps track of vendor data on construction projects. When a fabricator or contractor wins a job, they owe the buyer a pile of documentation — drawings, procedures, test reports — and every one of those documents has to be submitted, reviewed, and (eventually) approved. Onyx is a place to track all of that.

## Who it's for

Anyone responsible for documentation on a job: document controllers, project engineers, and project managers who need a quick answer to "what's still open on this project, and what happened the last time we submitted it?"

Onyx is an internal tool. You sign in with your company Microsoft account, and an admin sets up your access — there's no self-signup.

## How it works

- Each **project** holds a list of **vendor data items** — the individual documents the buyer requires.
- When you send a document to the buyer and get a return code back, that round-trip is saved as a **revision**, so the full back-and-forth history is always there. Return codes A and D mean approved; B and C mean it was rejected and needs to be resubmitted.
- Projects also hold **project documents** — things like drawings, specs, and contracts that come *from* the buyer and are versioned internally rather than submitted for approval.
- The home page shows every project with its open-item count ("N OPEN" or "ALL CLEAR"), so you always know where things stand at a glance.

## Setup

Requires Python 3.11+.

### 1. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure the environment

Create a `.env` file in the project root. Two variables are required:

```env
# SQLite for local dev; use an asyncpg URL for Postgres in production
DATABASE_URL=sqlite+aiosqlite:///./onyx.db

# Root directory for uploaded files (gitignored locally; outside the repo in prod)
FILE_STORAGE_ROOT=./uploads
```

Optional variables (defaults are fine for local development):

| Variable | Purpose |
|---|---|
| `TENANT_ID`, `CLIENT_ID`, `CLIENT_SECRET` | Microsoft Entra SSO credentials — only needed on a real deployment |
| `SESSION_SECRET` | Signs the OIDC handshake cookie; set a strong value in production |
| `ONYX_ADMIN_EMAILS` | Comma-separated break-glass admin emails, always granted admin on login |
| `APP_BASE_URL` | Public base URL used to build the Entra redirect URI (default `http://localhost:8000`) |
| `COOKIE_SECURE` | Set to `1` in production (https) to mark session cookies Secure |
| `SQL_ECHO` | Set to `1` to log SQL queries in local dev |

### 3. Create the database tables

```bash
python create_tables.py
```

### 4. (Optional) Seed demo data

Populates a few projects with VDIs, revisions, and files so the app is walkable in a browser:

```bash
python -m app.seed_data
```

### 5. Run the app

```bash
python main.py
```

The app starts at http://127.0.0.1:8000 with auto-reload enabled. A public liveness probe is available at `/healthz`.

## Running the tests

```bash
pytest
```

The test suite exercises the SSO flow against a mocked identity seam, so no Entra credentials are needed.
