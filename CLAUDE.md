# Bet Tracker Web App — CLAUDE.md

## Project Overview

A standalone web-based bet tracking application. **Separate project from the Discord bot (televivet).** No Discord. No asyncio. Full-stack: React frontend + FastAPI backend + SQLite/PostgreSQL.

Core purpose: track bets against matched events, monitor open bets vs live Betfair market, calculate CLV (odds CLV + line CLV) at close using Betfair as sole true-line source, auto-result completed games, and surface cashout signals when edge has eroded.

---

## Stack

| Layer | Choice |
|---|---|
| Frontend | React + TypeScript + Vite |
| Styling | Tailwind CSS |
| Backend | FastAPI (Python 3.11+) |
| Database | SQLite (dev) / PostgreSQL (prod) via SQLAlchemy |
| ORM | SQLAlchemy 2.x (async) |
| Migrations | Alembic |
| Odds data | The Odds API — event discovery, line snapshots, scores |
| True closing line | **Betfair Exchange LAY only** — no Pinnacle, no consensus CLV |
| Package manager | uv (backend), pnpm (frontend) |

---

## Critical Design Decisions

### 1. Event Matching via Dropdown — No Free Text

When logging a bet, the user **selects an event from a dropdown** populated live from The Odds API. The `event_id` is stored on the bet. This is non-negotiable — it enables:
- Closing line capture (we know the event)
- Auto-result via scores endpoint
- Betfair market matching
- Historical line snapshots

No manual text entry for events. The Add Bet form calls `/api/events?sport=...` and shows a searchable dropdown of upcoming games.

### 2. CLV = Two Signals for Spreads/Totals

**Odds CLV** (all market types): Did you beat the closing price?
- Your odds taken vs Betfair LAY at close
- Uses power devig on Betfair price
- Stored as `odds_clv_pct`

**Line CLV** (totals + handicap only): Did you beat the closing line?
- The line you got vs where the market closed
- Example: You bet o160.5. Market opened at o168.5, closed at o168.5. You got 8 pts of line value → `line_clv_pts = +8.0`
- This is independent of odds — it's pure market movement signal
- Stored as `line_clv_pts`

Both signals shown together in the UI. Line CLV is often more meaningful for totals/spreads because it can't be shaded — the number either moved or it didn't.

### 3. No Pinnacle — Betfair Only for True Line

Betfair Exchange LAY is the sole CLV reference. No Pinnacle anywhere in the codebase — not in config, not in calculations, not in UI labels. "Consensus" is only used for tracking where the market line opened/closed (to calculate line CLV pts) — never for odds CLV.

---

## Repo Structure

```
bet-tracker/
├── CLAUDE.md
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── db/
│   │   ├── models.py
│   │   ├── queries.py           # ALL DB access here — no SQL in routes
│   │   └── session.py
│   ├── routers/
│   │   ├── bets.py
│   │   ├── events.py
│   │   ├── odds.py
│   │   └── stats.py
│   ├── services/
│   │   ├── odds_client.py       # The Odds API wrapper
│   │   ├── betfair_client.py    # Betfair Exchange wrapper
│   │   ├── clv.py               # CLV logic (Betfair-only)
│   │   ├── auto_result.py       # Score-based auto-result
│   │   └── cashout_signal.py    # Live edge erosion signal
│   ├── scheduler.py             # APScheduler background jobs
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── OpenBets.tsx
│   │   │   ├── AddBet.tsx
│   │   │   ├── Upcoming.tsx
│   │   │   └── History.tsx
│   │   ├── components/
│   │   ├── hooks/
│   │   └── lib/
│   └── package.json
└── docker-compose.yml
```

---

## Database Schema

### `events`
```sql
id              TEXT PK       -- Odds API event_id
sport_key       TEXT
sport_title     TEXT
commence_time   DATETIME
home_team       TEXT
away_team       TEXT
status          TEXT          -- scheduled | live | completed
home_score      INT           -- null until completed
away_score      INT
last_updated    DATETIME
```

### `tracked_bets`
```sql
id              INTEGER PK AUTOINCREMENT
event_id        TEXT FK → events.id NOT NULL   -- always matched
sport_key       TEXT
event_name      TEXT          -- "Brisbane Broncos vs Penrith Panthers"
commence_time   DATETIME
selection       TEXT          -- team name or "Over" / "Under"
market_type     TEXT          -- h2h | handicap | totals
line            REAL          -- null for h2h; e.g. 160.5 or -3.5
side            TEXT          -- over | under | home | away
odds_taken      REAL          -- decimal odds
stake           REAL
bookmaker       TEXT          -- from TRACKED_BOOKMAKERS config
status          TEXT          -- open | won | lost | void | deleted
settle_source   TEXT          -- auto_scores | manual | null
notes           TEXT
created_at      DATETIME
updated_at      DATETIME
```

### `closing_lines`
```sql
id                      INTEGER PK AUTOINCREMENT
bet_id                  INTEGER FK → tracked_bets.id

-- Betfair data
betfair_lay_at_bet      REAL      -- Betfair LAY when bet was first logged
betfair_lay_at_close    REAL      -- Betfair LAY at commence_time - 5min

-- Odds CLV
odds_clv_pct            REAL      -- % edge vs Betfair close (positive = value)
beat_closing_odds       BOOLEAN

-- Line CLV (totals/handicap only — null for h2h)
line_at_open            REAL      -- consensus line when bet was placed (e.g. 168.5)
line_at_close           REAL      -- consensus line at close (e.g. 168.5)
line_clv_pts            REAL      -- points of line value (positive = you got better number)
beat_closing_line       BOOLEAN

captured_at             DATETIME
capture_source          TEXT      -- scheduled | manual_trigger | missed_recovery
```

### `odds_snapshots`
```sql
id              INTEGER PK AUTOINCREMENT
event_id        TEXT FK → events.id
bookmaker       TEXT
market_type     TEXT
selection       TEXT
odds            REAL
line            REAL
snapshot_time   DATETIME
```

### `betfair_snapshots`
```sql
id              INTEGER PK AUTOINCREMENT
event_id        TEXT
market_id       TEXT
selection_id    TEXT
selection_name  TEXT
market_type     TEXT
side            TEXT          -- BACK | LAY
price           REAL
size_available  REAL
snapshot_time   DATETIME
```

---

## Business Logic

### CLV (`services/clv.py`)

```python
def calc_odds_clv(odds_taken: float, betfair_lay_close: float) -> float:
    """
    Betfair LAY price ≈ fair price (exchange has small margin).
    fair_prob = 1 / betfair_lay_close
    your_implied = 1 / odds_taken
    CLV% = (fair_prob - your_implied) / your_implied
    Positive = you got better than fair = value.
    """
    fair_prob = 1 / betfair_lay_close
    your_implied = 1 / odds_taken
    return (fair_prob - your_implied) / your_implied

def calc_line_clv(line_taken: float, line_at_close: float, side: str) -> float:
    """
    Points of line value captured. Positive always = you got the better number.

    OVER / HOME bets: higher line = worse for you
        line_clv = line_at_close - line_taken
        e.g. took o160.5, closed o168.5 → +8.0 pts ✓  (line moved away from you = you got it cheap)
        e.g. took o168.5, closed o160.5 → -8.0 pts ✗

    UNDER / AWAY bets: lower line = worse for you
        line_clv = line_taken - line_at_close
        e.g. took u168.5, closed u160.5 → +8.0 pts ✓  (line moved down, you locked in the high number)
    """
    if side in ("over", "home"):
        return line_at_close - line_taken
    else:
        return line_taken - line_at_close
```

### Cashout Signal (`services/cashout_signal.py`)

```python
def cashout_signal(
    odds_taken: float,
    betfair_lay_at_bet: float,
    current_betfair_lay: float,
    threshold: float = 0.03
) -> dict:
    """
    Measures edge erosion since bet was placed.
    original_edge = fair_prob_at_bet - your_implied
    current_edge  = current_fair_prob - your_implied
    If current_edge < -threshold: recommend cashout
    """
    your_implied = 1 / odds_taken
    original_edge = (1 / betfair_lay_at_bet) - your_implied
    current_edge = (1 / current_betfair_lay) - your_implied

    if current_edge > 0:
        severity = "clear"      # still beating market
    elif current_edge > -threshold:
        severity = "watch"      # marginal
    else:
        severity = "cashout"    # no edge remaining

    return {
        "recommend_cashout": severity == "cashout",
        "severity": severity,                          # clear | watch | cashout
        "original_edge_pct": round(original_edge * 100, 2),
        "current_edge_pct": round(current_edge * 100, 2),
        "current_betfair_lay": current_betfair_lay,
    }
```

### Auto-Result (`services/auto_result.py`)

Source: The Odds API `/v4/sports/{sport_key}/scores` (returns data ~3 days post-game).

```python
def resolve_h2h(selection, home_team, away_team, home_score, away_score) -> str:
    if home_score == away_score: return "void"
    winner = home_team if home_score > away_score else away_team
    return "won" if selection == winner else "lost"

def resolve_totals(side, line, home_score, away_score) -> str:
    total = home_score + away_score
    if total == line: return "void"
    return "won" if (side == "over" and total > line) or (side == "under" and total < line) else "lost"

def resolve_handicap(side, line, home_score, away_score) -> str:
    # line is from home team's perspective (e.g. home -3.5)
    margin = home_score - away_score
    adjusted = (margin + line) if side == "home" else (-margin - line)
    if adjusted == 0: return "void"
    return "won" if adjusted > 0 else "lost"
```

Rules:
- Asian handicap → always return `"needs_manual"` (push edge cases)
- Never overwrite `settle_source="manual"`
- If score data absent → leave open, never guess

---

## API Routes

```
GET    /api/events                        # upcoming; ?sport=&days=3
GET    /api/events/{id}/lines             # all bookmaker lines for event
GET    /api/events/{id}/betfair           # Betfair LAY prices

GET    /api/bets                          # list; ?status=&sport=&bookmaker=
POST   /api/bets                          # create (event_id required)
GET    /api/bets/{id}                     # single bet + closing lines + cashout signal
PATCH  /api/bets/{id}/result              # {outcome: "won"|"lost"|"void"}
DELETE /api/bets/{id}                     # soft delete

GET    /api/stats/summary                 # PnL, ROI%, odds CLV win rate, line CLV win rate
GET    /api/stats/breakdown               # by sport | bookmaker | market_type
```

---

## Background Jobs (APScheduler)

| Job | Interval | What it does |
|---|---|---|
| `poll_upcoming_odds` | 5 min | Snapshot Odds API lines for all events with open bets |
| `poll_betfair` | 5 min | Snapshot Betfair LAY for open bet selections |
| `capture_closing_lines` | 1 min | Fires at commence_time - 5min per open bet |
| `poll_scores` | 10 min | Auto-result open bets past commence_time |
| `recover_missed_closes` | 1 hour | Re-attempt closing line capture for any missed bets |

**On bet creation**: Immediately snapshot current Betfair LAY for the selection → stored as `betfair_lay_at_bet` in closing_lines. This is the baseline for cashout edge erosion.

---

## Config

```python
class Settings(BaseSettings):
    ODDS_API_KEY: str
    BETFAIR_USERNAME: str
    BETFAIR_PASSWORD: str
    BETFAIR_APP_KEY: str
    DATABASE_URL: str = "sqlite+aiosqlite:///./bets.db"
    TRACKED_BOOKMAKERS: list[str] = ["betfair", "tab", "sportsbet", "neds", "pointsbet"]
    # No pinnacle — removed entirely
    SPORTS: list[str] = ["aussierules", "rugbyleague", "americanfootball_nfl", "basketball_nba"]
    CLOSING_LINE_WINDOW_MINUTES: int = 5
    CASHOUT_EDGE_THRESHOLD: float = 0.03
    BETFAIR_ENABLED: bool = True
```

---

## Conventions

- No raw SQL in routes — all DB via `db/queries.py`
- No business logic in routes — routes → services → queries
- **No Pinnacle** — not in config, not in CLV, not anywhere
- `event_id` required on all bets — no free-text events
- Async throughout — FastAPI + SQLAlchemy async
- TanStack Query for all frontend data fetching
- Soft delete only — `status=deleted`, never hard delete
- Never overwrite manual results with auto

## What NOT to Build

- No Pinnacle integration anywhere
- No Discord
- No auth
- No Asian handicap auto-result (return `needs_manual`)
- No free-text event entry
- No raw SQL in routes
