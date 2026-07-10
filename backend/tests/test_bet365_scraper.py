from types import SimpleNamespace

from backend.services.bet365_scraper import (
    _pair_fixtures_with_odds,
    match_event,
    same_team,
)


def _ev(home, away):
    return SimpleNamespace(home_team=home, away_team=away)


def test_match_event_exact():
    events = [
        _ev("Brisbane Broncos", "Penrith Panthers"),
        _ev("Sydney Roosters", "Melbourne Storm"),
    ]
    assert match_event("Brisbane Broncos", "Penrith Panthers", events) is events[0]
    # Reversed order (bet365 coupon order isn't home-first)
    assert match_event("Penrith Panthers", "Brisbane Broncos", events) is events[0]


def test_match_event_nickname_fallback():
    events = [_ev("Brisbane Broncos", "Penrith Panthers")]
    assert match_event("Broncos", "Panthers", events) is events[0]
    assert match_event("Bris Broncos", "Pen Panthers", events) is events[0]


def test_match_event_requires_both_teams():
    events = [_ev("Brisbane Broncos", "Penrith Panthers")]
    assert match_event("Broncos", "Storm", events) is None
    assert match_event("", "", events) is None


def test_same_team():
    assert same_team("Brisbane Broncos", "Brisbane Broncos")
    assert same_team("Broncos", "Brisbane Broncos")
    assert not same_team("Broncos", "Penrith Panthers")
    assert not same_team("", "Brisbane Broncos")


def _fx(team_a, team_b, top, bottom):
    return {"teamA": team_a, "teamB": team_b, "top": top, "bottom": bottom}


def _cell(v, x, y):
    return {"v": v, "x": x, "y": y}


def test_pair_fixtures_by_geometry():
    fixtures = [_fx("A", "B", 0, 40), _fx("C", "D", 50, 90)]
    odds = [
        _cell(1.80, 300, 10), _cell(2.00, 300, 30),  # fixture 1 h2h column
        _cell(1.50, 300, 60), _cell(2.60, 300, 80),  # fixture 2 h2h column
    ]
    rows = _pair_fixtures_with_odds(fixtures, odds)
    assert rows == [
        {"team_a": "A", "team_b": "B", "odds_a": 1.80, "odds_b": 2.00},
        {"team_a": "C", "team_b": "D", "odds_a": 1.50, "odds_b": 2.60},
    ]


def test_pair_fixtures_picks_leftmost_two_cell_column():
    fixtures = [_fx("A", "B", 0, 40)]
    odds = [
        _cell(1.80, 300, 10), _cell(2.00, 300, 30),  # h2h (leftmost)
        _cell(1.90, 400, 10), _cell(1.90, 400, 30),  # a later market column
        _cell(42.5, 500, 20),  # lone cell (e.g. total line) — not a pair
    ]
    rows = _pair_fixtures_with_odds(fixtures, odds)
    assert rows == [{"team_a": "A", "team_b": "B", "odds_a": 1.80, "odds_b": 2.00}]


def test_pair_fixtures_skips_rows_without_clean_pair():
    fixtures = [_fx("A", "B", 0, 40)]
    # only one aligned cell — suspended market or layout drift
    assert _pair_fixtures_with_odds(fixtures, [_cell(1.8, 300, 10)]) == []


def test_pair_fixtures_skips_junk_odds():
    fixtures = [_fx("A", "B", 0, 40)]
    odds = [_cell(1.0, 300, 10), _cell(2.0, 300, 30)]
    assert _pair_fixtures_with_odds(fixtures, odds) == []  # 1.0 isn't a price
