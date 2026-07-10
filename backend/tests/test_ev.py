import pytest

from backend.services.ev import build_ev_opportunities


def _event(bookmakers):
    return {
        "id": "evt1",
        "sport_key": "rugbyleague_nrl",
        "home_team": "Brisbane Broncos",
        "away_team": "Penrith Panthers",
        "bookmakers": bookmakers,
    }


def _betfair(markets):
    return {"key": "betfair_ex_au", "title": "Betfair", "markets": markets}


def _h2h_lay(home_price, away_price):
    return {
        "key": "h2h_lay",
        "outcomes": [
            {"name": "Brisbane Broncos", "price": home_price},
            {"name": "Penrith Panthers", "price": away_price},
        ],
    }


def test_h2h_ev_vs_betfair_lay():
    # Lay 2.0 / 2.1 → fair probs devig to sum 1, roughly 0.512 / 0.488
    event = _event(
        [
            _betfair([_h2h_lay(2.0, 2.1)]),
            {
                "key": "pointsbetau",
                "title": "PointsBet (AU)",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Brisbane Broncos", "price": 2.10},
                            {"name": "Penrith Panthers", "price": 1.75},
                        ],
                    }
                ],
            },
        ]
    )
    rows = build_ev_opportunities(event)
    assert len(rows) == 2
    home = next(r for r in rows if r["selection"] == "Brisbane Broncos")
    away = next(r for r in rows if r["selection"] == "Penrith Panthers")

    # API key mapped back to the tracker's bookmaker name
    assert home["bookmaker"] == "pointsbet"
    assert home["reference"] == "betfair_lay"
    assert home["side"] == "home"
    # Fair prob > 0.5 at odds 2.10 → positive EV
    assert home["ev_pct"] > 0
    # Away priced 1.75 when fair is ~2.05 → clearly negative EV
    assert away["ev_pct"] < 0
    # Devigged fair probs sum to 1
    assert home["fair_prob"] + away["fair_prob"] == pytest.approx(1.0, abs=1e-6)


def test_crossed_lay_back_book_yields_no_fair():
    # Lay 1.21 below back 1.95 is an impossible (crossed) book — one side is
    # stale and we can't tell which, so no fair line at all.
    event = _event(
        [
            _betfair(
                [
                    _h2h_lay(1.21, 5.0),
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Brisbane Broncos", "price": 1.95},
                            {"name": "Penrith Panthers", "price": 2.05},
                        ],
                    },
                ]
            ),
            {
                "key": "tab",
                "title": "TAB",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [{"name": "Brisbane Broncos", "price": 2.0}],
                    }
                ],
            },
        ]
    )
    rows = build_ev_opportunities(event)
    assert rows[0]["ev_pct"] is None
    assert rows[0]["reference"] is None


def test_junk_thin_book_yields_no_fair():
    # Real data from an NRL market with AUD 685 matched (2026-07-09): the
    # "back" for Souths was a $499 fishing order at 1.02 and the Knights lay
    # side was empty (1000). Devigging either side gave fair 1.08 and a
    # fantasy +84.9% EV. Both sides must fail the overround guard.
    event = _event(
        [
            _betfair(
                [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Brisbane Broncos", "price": 1.02},
                            {"name": "Penrith Panthers", "price": 1.92},
                        ],
                    },
                    {
                        "key": "h2h_lay",
                        "outcomes": [
                            {"name": "Brisbane Broncos", "price": 2.1},
                            {"name": "Penrith Panthers", "price": 1000.0},
                        ],
                    },
                ]
            ),
            {
                "key": "tab",
                "title": "TAB",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [{"name": "Brisbane Broncos", "price": 2.0}],
                    }
                ],
            },
        ]
    )
    rows = build_ev_opportunities(event)
    assert rows[0]["ev_pct"] is None
    assert rows[0]["reference"] is None


def test_back_prices_are_never_the_fair_line():
    # LAY-only policy: with no lay market, Betfair BACK must not become the
    # reference — the row stays unpriced.
    event = _event(
        [
            _betfair(
                [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Brisbane Broncos", "price": 1.95},
                            {"name": "Penrith Panthers", "price": 2.05},
                        ],
                    }
                ]
            ),
            {
                "key": "tab",
                "title": "TAB",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [{"name": "Brisbane Broncos", "price": 2.0}],
                    }
                ],
            },
        ]
    )
    rows = build_ev_opportunities(event)
    assert rows[0]["ev_pct"] is None
    assert rows[0]["reference"] is None


def test_totals_need_lay_at_matching_line():
    event = _event(
        [
            _betfair(
                [
                    # BACK totals alone must not price anything…
                    {
                        "key": "totals",
                        "outcomes": [
                            {"name": "Over", "price": 1.90, "point": 42.5},
                            {"name": "Under", "price": 2.10, "point": 42.5},
                        ],
                    },
                    # …only a LAY totals market does.
                    {
                        "key": "totals_lay",
                        "outcomes": [
                            {"name": "Over", "price": 1.98, "point": 42.5},
                            {"name": "Under", "price": 2.02, "point": 42.5},
                        ],
                    },
                ]
            ),
            {
                "key": "sportsbet",
                "title": "Sportsbet",
                "markets": [
                    {
                        "key": "totals",
                        "outcomes": [
                            {"name": "Over", "price": 2.05, "point": 42.5},
                            {"name": "Under", "price": 1.90, "point": 44.5},
                        ],
                    }
                ],
            },
        ]
    )
    rows = build_ev_opportunities(event)
    over = next(r for r in rows if r["selection"] == "Over")
    under = next(r for r in rows if r["selection"] == "Under")
    assert over["market_type"] == "totals"
    assert over["side"] == "over"
    assert over["ev_pct"] is not None  # lay exists at the same 42.5 line
    assert over["reference"] == "betfair_lay"
    assert under["ev_pct"] is None  # 44.5 ≠ 42.5 — no comparable fair price


def test_totals_back_only_yields_no_fair():
    event = _event(
        [
            _betfair(
                [
                    {
                        "key": "totals",
                        "outcomes": [
                            {"name": "Over", "price": 1.98, "point": 42.5},
                            {"name": "Under", "price": 2.02, "point": 42.5},
                        ],
                    }
                ]
            ),
            {
                "key": "sportsbet",
                "title": "Sportsbet",
                "markets": [
                    {
                        "key": "totals",
                        "outcomes": [
                            {"name": "Over", "price": 2.05, "point": 42.5},
                        ],
                    }
                ],
            },
        ]
    )
    rows = build_ev_opportunities(event)
    assert all(r["ev_pct"] is None for r in rows)


def test_no_betfair_means_no_ev():
    event = _event(
        [
            {
                "key": "neds",
                "title": "Neds",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Brisbane Broncos", "price": 1.9},
                            {"name": "Penrith Panthers", "price": 1.9},
                        ],
                    }
                ],
            }
        ]
    )
    rows = build_ev_opportunities(event)
    assert len(rows) == 2
    assert all(r["ev_pct"] is None and r["reference"] is None for r in rows)


def test_betfair_rows_excluded_and_lay_market_skipped():
    event = _event(
        [
            _betfair(
                [
                    _h2h_lay(2.0, 2.1),
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Brisbane Broncos", "price": 1.95},
                            {"name": "Penrith Panthers", "price": 2.05},
                        ],
                    },
                ]
            )
        ]
    )
    # Betfair is the reference, never a candidate row
    assert build_ev_opportunities(event) == []
