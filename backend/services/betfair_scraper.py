"""Betfair Exchange coupon scraper (Playwright).

Reads best BACK/LAY prices *with sizes* straight off the public exchange
coupon pages (no login, no app key). This is the ground truth The Odds API
sometimes garbles on thin markets, and it feeds the same betfair_snapshots
table the CLV/cashout logic reads — so it also works as a poor-man's
substitute for Betfair API credentials.

Coupon DOM (verified 2026-07): each fixture is a <tr> holding a
.mod-event-line (team names in ul.runners li.name, matched amount) and three
.coupon-runner cells — home / draw / away — each with .back/.lay cells whose
text is "price $size" (e.g. "3.15 $774"). Two-way sports leave the middle
cell empty.

Requires: pip install playwright && playwright install chromium
"""
import logging
import re
from typing import Optional

from backend.config import settings
from backend.services.team_match import match_event, same_team  # noqa: F401 — used by router

logger = logging.getLogger(__name__)

SPORT_URLS = {
    "rugbyleague_nrl": "https://www.betfair.com.au/exchange/plus/rugby-league",
    "aussierules_afl": "https://www.betfair.com.au/exchange/plus/australian-rules",
}

_COUPON_PARSER_JS = """
() => {
  const clean = (s) => s.replace(/\\s+/g, " ").trim();
  const rows = [];
  for (const line of document.querySelectorAll(".mod-event-line")) {
    let row = line.parentElement;
    let hops = 0;
    while (row && !row.querySelector(".coupon-runner") && hops < 6) { row = row.parentElement; hops++; }
    if (!row) continue;
    const names = [...line.querySelectorAll("ul.runners li.name")].map((el) => clean(el.textContent)).filter(Boolean);
    if (names.length < 2) continue;
    const matched = clean(line.querySelector(".matched-amount")?.textContent || "");
    const runners = [];
    for (const r of row.querySelectorAll(".coupon-runner")) {
      runners.push({
        back: clean(r.querySelector(".back")?.textContent || ""),
        lay: clean(r.querySelector(".lay")?.textContent || ""),
      });
    }
    rows.push({ teamA: names[0], teamB: names[names.length - 1], matched, runners });
  }
  return rows;
}
"""

_PRICE_SIZE_RE = re.compile(r"^([\d.]+)\s*\$([\d,]+)")


def _parse_cell(text: str) -> Optional[dict]:
    """'3.15 $774' -> {price: 3.15, size: 774.0}; empty/junk -> None."""
    m = _PRICE_SIZE_RE.match(text or "")
    if not m:
        return None
    try:
        price = float(m.group(1))
        size = float(m.group(2).replace(",", ""))
    except ValueError:
        return None
    if price < 1.01:
        return None
    return {"price": price, "size": size}


def _parse_matched(text: str) -> float:
    m = re.search(r"\$([\d,]+)", text or "")
    return float(m.group(1).replace(",", "")) if m else 0.0


def parse_coupon_rows(rows: list[dict]) -> list[dict]:
    """
    Raw coupon rows -> fixtures with back/lay per team.

    The three runner cells are [teamA, draw, teamB]; two-way sports leave the
    draw empty. Fixtures where neither team has any price are dropped.
    """
    fixtures = []
    for row in rows:
        runners = row.get("runners", [])
        if len(runners) < 2:
            continue
        cell_a, cell_b = runners[0], runners[-1]
        fx = {
            "team_a": row["teamA"],
            "team_b": row["teamB"],
            "matched": _parse_matched(row.get("matched", "")),
            "back_a": _parse_cell(cell_a.get("back")),
            "lay_a": _parse_cell(cell_a.get("lay")),
            "back_b": _parse_cell(cell_b.get("back")),
            "lay_b": _parse_cell(cell_b.get("lay")),
        }
        if any(fx[k] for k in ("back_a", "lay_a", "back_b", "lay_b")):
            fixtures.append(fx)
    return fixtures


async def scrape_sports(sport_keys: list[str]) -> dict[str, list[dict]]:
    """Scrape Betfair coupons for several sports in one browser session."""
    sport_keys = [k for k in sport_keys if k in SPORT_URLS]
    if not sport_keys:
        return {}

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error(
            "playwright not installed — run: pip install playwright && playwright install chromium"
        )
        return {}

    # Same launch strategy as the bet365 scraper (persistent installed-Chrome profile)
    from backend.services.bet365_scraper import launch_scraper_context

    results: dict[str, list[dict]] = {}
    try:
        async with async_playwright() as pw:
            context = await launch_scraper_context(pw)
            page = await context.new_page()
            for sport_key in sport_keys:
                try:
                    await page.goto(
                        SPORT_URLS[sport_key],
                        wait_until="domcontentloaded",
                        timeout=60_000,
                    )
                    await page.wait_for_selector(".coupon-runner", timeout=30_000)
                    await page.wait_for_timeout(2_000)
                    raw = await page.evaluate(_COUPON_PARSER_JS)
                    fixtures = parse_coupon_rows(raw)
                    logger.info(
                        "betfair %s: %d rows on page, %d fixtures with prices",
                        sport_key,
                        len(raw),
                        len(fixtures),
                    )
                    results[sport_key] = fixtures
                except Exception as exc:
                    logger.error("betfair scrape failed for %s: %s", sport_key, exc)
                    results[sport_key] = []
            await context.close()
    except Exception as exc:
        logger.error("betfair scrape session failed: %s", exc)

    return results
