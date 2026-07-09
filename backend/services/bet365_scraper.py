"""Best-effort bet365 AU scraper (Playwright).

bet365 is not carried by The Odds API (they pulled their odds from
aggregators), so H2H prices are read from the public competition coupon
pages at bet365.com.au instead. This is inherently fragile: bet365 changes
its markup and runs anti-bot checks, so every parse step degrades gracefully
and logs what it saw. Scraping is manual-trigger only (POST /api/ev/bet365)
to keep request volume trivial.

Requires: pip install playwright && playwright install chromium
The backend runs fine without it — the import is lazy.

Runs headed Chromium by default (BET365_HEADLESS=false) because bet365
blocks obvious headless browsers; a Chrome window opening on scrape is
expected on a desktop setup.
"""
import logging
import os
import tempfile

from backend.config import settings
from backend.services.team_match import match_event, same_team  # noqa: F401 — re-exported

logger = logging.getLogger(__name__)

BET365_BASE = "https://www.bet365.com.au"

# Nav labels to click on the bet365 homepage, in preference order. Deep-link
# hashes don't route on a fresh page load, so navigation goes through the
# side nav like a human would.
SPORT_NAV_LABELS = {
    "rugbyleague_nrl": ["NRL", "Rugby League"],
    "aussierules_afl": ["AFL", "Australian Rules"],
}
# Kept for router iteration: which sports the scraper knows how to reach
SPORT_IDS = SPORT_NAV_LABELS

# Pull fixture rows (with their screen positions) and H2H price cells out of
# the coupon DOM. Selectors use [class*=...] so minor class-hash churn doesn't
# break parsing; odds are matched to fixtures by vertical overlap because the
# column DOM nests unpredictably. Only 'ParticipantOddsOnly' cells are H2H
# prices — handicap/total cells use different Participant classes.
_COUPON_PARSER_JS = """
() => {
  const clean = (s) => s.replace(/\\s+/g, " ").trim();
  const isOdds = (t) => /^\\d+(\\.\\d+)?$/.test(t);

  const odds = [];
  for (const el of document.querySelectorAll("[class*='ParticipantOddsOnly']")) {
    if (el.querySelector("[class*='ParticipantOddsOnly']")) continue; // leaves only
    const t = clean(el.textContent);
    if (!isOdds(t)) continue;
    const r = el.getBoundingClientRect();
    odds.push({ v: parseFloat(t), x: Math.round(r.left), y: Math.round(r.top + r.height / 2) });
  }

  const fixtures = [];
  const seen = new Set();
  for (const row of document.querySelectorAll("div[class*='ParticipantFixtureDetails']")) {
    if (row.parentElement && row.parentElement.closest("div[class*='ParticipantFixtureDetails']")) continue;
    const teams = [...row.querySelectorAll("div[class*='Team'], span[class*='Team']")]
      .filter((el) => !el.querySelector("div[class*='Team'], span[class*='Team']")) // leaf names only
      .map((el) => clean(el.textContent))
      .filter(Boolean);
    if (teams.length < 2) continue;
    const r = row.getBoundingClientRect();
    const key = teams[0] + "|" + teams[1] + "|" + Math.round(r.top);
    if (seen.has(key)) continue;
    seen.add(key);
    fixtures.push({ teamA: teams[0], teamB: teams[1], top: Math.round(r.top), bottom: Math.round(r.bottom) });
  }

  return { fixtures, odds };
}
"""


def _pair_fixtures_with_odds(fixtures: list[dict], odds: list[dict]) -> list[dict]:
    """
    Attach H2H prices to fixtures by geometry: a fixture's two prices are the
    odds cells that overlap its row vertically, in the leftmost column (x)
    that holds exactly two cells. Top cell belongs to the first-listed team.
    Fixtures with no clean two-cell column (suspended, layout change) are
    skipped rather than mispaired.
    """
    results = []
    for fx in fixtures:
        aligned = [o for o in odds if fx["top"] <= o["y"] <= fx["bottom"]]
        columns: dict[int, list[dict]] = {}
        for o in aligned:
            columns.setdefault(o["x"], []).append(o)
        two_cell_xs = sorted(x for x, cells in columns.items() if len(cells) == 2)
        if not two_cell_xs:
            continue
        cell_top, cell_bottom = sorted(columns[two_cell_xs[0]], key=lambda o: o["y"])
        if cell_top["v"] <= 1 or cell_bottom["v"] <= 1:
            continue
        results.append(
            {
                "team_a": fx["teamA"],
                "team_b": fx["teamB"],
                "odds_a": cell_top["v"],
                "odds_b": cell_bottom["v"],
            }
        )
    return results


def _profile_dir() -> str:
    """
    Dedicated persistent Chrome profile for scraping. A fresh cookie-less
    context on every scrape is a classic bot signal; a returning profile with
    stored cookies/consent gets soft-blocked far less. Lives outside the repo
    (which may sit in OneDrive — syncing a browser profile is churn).
    """
    base = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
    path = os.path.join(base, "degentracker", "chrome-profile")
    os.makedirs(path, exist_ok=True)
    return path


async def launch_scraper_context(pw):
    """
    Persistent context on the user's installed Chrome. bet365 soft-blocks
    Playwright's bundled Chrome-for-Testing (page loads, odds stream never
    delivers), so real Chrome is strongly preferred.
    """
    kwargs = {
        "headless": settings.BET365_HEADLESS,
        "args": ["--disable-blink-features=AutomationControlled"],
        "viewport": {"width": 1440, "height": 900},
        "locale": "en-AU",
        "timezone_id": "Australia/Sydney",
    }
    try:
        return await pw.chromium.launch_persistent_context(
            _profile_dir(), channel="chrome", **kwargs
        )
    except Exception:
        logger.warning(
            "scraper: installed Chrome not found, falling back to bundled Chromium "
            "(more likely to be blocked)"
        )
        return await pw.chromium.launch_persistent_context(_profile_dir(), **kwargs)


async def _scrape_sport_on_page(page, sport_key: str) -> list[dict]:
    """From the bet365 homepage, click into one sport's coupon and parse it."""
    # Deep-link hashes don't route reliably — reset to the homepage and click
    # the nav like a human. Also required between sports: the SPA's nav state
    # goes stale after a coupon loads.
    await page.goto(BET365_BASE, wait_until="domcontentloaded", timeout=45_000)
    await page.wait_for_timeout(3_000)
    clicked = False
    for label in SPORT_NAV_LABELS.get(sport_key, []):
        try:
            await page.get_by_text(label, exact=True).first.click(timeout=5_000)
            clicked = True
            break
        except Exception:
            continue
    if not clicked:
        logger.warning("bet365 %s: no nav link found", sport_key)
        return []

    try:
        await page.wait_for_selector(
            "div[class*='ParticipantFixtureDetails']", timeout=20_000
        )
    except Exception:
        # One reload retry — the odds stream sometimes stalls on first load
        try:
            await page.reload(wait_until="domcontentloaded", timeout=45_000)
            await page.wait_for_selector(
                "div[class*='ParticipantFixtureDetails']", timeout=15_000
            )
        except Exception:
            logger.warning(
                "bet365 %s: no fixtures rendered — soft-blocked (too many recent "
                "scrapes?) or empty coupon; try again later",
                sport_key,
            )
            return []
    # Coupon odds hydrate after the fixture skeleton appears
    await page.wait_for_timeout(2_500)
    data = await page.evaluate(_COUPON_PARSER_JS)

    fixtures = _pair_fixtures_with_odds(data.get("fixtures", []), data.get("odds", []))
    logger.info(
        "bet365 %s: %d fixtures on page, %d parsed with odds",
        sport_key,
        len(data.get("fixtures", [])),
        len(fixtures),
    )
    return fixtures


async def scrape_sports(sport_keys: list[str]) -> dict[str, list[dict]]:
    """
    Scrape H2H fixtures for several sports in one browser session.

    Returns {sport_key: [{team_a, team_b, odds_a, odds_b}]} in on-page order.
    bet365 coupons don't mark home/away, so callers must resolve orientation
    via match_event()/same_team() against the tracked event's teams.
    """
    if not settings.BET365_SCRAPE_ENABLED:
        logger.info("bet365 scraping disabled (BET365_SCRAPE_ENABLED=false)")
        return {}
    sport_keys = [k for k in sport_keys if k in SPORT_NAV_LABELS]
    if not sport_keys:
        return {}

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error(
            "playwright not installed — run: pip install playwright && playwright install chromium"
        )
        return {}

    results: dict[str, list[dict]] = {}
    try:
        async with async_playwright() as pw:
            context = await launch_scraper_context(pw)
            page = await context.new_page()
            await page.goto(BET365_BASE, wait_until="domcontentloaded", timeout=45_000)
            await page.wait_for_timeout(3_000)
            try:
                await page.get_by_text("Accept All", exact=True).first.click(
                    timeout=5_000
                )
            except Exception:
                pass  # no cookie banner — already accepted (persistent profile)

            for sport_key in sport_keys:
                try:
                    results[sport_key] = await _scrape_sport_on_page(page, sport_key)
                except Exception as exc:
                    logger.error("bet365 scrape failed for %s: %s", sport_key, exc)
                    results[sport_key] = []
            await context.close()
    except Exception as exc:
        logger.error("bet365 scrape session failed: %s", exc)

    return results


async def scrape_sport(sport_key: str) -> list[dict]:
    """Scrape a single sport (own browser session)."""
    results = await scrape_sports([sport_key])
    return results.get(sport_key, [])
