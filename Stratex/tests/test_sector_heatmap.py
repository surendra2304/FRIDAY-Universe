"""TASK-IG2-WEB-04 — tests for api/sector_heatmap.py.

Network-free: Stooq responses are fixture strings and the fetcher is
injected, so these tests prove the parsing/aggregation/honesty rules, not
Stooq's uptime.
"""

from api.sector_heatmap import (
    SECTORS,
    aggregate_sector,
    build_heatmap,
    parse_stooq_daily,
    pct_change,
)

CSV_TWO_DAYS = """Date,Open,High,Low,Close,Volume
2026-11-13,100.0,101.0,99.0,100.0,1000
2026-11-16,102.0,103.0,101.0,102.0,1200
"""

CSV_WITH_ND = """Date,Open,High,Low,Close,Volume
2026-11-13,100.0,101.0,99.0,100.0,1000
2026-11-14,N/D,N/D,N/D,N/D,0
2026-11-16,102.0,103.0,101.0,101.0,1200
"""


def test_parse_returns_latest_and_previous_close():
    assert parse_stooq_daily(CSV_TWO_DAYS) == (102.0, 100.0)


def test_parse_skips_no_data_rows():
    assert parse_stooq_daily(CSV_WITH_ND) == (101.0, 100.0)


def test_parse_refuses_single_close():
    one_day = "Date,Open,High,Low,Close,Volume\n2026-11-16,1,1,1,50.0,10\n"
    assert parse_stooq_daily(one_day) is None
    assert parse_stooq_daily("") is None
    assert parse_stooq_daily("not a csv at all") is None


def test_pct_change():
    assert pct_change(102.0, 100.0) == 2.0
    assert pct_change(97.5, 100.0) == -2.5
    assert pct_change(10.0, 0.0) is None


def test_aggregate_ignores_unavailable_members():
    members = [
        {"symbol": "A", "change_pct": 2.0},
        {"symbol": "B", "change_pct": None},
        {"symbol": "C", "change_pct": -1.0},
    ]
    assert aggregate_sector(members) == 0.5


def test_aggregate_all_unavailable_is_none():
    members = [{"symbol": "A", "change_pct": None}]
    assert aggregate_sector(members) is None


def test_build_heatmap_with_injected_fetcher():
    def fake_fetch(stooq_symbol):
        return 1.5 if stooq_symbol != "btcusd" else None

    payload = build_heatmap(fetch=fake_fetch)
    assert payload["source"].startswith("stooq")
    assert len(payload["sectors"]) == len(SECTORS)
    crypto = next(s for s in payload["sectors"] if s["sector"] == "Crypto")
    # BTC unavailable, ETH at +1.5 -> sector change is ETH alone, honestly counted.
    assert crypto["change_pct"] == 1.5
    assert crypto["members_available"] == 1
    assert crypto["members_total"] == 2
    # Sectors with data sort above sectors without.
    assert payload["sectors"][0]["change_pct"] is not None


def test_build_heatmap_all_down():
    payload = build_heatmap(fetch=lambda symbol: None)
    assert all(s["change_pct"] is None for s in payload["sectors"])
    assert all(s["members_available"] == 0 for s in payload["sectors"])
