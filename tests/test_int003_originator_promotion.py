"""TASK-INT-003 follow-up (the D2 lever): originator promotion in
collect_live_brief (no provider calls).

Root cause (INT-003 D2 investigation, 2026-11-17): the live research
pipeline had no primary-source preference at any stage — candidates were
consumed in search-rank order until 5 fetchable documents filled the
source slots, so D2 (primary-source ratio) scored 0.00 on the acceptance
re-run. The fix is ordering only, the mirror image of PR #322's
news-redirector demotion: within the non-redirector prefix of the pool,
originator-likely candidates (host ends .gov / .gov.<cc> / .edu / .int,
or the registrable domain label matches a query content token) are
stable-sorted ahead of the rest. Same pool, same fetch, same passage
filters, same cap; redirectors can never be promoted. Each source record
carries originator_likely and the result carries primary_source_count /
source_count so future acceptance re-runs score D2 mechanically.
"""
import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

SOURCE = Path(__file__).resolve().parents[1] / "IntelX/intelx/api/live_research_task.py"
spec = importlib.util.spec_from_file_location("live_research_task_int003_d2", SOURCE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

NASA_PROSE = b"NASA Artemis mission preparations continue at the Kennedy Space Center this year."
LONGEVITY_PROSE = b"Longevity science findings from the institute describe the cohort and measured outcomes."
CROWDSTRIKE_PROSE = b"CrowdStrike incident findings describe the update failure and affected hosts in detail."
ITER_PROSE = b"ITER fusion assembly progress continues with the tokamak components arriving on site."
BATTERY_PROSE = b"Battery storage update describes cell chemistry results and cycle life measurements."
GOOGLE_PROSE = b"Google summarization update describes the model changes and evaluation results."


def _run(query, urls, prose, max_sources=5):
    search = SimpleNamespace(fetch=AsyncMock(
        return_value=[SimpleNamespace(title="Fixture", url=u) for u in urls]))
    attempted = []

    async def fetch_side(url, max_bytes=1_000_000):
        attempted.append(url)
        return SimpleNamespace(status_code=200, content_type="text/plain",
                               final_url=url, content=prose)

    fetch = SimpleNamespace(fetch=AsyncMock(side_effect=fetch_side))
    result = asyncio.run(m.collect_live_brief(query, search, fetch, max_sources=max_sources))
    return result, attempted


def test_gov_originator_at_pool_tail_is_fetched_first():
    # The originator sits at pool rank 20 behind nineteen news/blog hosts;
    # without promotion it is tried last (INT-003 baseline: nasa.gov never
    # reached a slot). With promotion it is attempted first.
    fillers = [f"https://site{i}.example.com/doc" for i in range(19)]
    nasa = "https://www.nasa.gov/artemis"
    result, attempted = _run(
        "What is the status of NASA Artemis II mission preparations?",
        fillers + [nasa], NASA_PROSE)
    assert attempted[0] == nasa
    assert result["sources"][0]["url"] == nasa
    assert result["sources"][0]["originator_likely"] is True


def test_edu_int_and_gov_cc_hosts_are_promoted_stably():
    news_a = "https://dailynews.com/story"
    news_b = "https://techblog.io/post"
    edu = "https://news.usc.edu/study"
    intl = "https://www.who.int/report"
    gov_cc = "https://www.mod.gov.uk/release"
    news_c = "https://wirepost.com/item"
    result, attempted = _run(
        "latest findings on longevity science studies",
        [news_a, news_b, edu, intl, gov_cc, news_c], LONGEVITY_PROSE, max_sources=6)
    # Promoted hosts keep their pool-relative order (stable sort), and the
    # non-promoted hosts keep theirs.
    assert attempted == [edu, intl, gov_cc, news_a, news_b, news_c]
    assert [s["originator_likely"] for s in result["sources"]] == [True, True, True, False, False, False]


def test_query_token_match_promotes_com_originator():
    news = "https://dailynews.com/story"
    originator = "https://www.crowdstrike.com/incident"
    result, attempted = _run(
        "What did CrowdStrike publish about the incident?",
        [news, originator], CROWDSTRIKE_PROSE, max_sources=2)
    assert attempted[0] == originator
    assert result["sources"][0]["originator_likely"] is True


def test_query_token_match_promotes_org_originator():
    blog = "https://fusionblog.com/post"
    originator = "https://www.iter.org/assembly"
    result, attempted = _run(
        "ITER fusion reactor assembly progress",
        [blog, originator], ITER_PROSE, max_sources=2)
    assert attempted[0] == originator
    assert result["sources"][0]["originator_likely"] is True


def test_no_query_token_match_means_no_promotion():
    # crowdstrike.com is originator-likely only for a query that names it;
    # an unrelated query must leave pool order and labels untouched.
    originator_shaped = "https://www.crowdstrike.com/incident"
    blog = "https://batteryjournal.com/post"
    result, attempted = _run(
        "battery storage research update",
        [originator_shaped, blog], BATTERY_PROSE, max_sources=2)
    assert attempted == [originator_shaped, blog]
    assert result["sources"][0]["originator_likely"] is False


def test_redirector_is_never_promoted_even_on_token_match():
    # The query names Google, so the redirector's registrable label
    # ("google") matches a query token — but news.google.com is a
    # redirector, and redirectors stay last-resort (PR #322).
    article = "https://example.org/doc"
    redirector = "https://news.google.com/rss/articles/FIXTURE"
    result, attempted = _run(
        "Google summarization research update",
        [redirector, article], GOOGLE_PROSE, max_sources=1)
    assert attempted == [article]
    assert result["sources"][0]["url"] == article


def test_non_originator_pool_order_is_preserved_exactly():
    pool = ["https://example.com/a", "https://news-site.org/b",
            "https://blog.example.net/c", "https://wire.com/d"]
    result, attempted = _run("battery storage research update", pool, BATTERY_PROSE, max_sources=4)
    assert attempted == pool
    assert [s["originator_likely"] for s in result["sources"]] == [False, False, False, False]


def test_cap_still_respected_with_promotion():
    news_a = "https://dailynews.com/story"
    gov = "https://www.nih.gov/study"
    news_b = "https://techblog.io/post"
    edu = "https://news.usc.edu/study"
    news_c = "https://wirepost.com/item"
    result, attempted = _run(
        "latest findings on longevity science studies",
        [news_a, gov, news_b, edu, news_c], LONGEVITY_PROSE, max_sources=2)
    # Promotion reorders the attempts; the cap still stops the loop after
    # two accepted sources — the two promoted originators.
    assert attempted == [gov, edu]
    assert len(result["sources"]) == 2
    assert result["primary_source_count"] == 2
    assert result["source_count"] == 2


def test_result_records_primary_and_source_counts():
    news_a = "https://dailynews.com/story"
    nasa = "https://www.nasa.gov/artemis"
    news_b = "https://techblog.io/post"
    result, attempted = _run(
        "What is the status of NASA Artemis II mission preparations?",
        [news_a, nasa, news_b], NASA_PROSE, max_sources=3)
    assert [s["url"] for s in result["sources"]] == [nasa, news_a, news_b]
    assert [s["originator_likely"] for s in result["sources"]] == [True, False, False]
    assert result["source_count"] == 3
    assert result["primary_source_count"] == 1
