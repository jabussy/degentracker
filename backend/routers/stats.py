from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from collections import defaultdict
from typing import Optional

from backend.db.session import get_db
from backend.db import queries

router = APIRouter(prefix="/api/stats", tags=["stats"])


def _calc_pnl(bet) -> Optional[float]:
    if bet.status == "won":
        return round((bet.odds_taken - 1) * bet.stake, 2)
    elif bet.status == "lost":
        return round(-bet.stake, 2)
    elif bet.status == "void":
        return 0.0
    return None


def _build_summary(bets: list) -> dict:
    settled = [b for b in bets if b.status in ("won", "lost", "void")]
    total_staked = sum(b.stake for b in settled)
    net_pnl = sum((_calc_pnl(b) or 0.0) for b in settled)
    roi = (net_pnl / total_staked * 100) if total_staked else 0.0

    clv_eligible = [
        b for b in settled
        if b.closing_line and b.closing_line.beat_closing_odds is not None
    ]
    odds_clv_win_rate = (
        sum(1 for b in clv_eligible if b.closing_line.beat_closing_odds) / len(clv_eligible) * 100
        if clv_eligible else None
    )

    line_clv_eligible = [
        b for b in settled
        if b.closing_line
        and b.closing_line.beat_closing_line is not None
        and b.market_type in ("handicap", "totals")
    ]
    line_clv_win_rate = (
        sum(1 for b in line_clv_eligible if b.closing_line.beat_closing_line)
        / len(line_clv_eligible) * 100
        if line_clv_eligible else None
    )

    avg_odds_clv = (
        sum(b.closing_line.odds_clv_pct for b in clv_eligible if b.closing_line.odds_clv_pct is not None)
        / len(clv_eligible) * 100
        if clv_eligible else None
    )
    avg_line_clv = (
        sum(b.closing_line.line_clv_pts for b in line_clv_eligible if b.closing_line.line_clv_pts is not None)
        / len(line_clv_eligible)
        if line_clv_eligible else None
    )

    return {
        "total_staked": round(total_staked, 2),
        "net_pnl": round(net_pnl, 2),
        "roi_pct": round(roi, 2),
        "settled_count": len(settled),
        "open_count": sum(1 for b in bets if b.status == "open"),
        "total_exposure": round(sum(b.stake for b in bets if b.status == "open"), 2),
        "odds_clv_win_rate_pct": round(odds_clv_win_rate, 2) if odds_clv_win_rate is not None else None,
        "line_clv_win_rate_pct": round(line_clv_win_rate, 2) if line_clv_win_rate is not None else None,
        "avg_odds_clv_pct": round(avg_odds_clv, 2) if avg_odds_clv is not None else None,
        "avg_line_clv_pts": round(avg_line_clv, 2) if avg_line_clv is not None else None,
    }


@router.get("/summary")
async def get_summary(db: AsyncSession = Depends(get_db)):
    all_bets = await queries.list_bets(db)
    return _build_summary(all_bets)


@router.get("/breakdown")
async def get_breakdown(
    group_by: str = Query("sport", pattern="^(sport|bookmaker|market_type)$"),
    db: AsyncSession = Depends(get_db),
):
    all_bets = await queries.list_bets(db)
    groups: dict[str, list] = defaultdict(list)
    for bet in all_bets:
        if group_by == "sport":
            key = bet.sport_key
        elif group_by == "bookmaker":
            key = bet.bookmaker
        else:
            key = bet.market_type
        groups[key].append(bet)

    return {
        "group_by": group_by,
        "breakdown": {key: _build_summary(bets) for key, bets in sorted(groups.items())},
    }
