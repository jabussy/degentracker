"""Fuzzy team/fixture matching shared by the bookmaker scrapers.

Scraped sites abbreviate team names differently — bet365 says "GWS GIANTS",
Betfair says "North Qld" — so matching is by normalised token overlap
("north qld" ∩ "north queensland cowboys" → "north"). Ambiguous single
tokens (e.g. "sydney" hits both Sydney Roosters and South Sydney) are
disambiguated by requiring BOTH teams of a fixture to match the same event.
"""
import re
from typing import Optional


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", name.lower()).strip()


# Abbreviations that share no token with the canonical name
TOKEN_ALIASES = {
    "gws": {"greater", "western", "sydney", "giants"},
}


def _tokens(name: str) -> set:
    tokens = {t for t in _norm(name).split() if len(t) >= 3}
    for t in list(tokens):
        tokens |= TOKEN_ALIASES.get(t, set())
    return tokens


def same_team(scraped_name: str, event_team: str) -> bool:
    """Exact normalised match, or any shared name token (≥3 chars)."""
    if not scraped_name or not event_team:
        return False
    if _norm(scraped_name) == _norm(event_team):
        return True
    return bool(_tokens(scraped_name) & _tokens(event_team))


def match_event(home: str, away: str, events: list) -> Optional[object]:
    """
    Match a scraped fixture to a tracked event (objects with
    .home_team/.away_team), either orientation. Exact pairs win over fuzzy.
    """
    h, a = _norm(home), _norm(away)
    for ev in events:
        eh, ea = _norm(ev.home_team or ""), _norm(ev.away_team or "")
        if (h == eh and a == ea) or (h == ea and a == eh):
            return ev
    for ev in events:
        if (same_team(home, ev.home_team) and same_team(away, ev.away_team)) or (
            same_team(home, ev.away_team) and same_team(away, ev.home_team)
        ):
            return ev
    return None
