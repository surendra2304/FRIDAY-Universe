"""
IntelX Deep Layer 12 — Real SOCMINT / Social Media Research Engine

Real repository integration:
    ScrapeCreators/social-media-research-skills
    Upstream: https://github.com/ScrapeCreators/social-media-research-skills

The upstream project ships 13 agent skills for turning public social data into
business artifacts. Those skills are prompt/workflow documents; this module
implements the *computation* behind them so the IntelX agent can run them
offline and deterministically:

    outlier-post-finder       -> OutlierPostFinder      (robust z / MAD baselines)
    transcript-intelligence   -> TranscriptIntelligence (atoms, hooks, claims, quotes)
    comment-mining            -> CommentMiner           (VOC taxonomy, themes, ideas)
    competitor-social-research-> CompetitorTeardown     (pillars, cadence, gaps)
    ad-library-teardown       -> AdLibraryTeardown      (angles, CTAs, offers, longevity)
    trend-discovery           -> TrendDiscovery         (EWMA velocity + acceleration)
    influencer-prospecting    -> InfluencerProspecting  (weighted fit score, tiers, CSV)
    audience-research         -> AudienceResearch       (fit report, confidence labels)
    social-listening-brief    -> SocialListeningBrief   (themes, sentiment, caveats)
    product-demand-research   -> ProductDemandResearch  (demand signals, objections)
    creator-profile-teardown  -> CreatorProfileTeardown (positioning + playbook)
    content-repurposing       -> ContentRepurposing     (LinkedIn / X / scripts / news)
    scrapecreators-api        -> ScrapecreatorsRouter   (endpoint routing + credits)

All statistics are stdlib-only (statistics, math, collections) so every number in
the tests is reproducible without network access. Real ScrapeCreators HTTP calls
are represented by :class:`ScrapecreatorsRouter`, which builds the exact request
spec; transport is injected so tests stay offline.
"""

from __future__ import annotations

import csv
import io
import math
import re
import statistics
import urllib.parse
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

# ─────────────────────────────────────────────────────────────────────────────
# Platform registry
# ─────────────────────────────────────────────────────────────────────────────

PLATFORMS: dict[str, dict[str, Any]] = {
    "tiktok": {"short_form": True, "max_caption": 2200, "dominant_length_s": 34.0, "weight_views": 1.00},
    "instagram": {"short_form": True, "max_caption": 2200, "dominant_length_s": 40.0, "weight_views": 0.90},
    "youtube": {"short_form": False, "max_caption": 5000, "dominant_length_s": 480.0, "weight_views": 1.00},
    "youtube_shorts": {"short_form": True, "max_caption": 5000, "dominant_length_s": 45.0, "weight_views": 1.00},
    "x": {"short_form": True, "max_caption": 280, "dominant_length_s": 0.0, "weight_views": 0.70},
    "reddit": {"short_form": False, "max_caption": 40000, "dominant_length_s": 0.0, "weight_views": 0.80},
    "linkedin": {"short_form": False, "max_caption": 3000, "dominant_length_s": 0.0, "weight_views": 0.60},
    "facebook": {"short_form": False, "max_caption": 63206, "dominant_length_s": 90.0, "weight_views": 0.85},
    "threads": {"short_form": True, "max_caption": 500, "dominant_length_s": 0.0, "weight_views": 0.65},
    "bluesky": {"short_form": True, "max_caption": 300, "dominant_length_s": 0.0, "weight_views": 0.60},
    "pinterest": {"short_form": False, "max_caption": 800, "dominant_length_s": 0.0, "weight_views": 0.55},
    "rumble": {"short_form": False, "max_caption": 5000, "dominant_length_s": 600.0, "weight_views": 0.75},
}

_STOPWORDS = frozenset(
    """a an and the or but if then than that this these those of to in on for with at by from as is are was were be been
    being do does did doing have has had having i you he she it we they me him her them my your his its our their not no
    so very just really about into over under again more most other some such only own same too can will would should
    could may might must here there when where why how what which who whom while after before because until during
    get got make made take takes use used using want wants need needs know knows think thinks say says said like likes
    one two three new also way ways things thing people time times year years day days""".split()
)

_WORD_RE = re.compile(r"[a-z0-9][a-z0-9'\-]+")
_HASHTAG_RE = re.compile(r"#([a-z0-9_]+)", re.IGNORECASE)
_URL_RE = re.compile(r"https?://\S+")
_MENTION_RE = re.compile(r"@([a-z0-9_.]+)", re.IGNORECASE)


def tokenize(text: str) -> list[str]:
    """Lowercase word tokens with stopwords removed."""
    return [t for t in _WORD_RE.findall((text or "").lower()) if t not in _STOPWORDS and len(t) > 2]


def top_terms(texts: Iterable[str], limit: int = 12) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for text in texts:
        counter.update(tokenize(text))
    return counter.most_common(limit)


def safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    return numerator / denominator if denominator else default


def clamp01(value: float) -> float:
    return 0.0 if value < 0.0 else (1.0 if value > 1.0 else value)


# ─────────────────────────────────────────────────────────────────────────────
# Core data model
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class SocialPost:
    """A single public social post/reel/short/tweet."""

    post_id: str = ""
    platform: str = "tiktok"
    author: str = ""
    caption: str = ""
    published_hour: int = 0
    views: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    saves: int = 0
    duration_s: float = 0.0
    followers: int = 0

    @property
    def interactions(self) -> int:
        return self.likes + self.comments + self.shares + self.saves

    @property
    def engagement_rate(self) -> float:
        """Interactions per view. Falls back to per-follower reach when views are hidden."""
        denom = self.views if self.views else self.followers
        return safe_div(self.interactions, denom)

    @property
    def share_rate(self) -> float:
        return safe_div(self.shares, self.views)

    @property
    def comment_rate(self) -> float:
        return safe_div(self.comments, self.views)

    @property
    def hashtags(self) -> list[str]:
        return [h.lower() for h in _HASHTAG_RE.findall(self.caption)]

    @property
    def mentions(self) -> list[str]:
        return [m.lower() for m in _MENTION_RE.findall(self.caption)]

    @property
    def caption_without_meta(self) -> str:
        text = _URL_RE.sub(" ", self.caption)
        text = _HASHTAG_RE.sub(" ", text)
        return re.sub(r"\s+", " ", text).strip()

    @property
    def format_bucket(self) -> str:
        if self.duration_s <= 0:
            return "text"
        if self.duration_s <= 45:
            return "short"
        if self.duration_s <= 300:
            return "mid"
        return "long"

    def to_dict(self) -> dict[str, Any]:
        return {
            "post_id": self.post_id,
            "platform": self.platform,
            "author": self.author,
            "published_hour": self.published_hour,
            "views": self.views,
            "likes": self.likes,
            "comments": self.comments,
            "shares": self.shares,
            "saves": self.saves,
            "duration_s": round(self.duration_s, 2),
            "followers": self.followers,
            "engagement_rate": round(self.engagement_rate, 6),
            "format_bucket": self.format_bucket,
            "hashtags": self.hashtags,
        }


@dataclass
class CreatorBaseline:
    """Robust performance baseline for one creator (median + MAD, not mean/std)."""

    posts: list[SocialPost] = field(default_factory=list)

    @property
    def view_series(self) -> list[int]:
        return [p.views for p in self.posts if p.views > 0]

    @property
    def median_views(self) -> float:
        series = self.view_series
        return float(statistics.median(series)) if series else 0.0

    @property
    def mad(self) -> float:
        """Median absolute deviation."""
        series = self.view_series
        if len(series) < 2:
            return 0.0
        med = statistics.median(series)
        return float(statistics.median([abs(v - med) for v in series]))

    @property
    def mean_views(self) -> float:
        series = self.view_series
        return safe_div(sum(series), len(series))

    @property
    def p75_views(self) -> float:
        series = sorted(self.view_series)
        if not series:
            return 0.0
        idx = min(len(series) - 1, int(round(0.75 * (len(series) - 1))))
        return float(series[idx])

    def robust_sigma(self) -> float:
        """Consistent sigma estimate from MAD (1.4826 * MAD), floored at 1.0."""
        return max(1.0, 1.4826 * self.mad)

    def robust_z(self, views: float) -> float:
        return (views - self.median_views) / self.robust_sigma()

    def outlier_threshold(self, min_factor: float = 3.0, min_z: float = 2.5) -> float:
        """Views needed to be an outlier: the looser of the ratio and z rules."""
        return max(self.median_views * min_factor, self.median_views + min_z * self.robust_sigma())

    def summary(self) -> dict[str, Any]:
        return {
            "posts": len(self.posts),
            "median_views": round(self.median_views, 2),
            "mean_views": round(self.mean_views, 2),
            "p75_views": round(self.p75_views, 2),
            "mad": round(self.mad, 2),
            "robust_sigma": round(self.robust_sigma(), 2),
            "outlier_threshold": round(self.outlier_threshold(), 2),
        }


# ─────────────────────────────────────────────────────────────────────────────
# skill: outlier-post-finder
# ─────────────────────────────────────────────────────────────────────────────

HOOK_PATTERNS: list[tuple[str, str, float]] = [
    ("curiosity_gap", r"\b(the (?:secret|truth|reason|real reason)|nobody (?:talks|tells)|what no one)\b", 1.0),
    ("contrarian", r"\b(i was wrong|everyone thinks|stop (?:doing|believing)|unpopular opinion|myth)\b", 0.95),
    ("negation", r"\b(never|don'?t|stop|avoid|worst|wrong|mistake|fail(?:ed|ure)?)\b", 0.80),
    ("number_list", r"\b(\d+\s+(?:ways|things|reasons|steps|mistakes|tips|rules))\b", 0.85),
    ("question", r"^[^.!?]{3,}\?", 0.70),
    ("stakes", r"\b(cost me|lost|saved me|\$\d|million|billion|years? of)\b", 0.75),
    ("how_to", r"\b(how (?:to|i)|here'?s how|step by step|tutorial)\b", 0.65),
    ("identity", r"\b(if you'?re|for (?:founders|creators|agencies|beginners)|as a)\b", 0.60),
    ("urgency", r"\b(before (?:you|it)|right now|today only|in \d+ (?:days|minutes|hours))\b", 0.60),
    ("proof", r"\b(study|studies|research|data|case study|proof|tested|results?)\b", 0.55),
]


@dataclass
class HookHit:
    """A detected hook with the exact text that triggered it."""

    hook_type: str
    text: str
    strength: float

    def to_dict(self) -> dict[str, Any]:
        return {"hook_type": self.hook_type, "text": self.text, "strength": round(self.strength, 3)}


class HookExtractor:
    """Detect hook patterns in the first spoken/written seconds of a post."""

    def __init__(self, opening_words: int = 14):
        self.opening_words = opening_words

    def opening(self, text: str) -> str:
        words = (text or "").split()
        return " ".join(words[: self.opening_words])

    def extract(self, text: str) -> list[HookHit]:
        opening = self.opening(text)
        lowered = opening.lower()
        hits: list[HookHit] = []
        for name, pattern, weight in HOOK_PATTERNS:
            match = re.search(pattern, lowered)
            if match:
                hits.append(HookHit(name, opening[max(0, match.start() - 12) : match.end() + 24].strip(), weight))
        # whole-text fallback: hooks sometimes land after the opener
        if not hits:
            full = (text or "").lower()
            for name, pattern, weight in HOOK_PATTERNS:
                match = re.search(pattern, full)
                if match:
                    hits.append(HookHit(name, (text or "")[match.start() : match.end() + 24].strip(), weight * 0.6))
                    break
        hits.sort(key=lambda h: h.strength, reverse=True)
        return hits

    def score(self, text: str) -> float:
        hits = self.extract(text)
        if not hits:
            return 0.0
        total = sum(h.strength for h in hits)
        return clamp01(total / 2.2)


@dataclass
class OutlierResult:
    post: SocialPost
    baseline_median: float
    outlier_factor: float
    robust_z: float
    hooks: list[HookHit] = field(default_factory=list)

    @property
    def is_outlier(self) -> bool:
        return self.outlier_factor >= 3.0 or self.robust_z >= 2.5

    @property
    def hook_strength(self) -> float:
        return clamp01(sum(h.strength for h in self.hooks) / 2.2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "post_id": self.post.post_id,
            "platform": self.post.platform,
            "author": self.post.author,
            "views": self.post.views,
            "baseline_median": round(self.baseline_median, 2),
            "outlier_factor": round(self.outlier_factor, 3),
            "robust_z": round(self.robust_z, 3),
            "hook_types": [h.hook_type for h in self.hooks],
            "hook_strength": round(self.hook_strength, 3),
            "engagement_rate": round(self.post.engagement_rate, 6),
            "duration_s": round(self.post.duration_s, 2),
            "caption": self.post.caption[:120],
        }


class OutlierPostFinder:
    """skill: outlier-post-finder — posts that beat a creator's own baseline."""

    def __init__(self, min_views: int = 1_000, min_factor: float = 3.0, min_z: float = 2.5):
        self.min_views = min_views
        self.min_factor = min_factor
        self.min_z = min_z
        self.hooks = HookExtractor()

    def baseline(self, posts: list[SocialPost], author: str | None = None) -> CreatorBaseline:
        subset = [p for p in posts if author is None or p.author == author]
        return CreatorBaseline(posts=subset)

    def find(self, posts: list[SocialPost], author: str | None = None) -> list[OutlierResult]:
        base = self.baseline(posts, author)
        median = base.median_views
        results: list[OutlierResult] = []
        for post in base.posts:
            if post.views < self.min_views:
                continue
            factor = safe_div(post.views, median)
            z = base.robust_z(post.views)
            if factor < self.min_factor and z < self.min_z:
                continue
            results.append(
                OutlierResult(
                    post=post,
                    baseline_median=median,
                    outlier_factor=factor,
                    robust_z=z,
                    hooks=self.hooks.extract(post.caption_without_meta),
                )
            )
        results.sort(key=lambda r: r.outlier_factor, reverse=True)
        return results

    def patterns(self, results: list[OutlierResult]) -> list[dict[str, Any]]:
        """Repeatable patterns across outliers: format, length band, hashtag count, hook type."""
        if not results:
            return []
        buckets: dict[tuple[str, str], list[OutlierResult]] = defaultdict(list)
        for r in results:
            buckets[(r.post.format_bucket, r.hooks[0].hook_type if r.hooks else "none")].append(r)
        patterns = []
        for (fmt, hook), group in buckets.items():
            durations = [r.post.duration_s for r in group if r.post.duration_s > 0]
            patterns.append(
                {
                    "format": fmt,
                    "dominant_hook": hook,
                    "occurrences": len(group),
                    "share_of_outliers": round(safe_div(len(group), len(results)), 3),
                    "median_duration_s": round(statistics.median(durations), 2) if durations else 0.0,
                    "median_factor": round(statistics.median([r.outlier_factor for r in group]), 3),
                    "median_hashtags": round(statistics.median([len(r.post.hashtags) for r in group]), 2),
                }
            )
        patterns.sort(key=lambda p: (p["occurrences"], p["median_factor"]), reverse=True)
        return patterns

    def hooks_to_steal(self, results: list[OutlierResult], limit: int = 5) -> list[dict[str, Any]]:
        scored: list[dict[str, Any]] = []
        for r in results:
            for hook in r.hooks:
                scored.append(
                    {
                        "hook_type": hook.hook_type,
                        "text": hook.text,
                        "strength": round(hook.strength, 3),
                        "views": r.post.views,
                        "outlier_factor": round(r.outlier_factor, 2),
                        "steal_score": round(hook.strength * math.log1p(r.outlier_factor), 4),
                    }
                )
        scored.sort(key=lambda h: h["steal_score"], reverse=True)
        return scored[:limit]

    def report(self, posts: list[SocialPost], author: str | None = None) -> dict[str, Any]:
        base = self.baseline(posts, author)
        results = self.find(posts, author)
        return {
            "creator": author or "(all)",
            "baseline": base.summary(),
            "outlier_count": len(results),
            "outliers": [r.to_dict() for r in results],
            "patterns": self.patterns(results),
            "hooks_to_steal": self.hooks_to_steal(results),
        }


# ─────────────────────────────────────────────────────────────────────────────
# skill: comment-mining
# ─────────────────────────────────────────────────────────────────────────────

_POSITIVE = frozenset(
    "love great amazing awesome thanks thank helpful useful brilliant perfect works insane crazy good best clear".split()
)
_NEGATIVE = frozenset(
    "hate bad awful broken useless trash worst annoying confusing wrong scam expensive slow buggy disappointing failed".split()
)
_QUESTION_CUES = ("?", "how do i", "how to", "what about", "does it", "can you", "anyone know", "which one")
_OBJECTION_CUES = ("but", "however", "too expensive", "doesn't work", "does not work", "not worth", "no way", "problem is")
_PAIN_CUES = ("struggle", "struggling", "frustrated", "frustrating", "waste", "wasted", "hours every", "can't", "cant", "impossible", "nightmare")
_DEMAND_CUES = ("wish there was", "i'd pay", "would pay", "need a tool", "please make", "shut up and take my money", "is there a", "any tool")
_CHURN_CUES = ("cancelled", "canceled", "cancel my", "switching to", "switch to", "refund", "unsubscribed")


@dataclass
class Comment:
    comment_id: str = ""
    author: str = ""
    text: str = ""
    likes: int = 0
    replies: int = 0
    is_author: bool = False

    @property
    def weight(self) -> float:
        """Engagement weight used when ranking quotes and themes."""
        return 1.0 + math.log1p(self.likes) + 0.5 * math.log1p(self.replies)


@dataclass
class CommentClassification:
    comment: Comment
    categories: list[str]
    sentiment: float
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "comment_id": self.comment.comment_id,
            "text": self.comment.text[:160],
            "categories": self.categories,
            "sentiment": round(self.sentiment, 3),
            "confidence": round(self.confidence, 3),
            "likes": self.comment.likes,
        }


@dataclass
class VOCReport:
    themes: list[tuple[str, float]]
    category_counts: dict[str, int]
    questions: list[dict[str, Any]]
    objections: list[dict[str, Any]]
    pain_points: list[dict[str, Any]]
    product_ideas: list[dict[str, Any]]
    churn_risks: list[dict[str, Any]]
    quotes: list[dict[str, Any]]
    sentiment_mix: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "themes": [{"term": t, "weight": round(w, 3)} for t, w in self.themes],
            "category_counts": self.category_counts,
            "questions": self.questions,
            "objections": self.objections,
            "pain_points": self.pain_points,
            "product_ideas": self.product_ideas,
            "churn_risks": self.churn_risks,
            "quotes": self.quotes,
            "sentiment_mix": {k: round(v, 4) for k, v in self.sentiment_mix.items()},
        }


class CommentMiner:
    """skill: comment-mining — voice-of-customer extraction from comments."""

    def __init__(self, top_terms_limit: int = 15, quote_limit: int = 8):
        self.top_terms_limit = top_terms_limit
        self.quote_limit = quote_limit

    def sentiment(self, text: str) -> float:
        tokens = [t.lower() for t in _WORD_RE.findall(text or "")]
        if not tokens:
            return 0.0
        pos = sum(1 for t in tokens if t in _POSITIVE)
        neg = sum(1 for t in tokens if t in _NEGATIVE)
        return max(-1.0, min(1.0, safe_div(pos - neg, max(1.0, math.sqrt(len(tokens))))))

    def classify(self, comment: Comment) -> CommentClassification:
        text = (comment.text or "").lower()
        cats: list[str] = []
        if any(cue in text for cue in _QUESTION_CUES):
            cats.append("question")
        if any(cue in text for cue in _OBJECTION_CUES):
            cats.append("objection")
        if any(cue in text for cue in _PAIN_CUES):
            cats.append("pain_point")
        if any(cue in text for cue in _DEMAND_CUES):
            cats.append("product_idea")
        if any(cue in text for cue in _CHURN_CUES):
            cats.append("churn_risk")
        sent = self.sentiment(comment.text)
        if sent > 0.25:
            cats.append("praise")
        elif sent < -0.25:
            cats.append("complaint")
        if not cats:
            cats.append("other")
        hits = len([c for c in cats if c not in ("praise", "complaint", "other")])
        confidence = clamp01(0.35 + 0.3 * hits + min(0.25, math.log1p(comment.likes) * 0.08))
        return CommentClassification(comment, cats, sent, confidence)

    def mine(self, comments: list[Comment]) -> VOCReport:
        classifications = [self.classify(c) for c in comments]
        counts: Counter[str] = Counter()
        for c in classifications:
            for cat in c.categories:
                counts[cat] += 1

        theme_weights: Counter[str] = Counter()
        for c in classifications:
            for term in set(tokenize(c.comment.text)):
                theme_weights[term] += c.comment.weight

        def collect(category: str) -> list[dict[str, Any]]:
            rows = [
                {
                    "text": c.comment.text[:200],
                    "likes": c.comment.likes,
                    "sentiment": round(c.sentiment, 3),
                    "confidence": round(c.confidence, 3),
                }
                for c in classifications
                if category in c.categories
            ]
            rows.sort(key=lambda r: (r["likes"], r["confidence"]), reverse=True)
            return rows[: self.quote_limit]

        quotes = sorted(
            (
                {"text": c.comment.text[:200], "likes": c.comment.likes, "sentiment": round(c.sentiment, 3)}
                for c in classifications
            ),
            key=lambda r: r["likes"],
            reverse=True,
        )[: self.quote_limit]

        total = max(1, len(classifications))
        positive = sum(1 for c in classifications if c.sentiment > 0.15)
        negative = sum(1 for c in classifications if c.sentiment < -0.15)
        neutral = total - positive - negative

        return VOCReport(
            themes=theme_weights.most_common(self.top_terms_limit),
            category_counts=dict(counts),
            questions=collect("question"),
            objections=collect("objection"),
            pain_points=collect("pain_point"),
            product_ideas=collect("product_idea"),
            churn_risks=collect("churn_risk"),
            quotes=quotes,
            sentiment_mix={
                "positive": safe_div(positive, total),
                "neutral": safe_div(neutral, total),
                "negative": safe_div(negative, total),
                "mean": safe_div(sum(c.sentiment for c in classifications), total),
            },
        )

    def content_ideas(self, report: VOCReport, limit: int = 6) -> list[dict[str, Any]]:
        """Turn mined language into content ideas — questions become posts, pains become hooks."""
        ideas: list[dict[str, Any]] = []
        for q in report.questions:
            ideas.append(
                {
                    "idea": f"Answer: {q['text'][:110]}",
                    "format": "short_video",
                    "source": "question",
                    "priority": round(0.6 + 0.04 * math.log1p(q["likes"]), 3),
                }
            )
        for p in report.pain_points:
            ideas.append(
                {
                    "idea": f"Kill this pain: {p['text'][:110]}",
                    "format": "short_video",
                    "source": "pain_point",
                    "priority": round(0.7 + 0.04 * math.log1p(p["likes"]), 3),
                }
            )
        for term, weight in report.themes[: max(0, limit - len(ideas))]:
            ideas.append(
                {
                    "idea": f"Pillar piece on '{term}'",
                    "format": "long_form",
                    "source": "theme",
                    "priority": round(clamp01(math.log1p(weight) / 6.0), 3),
                }
            )
        ideas.sort(key=lambda i: i["priority"], reverse=True)
        return ideas[:limit]


# ─────────────────────────────────────────────────────────────────────────────
# skill: transcript-intelligence
# ─────────────────────────────────────────────────────────────────────────────

_CLAIM_RE = re.compile(
    r"\b(studies show|study shows|research shows|according to|the data|peer[- ]reviewed|in fact|"
    r"turns out|evidence shows|we found|results show)\b",
    re.IGNORECASE,
)
_STAT_RE = re.compile(r"\b\d+(?:[.,]\d+)?\s?(?:%|percent|million|billion|thousand|k\b|x\b|times|hours?|minutes?|days?|years?)(?![a-z0-9])", re.IGNORECASE)
_QUOTE_RE = re.compile(r'"([^"]{12,240})"')


@dataclass
class ContentAtom:
    """The smallest reusable piece of a transcript (a hook, claim, quote or stat)."""

    atom_id: str
    kind: str  # hook | claim | quote | stat | story
    text: str
    start_s: float
    end_s: float
    score: float

    @property
    def duration(self) -> float:
        return round(self.end_s - self.start_s, 3)

    def to_dict(self) -> dict[str, Any]:
        return {
            "atom_id": self.atom_id,
            "kind": self.kind,
            "text": self.text,
            "start_s": round(self.start_s, 2),
            "end_s": round(self.end_s, 2),
            "duration_s": self.duration,
            "score": round(self.score, 3),
        }


@dataclass
class TranscriptIntelligenceResult:
    word_count: int
    duration_s: float
    words_per_minute: float
    summary: list[str]
    hooks: list[HookHit]
    claims: list[ContentAtom]
    quotes: list[ContentAtom]
    stats: list[ContentAtom]
    atoms: list[ContentAtom]
    keywords: list[tuple[str, int]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "word_count": self.word_count,
            "duration_s": round(self.duration_s, 2),
            "words_per_minute": round(self.words_per_minute, 2),
            "summary": self.summary,
            "hooks": [h.to_dict() for h in self.hooks],
            "claims": [a.to_dict() for a in self.claims],
            "quotes": [a.to_dict() for a in self.quotes],
            "stats": [a.to_dict() for a in self.stats],
            "atom_count": len(self.atoms),
            "keywords": self.keywords,
        }


class TranscriptIntelligence:
    """skill: transcript-intelligence — summarize transcripts into reusable atoms."""

    def __init__(self, wpm: float = 155.0, atom_words: int = 45, summary_sentences: int = 5):
        self.wpm = wpm
        self.atom_words = atom_words
        self.summary_sentences = summary_sentences
        self.hooks = HookExtractor()

    def estimate_duration(self, text: str) -> float:
        words = len((text or "").split())
        return safe_div(words, self.wpm) * 60.0

    def _sentences(self, text: str) -> list[str]:
        parts = re.split(r"(?<=[.!?])\s+", (text or "").strip())
        return [p.strip() for p in parts if p.strip()]

    def _atoms(self, text: str) -> list[tuple[str, float, float]]:
        """Split the transcript into equal-atom windows with estimated timestamps."""
        words = (text or "").split()
        atoms: list[tuple[str, float, float]] = []
        sec_per_word = 60.0 / self.wpm
        for idx in range(0, len(words), self.atom_words):
            chunk = words[idx : idx + self.atom_words]
            start = idx * sec_per_word
            end = (idx + len(chunk)) * sec_per_word
            atoms.append((" ".join(chunk), start, end))
        return atoms

    def summarize(self, text: str) -> list[str]:
        sentences = self._sentences(text)
        if not sentences:
            return []
        freq: Counter[str] = Counter(tokenize(text))
        max_freq = max(freq.values()) if freq else 1
        scores: list[tuple[float, int, str]] = []
        total = len(sentences)
        for i, sentence in enumerate(sentences):
            toks = tokenize(sentence)
            if not toks:
                continue
            position_bonus = 1.0 if i < max(1, total // 10) else (0.6 if i >= total * 0.9 else 0.35)
            density = safe_div(sum(freq[t] for t in toks), max(1, len(toks)) * max_freq)
            length_penalty = 1.0 - abs(len(toks) - 18) / max(18.0, float(len(toks)))
            scores.append((0.5 * position_bonus + 2.0 * density + 0.3 * max(0.0, length_penalty), i, sentence))
        scores.sort(reverse=True)
        ordered = sorted(scores[: self.summary_sentences], key=lambda s: s[1])
        return [s[2] for s in ordered]

    def analyze(self, text: str, duration_s: float | None = None) -> TranscriptIntelligenceResult:
        words = (text or "").split()
        duration = duration_s if duration_s and duration_s > 0 else self.estimate_duration(text)
        atoms_raw = self._atoms(text)
        hooks = self.hooks.extract(text)

        atoms: list[ContentAtom] = []
        claims: list[ContentAtom] = []
        quotes: list[ContentAtom] = []
        stats: list[ContentAtom] = []

        for i, (chunk, start, end) in enumerate(atoms_raw):
            lowered = chunk.lower()
            if _CLAIM_RE.search(lowered):
                kind, bucket = "claim", claims
            elif _QUOTE_RE.search(chunk):
                kind, bucket = "quote", quotes
            elif _STAT_RE.search(chunk):
                kind, bucket = "stat", stats
            elif any(h.hook_type for h in self.hooks.extract(chunk)) and i == 0:
                kind, bucket = "hook", atoms
            else:
                kind, bucket = "story", atoms
            hook_score = self.hooks.score(chunk)
            density = clamp01(safe_div(len(set(tokenize(chunk))), 24.0))
            atom = ContentAtom(f"atom-{i:03d}", kind, chunk, start, end, round(clamp01(0.55 * hook_score + 0.45 * density), 3))
            if bucket is not atoms:
                bucket.append(atom)
            atoms.append(atom)

        atoms.sort(key=lambda a: a.score, reverse=True)
        return TranscriptIntelligenceResult(
            word_count=len(words),
            duration_s=duration,
            words_per_minute=safe_div(len(words), duration / 60.0) if duration else 0.0,
            summary=self.summarize(text),
            hooks=hooks,
            claims=claims,
            quotes=quotes,
            stats=stats,
            atoms=atoms,
            keywords=top_terms([text], 12),
        )


# ─────────────────────────────────────────────────────────────────────────────
# skill: competitor-social-research
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class CompetitorProfile:
    name: str
    posts: list[SocialPost] = field(default_factory=list)
    followers: int = 0

    @property
    def pillars(self) -> list[tuple[str, int]]:
        return top_terms([p.caption_without_meta for p in self.posts], 8)

    @property
    def cadence_per_week(self) -> float:
        if not self.posts:
            return 0.0
        hours = {p.published_hour for p in self.posts}
        days = max(1, len(hours) // 3)
        return round(safe_div(len(self.posts), days) * 7.0, 2)

    @property
    def median_views(self) -> float:
        series = [p.views for p in self.posts if p.views > 0]
        return float(statistics.median(series)) if series else 0.0

    @property
    def mean_engagement_rate(self) -> float:
        rates = [p.engagement_rate for p in self.posts]
        return safe_div(sum(rates), len(rates))

    def format_mix(self) -> dict[str, float]:
        counts = Counter(p.format_bucket for p in self.posts)
        total = max(1, sum(counts.values()))
        return {k: round(safe_div(v, total), 3) for k, v in sorted(counts.items())}

    def summary(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "followers": self.followers,
            "posts": len(self.posts),
            "median_views": round(self.median_views, 2),
            "mean_engagement_rate": round(self.mean_engagement_rate, 6),
            "cadence_per_week": self.cadence_per_week,
            "pillars": self.pillars,
            "format_mix": self.format_mix(),
        }


class CompetitorTeardown:
    """skill: competitor-social-research — compare accounts and surface gaps."""

    def __init__(self, gap_threshold: float = 0.12):
        self.gap_threshold = gap_threshold
        self.profiles: dict[str, CompetitorProfile] = {}

    def add(self, name: str, posts: list[SocialPost], followers: int = 0) -> CompetitorProfile:
        profile = CompetitorProfile(name=name, posts=list(posts), followers=followers)
        self.profiles[name] = profile
        return profile

    def compare(self, ours: str) -> dict[str, Any]:
        if ours not in self.profiles:
            raise KeyError(f"unknown profile: {ours}")
        own = self.profiles[ours]
        own_terms = dict(own.pillars)
        own_total = max(1, sum(own_terms.values()))
        rows: list[dict[str, Any]] = []
        for name, profile in self.profiles.items():
            if name == ours:
                continue
            terms = dict(profile.pillars)
            total = max(1, sum(terms.values()))
            rows.append(
                {
                    "competitor": name,
                    "followers": profile.followers,
                    "median_views": round(profile.median_views, 2),
                    "engagement_rate": round(profile.mean_engagement_rate, 6),
                    "cadence_per_week": profile.cadence_per_week,
                    "format_mix": profile.format_mix(),
                    "pillars": profile.pillars,
                }
            )
        gaps: list[dict[str, Any]] = []
        for name, profile in self.profiles.items():
            if name == ours:
                continue
            terms = dict(profile.pillars)
            total = max(1, sum(terms.values()))
            for term, count in terms.items():
                their_share = safe_div(count, total)
                our_share = safe_div(own_terms.get(term, 0), own_total)
                if their_share - our_share >= self.gap_threshold:
                    gaps.append(
                        {
                            "term": term,
                            "competitor": name,
                            "their_share": round(their_share, 3),
                            "our_share": round(our_share, 3),
                            "gap": round(their_share - our_share, 3),
                        }
                    )
        gaps.sort(key=lambda g: g["gap"], reverse=True)
        return {
            "account": own.summary(),
            "competitors": rows,
            "gaps": gaps,
            "recommendations": self.recommendations(own, gaps),
        }

    def recommendations(self, own: CompetitorProfile, gaps: list[dict[str, Any]]) -> list[str]:
        recs: list[str] = []
        for gap in gaps[:4]:
            recs.append(f"Publish 2-3 pieces on '{gap['term']}' — competitors hold {gap['their_share']:.0%} share vs your {gap['our_share']:.0%}.")
        mix = own.format_mix()
        if mix.get("short", 0.0) < 0.4:
            recs.append("Short-form is under-weighted in your mix; target >=40% of posts under 45s.")
        if own.cadence_per_week < 3:
            recs.append(f"Cadence is {own.cadence_per_week}/week; test 5/week for two weeks before judging results.")
        if not recs:
            recs.append("No material gaps detected — double down on your best-performing pillar.")
        return recs


# ─────────────────────────────────────────────────────────────────────────────
# skill: ad-library-teardown
# ─────────────────────────────────────────────────────────────────────────────

_ANGLE_PATTERNS: list[tuple[str, str]] = [
    ("pain_relief", r"\b(tired of|struggle|struggling|sick of|stop wasting|frustrat)\w*\b"),
    ("aspiration", r"\b(become|unlock|level up|imagine|transform|best version|dream)\b"),
    ("fear_loss", r"\b(don'?t miss|before it'?s too late|last chance|risk|losing|running out)\b"),
    ("social_proof", r"\b(\d[\d,.]*\s*(?:customers|users|teams|founders|reviews)|trusted by|used by|join \d)\b"),
    ("discount", r"\b(\d{1,2}% off|save \d|free trial|discount|half price|bogo)\b"),
    ("urgency", r"\b(today only|limited time|ends (?:soon|tonight)|deadline|hours left|now)\b"),
    ("authority", r"\b(award|certified|#1|world'?s leading|doctor|expert|clinically)\b"),
    ("curiosity", r"\b(secret|nobody|what happens|the truth|discover|revealed)\b"),
]

_CTA_PATTERNS: list[tuple[str, str]] = [
    ("get_started", r"\b(get started|start (?:free|now)|try it|sign up)\b"),
    ("learn_more", r"\b(learn more|see how|read more|find out|watch)\b"),
    ("book_demo", r"\b(book a|book your|schedule a|request a) (demo|call|consult)\b"),
    ("buy_now", r"\b(buy now|shop now|order now|add to cart)\b"),
    ("download", r"\b(download|get the (?:guide|checklist|template)|grab the)\b"),
    ("subscribe", r"\b(subscribe|join (?:the )?(?:newsletter|waitlist|community))\b"),
]

_OFFER_PATTERNS: list[tuple[str, str]] = [
    ("free_trial", r"\bfree trial\b"),
    ("money_back", r"\bmoney[- ]back|refund\b"),
    ("bundle", r"\bbundle|package|everything included\b"),
    ("discount_pct", r"(\d{1,2}%\s*off|save\s+\d{1,2}%|\d{1,2}%\s*discount)"),
    ("free_shipping", r"\bfree shipping\b"),
    ("lead_magnet", r"\bfree (?:guide|checklist|template|ebook|audit|course)\b"),
    ("limited_seats", r"\b(only \d+ (?:spots|seats)|limited (?:spots|seats)|waitlist)\b"),
]


@dataclass
class AdCreative:
    creative_id: str = ""
    platform: str = "meta"
    advertiser: str = ""
    headline: str = ""
    body: str = ""
    cta_button: str = ""
    first_seen_day: int = 0
    last_seen_day: int = 0
    impressions: int = 0
    spend_estimate: float = 0.0

    @property
    def days_active(self) -> int:
        return max(1, self.last_seen_day - self.first_seen_day + 1)

    @property
    def text(self) -> str:
        return f"{self.headline}. {self.body}".strip()

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "platform": self.platform,
            "advertiser": self.advertiser,
            "headline": self.headline,
            "days_active": self.days_active,
            "impressions": self.impressions,
            "spend_estimate": round(self.spend_estimate, 2),
        }


class AdLibraryTeardown:
    """skill: ad-library-teardown — messaging angles, hooks, CTAs, offers, tests."""

    def __init__(self, longevity_window: int = 21):
        self.longevity_window = longevity_window
        self.creatives: list[AdCreative] = []

    def add(self, creative: AdCreative) -> AdCreative:
        self.creatives.append(creative)
        return creative

    def classify_angles(self, creative: AdCreative) -> list[str]:
        text = creative.text.lower()
        return [name for name, pattern in _ANGLE_PATTERNS if re.search(pattern, text)]

    def classify_cta(self, creative: AdCreative) -> list[str]:
        text = (creative.cta_button + " " + creative.text).lower()
        return [name for name, pattern in _CTA_PATTERNS if re.search(pattern, text)]

    def classify_offers(self, creative: AdCreative) -> list[str]:
        text = creative.text.lower()
        return [name for name, pattern in _OFFER_PATTERNS if re.search(pattern, text)]

    def longevity_score(self, creative: AdCreative) -> float:
        """Longer-running creatives imply winning performance (ad libraries self-report)."""
        return round(clamp01(math.log1p(creative.days_active) / math.log1p(self.longevity_window * 4)), 3)

    def hook_strength(self, creative: AdCreative) -> float:
        return round(HookExtractor().score(creative.headline or creative.body), 3)

    def teardown(self, advertiser: str | None = None) -> dict[str, Any]:
        creatives = [c for c in self.creatives if advertiser is None or c.advertiser == advertiser]
        if not creatives:
            return {"advertiser": advertiser or "(all)", "creatives": 0}

        angles: Counter[str] = Counter()
        ctas: Counter[str] = Counter()
        offers: Counter[str] = Counter()
        rows: list[dict[str, Any]] = []
        for c in creatives:
            a = self.classify_angles(c)
            ct = self.classify_cta(c)
            of = self.classify_offers(c)
            angles.update(a)
            ctas.update(ct)
            offers.update(of)
            rows.append(
                {
                    **c.to_dict(),
                    "angles": a,
                    "ctas": ct,
                    "offers": of,
                    "longevity_score": self.longevity_score(c),
                    "hook_strength": self.hook_strength(c),
                    "headline": c.headline,
                }
            )
        rows.sort(key=lambda r: (r["longevity_score"], r["hook_strength"]), reverse=True)
        return {
            "advertiser": advertiser or "(all)",
            "creatives": len(creatives),
            "angle_mix": {k: round(safe_div(v, len(creatives)), 3) for k, v in angles.most_common()},
            "cta_mix": {k: round(safe_div(v, len(creatives)), 3) for k, v in ctas.most_common()},
            "offer_mix": {k: round(safe_div(v, len(creatives)), 3) for k, v in offers.most_common()},
            "top_creatives": rows[:10],
            "test_ideas": self.test_ideas(angles, ctas, offers, creatives),
        }

    def test_ideas(
        self,
        angles: Counter[str],
        ctas: Counter[str],
        offers: Counter[str],
        creatives: list[AdCreative],
    ) -> list[dict[str, Any]]:
        ideas: list[dict[str, Any]] = []
        used_angles = {a for a in angles}
        for name, _ in _ANGLE_PATTERNS:
            if name not in used_angles:
                ideas.append({"test": f"Untested angle: {name}", "priority": 0.75, "type": "angle"})
        top_angle = angles.most_common(1)[0][0] if angles else "curiosity"
        for name, _ in _CTA_PATTERNS[:3]:
            if name not in ctas:
                ideas.append({"test": f"Pair '{top_angle}' angle with untested CTA '{name}'", "priority": 0.65, "type": "cta"})
        for name, _ in _OFFER_PATTERNS[:3]:
            if name not in offers:
                ideas.append({"test": f"Add offer mechanic '{name}' to the longest-running creative", "priority": 0.6, "type": "offer"})
        longest = max(creatives, key=lambda c: c.days_active)
        ideas.append(
            {
                "test": f"Iterate {longest.creative_id} (live {longest.days_active}d) into 3 hook variants",
                "priority": 0.9,
                "type": "iteration",
            }
        )
        ideas.sort(key=lambda i: i["priority"], reverse=True)
        return ideas


# ─────────────────────────────────────────────────────────────────────────────
# skill: trend-discovery
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class TrendSignal:
    """A hashtag / sound / format with an observed time series."""

    name: str
    kind: str = "hashtag"  # hashtag | sound | topic | format
    series: list[float] = field(default_factory=list)

    def observe(self, value: float) -> None:
        self.series.append(float(value))

    @property
    def latest(self) -> float:
        return self.series[-1] if self.series else 0.0

    @property
    def baseline(self) -> float:
        head = self.series[: max(1, len(self.series) // 3)]
        return safe_div(sum(head), len(head))

    def ewma(self, alpha: float = 0.4) -> list[float]:
        out: list[float] = []
        level = self.series[0] if self.series else 0.0
        for value in self.series:
            level = alpha * value + (1 - alpha) * level
            out.append(level)
        return out

    def velocity(self, alpha: float = 0.4) -> float:
        """Normalized slope of the EWMA-smoothed series."""
        smooth = self.ewma(alpha)
        if len(smooth) < 2:
            return 0.0
        delta = smooth[-1] - smooth[0]
        scale = max(1.0, abs(self.baseline))
        return round(safe_div(delta, scale), 4)

    def acceleration(self, alpha: float = 0.4) -> float:
        smooth = self.ewma(alpha)
        if len(smooth) < 3:
            return 0.0
        mid = len(smooth) // 2
        early = safe_div(smooth[mid] - smooth[0], max(1, mid))
        late = safe_div(smooth[-1] - smooth[mid], max(1, len(smooth) - mid))
        return round(late - early, 4)

    def momentum(self) -> float:
        return round(clamp01(0.5 + 0.35 * self.velocity() + 0.25 * self.acceleration()), 4)

    def phase(self) -> str:
        v, a = self.velocity(), self.acceleration()
        if v > 0.25 and a > 0:
            return "emerging"
        if v > 0.25 and a <= 0:
            return "peaking"
        if v < -0.15:
            return "fading"
        return "flat"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "observations": len(self.series),
            "latest": round(self.latest, 3),
            "baseline": round(self.baseline, 3),
            "velocity": self.velocity(),
            "acceleration": self.acceleration(),
            "momentum": self.momentum(),
            "phase": self.phase(),
        }


class TrendDiscovery:
    """skill: trend-discovery — rank trends by volume velocity, not raw volume."""

    def __init__(self, alpha: float = 0.4, min_observations: int = 3):
        self.alpha = alpha
        self.min_observations = min_observations
        self.signals: dict[str, TrendSignal] = {}

    def observe(self, name: str, value: float, kind: str = "hashtag") -> TrendSignal:
        signal = self.signals.setdefault(name, TrendSignal(name=name, kind=kind))
        signal.observe(value)
        return signal

    def rank(self, limit: int = 10) -> list[dict[str, Any]]:
        rows = [s.to_dict() for s in self.signals.values() if len(s.series) >= self.min_observations]
        rows.sort(key=lambda r: (r["momentum"], r["velocity"]), reverse=True)
        return rows[:limit]

    def brief(self, niche: str, limit: int = 10) -> dict[str, Any]:
        ranked = self.rank(limit)
        phases = Counter(r["phase"] for r in ranked)
        angles: list[dict[str, Any]] = []
        for row in ranked[:5]:
            angles.append(
                {
                    "trend": row["name"],
                    "kind": row["kind"],
                    "phase": row["phase"],
                    "suggested_angle": self._angle(niche, row),
                    "confidence": round(clamp01(row["momentum"] * 0.8 + 0.2 * (row["observations"] / 10.0)), 3),
                }
            )
        return {
            "niche": niche,
            "signals_tracked": len(self.signals),
            "phase_mix": dict(phases),
            "trends": ranked,
            "content_angles": angles,
        }

    @staticmethod
    def _angle(niche: str, row: dict[str, Any]) -> str:
        phase = row["phase"]
        if phase == "emerging":
            return f"Be early: publish a {niche} take on '{row['name']}' this week while velocity is accelerating."
        if phase == "peaking":
            return f"Ride it now: remix '{row['name']}' for {niche} with your own hook before it decays."
        if phase == "fading":
            return f"Archive '{row['name']}' — reuse the format later, not the sound."
        return f"Watch '{row['name']}' for one more cycle before committing production time."


# ─────────────────────────────────────────────────────────────────────────────
# skill: influencer-prospecting
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class InfluencerProspect:
    handle: str
    platform: str = "tiktok"
    followers: int = 0
    avg_views: int = 0
    engagement_rate: float = 0.0
    niche_tags: tuple[str, ...] = ()
    growth_30d: float = 0.0
    brand_safety: float = 1.0
    audience_country: str = "US"
    contact: str = ""

    @property
    def view_ratio(self) -> float:
        return safe_div(self.avg_views, self.followers)


class InfluencerProspecting:
    """skill: influencer-prospecting — weighted fit score, tiers, CSV export."""

    WEIGHTS = {
        "niche_fit": 0.30,
        "engagement": 0.25,
        "reach": 0.15,
        "growth": 0.15,
        "safety": 0.10,
        "consistency": 0.05,
    }

    def __init__(self, target_niche: tuple[str, ...] = (), target_market: str = "US"):
        self.target_niche = tuple(t.lower() for t in target_niche)
        self.target_market = target_market.upper()

    def niche_fit(self, prospect: InfluencerProspect) -> float:
        if not self.target_niche:
            return 0.5
        tags = {t.lower() for t in prospect.niche_tags}
        overlap = len(tags & set(self.target_niche))
        return clamp01(safe_div(overlap, max(1, len(self.target_niche))))

    def reach_score(self, prospect: InfluencerProspect) -> float:
        """Log-scaled follower score, peaking in the 20k-500k micro/mid band sweet spot."""
        if prospect.followers <= 0:
            return 0.0
        score = math.log10(prospect.followers) / 7.0
        band_bonus = 0.15 if 20_000 <= prospect.followers <= 500_000 else 0.0
        return clamp01(score + band_bonus)

    def engagement_score(self, prospect: InfluencerProspect) -> float:
        """2% engagement is a solid benchmark; sqrt-compressed above that."""
        return clamp01(math.sqrt(max(0.0, prospect.engagement_rate) / 0.02))

    def growth_score(self, prospect: InfluencerProspect) -> float:
        return clamp01(0.5 + prospect.growth_30d * 2.5)

    def consistency_score(self, prospect: InfluencerProspect) -> float:
        return clamp01(prospect.view_ratio * 1.5)

    def score(self, prospect: InfluencerProspect) -> dict[str, Any]:
        parts = {
            "niche_fit": self.niche_fit(prospect),
            "engagement": self.engagement_score(prospect),
            "reach": self.reach_score(prospect),
            "growth": self.growth_score(prospect),
            "safety": clamp01(prospect.brand_safety),
            "consistency": self.consistency_score(prospect),
        }
        market_penalty = 0.0 if prospect.audience_country.upper() == self.target_market else 0.08
        total = sum(parts[k] * w for k, w in self.WEIGHTS.items()) - market_penalty
        total = clamp01(total)
        tier = "A" if total >= 0.72 else ("B" if total >= 0.55 else ("C" if total >= 0.38 else "D"))
        return {
            "handle": prospect.handle,
            "platform": prospect.platform,
            "followers": prospect.followers,
            "parts": {k: round(v, 4) for k, v in parts.items()},
            "market_penalty": round(market_penalty, 3),
            "fit_score": round(total, 4),
            "tier": tier,
        }

    def rank(self, prospects: list[InfluencerProspect]) -> list[dict[str, Any]]:
        rows = [self.score(p) for p in prospects]
        rows.sort(key=lambda r: r["fit_score"], reverse=True)
        return rows

    def outreach_notes(self, scored: dict[str, Any], prospect: InfluencerProspect) -> str:
        strongest = max(scored["parts"].items(), key=lambda kv: kv[1] * self.WEIGHTS[kv[0]])
        return (
            f"{prospect.handle} ({scored['tier']} tier, fit {scored['fit_score']:.2f}): "
            f"lead with {strongest[0].replace('_', ' ')}, {prospect.followers:,} followers, "
            f"{prospect.engagement_rate:.2%} engagement, growth {prospect.growth_30d:+.1%}."
        )

    def to_csv(self, prospects: list[InfluencerProspect]) -> str:
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            ["handle", "platform", "followers", "avg_views", "engagement_rate", "growth_30d", "fit_score", "tier", "contact"]
        )
        for prospect, scored in zip(prospects, self.rank(prospects)):
            writer.writerow(
                [
                    prospect.handle,
                    prospect.platform,
                    prospect.followers,
                    prospect.avg_views,
                    f"{prospect.engagement_rate:.4f}",
                    f"{prospect.growth_30d:.4f}",
                    f"{scored['fit_score']:.4f}",
                    scored["tier"],
                    prospect.contact,
                ]
            )
        return buf.getvalue()

    def prospect_list(self, prospects: list[InfluencerProspect], limit: int = 25) -> dict[str, Any]:
        by_handle = {p.handle: p for p in prospects}
        ranked = self.rank(prospects)[:limit]
        for row in ranked:
            prospect = by_handle[row["handle"]]
            row["outreach_notes"] = self.outreach_notes(row, prospect)
        tiers = Counter(row["tier"] for row in ranked)
        return {
            "target_niche": list(self.target_niche),
            "target_market": self.target_market,
            "count": len(ranked),
            "tier_mix": dict(tiers),
            "prospects": ranked,
        }


# ─────────────────────────────────────────────────────────────────────────────
# skill: audience-research
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class AudienceProfile:
    handle: str
    followers: int = 0
    countries: dict[str, float] = field(default_factory=dict)
    age_brackets: dict[str, float] = field(default_factory=dict)
    interests: tuple[str, ...] = ()
    engagement_rate: float = 0.0
    follower_growth_30d: float = 0.0
    suspicious_follower_share: float = 0.0

    @property
    def authenticity(self) -> float:
        """Engagement plausibility adjusted for low-quality follower share."""
        er_component = clamp01(self.engagement_rate / 0.03)
        quality = clamp01(1.0 - self.suspicious_follower_share)
        return round(clamp01(0.6 * er_component + 0.4 * quality), 4)

    @property
    def completeness(self) -> float:
        fields = [
            bool(self.countries),
            bool(self.age_brackets),
            bool(self.interests),
            self.followers > 0,
            self.engagement_rate > 0,
        ]
        return round(safe_div(sum(1 for f in fields if f), len(fields)), 3)


class AudienceResearch:
    """skill: audience-research — audience fit with explicit confidence labels."""

    def __init__(self, target_country: str = "US", target_interests: tuple[str, ...] = ()):
        self.target_country = target_country.upper()
        self.target_interests = tuple(i.lower() for i in target_interests)

    def geo_fit(self, profile: AudienceProfile) -> float:
        if not profile.countries:
            return 0.0
        return clamp01(profile.countries.get(self.target_country, 0.0) / 100.0 if max(profile.countries.values()) > 1.0 else profile.countries.get(self.target_country, 0.0))

    def interest_fit(self, profile: AudienceProfile) -> float:
        if not self.target_interests:
            return 0.5
        interests = {i.lower() for i in profile.interests}
        return clamp01(safe_div(len(interests & set(self.target_interests)), max(1, len(self.target_interests))))

    def scale_fit(self, profile: AudienceProfile) -> float:
        if profile.followers <= 0:
            return 0.0
        return clamp01(math.log10(profile.followers) / 6.0)

    def growth_fit(self, profile: AudienceProfile) -> float:
        return clamp01(0.5 + profile.follower_growth_30d * 3.0)

    def fit_report(self, profile: AudienceProfile) -> dict[str, Any]:
        parts = {
            "geo_fit": self.geo_fit(profile),
            "interest_fit": self.interest_fit(profile),
            "scale_fit": self.scale_fit(profile),
            "growth_fit": self.growth_fit(profile),
            "authenticity": profile.authenticity,
        }
        weights = {"geo_fit": 0.28, "interest_fit": 0.28, "scale_fit": 0.14, "growth_fit": 0.15, "authenticity": 0.15}
        total = clamp01(sum(parts[k] * w for k, w in weights.items()))
        completeness = profile.completeness
        confidence = "high" if completeness >= 0.8 else ("medium" if completeness >= 0.5 else "low")
        notes: list[str] = []
        if profile.suspicious_follower_share > 0.2:
            notes.append(f"{profile.suspicious_follower_share:.0%} of followers look low-quality; treat reach estimates with care.")
        if not profile.age_brackets:
            notes.append("No age data available — demographic fit is inferred from geo + interests only.")
        top_geo = sorted(profile.countries.items(), key=lambda kv: kv[1], reverse=True)[:3]
        if top_geo and top_geo[0][0].upper() != self.target_country:
            notes.append(f"Largest audience is {top_geo[0][0]} ({top_geo[0][1]}), not the target market {self.target_country}.")
        return {
            "handle": profile.handle,
            "parts": {k: round(v, 4) for k, v in parts.items()},
            "fit_score": round(total, 4),
            "confidence": confidence,
            "completeness": completeness,
            "verdict": self._verdict(total, confidence),
            "notes": notes,
        }

    @staticmethod
    def _verdict(score: float, confidence: str) -> str:
        if score >= 0.7 and confidence == "high":
            return "strong_fit"
        if score >= 0.7:
            return "promising_unverified"
        if score >= 0.45:
            return "partial_fit"
        return "poor_fit"


# ─────────────────────────────────────────────────────────────────────────────
# skill: social-listening-brief
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class Mention:
    mention_id: str = ""
    platform: str = "reddit"
    text: str = ""
    author: str = ""
    likes: int = 0
    url: str = ""

    @property
    def weight(self) -> float:
        return 1.0 + math.log1p(self.likes)


class SocialListeningBrief:
    """skill: social-listening-brief — multi-source themes with sentiment caveats."""

    def __init__(self, miner: CommentMiner | None = None, min_mentions: int = 3):
        self.miner = miner or CommentMiner()
        self.min_mentions = min_mentions

    def build(self, topic: str, mentions: list[Mention], theme_limit: int = 8) -> dict[str, Any]:
        comments = [Comment(comment_id=m.mention_id, author=m.author, text=m.text, likes=m.likes) for m in mentions]
        report = self.miner.mine(comments)

        by_platform: dict[str, list[Mention]] = defaultdict(list)
        for m in mentions:
            by_platform[m.platform].append(m)
        platform_mix = {p: round(safe_div(len(v), len(mentions)), 3) for p, v in sorted(by_platform.items())}

        theme_weights: Counter[str] = Counter()
        for m in mentions:
            for term in set(tokenize(m.text)):
                theme_weights[term] += m.weight
        themes = [
            {"term": term, "weight": round(weight, 3), "mentions": sum(1 for m in mentions if term in tokenize(m.text))}
            for term, weight in theme_weights.most_common(theme_limit)
        ]

        examples = sorted(mentions, key=lambda m: m.likes, reverse=True)[:5]
        caveats: list[str] = []
        if len(mentions) < 30:
            caveats.append(f"Small sample ({len(mentions)} mentions) — treat theme rank as directional only.")
        dominant = max(platform_mix.items(), key=lambda kv: kv[1]) if platform_mix else ("none", 0.0)
        if dominant[1] > 0.5:
            caveats.append(f"{dominant[1]:.0%} of mentions come from {dominant[0]}; platform skew is likely.")
        if report.sentiment_mix["negative"] > 0.4:
            caveats.append("Negative mentions dominate — social platforms over-index on complaints.")
        if not caveats:
            caveats.append("Sample is balanced across sources; sentiment read is reasonably reliable.")

        return {
            "topic": topic,
            "mentions": len(mentions),
            "platform_mix": platform_mix,
            "themes": themes,
            "sentiment_mix": {k: round(v, 4) for k, v in report.sentiment_mix.items()},
            "cited_examples": [
                {"platform": m.platform, "url": m.url, "likes": m.likes, "text": m.text[:180]} for m in examples
            ],
            "caveats": caveats,
            "confidence": self._confidence(len(mentions), platform_mix),
        }

    @staticmethod
    def _confidence(count: int, platform_mix: dict[str, float]) -> str:
        if count < 10:
            return "low"
        dominant = max(platform_mix.values()) if platform_mix else 1.0
        if count >= 50 and dominant <= 0.6:
            return "high"
        return "medium"


# ─────────────────────────────────────────────────────────────────────────────
# skill: product-demand-research
# ─────────────────────────────────────────────────────────────────────────────


class ProductDemandResearch:
    """skill: product-demand-research — validate demand from posts/comments/Reddit."""

    def __init__(self, miner: CommentMiner | None = None):
        self.miner = miner or CommentMiner()

    def demand_signals(self, comments: list[Comment]) -> dict[str, Any]:
        report = self.miner.mine(comments)
        willingness = [row for row in report.product_ideas]
        pains = report.pain_points
        objections = report.objections

        signal_count = len(willingness) + len(pains)
        breadth = len({term for term, _ in report.themes[:12]})
        intensity = safe_div(sum(c.likes for c in comments), len(comments)) if comments else 0.0
        demand_score = clamp01(
            0.40 * clamp01(safe_div(signal_count, max(1, len(comments))) * 3.0)
            + 0.25 * clamp01(math.log1p(breadth) / math.log1p(25.0))
            + 0.20 * clamp01(math.log1p(intensity) / math.log1p(200.0))
            + 0.15 * (1.0 - report.sentiment_mix["negative"])
        )
        verdict = (
            "strong_demand" if demand_score >= 0.66 else ("moderate_demand" if demand_score >= 0.40 else "weak_demand")
        )
        return {
            "comments_analyzed": len(comments),
            "explicit_demand_signals": len(willingness),
            "pain_points": len(pains),
            "objections": len(objections),
            "mean_likes": round(intensity, 2),
            "demand_score": round(demand_score, 4),
            "verdict": verdict,
            "exact_language": [row["text"] for row in (willingness + pains)[:8]],
            "objection_language": [row["text"] for row in objections[:5]],
            "ideas": self.miner.content_ideas(report),
        }


# ─────────────────────────────────────────────────────────────────────────────
# skill: creator-profile-teardown
# ─────────────────────────────────────────────────────────────────────────────


class CreatorProfileTeardown:
    """skill: creator-profile-teardown — why an account works and what to copy."""

    def __init__(self, outlier_finder: OutlierPostFinder | None = None):
        self.outliers = outlier_finder or OutlierPostFinder()

    def teardown(self, handle: str, posts: list[SocialPost], followers: int = 0, bio: str = "") -> dict[str, Any]:
        baseline = CreatorBaseline(posts=posts)
        outlier_results = self.outliers.find(posts, handle if any(p.author == handle for p in posts) else None)
        pillar_terms = top_terms([p.caption_without_meta for p in posts], 6)
        total = max(1, sum(count for _, count in pillar_terms))
        pillars = [
            {"pillar": term, "share": round(safe_div(count, total), 3), "posts": count} for term, count in pillar_terms
        ]
        mix = Counter(p.format_bucket for p in posts)
        dominant_format = mix.most_common(1)[0][0] if mix else "short"
        cadence = CompetitorProfile(name=handle, posts=posts, followers=followers).cadence_per_week
        positioning = self._positioning(bio, pillar_terms)
        if outlier_results:
            hook_line = f"Open with a {self._top_hook_type(outlier_results)} hook — it drives {len(outlier_results)} outlier(s)."
        else:
            hook_line = "No outliers yet — test three hook types (curiosity, contrarian, number-list) before scaling."
        playbook = [
            hook_line,
            f"Lead format: {dominant_format} ({safe_div(mix[dominant_format], max(1, len(posts))):.0%} of posts).",
            f"Cadence: about {cadence} posts/week.",
            f"Median views {baseline.median_views:,.0f}; outliers clear it by {self._median_factor(outlier_results):.1f}x.",
        ]
        return {
            "handle": handle,
            "followers": followers,
            "posts_analyzed": len(posts),
            "baseline": baseline.summary(),
            "positioning": positioning,
            "content_pillars": pillars,
            "format_mix": {k: round(safe_div(v, len(posts)), 3) for k, v in sorted(mix.items())},
            "cadence_per_week": cadence,
            "outliers": [r.to_dict() for r in outlier_results[:5]],
            "playbook": playbook,
        }

    @staticmethod
    def _positioning(bio: str, pillars: list[tuple[str, int]]) -> str:
        terms = [t for t, _ in pillars[:3]]
        if bio:
            return f"{bio.strip()} (topics: {', '.join(terms)})" if terms else bio.strip()
        return "positions around " + ", ".join(terms) if terms else "no clear positioning detected"

    @staticmethod
    def _top_hook_type(results: list[OutlierResult]) -> str:
        counts = Counter(r.hooks[0].hook_type for r in results if r.hooks)
        return counts.most_common(1)[0][0] if counts else "curiosity_gap"

    @staticmethod
    def _median_factor(results: list[OutlierResult]) -> float:
        return statistics.median([r.outlier_factor for r in results]) if results else 0.0


# ─────────────────────────────────────────────────────────────────────────────
# skill: content-repurposing
# ─────────────────────────────────────────────────────────────────────────────


class ContentRepurposing:
    """skill: content-repurposing — one transcript becomes many platform assets."""

    def __init__(self, wpm: float = 155.0):
        self.wpm = wpm
        self.transcripts = TranscriptIntelligence(wpm=wpm)

    def words_for_seconds(self, seconds: float) -> int:
        return int(round(seconds / 60.0 * self.wpm))

    def linkedin_post(self, text: str, max_chars: int = 3000) -> str:
        body = self.transcripts.summarize(text)
        hooks = self.transcripts.hooks.extract(text)
        opening = hooks[0].text if hooks else (body[0] if body else text[:120])
        lines = [opening.strip(), ""]
        for sentence in body[:4]:
            lines.append(f"• {sentence}")
        lines += ["", "What would you add?"]
        post = "\n".join(lines)
        return post[:max_chars]

    def x_thread(self, text: str, tweet_chars: int = 280, max_tweets: int = 7) -> list[str]:
        sentences = self.transcripts._sentences(text)
        if not sentences:
            return []
        hooks = self.transcripts.hooks.extract(text)
        first = hooks[0].text if hooks else sentences[0]
        tweets: list[str] = []
        budget = tweet_chars - 8  # leave room for " n/m" counters and links
        current = f"1/ {first.strip()}"
        idx = 2
        for sentence in sentences[1:]:
            candidate = f"{current} {sentence}".strip() if len(tweets) == 0 else f"{current} {sentence}".strip()
            if len(candidate) <= budget:
                current = candidate
            else:
                tweets.append(current)
                if idx > max_tweets:
                    break
                current = f"{idx}/ {sentence}"
                idx += 1
        if current and len(tweets) < max_tweets:
            tweets.append(current)
        return tweets

    def short_script(self, text: str, target_seconds: float = 55.0) -> dict[str, Any]:
        budget = self.words_for_seconds(target_seconds)
        sentences = self.transcripts._sentences(text)
        hooks = self.transcripts.hooks.extract(text)
        hook = hooks[0].text if hooks else (sentences[0] if sentences else "")
        body_words: list[str] = []
        for sentence in sentences[1:]:
            if len((" ".join(body_words) + " " + sentence).split()) > int(budget * 0.72):
                break
            body_words.append(sentence)
        cta = "Follow for more." if "follow" not in text.lower() else "Follow along for part two."
        script = f"{hook.strip()}\n\n{' '.join(body_words).strip()}\n\n{cta}"
        words = len(script.split())
        return {
            "script": script,
            "word_count": words,
            "target_seconds": target_seconds,
            "estimated_seconds": round(words / self.wpm * 60.0, 2),
            "within_budget": words <= budget,
        }

    def newsletter_blurb(self, text: str, max_words: int = 120) -> str:
        summary = self.transcripts.summarize(text)
        words: list[str] = []
        for sentence in summary:
            words.extend(sentence.split())
            if len(words) >= max_words:
                break
        return " ".join(words[:max_words])

    def repurpose(self, text: str) -> dict[str, Any]:
        intel = self.transcripts.analyze(text)
        return {
            "source": {
                "word_count": intel.word_count,
                "duration_s": round(intel.duration_s, 2),
                "keywords": intel.keywords[:8],
            },
            "linkedin_post": self.linkedin_post(text),
            "x_thread": self.x_thread(text),
            "short_script": self.short_script(text),
            "newsletter_blurb": self.newsletter_blurb(text),
            "content_atoms": [a.to_dict() for a in intel.atoms[:6]],
        }


# ─────────────────────────────────────────────────────────────────────────────
# skill: scrapecreators-api — endpoint routing
# ─────────────────────────────────────────────────────────────────────────────

SCRAPECREATORS_BASE = "https://api.scrapecreators.com"


@dataclass
class EndpointSpec:
    """One ScrapeCreators endpoint: platform + operation -> request spec."""

    platform: str
    operation: str
    path: str
    method: str = "GET"
    params: tuple[str, ...] = ()
    credits: int = 1

    @property
    def url(self) -> str:
        return f"{SCRAPECREATORS_BASE}{self.path}"

    def build_url(self, values: dict[str, Any]) -> str:
        query = urllib.parse.urlencode({k: v for k, v in values.items() if k in self.params and v is not None})
        return f"{self.url}?{query}" if query else self.url

    def missing_params(self, values: dict[str, Any]) -> list[str]:
        return [p for p in self.params if p not in values or values[p] in (None, "")]

    def to_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "operation": self.operation,
            "url": self.url,
            "method": self.method,
            "params": list(self.params),
            "credits": self.credits,
        }


class ScrapecreatorsRouter:
    """skill: scrapecreators-api — route a raw research request to the right endpoint."""

    ENDPOINTS: tuple[EndpointSpec, ...] = (
        EndpointSpec("tiktok", "profile", "/v1/tiktok/profile", params=("handle",), credits=1),
        EndpointSpec("tiktok", "posts", "/v1/tiktok/profile/videos", params=("handle", "cursor"), credits=1),
        EndpointSpec("tiktok", "hashtag", "/v1/tiktok/hashtag/posts", params=("hashtag", "cursor"), credits=2),
        EndpointSpec("tiktok", "comments", "/v1/tiktok/video/comments", params=("url", "cursor"), credits=2),
        EndpointSpec("tiktok", "transcript", "/v1/tiktok/video/transcript", params=("url",), credits=5),
        EndpointSpec("instagram", "profile", "/v1/instagram/profile", params=("handle",), credits=1),
        EndpointSpec("instagram", "posts", "/v1/instagram/profile/posts", params=("handle", "cursor"), credits=1),
        EndpointSpec("instagram", "comments", "/v1/instagram/post/comments", params=("url", "cursor"), credits=2),
        EndpointSpec("youtube", "channel", "/v1/youtube/channel", params=("handle",), credits=1),
        EndpointSpec("youtube", "videos", "/v1/youtube/channel/videos", params=("handle", "cursor"), credits=1),
        EndpointSpec("youtube", "transcript", "/v1/youtube/video/transcript", params=("url",), credits=5),
        EndpointSpec("youtube", "comments", "/v1/youtube/video/comments", params=("url", "cursor"), credits=2),
        EndpointSpec("reddit", "search", "/v1/reddit/search", params=("query", "subreddit", "sort"), credits=1),
        EndpointSpec("reddit", "comments", "/v1/reddit/post/comments", params=("url",), credits=2),
        EndpointSpec("x", "profile", "/v1/twitter/profile", params=("handle",), credits=1),
        EndpointSpec("x", "search", "/v1/twitter/search", params=("query", "cursor"), credits=2),
        EndpointSpec("linkedin", "profile", "/v1/linkedin/profile", params=("handle",), credits=1),
        EndpointSpec("linkedin", "posts", "/v1/linkedin/profile/posts", params=("handle", "cursor"), credits=2),
        EndpointSpec("facebook", "ads", "/v1/facebook/ads/library", params=("query", "country"), credits=5),
        EndpointSpec("google", "ads", "/v1/google/ads/library", params=("query", "country"), credits=5),
    )

    def __init__(self, api_key: str = "", credits_per_month: int = 10_000, transport: Callable[[EndpointSpec, dict], dict] | None = None):
        self.api_key = api_key
        self.credits_per_month = credits_per_month
        self.credits_used = 0
        self.calls: list[dict[str, Any]] = []
        self.transport = transport

    def resolve(self, platform: str, operation: str) -> EndpointSpec | None:
        for spec in self.ENDPOINTS:
            if spec.platform == platform and spec.operation == operation:
                return spec
        return None

    def operations(self, platform: str) -> list[str]:
        return [s.operation for s in self.ENDPOINTS if s.platform == platform]

    def route(self, platform: str, operation: str, values: dict[str, Any]) -> dict[str, Any]:
        spec = self.resolve(platform, operation)
        if spec is None:
            return {"ok": False, "error": f"no endpoint for {platform}/{operation}"}
        missing = spec.missing_params(values)
        if missing:
            return {"ok": False, "error": f"missing params: {', '.join(missing)}", "endpoint": spec.to_dict()}
        if self.credits_used + spec.credits > self.credits_per_month:
            return {"ok": False, "error": "credit budget exhausted", "endpoint": spec.to_dict()}
        self.credits_used += spec.credits
        request = {"endpoint": spec.to_dict(), "url": spec.build_url(values), "api_key_set": bool(self.api_key)}
        self.calls.append(request)
        if self.transport is not None:
            payload = self.transport(spec, values)
            request["payload"] = payload
        request["ok"] = True
        return request

    @property
    def credits_remaining(self) -> int:
        return max(0, self.credits_per_month - self.credits_used)
