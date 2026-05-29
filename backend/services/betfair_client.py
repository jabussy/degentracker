import logging
from datetime import datetime, timezone
from typing import Optional
import httpx

from backend.config import settings

logger = logging.getLogger(__name__)

BETFAIR_LOGIN_URL = "https://identitysso.betfair.com/api/login"
BETFAIR_API_URL = "https://api.betfair.com/exchange/betting/json-rpc/v1"

_session_token: Optional[str] = None


async def _login() -> Optional[str]:
    global _session_token
    if not settings.BETFAIR_ENABLED:
        return None
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                BETFAIR_LOGIN_URL,
                data={
                    "username": settings.BETFAIR_USERNAME,
                    "password": settings.BETFAIR_PASSWORD,
                },
                headers={
                    "X-Application": settings.BETFAIR_APP_KEY,
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") == "SUCCESS":
                _session_token = data["token"]
                return _session_token
            logger.error("Betfair login failed: %s", data.get("error"))
            return None
    except Exception as exc:
        logger.error("Betfair login exception: %s", exc)
        return None


async def _get_token() -> Optional[str]:
    global _session_token
    if _session_token:
        return _session_token
    return await _login()


async def _betfair_request(body: list) -> Optional[list]:
    if not settings.BETFAIR_ENABLED:
        logger.warning("Betfair disabled — skipping request")
        return None

    token = await _get_token()
    if not token:
        return None

    headers = {
        "X-Application": settings.BETFAIR_APP_KEY,
        "X-Authentication": token,
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(BETFAIR_API_URL, json=body, headers=headers)
            if resp.status_code == 401:
                global _session_token
                _session_token = None
                token = await _login()
                if not token:
                    return None
                headers["X-Authentication"] = token
                resp = await client.post(BETFAIR_API_URL, json=body, headers=headers)
            resp.raise_for_status()
            results = resp.json()
            if results and "result" in results[0]:
                return results[0]["result"]
            return None
    except Exception as exc:
        logger.error("Betfair API error: %s", exc)
        return None


async def get_lay_price(event_id: str, selection_name: str) -> Optional[float]:
    """Return best LAY price for a selection, or None."""
    if not settings.BETFAIR_ENABLED:
        logger.warning("Betfair disabled — cannot fetch LAY price")
        return None

    snapshot = await get_market_snapshot(event_id)
    if not snapshot:
        return None

    for runner in snapshot:
        if runner["selection_name"].lower() == selection_name.lower():
            return runner.get("lay_price")
    return None


async def get_market_lays(
    event_id: str, selection_name: str
) -> tuple[Optional[float], list[float]]:
    """
    Return (selection's LAY, [other runners' LAYs]) for an event's MATCH_ODDS market.

    The other runners feed power-devigging so odds CLV references a fair line that
    sums to 1 across the market. Returns (None, []) if the snapshot is unavailable.
    """
    if not settings.BETFAIR_ENABLED:
        return None, []

    snapshot = await get_market_snapshot(event_id)
    if not snapshot:
        return None, []

    sel = selection_name.lower()
    own: Optional[float] = None
    others: list[float] = []
    for runner in snapshot:
        price = runner.get("lay_price")
        if price is None:
            continue
        if runner["selection_name"].lower() == sel:
            own = price
        else:
            others.append(price)
    return own, others


async def get_market_snapshot(event_id: str) -> Optional[list[dict]]:
    """Fetch all runners with LAY prices for an event."""
    if not settings.BETFAIR_ENABLED:
        logger.warning("Betfair disabled — cannot fetch market snapshot")
        return None

    body = [
        {
            "jsonrpc": "2.0",
            "method": "SportsAPING/v1.0/listMarketCatalogue",
            "params": {
                "filter": {
                    "marketCountries": ["AU", "GB", "US"],
                    "marketTypeCodes": ["MATCH_ODDS"],
                },
                "marketProjection": ["RUNNER_DESCRIPTION", "EVENT"],
                "maxResults": 200,
            },
            "id": 1,
        }
    ]

    result = await _betfair_request(body)
    if not result:
        return None

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    runners_data = []

    for market in result:
        market_id = market.get("marketId")
        runners = market.get("runners", [])
        if not market_id:
            continue

        prices_body = [
            {
                "jsonrpc": "2.0",
                "method": "SportsAPING/v1.0/listMarketBook",
                "params": {
                    "marketIds": [market_id],
                    "priceProjection": {
                        "priceData": ["EX_BEST_OFFERS"],
                        "exBestOffersOverrides": {"bestPricesDepth": 1},
                    },
                },
                "id": 1,
            }
        ]
        prices_result = await _betfair_request(prices_body)
        if not prices_result:
            continue

        runner_map = {r["selectionId"]: r["runnerName"] for r in runners}
        for mkt in prices_result:
            for runner in mkt.get("runners", []):
                sel_id = runner["selectionId"]
                sel_name = runner_map.get(sel_id, str(sel_id))
                lay_orders = runner.get("ex", {}).get("availableToLay", [])
                if lay_orders:
                    best_lay = lay_orders[0]
                    runners_data.append(
                        {
                            "market_id": market_id,
                            "selection_id": str(sel_id),
                            "selection_name": sel_name,
                            "lay_price": best_lay.get("price"),
                            "size_available": best_lay.get("size"),
                            "snapshot_time": now,
                        }
                    )

    return runners_data if runners_data else None


async def build_betfair_snapshot_records(event_id: str, snapshot: list[dict]) -> list[dict]:
    """Convert market snapshot into betfair_snapshots DB records."""
    records = []
    for runner in snapshot:
        if runner.get("lay_price") is not None:
            records.append(
                {
                    "event_id": event_id,
                    "market_id": runner.get("market_id"),
                    "selection_id": runner.get("selection_id"),
                    "selection_name": runner["selection_name"],
                    "market_type": "h2h",
                    "side": "LAY",
                    "price": runner["lay_price"],
                    "size_available": runner.get("size_available"),
                    "snapshot_time": runner.get(
                        "snapshot_time",
                        datetime.now(timezone.utc).replace(tzinfo=None),
                    ),
                }
            )
    return records
