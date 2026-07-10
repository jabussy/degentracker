"""EV opportunity detection.

Fair probabilities come from Betfair LAY only (project rule — no Pinnacle,
no consensus, and no back-price fallback): LAY prices power-devigged
(Clarke 2007) so probabilities sum to 1. BACK prices are used solely to
validate the lay (a lay crossing below back means one side is stale) — never
as the fair line. Lined markets (spreads/totals) need a lay source at the
same line (`spreads_lay`/`totals_lay` market keys); without one those rows
carry no EV — comparing odds across different lines, or against a back
price, is not a fair comparison.

EV% = fair_prob * odds - 1  (expected profit per unit staked).
Kelly fraction = EV / (odds - 1); the UI shows quarter-Kelly.
"""
from typing import Optional

from backend.services.clv import power_devig
from backend.services.odds_client import tracker_bookmaker_key

BETFAIR_API_KEY = "betfair_ex_au"

MARKET_TYPE_MAP = {"h2h": "h2h", "spreads": "handicap", "totals": "totals"}


def _fair_probs(outcomes: list[dict]) -> dict:
    """Power-devig a market's outcomes -> {name: fair_prob}."""
    priced = [o for o in outcomes if o.get("price")]
    if len(priced) < 2:
        return {}
    probs = power_devig([o["price"] for o in priced])
    return {o["name"]: p for o, p in zip(priced, probs)}


def _fair_probs_by_line(outcomes: list[dict]) -> dict:
    """Devig a lined market -> {(name, point): fair_prob}."""
    probs = _fair_probs(outcomes)
    return {
        (o["name"], o["point"]): probs[o["name"]]
        for o in outcomes
        if o["name"] in probs and o.get("point") is not None
    }


# Thin Betfair books relay junk ladder orders through The Odds API (e.g. a
# $499 fishing order at 1.02 reported as the "back" price, or an empty lay
# side showing 1000). Guards below make a junk book produce NO fair line —
# never a wrong one.

# A real 2-way book's implied probabilities sum close to 1 (back side ~102%,
# lay side ~98%). A ladder polluted by junk orders sums wildly off.
OVERROUND_MIN = 0.90
OVERROUND_MAX = 1.20
# And lay sits at or just above back — a lay far above back (or below it,
# a crossed book) means one side is stale and we can't tell which.
MAX_LAY_BACK_SPREAD = 1.2


def _overround_ok(outcomes: list[dict]) -> bool:
    priced = [o for o in outcomes if o.get("price")]
    if len(priced) < 2:
        return False
    total = sum(1 / o["price"] for o in priced)
    return OVERROUND_MIN <= total <= OVERROUND_MAX


def _lay_back_coherent(lay_outcomes: list[dict], back_outcomes: list[dict]) -> bool:
    back_by_name = {o["name"]: o.get("price") for o in back_outcomes}
    checked = 0
    for o in lay_outcomes:
        lay, back = o.get("price"), back_by_name.get(o["name"])
        if not lay or not back:
            continue
        checked += 1
        if lay < back or lay > back * MAX_LAY_BACK_SPREAD:
            return False
    return checked > 0


def _side_for(selection: str, home: str, away: str) -> Optional[str]:
    if selection == "Over":
        return "over"
    if selection == "Under":
        return "under"
    if selection == home:
        return "home"
    if selection == away:
        return "away"
    return None


def build_ev_opportunities(event: dict) -> list[dict]:
    """
    Score every non-Betfair bookmaker outcome of one Odds API event against
    the Betfair fair line. Rows without a usable Betfair reference are still
    returned (ev_pct=None) so the UI can show the price and say why.
    """
    home = event.get("home_team", "")
    away = event.get("away_team", "")
    bookmakers = event.get("bookmakers", [])

    h2h_fair: dict = {}
    spread_fair: dict = {}
    total_fair: dict = {}

    bf = next((b for b in bookmakers if b.get("key") == BETFAIR_API_KEY), None)
    if bf:
        bf_markets = {m["key"]: m for m in bf.get("markets", [])}
        lay_outcomes = bf_markets.get("h2h_lay", {}).get("outcomes", [])
        back_outcomes = bf_markets.get("h2h", {}).get("outcomes", [])
        # LAY is the only fair line. It must look like a real book, and when
        # BACK is present it must not cross it (a crossed book means the lay
        # is stale). BACK alone is never a reference.
        if _overround_ok(lay_outcomes) and (
            not back_outcomes or _lay_back_coherent(lay_outcomes, back_outcomes)
        ):
            h2h_fair = _fair_probs(lay_outcomes)
        for mkey, store in (("spreads_lay", "spread"), ("totals_lay", "total")):
            outcomes = bf_markets.get(mkey, {}).get("outcomes", [])
            if _overround_ok(outcomes):
                if store == "spread":
                    spread_fair = _fair_probs_by_line(outcomes)
                else:
                    total_fair = _fair_probs_by_line(outcomes)

    rows: list[dict] = []
    for bm in bookmakers:
        bm_key = bm.get("key", "")
        if bm_key == BETFAIR_API_KEY:
            continue
        for market in bm.get("markets", []):
            market_type = MARKET_TYPE_MAP.get(market.get("key", ""))
            if market_type is None:
                continue
            for outcome in market.get("outcomes", []):
                price = outcome.get("price")
                if not price or price <= 1:
                    continue
                name = outcome["name"]
                point = outcome.get("point")

                if market_type == "h2h":
                    fair_prob = h2h_fair.get(name)
                elif market_type == "handicap":
                    fair_prob = spread_fair.get((name, point))
                else:
                    fair_prob = total_fair.get((name, point))
                reference = "betfair_lay" if fair_prob is not None else None

                ev = fair_prob * price - 1 if fair_prob else None
                rows.append(
                    {
                        "market_type": market_type,
                        "selection": name,
                        "side": _side_for(name, home, away),
                        "line": point,
                        "bookmaker": tracker_bookmaker_key(bm_key),
                        "bookmaker_title": bm.get("title", bm_key),
                        "odds": price,
                        "fair_prob": round(fair_prob, 6) if fair_prob else None,
                        "fair_odds": round(1 / fair_prob, 3) if fair_prob else None,
                        "ev_pct": round(ev * 100, 2) if ev is not None else None,
                        "kelly_pct": (
                            round(ev / (price - 1) * 100, 2) if ev is not None else None
                        ),
                        "reference": reference,
                    }
                )
    return rows
