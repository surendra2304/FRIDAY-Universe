"""
Real Deep Layer 12 Tests — ScrapeCreators/social-media-research-skills → IntelX.

Functional tests for IntelX/app/agents/real_socmint_research.py:
post metrics, robust outlier baselines (median + 1.4826*MAD), hook extraction,
VOC comment mining, transcript intelligence, competitor gaps, ad-library
teardowns, trend momentum, influencer fit tiers, audience fit, social
listening, product demand, creator teardown, repurposing and the
ScrapeCreators endpoint router with credit accounting.
"""

import importlib.util
import os
import sys

import pytest

MODULE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "IntelX", "app", "agents", "real_socmint_research.py")

spec = importlib.util.spec_from_file_location("real_socmint_research", MODULE_PATH)
sc = importlib.util.module_from_spec(spec)
sys.modules["real_socmint_research"] = sc
spec.loader.exec_module(sc)


@pytest.fixture()
def posts():
    return [
        sc.SocialPost(post_id="p1", platform="tiktok", author="acme",
                      caption="Stop scrolling. Here is how I fixed my sleep in 30 days #sleep #health",
                      views=12000, likes=900, comments=80, shares=210, saves=400,
                      duration_s=32.0, followers=45000),
        sc.SocialPost(post_id="p2", author="acme", caption="Day 12 of the experiment",
                      views=3200, likes=120, comments=9, shares=4, saves=30, duration_s=18.0),
        sc.SocialPost(post_id="p3", author="acme", caption="Quick update",
                      views=2800, likes=90, comments=5, shares=2, saves=20, duration_s=21.0),
        sc.SocialPost(post_id="p4", author="acme", caption="Another one from the lab",
                      views=4100, likes=140, comments=11, shares=6, saves=40, duration_s=15.0),
        sc.SocialPost(post_id="p5", author="rival",
                      caption="Why nobody tells you this about magnesium #sleep",
                      views=52000, likes=5200, comments=610, shares=1800, saves=3100,
                      duration_s=44.0, followers=210000),
        sc.SocialPost(post_id="p6", author="rival", caption="Morning routine that works",
                      views=8300, likes=300, comments=20, shares=15, saves=90, duration_s=27.0),
    ]


@pytest.fixture()
def comments():
    return [
        sc.Comment("c1", "ana", "How much does it cost? I cannot justify the price.", likes=45, replies=3),
        sc.Comment("c2", "bob", "This is amazing, saved my mornings!", likes=12),
        sc.Comment("c3", "cara", "I cancelled after two weeks, the app is too slow and keeps crashing.", likes=8),
        sc.Comment("c4", "dan", "Does it work with Android?", likes=5),
    ]


# ── post metrics ─────────────────────────────────────────────────────────────

def test_post_metrics_and_format_bucket(posts):
    p = posts[0]
    assert p.interactions == 900 + 80 + 210 + 400
    assert p.engagement_rate == pytest.approx(1590 / 12000, rel=1e-6)
    assert p.share_rate == pytest.approx(210 / 12000, rel=1e-6)
    assert p.hashtags == ["sleep", "health"]
    assert p.mentions == []
    assert p.format_bucket == "short"
    assert "sleep" in p.caption_without_meta
    assert "#sleep" not in p.caption_without_meta


def test_format_bucket_medium_and_long():
    assert sc.SocialPost(duration_s=0.0).format_bucket == "text"
    assert sc.SocialPost(duration_s=45.0).format_bucket == "short"
    assert sc.SocialPost(duration_s=120.0).format_bucket == "mid"
    assert sc.SocialPost(duration_s=600.0).format_bucket == "long"


# ── robust baseline + outliers ───────────────────────────────────────────────

def test_creator_baseline_robust_statistics(posts):
    baseline = sc.CreatorBaseline(posts=[p for p in posts if p.author == "acme"])
    summary = baseline.summary()
    assert summary["posts"] == 4
    assert summary["median_views"] == pytest.approx(3650.0)
    assert summary["robust_sigma"] == pytest.approx(1.4826 * 650.0, rel=1e-4)
    assert summary["outlier_threshold"] > summary["median_views"]


def test_outlier_detection_flags_only_the_breakout(posts):
    finder = sc.OutlierPostFinder()
    results = finder.find(posts, author="acme")
    flagged = [r.post.post_id for r in results if r.is_outlier]
    assert flagged == ["p1"]
    top = results[0]
    assert top.outlier_factor == pytest.approx(12000 / 3650.0, rel=1e-3)
    assert top.robust_z > 3.0
    assert top.hook_strength > 0.0


def test_outlier_report_patterns_and_hooks(posts):
    report = sc.OutlierPostFinder().report(posts, author="acme")
    assert report["creator"] == "acme"
    assert report["outlier_count"] == 1
    assert report["patterns"], "expected at least one pattern row"
    assert report["hooks_to_steal"]
    first = report["hooks_to_steal"][0]
    assert {"hook_type", "text", "strength", "steal_score"} <= set(first)


# ── hooks ────────────────────────────────────────────────────────────────────

def test_hook_extractor_detects_opening_patterns():
    extractor = sc.HookExtractor(opening_words=14)
    hits = extractor.extract("Stop scrolling. Here is how I fixed my sleep in 30 days")
    kinds = {h.hook_type for h in hits}
    assert "negation" in kinds
    assert "how_to" in kinds
    assert extractor.opening("one two three four").split() == ["one", "two", "three", "four"]
    assert 0.0 <= extractor.score("Stop scrolling. Here is how") <= 1.0


def test_hook_score_is_zero_for_flat_copy():
    assert sc.HookExtractor().score("The meeting is scheduled for Tuesday afternoon.") == 0.0


# ── VOC mining ───────────────────────────────────────────────────────────────

def test_comment_miner_classifies_questions_and_churn(comments):
    miner = sc.CommentMiner()
    assert miner.classify(comments[0]).categories and "question" in miner.classify(comments[0]).categories
    churn = miner.classify(comments[2])
    assert any("churn" in c for c in churn.categories)
    assert miner.sentiment("This is amazing") > 0
    assert miner.sentiment("terrible and broken") < 0


def test_voc_report_has_themes_questions_and_ideas(comments):
    report = sc.CommentMiner().mine(comments)
    assert report.questions
    assert report.churn_risks
    assert report.sentiment_mix
    ideas = sc.CommentMiner().content_ideas(report, limit=4)
    assert len(ideas) <= 4
    assert {"idea", "format", "source", "priority"} <= set(ideas[0])


# ── transcript intelligence ──────────────────────────────────────────────────

def test_transcript_intelligence_atoms_and_stats():
    ti = sc.TranscriptIntelligence()
    assert ti.estimate_duration("word " * 155) == pytest.approx(60.0, rel=1e-3)
    text = ("Stop scrolling. Here is how I fixed my sleep in 30 days. "
            "I slept 42 percent better after week two. "
            "The number that mattered was 7 hours and 40 minutes of consistent sleep. "
            "My doctor said this is the single biggest lever.")
    result = ti.analyze(text, duration_s=30.0)
    assert result.word_count == len(text.split())
    assert result.words_per_minute == pytest.approx(result.word_count / 30.0 * 60.0, rel=1e-6)
    assert result.summary
    assert result.atoms
    assert result.keywords[0][0] == "sleep"
    stats = [a for a in result.stats]
    assert all(a.kind == "stat" for a in stats)


# ── competitor teardown ──────────────────────────────────────────────────────

def test_competitor_teardown_finds_content_gaps(posts):
    teardown = sc.CompetitorTeardown(gap_threshold=0.05)
    teardown.add("acme", posts[:4], followers=45000)
    teardown.add("rival", posts[4:], followers=210000)
    comparison = teardown.compare("acme")
    assert comparison["account"]["name"] == "acme"
    assert [row["competitor"] for row in comparison["competitors"]] == ["rival"]
    assert comparison["gaps"], "expected topical gaps"
    assert comparison["recommendations"]
    for gap in comparison["gaps"]:
        assert gap["gap"] >= 0.05


def test_competitor_profile_metrics(posts):
    profile = sc.CompetitorProfile(name="acme", posts=posts[:4], followers=45000)
    summary = profile.summary()
    assert summary["posts"] == 4
    assert 0.0 < profile.mean_engagement_rate < 1.0
    assert pytest.approx(sum(profile.format_mix().values()), rel=1e-6) == 1.0


# ── ad library ───────────────────────────────────────────────────────────────

def test_ad_library_classification_and_longevity():
    library = sc.AdLibraryTeardown()
    creative = sc.AdCreative(
        creative_id="a1", advertiser="acme",
        headline="Sleep better in 7 days",
        body="Stop scrolling. Our magnesium blend is 40 percent cheaper. Free shipping today only.",
        cta_button="Shop now", first_seen_day=1, last_seen_day=30,
        impressions=250000, spend_estimate=4200.0)
    library.add(creative)
    assert creative.days_active == 30
    assert "urgency" in library.classify_angles(creative)
    assert library.classify_cta(creative) == ["buy_now"]
    assert "free_shipping" in library.classify_offers(creative)
    assert library.longevity_score(creative) > 0.5
    assert 0.0 <= library.hook_strength(creative) <= 1.0


def test_ad_library_teardown_generates_test_ideas():
    library = sc.AdLibraryTeardown()
    creative = sc.AdCreative(creative_id="a1", advertiser="acme", headline="Sleep better",
                             body="Free shipping today only.", cta_button="Shop now",
                             first_seen_day=1, last_seen_day=30)
    library.add(creative)
    report = library.teardown("acme")
    assert report["creatives"] == 1
    assert report["top_creatives"]
    ideas = report["test_ideas"]
    assert ideas
    assert any(idea["type"] == "iteration" for idea in ideas)


# ── trends ───────────────────────────────────────────────────────────────────

def test_trend_discovery_ranks_by_momentum():
    discovery = sc.TrendDiscovery()
    for value in [10, 14, 22, 40, 75, 130, 180, 240, 300]:
        discovery.observe("#sleepmaxxing", float(value))
    for value in [50, 52, 49, 51, 50, 48, 50, 51, 49]:
        discovery.observe("#caffeine", float(value))
    ranked = discovery.rank(5)
    assert ranked[0]["name"] == "#sleepmaxxing"
    assert ranked[0]["momentum"] > ranked[-1]["momentum"]
    assert ranked[0]["phase"] in {"emerging", "accelerating", "peaking", "declining", "flat"}
    assert ranked[-1]["name"] == "#caffeine"
    brief = discovery.brief("sleep supplements", limit=3)
    assert brief["niche"] == "sleep supplements"
    assert brief["trends"] and brief["content_angles"]


def test_trend_signal_ewma_and_velocity():
    signal = sc.TrendSignal(name="x")
    for value in [1.0, 2.0, 3.0, 4.0]:
        signal.observe(value)
    ewma = signal.ewma(0.4)
    assert len(ewma) == 4
    assert ewma[-1] > ewma[0]
    assert signal.velocity() > 0
    assert signal.latest == 4.0


# ── influencer + audience fit ────────────────────────────────────────────────

def test_influencer_scoring_tiers_and_penalties():
    prospects = sc.InfluencerProspecting(target_niche=("sleep", "health"), target_market="US")
    strong = sc.InfluencerProspect("ana", "tiktok", 120000, 95000, 0.062,
                                   ("sleep", "health"), 0.22, 0.95, "US", "ana@x.com")
    weak = sc.InfluencerProspect("zed", "tiktok", 4000, 900, 0.004,
                                 ("crypto",), -0.05, 0.8, "BR", "zed@x.com")
    scored = prospects.score(strong)
    assert scored["tier"] == "A"
    assert scored["fit_score"] > 0.9
    assert scored["market_penalty"] == 0.0
    other = prospects.score(weak)
    assert other["market_penalty"] == pytest.approx(0.08)
    assert other["tier"] == "D"
    ranked = prospects.rank([weak, strong])
    assert [row["handle"] for row in ranked] == ["ana", "zed"]
    assert "ana" in prospects.outreach_notes(scored, strong)
    csv_output = prospects.to_csv([strong, weak])
    assert csv_output.splitlines()[0].startswith("handle,platform,followers")


def test_audience_fit_report():
    research = sc.AudienceResearch(target_country="US", target_interests=("sleep",))
    profile = sc.AudienceProfile("ana", followers=120000, countries={"US": 0.7, "UK": 0.2},
                                 age_brackets={"25-34": 0.4}, interests=("sleep",),
                                 engagement_rate=0.062, follower_growth_30d=0.12,
                                 suspicious_follower_share=0.03)
    report = research.fit_report(profile)
    assert report["handle"] == "ana"
    assert report["verdict"] == "strong_fit"
    assert report["fit_score"] > 0.7
    assert report["parts"]["geo_fit"] == pytest.approx(0.7)
    assert report["confidence"] in {"high", "medium", "low"}


# ── listening, demand, creator teardown, repurposing ─────────────────────────

def test_social_listening_brief():
    mentions = [
        sc.Mention("m1", "reddit", "The price is too high for what you get", "u1", 30),
        sc.Mention("m2", "reddit", "Price is fine, but onboarding is confusing", "u2", 12),
        sc.Mention("m3", "x", "I would pay double for offline mode", "u3", 8),
        sc.Mention("m4", "x", "Support never replied, cancelling", "u4", 4),
    ]
    brief = sc.SocialListeningBrief().build("our product", mentions, theme_limit=5)
    assert brief["platform_mix"]["reddit"] == pytest.approx(0.5)
    assert brief["mentions"] == 4
    assert brief["themes"]


def test_product_demand_signals(comments):
    demand_comments = comments + [
        sc.Comment("c5", "eve", "I wish there was a tool for this, I'd pay double every month.", likes=21),
        sc.Comment("c6", "fay", "I struggle with this every single night, it is a nightmare.", likes=14),
    ]
    signals = sc.ProductDemandResearch().demand_signals(demand_comments)
    assert signals["comments_analyzed"] == 6
    assert signals["explicit_demand_signals"] >= 1
    assert signals["pain_points"] >= 1
    assert signals["verdict"] in {"strong_demand", "moderate_demand", "weak_demand"}
    assert 0.0 <= signals["demand_score"] <= 1.0
    assert signals["exact_language"] or signals["objection_language"]


def test_creator_profile_teardown(posts):
    teardown = sc.CreatorProfileTeardown()
    report = teardown.teardown("acme", posts[:4], followers=45000, bio="sleep science for busy people")
    assert report["handle"] == "acme"
    assert report["posts_analyzed"] == 4
    assert report["content_pillars"]
    assert report["format_mix"]["short"] == pytest.approx(1.0)
    assert "hook" in report["playbook"][0].lower()
    assert "sleep science" in report["positioning"]


def test_content_repurposing_produces_all_assets():
    repurposer = sc.ContentRepurposing()
    text = ("Stop scrolling. Here is how I fixed my sleep in 30 days. "
            "I tracked my sleep for 30 days. The first week was rough. Then it clicked.")
    assets = repurposer.repurpose(text)
    assert set(assets) == {"source", "content_atoms", "x_thread", "linkedin_post",
                           "newsletter_blurb", "short_script"}
    assert assets["x_thread"] and all(len(t) <= 280 for t in assets["x_thread"])
    assert len(assets["linkedin_post"]) <= 3000
    assert len(assets["newsletter_blurb"].split()) <= 120
    assert assets["short_script"]["target_seconds"] >= 0
    assert repurposer.words_for_seconds(60.0) == 155


# ── endpoint router ──────────────────────────────────────────────────────────

def test_router_resolves_endpoint_and_deducts_credits():
    router = sc.ScrapecreatorsRouter(api_key="test-key", credits_per_month=10_000)
    spec_endpoint = router.resolve("tiktok", "transcript")
    assert spec_endpoint is not None
    assert spec_endpoint.credits == 5
    assert router.operations("tiktok") == ["profile", "posts", "hashtag", "comments", "transcript"]
    routed = router.route("tiktok", "transcript", {"url": "https://tiktok.com/@x/video/1"})
    assert routed["ok"] is True
    assert routed["api_key_set"] is True
    assert "transcript" in routed["url"]
    assert router.credits_remaining == 10_000 - 5


def test_router_rejects_missing_parameters():
    router = sc.ScrapecreatorsRouter(api_key="k")
    routed = router.route("tiktok", "transcript", {})
    assert routed["ok"] is False
    assert "url" in routed["error"]
    assert routed["endpoint"]["credits"] == 5
    assert router.credits_remaining == 10_000
    exhausted = sc.ScrapecreatorsRouter(api_key="k", credits_per_month=3)
    assert exhausted.route("tiktok", "transcript", {"url": "x"})["ok"] is False
    assert router.route("myspace", "profile", {})["ok"] is False


def test_router_unknown_platform_returns_none():
    assert sc.ScrapecreatorsRouter().resolve("myspace", "profile") is None


# ── helpers ──────────────────────────────────────────────────────────────────

def test_tokenize_and_top_terms_drop_stopwords():
    assert sc.tokenize("The Quick Brown Fox jumps") == ["quick", "brown", "fox", "jumps"]
    terms = sc.top_terms(["sleep sleep magnesium", "sleep routine"], limit=3)
    assert terms[0][0] == "sleep"
    assert sc.clamp01(1.7) == 1.0 and sc.clamp01(-1.0) == 0.0
    assert sc.safe_div(1.0, 0.0, default=9.0) == 9.0
