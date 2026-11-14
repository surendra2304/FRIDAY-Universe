"""
VyralX/app/services/creator_monetization_engine.py — VyralX Creator Monetization Engine.

Monetization intelligence for content creators: revenue optimization, sponsorship
matching, affiliate management, pricing strategy, and earnings forecasting across
platforms and content types.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field

from fastapi import APIRouter

router = APIRouter()


@dataclass
class RevenueStream:
    """A revenue stream."""
    stream_id: str
    creator_id: str
    stream_type: str = ""  # ads, sponsorship, affiliate, subscription, merchandise, tips
    platform: str = ""
    earnings_today: float = 0.0
    earnings_week: float = 0.0
    earnings_month: float = 0.0
    growth_rate: float | None = None
    data_status: str = "no_data"
    data_note: str = ""
    active: bool = True


@dataclass
class SponsorshipMatch:
    """A sponsorship match."""
    match_id: str
    creator_id: str
    sponsor_name: str = ""
    sponsor_industry: str = ""
    estimated_value: float | None = None
    match_score: float | None = None
    reason: str = ""
    data_status: str = "no_data"
    data_note: str = ""
    status: str = "pending"  # pending, contacted, agreed, completed


@dataclass
class AffiliateCampaign:
    """An affiliate campaign."""
    campaign_id: str
    creator_id: str
    merchant: str = ""
    product_category: str = ""
    commission_rate: float = 0.0
    clicks: int = 0
    conversions: int = 0
    earnings: float = 0.0
    epc: float = 0.0  # earnings per click
    status: str = "active"  # active, paused, ended


@dataclass
class SubscriptionTier:
    """A subscription tier."""
    tier_id: str
    creator_id: str
    tier_name: str = ""
    price_monthly: float = 0.0
    benefits: list[str] = field(default_factory=list)
    subscribers: int = 0
    monthly_revenue: float = 0.0
    churn_rate: float | None = None


@dataclass
class PricingStrategy:
    """A pricing strategy recommendation."""
    strategy_id: str
    creator_id: str
    content_type: str = ""
    recommended_price: float = 0.0
    current_price: float = 0.0
    competitive_range: tuple[float, float] = (0.0, 0.0)
    confidence: float | None = None
    reasoning: str = ""
    data_status: str = "no_data"
    data_note: str = ""


@dataclass
class EarningsForecast:
    """An earnings forecast."""
    forecast_id: str
    creator_id: str
    horizon_days: int = 30
    projected_earnings: float = 0.0
    confidence_interval: tuple[float, float] = (0.0, 0.0)
    growth_projection: float | None = None
    data_status: str = "estimated_from_inputs"
    data_note: str = ""
    risk_factors: list[str] = field(default_factory=list)
    created_at: float = 0.0


@dataclass
class OptimizationRecommendation:
    """An optimization recommendation."""
    recommendation_id: str
    creator_id: str
    area: str = ""  # revenue, audience, content, sponsorship, pricing
    description: str = ""
    potential_impact: float | None = None
    implementation_difficulty: str = "medium"  # easy, medium, hard
    estimated_time: str = "1 week"


class CreatorMonetizationEngine:
    """Creator monetization intelligence engine."""

    def __init__(self):
        self._streams: dict[str, RevenueStream] = {}
        self._matches: list[SponsorshipMatch] = []
        self._campaigns: dict[str, AffiliateCampaign] = {}
        self._tiers: dict[str, SubscriptionTier] = {}
        self._strategies: list[PricingStrategy] = []
        self._forecasts: list[EarningsForecast] = []
        self._recommendations: list[OptimizationRecommendation] = []

    def add_revenue_stream(
        self,
        creator_id: str,
        stream_type: str,
        platform: str,
        earnings_today: float = 0.0,
    ) -> RevenueStream:
        """Add a revenue stream."""
        stream = RevenueStream(
            stream_id=hashlib.md5(
                f"stream:{creator_id}:{stream_type}:{time.time()}".encode()
            ).hexdigest()[:12],
            creator_id=creator_id,
            stream_type=stream_type,
            platform=platform,
            earnings_today=earnings_today,
            earnings_week=earnings_today * 7,
            earnings_month=earnings_today * 30,
            # Week/month are flat extrapolations of the supplied daily
            # figure (x7 / x30). No earnings history exists, so no growth
            # rate can be computed. (TASK-REL-020: previously derived
            # from an md5 hash.)
            growth_rate=None,
            data_status="no_data",
            data_note=(
                "growth_rate unavailable: only a single daily earnings "
                "figure was supplied; week/month are flat x7/x30 "
                "extrapolations of it."
            ),
        )
        self._streams[stream.stream_id] = stream
        return stream

    def match_sponsor(
        self,
        creator_id: str,
        sponsor_name: str,
        sponsor_industry: str = "",
    ) -> SponsorshipMatch:
        """Match a creator with a sponsor."""
        match = SponsorshipMatch(
            match_id=hashlib.md5(
                f"match:{creator_id}:{sponsor_name}:{time.time()}".encode()
            ).hexdigest()[:12],
            creator_id=creator_id,
            sponsor_name=sponsor_name,
            sponsor_industry=sponsor_industry,
            # No audience-overlap or rate-card data exists for either
            # party. (TASK-REL-020: value/score were previously derived
            # from md5 hashes, and the reason asserted an audience
            # overlap that was never measured.)
            estimated_value=None,
            match_score=None,
            reason=(
                "Match recorded for manual review; audience overlap with "
                f"the {sponsor_industry or 'sponsor'} market has not been "
                "measured."
            ),
            data_status="no_data",
            data_note=(
                "estimated_value and match_score unavailable: no audience "
                "or sponsorship rate data is connected."
            ),
        )

        self._matches.append(match)
        return match

    def create_affiliate_campaign(
        self,
        creator_id: str,
        merchant: str,
        product_category: str = "",
        commission_rate: float = 0.1,
    ) -> AffiliateCampaign:
        """Create an affiliate campaign."""
        campaign = AffiliateCampaign(
            campaign_id=hashlib.md5(
                f"campaign:{creator_id}:{merchant}:{time.time()}".encode()
            ).hexdigest()[:12],
            creator_id=creator_id,
            merchant=merchant,
            product_category=product_category,
            commission_rate=commission_rate,
        )
        self._campaigns[campaign.campaign_id] = campaign
        return campaign

    def create_subscription_tier(
        self,
        creator_id: str,
        tier_name: str,
        price_monthly: float,
        benefits: list[str] | None = None,
    ) -> SubscriptionTier:
        """Create a subscription tier."""
        tier = SubscriptionTier(
            tier_id=hashlib.md5(
                f"tier:{creator_id}:{tier_name}:{time.time()}".encode()
            ).hexdigest()[:12],
            creator_id=creator_id,
            tier_name=tier_name,
            price_monthly=price_monthly,
            benefits=benefits or ["Exclusive content", "Ad-free experience", "Community access"],
            subscribers=0,
            monthly_revenue=0.0,
            # No subscribers exist yet, so no churn rate exists.
            # (TASK-REL-020: previously a constant 0.05.)
            churn_rate=None,
        )
        self._tiers[tier.tier_id] = tier
        return tier

    def recommend_pricing(self, creator_id: str, content_type: str, current_price: float) -> PricingStrategy:
        """Recommend a pricing strategy."""
        competitive_low = current_price * 0.5
        competitive_high = current_price * 2.0
        recommended = (competitive_low + competitive_high) / 2

        strategy = PricingStrategy(
            strategy_id=hashlib.md5(
                f"strategy:{creator_id}:{content_type}:{time.time()}".encode()
            ).hexdigest()[:12],
            creator_id=creator_id,
            content_type=content_type,
            recommended_price=recommended,
            current_price=current_price,
            competitive_range=(competitive_low, competitive_high),
            # (TASK-REL-020: confidence was previously derived from an
            # md5 hash, and the reasoning claimed a competitive analysis
            # and willingness-to-pay study that do not exist. The range
            # below is plain arithmetic on the supplied current price.)
            confidence=None,
            reasoning=(
                "Range is arithmetic on the current price only "
                "(0.5x to 2.0x; midpoint recommended). No competitor "
                "pricing or willingness-to-pay data is available."
            ),
            data_status="no_data",
            data_note=(
                "confidence unavailable: no market data is connected."
            ),
        )

        self._strategies.append(strategy)
        return strategy

    def forecast_earnings(self, creator_id: str, horizon_days: int = 30) -> EarningsForecast:
        """Forecast creator earnings."""
        total_today = sum(s.earnings_today for s in self._streams.values() if s.creator_id == creator_id)
        projected = total_today * horizon_days * (1.1 ** (horizon_days / 30))

        forecast = EarningsForecast(
            forecast_id=hashlib.md5(
                f"forecast:{creator_id}:{time.time()}".encode()
            ).hexdigest()[:12],
            creator_id=creator_id,
            horizon_days=horizon_days,
            projected_earnings=projected,
            confidence_interval=(projected * 0.7, projected * 1.3),
            # (TASK-REL-020: growth_projection was previously derived
            # from an md5 hash of the creator id.)
            growth_projection=None,
            data_status="estimated_from_inputs",
            data_note=(
                "Projection = (sum of the creator's stored streams' "
                "daily earnings) x horizon_days x fixed 1.1-per-month "
                "compounding assumption; interval is a flat +/-30% band. "
                "These are stated assumptions over supplied figures, not "
                "measured growth; growth_projection is unavailable."
            ),
            risk_factors=["Market competition", "Audience engagement changes", "Platform policy changes"],
            created_at=time.time(),
        )

        self._forecasts.append(forecast)
        return forecast

    def generate_recommendation(self, creator_id: str) -> list[OptimizationRecommendation]:
        """Generate optimization recommendations."""
        recommendations = []

        recommendations.append(OptimizationRecommendation(
            recommendation_id=hashlib.md5(f"rec:{creator_id}:revenue:{time.time()}".encode()).hexdigest()[:12],
            creator_id=creator_id,
            area="revenue",
            description="Diversify revenue streams to reduce platform dependency",
            potential_impact=None,
            implementation_difficulty="medium",
            estimated_time="2 weeks",
        ))

        recommendations.append(OptimizationRecommendation(
            recommendation_id=hashlib.md5(f"rec:{creator_id}:sponsorship:{time.time()}".encode()).hexdigest()[:12],
            creator_id=creator_id,
            area="sponsorship",
            description="Pursue premium sponsorship deals in your niche",
            potential_impact=None,
            implementation_difficulty="hard",
            estimated_time="1 month",
        ))

        recommendations.append(OptimizationRecommendation(
            recommendation_id=hashlib.md5(f"rec:{creator_id}:pricing:{time.time()}".encode()).hexdigest()[:12],
            creator_id=creator_id,
            area="pricing",
            description="Test subscription tiers at different price points",
            potential_impact=None,
            implementation_difficulty="easy",
            estimated_time="1 week",
        ))

        self._recommendations.extend(recommendations)
        return recommendations

    def get_report(self) -> dict:
        """Get monetization report."""
        total_creators = len(set(s.creator_id for s in self._streams.values()))
        total_earnings_month = sum(s.earnings_month for s in self._streams.values())
        total_earnings_today = sum(s.earnings_today for s in self._streams.values())

        return {
            "total_creators": total_creators,
            "total_streams": len(self._streams),
            "total_sponsorship_matches": len(self._matches),
            "total_affiliate_campaigns": len(self._campaigns),
            "total_subscription_tiers": len(self._tiers),
            "total_forecasts": len(self._forecasts),
            "total_recommendations": len(self._recommendations),
            "total_earnings_today": total_earnings_today,
            "total_earnings_month": total_earnings_month,
            "avg_growth_rate": (
                sum(s.growth_rate for s in self._streams.values() if s.growth_rate is not None)
                / max(1, sum(1 for s in self._streams.values() if s.growth_rate is not None))
                if any(s.growth_rate is not None for s in self._streams.values()) else None
            ),
            "revenue_by_type": {
                stream_type: sum(s.earnings_month for s in self._streams.values() if s.stream_type == stream_type)
                for stream_type in set(s.stream_type for s in self._streams.values())
            },
            "recent_forecasts": [
                {
                    "creator": f.creator_id,
                    "horizon_days": f.horizon_days,
                    "projected": f.projected_earnings,
                    "growth": f.growth_projection,
                }
                for f in self._forecasts[-5:]
            ],
        }


# Module-level singleton
monetization_engine = CreatorMonetizationEngine()


# ── API Routes ──────────────────────────────────────────────────────────────


@router.post("/api/v1/vyralx/creator/monetization/streams")
async def add_revenue_stream(payload: dict):
    """Add a revenue stream."""
    stream = monetization_engine.add_revenue_stream(
        creator_id=payload["creator_id"],
        stream_type=payload["stream_type"],
        platform=payload["platform"],
        earnings_today=payload.get("earnings_today", 0.0),
    )
    return {"stream_id": stream.stream_id, "type": stream.stream_type, "earnings_today": stream.earnings_today}


@router.post("/api/v1/vyralx/creator/monetization/sponsors")
async def match_sponsor(payload: dict):
    """Match a creator with a sponsor."""
    match = monetization_engine.match_sponsor(
        creator_id=payload["creator_id"],
        sponsor_name=payload["sponsor_name"],
        sponsor_industry=payload.get("sponsor_industry", ""),
    )
    return {"match_id": match.match_id, "sponsor": match.sponsor_name, "score": match.match_score, "estimated_value": match.estimated_value, "reason": match.reason, "data_status": match.data_status, "data_note": match.data_note}


@router.post("/api/v1/vyralx/creator/monetization/campaigns")
async def create_affiliate_campaign(payload: dict):
    """Create an affiliate campaign."""
    campaign = monetization_engine.create_affiliate_campaign(
        creator_id=payload["creator_id"],
        merchant=payload["merchant"],
        product_category=payload.get("product_category", ""),
        commission_rate=payload.get("commission_rate", 0.1),
    )
    return {"campaign_id": campaign.campaign_id, "merchant": campaign.merchant, "rate": campaign.commission_rate}


@router.get("/api/v1/vyralx/creator/monetization/forecast/{creator_id}")
async def forecast_earnings(creator_id: str, horizon_days: int = 30):
    """Forecast creator earnings."""
    forecast = monetization_engine.forecast_earnings(creator_id, horizon_days)
    return {
        "projected": forecast.projected_earnings,
        "confidence_low": forecast.confidence_interval[0],
        "confidence_high": forecast.confidence_interval[1],
        "growth": forecast.growth_projection,
        "data_status": forecast.data_status,
        "data_note": forecast.data_note,
    }


@router.get("/api/v1/vyralx/creator/monetization/report")
async def get_report():
    """Get monetization report."""
    return monetization_engine.get_report()
