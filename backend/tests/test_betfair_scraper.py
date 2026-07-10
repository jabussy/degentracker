from backend.services.betfair_scraper import _parse_cell, _parse_matched, parse_coupon_rows
from backend.services.team_match import match_event, same_team
from types import SimpleNamespace


def test_parse_cell():
    assert _parse_cell("3.15 $774") == {"price": 3.15, "size": 774.0}
    assert _parse_cell("1.46 $1,551") == {"price": 1.46, "size": 1551.0}
    assert _parse_cell("") is None
    assert _parse_cell("1.0 $50") is None  # below minimum exchange price
    assert _parse_cell("$774") is None


def test_parse_matched():
    assert _parse_matched("$3,200") == 3200.0
    assert _parse_matched("") == 0.0


def test_parse_coupon_rows_two_way():
    rows = [
        {
            "teamA": "Wests Tigers",
            "teamB": "NZ Warriors",
            "matched": "$3,200",
            "runners": [
                {"back": "3.15 $774", "lay": "3.2 $2230"},
                {"back": "", "lay": ""},  # empty draw column
                {"back": "1.45 $4922", "lay": "1.46 $1551"},
            ],
        },
        {
            "teamA": "A",
            "teamB": "B",
            "matched": "$0",
            "runners": [{"back": "", "lay": ""}, {"back": "", "lay": ""}, {"back": "", "lay": ""}],
        },
    ]
    fixtures = parse_coupon_rows(rows)
    assert len(fixtures) == 1  # priceless fixture dropped
    fx = fixtures[0]
    assert fx["team_a"] == "Wests Tigers"
    assert fx["matched"] == 3200.0
    assert fx["back_a"] == {"price": 3.15, "size": 774.0}
    assert fx["lay_a"] == {"price": 3.2, "size": 2230.0}
    assert fx["back_b"] == {"price": 1.45, "size": 4922.0}
    assert fx["lay_b"] == {"price": 1.46, "size": 1551.0}


def test_betfair_short_names_match_events():
    events = [
        SimpleNamespace(home_team="Wests Tigers", away_team="New Zealand Warriors"),
        SimpleNamespace(home_team="Manly Warriors FAKE", away_team="Foo"),  # decoy
        SimpleNamespace(home_team="Manly Sea Eagles", away_team="North Queensland Cowboys"),
        SimpleNamespace(home_team="South Sydney Rabbitohs", away_team="Newcastle Knights"),
        SimpleNamespace(home_team="Sydney Roosters", away_team="Parramatta Eels"),
    ]
    assert match_event("Wests Tigers", "NZ Warriors", events) is events[0]
    assert match_event("Manly", "North Qld", events) is events[2]
    # "Sydney" alone is ambiguous — the second team disambiguates
    assert match_event("South Sydney", "Newcastle", events) is events[3]
    assert match_event("Sydney", "Parramatta", events) is events[4]
    assert same_team("South Sydney", "South Sydney Rabbitohs")
    assert not same_team("North Qld", "Newcastle Knights")


def test_gws_alias():
    events = [
        SimpleNamespace(home_team="Greater Western Sydney Giants", away_team="Geelong Cats"),
    ]
    assert match_event("GWS", "Geelong", events) is events[0]
    assert same_team("GWS", "Greater Western Sydney Giants")
