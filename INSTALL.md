# Installation Guide

Bet Tracker is a full-stack app: a **FastAPI (Python)** backend and a **React + Vite (Node)** frontend. You install and run them separately.

---

## 1. Prerequisites

| Tool | Required version | Notes |
|---|---|---|
| **Python** | 3.11+ | Runs the backend |
| **Node.js** | 18+ (20 LTS recommended) | Runs the frontend — install this |
| **git** | any | |
| uv | optional | Faster Python installs; pip works fine instead |
| pnpm | optional | npm works fine instead
### Install Node.js (Windows)

Pick one:

```powershell
# Option A: winget (built into Windows 11)
winget install OpenJS.NodeJS.LTS

# Option B: download the LTS installer from https://nodejs.org and run it
```

Close and reopen your terminal afterwards, then verify:

```powershell
node --version   # should print v20.x (or v18+)
npm --version
```

---

## 2. Backend (Python / FastAPI)

All commands run from the **repo root** (`degentracker/`), because the app is imported as the `backend` package.

### 2a. Create a virtual environment

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

> If PowerShell blocks the activate script, run once:
> `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`

### 2b. Install the Python libraries

```powershell
pip install -r backend/requirements.txt
```

<details>
<summary>Prefer <code>uv</code> (faster)?</summary>

```powershell
pip install uv          # one-time
uv venv
.venv\Scripts\Activate.ps1
uv pip install -r backend/requirements.txt
```
</details>

These are the backend libraries (from `backend/requirements.txt`):

| Library | Purpose |
|---|---|
| `fastapi` | Web framework / API routes |
| `uvicorn[standard]` | ASGI server that runs the app |
| `sqlalchemy` | Async ORM (database models & queries) |
| `aiosqlite` | Async SQLite driver (dev database) |
| `alembic` | Database migrations |
| `pydantic` | Request/response validation |
| `pydantic-settings` | Loads config from `.env` |
| `httpx` | Async HTTP client (The Odds API + Betfair) |
| `apscheduler` | Background jobs (odds polling, CLV capture, auto-result) |
| `python-dotenv` | Reads the `.env` file |
| `playwright` | bet365 scraper (optional — see below) |

### 2c. Scrapers: bet365 + Betfair (optional)

bet365 isn't carried by The Odds API, so its odds come from a Playwright
scraper (**Scrape bet365** button on the Find EV page). A second scraper
(**Scrape Betfair**) reads true best back/lay prices with sizes off the
public Betfair Exchange coupons — no Betfair account or app key needed —
and those replace The Odds API's Betfair prices as the EV fair line.
One-time setup after installing requirements:

```powershell
playwright install chromium
```

Notes:
- The scraper strongly prefers your **installed Google Chrome** — bet365
  soft-blocks Playwright's bundled test browser (the page loads but odds
  never render). Keep Chrome installed.
- It runs a **visible** Chrome window by default (`BET365_HEADLESS=false`);
  bet365 blocks obvious headless browsers.
- Disable entirely with `BET365_SCRAPE_ENABLED=false` in `.env`.
- It's a scraper: bet365 markup changes will break it and scraping breaches
  bet365's terms of use — it fails gracefully and logs when it can't parse.

> **Production with PostgreSQL:** the dev DB is SQLite (no extra install). For a Postgres `DATABASE_URL`, also `pip install asyncpg`.

---

## 3. Frontend (Node / React + Vite)

From the **`frontend/`** directory:

```powershell
cd frontend
npm install
```

<details>
<summary>Prefer <code>pnpm</code>?</summary>

```powershell
corepack enable          # enables pnpm (ships with Node 16.13+)
pnpm install
```
</details>

These are the frontend libraries (from `frontend/package.json`):

| Library | Purpose |
|---|---|
| `react`, `react-dom` | UI framework |
| `react-router-dom` | Client-side routing (Dashboard / Bets / Upcoming / History) |
| `@tanstack/react-query` | Data fetching & caching from the API |
| `recharts` | Charts on the dashboard |
| `vite`, `@vitejs/plugin-react` | Dev server & build tooling |
| `typescript`, `@types/react`, `@types/react-dom` | TypeScript + type defs |
| `tailwindcss`, `postcss`, `autoprefixer` | Styling |

---

## 4. Configure environment variables

Create a `.env` in the repo root from the template, then fill in your keys:

```powershell
Copy-Item .env.example .env
```

The backend reads (see `backend/config.py`):

- `ODDS_API_KEY` — from https://the-odds-api.com
- `BETFAIR_USERNAME`, `BETFAIR_PASSWORD`, `BETFAIR_APP_KEY` — Betfair Exchange
- `BETFAIR_ENABLED` — set to `false` to run with just the Odds API key (no Betfair)
- `DATABASE_URL` — optional; defaults to `sqlite+aiosqlite:///./bets.db`

The app still starts without keys, but odds/events will be empty until they're set.

---

## 5. Run it (two terminals)

**Terminal 1 — backend** (repo root, venv activated):

```powershell
uvicorn backend.main:app --reload --port 8000
```

- API: http://localhost:8000
- Interactive docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

**Terminal 2 — frontend** (`frontend/`):

```powershell
npm run dev
```

- App: **http://localhost:5173**

The Vite dev server proxies `/api/*` to the backend on port 8000, so both must be running.

---

## Quick reference

```powershell
# Backend (repo root)
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
Copy-Item .env.example .env        # then edit .env
uvicorn backend.main:app --reload --port 8000

# Frontend (frontend/)  — requires Node.js installed first
cd frontend
npm install
npm run dev
```
