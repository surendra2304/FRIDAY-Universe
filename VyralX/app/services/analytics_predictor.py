"""
VyralX/app/services/analytics_predictor.py — VyralX Analytics Predictor.

HONESTY CONTRACT (TASK-VYR-002, following the TASK-REL-020 fleet standard):

This module is a **deterministic heuristic estimator over caller-supplied
inputs**. It is not trained on, or calibrated against, any measured channel
data — VyralX has no analytics feed wired into it, and nothing in the fleet
calls it in production today. It therefore follows the same rules as the
REL-020-remediated VyralX surfaces:

- every result carries ``data_status`` and a ``basis`` naming the exact
  assumptions/formula the number came from;
- ``confidence`` is always ``None``: a confidence figure would claim
  calibration against real outcomes, and no such data exists here;
- NO randomness anywhere — the same inputs always produce the same outputs
  (the previous retention forecaster added ``random.uniform`` jitter to a
  reported curve, and estimated watch hours from a silent "100 viewers"
  constant; both are removed);
- a quantity that cannot be derived from the supplied inputs is ``None``
  with ``data_status="no_data"``, never an invented constant.

Capabilities:
1. View Count Estimation: heuristic estimate of future view counts
2. Audience Retention Modelling: deterministic retention-curve model
3. Video Performance Scoring: heuristic pre-publish score over the above
4. Channel Growth Projection: compound-growth scenario over stated rates
5. Competitor Analysis: rule-based gap notes over caller-supplied figures
6. Trend Detection: keyword frequencies measured from supplied results
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# The view-estimate model's stated assumptions. These are heuristic choices,
# not measurements; they are surfaced verbatim in every prediction's basis.
_BASE_VIEW_FRACTION = 0.10  # assumes 10% of subscribers watch a new upload
_HIGH_DEMAND_NICHES = {"technology", "gaming", "finance", "education", "howto"}
_LIFESTYLE_NICHES = {"lifestyle", "beauty", "fashion"}


@dataclass
class ViewPrediction:
    """Heuristic view-count estimate for a video (not a measured forecast)."""
    title: str
    predicted_views: int
    predicted_ctr: float
    growth_rate: float
    confidence: float | None  # always None — no calibration data exists
    time_to_peak: float  # hours
    data_status: str = "estimated_from_inputs"
    basis: str = ""


@dataclass
class RetentionForecast:
    """Deterministic retention-curve model output."""
    title: str
    predicted_retention_curve: list[float]
    estimated_watch_hours: float | None  # None unless a viewer estimate is supplied
    drop_off_points: list[float]  # timestamps where big drops happen
    engagement_score: float
    data_status: str = "estimated_from_inputs"
    basis: str = ""


@dataclass
class ChannelGrowthModel:
    """Compound-growth scenario projection (stated rates, not a forecast)."""
    channel_name: str
    current_subscribers: int
    predicted_subscribers: int
    growth_rate: float
    projected_months: int
    confidence: float | None  # always None — no calibration data exists
    risk_factors: list[str]
    data_status: str = "estimated_from_inputs"
    basis: str = ""
    assumptions: list[str] = field(default_factory=list)


@dataclass
class CompetitorInsight:
    """Rule-based gap notes over caller-supplied competitor figures."""
    competitor_name: str
    total_videos: int
    avg_views: int
    upload_frequency: float  # videos per week
    top_topics: list[str]
    engagement_rate: float
    subscriber_growth: float
    gap_analysis: str
    data_status: str = "caller_supplied"
    basis: str = "All figures are the caller's own inputs, echoed unchanged; gap notes are threshold rules over those inputs. No competitor data is fetched or measured by VyralX."


class AnalyticsPredictor:
    """Heuristic predictive analytics for YouTube channel planning.

    Every method is a pure function of its inputs (plus the module's stated
    heuristic constants). See the module docstring for the honesty contract.
    """

    def __init__(self):
        self._predictions: list[ViewPrediction] = []
        self._forecasts: list[RetentionForecast] = []
        self._growth_models: dict[str, ChannelGrowthModel] = {}
        self._competitor_insights: dict[str, CompetitorInsight] = {}

    # ── View Count Estimation ──────────────────────────────────────────────

    def predict_views(
        self,
        title: str,
        description: str,
        tags: list[str],
        channel_subscribers: int,
        niche: str = "",
        competitor_avg_views: int = 10000,
    ) -> ViewPrediction:
        """Estimate view count for a video before publishing.

        Heuristic model: base = 10% of the channel's subscribers, scaled by
        title/description/tag/niche rule factors listed in the result basis.
        ``competitor_avg_views`` is accepted for signature compatibility and
        is not used by the model (it never was); it is named in the basis so
        no reader believes it influenced the estimate.
        """
        # Base views from channel size
        base_views = channel_subscribers * _BASE_VIEW_FRACTION

        # Title quality factor
        title_factor = 1.0
        if len(title) < 30:
            title_factor *= 0.9  # Short titles underperform
        if len(title) > 80:
            title_factor *= 0.85  # Too long
        if any(w in title.lower() for w in ["how", "tutorial", "guide", "best", "review"]):
            title_factor *= 1.2  # How-to titles perform well
        if any(w in title.lower() for w in ["vlog", "day in the life"]):
            title_factor *= 0.8  # Vlogs underperform

        # Description quality
        desc_factor = 1.0
        if len(description) > 200:
            desc_factor *= 1.1
        if len(description) < 50:
            desc_factor *= 0.9

        # Tag quality
        tag_factor = 1.0
        if len(tags) > 10:
            tag_factor *= 0.95
        if len(tags) < 3:
            tag_factor *= 0.8
        if niche and any(niche.lower() in t.lower() for t in tags):
            tag_factor *= 1.15

        # Niche factor
        niche_factor = 1.0
        if niche.lower() in _HIGH_DEMAND_NICHES:
            niche_factor *= 1.3
        elif niche.lower() in _LIFESTYLE_NICHES:
            niche_factor *= 1.1

        # Calculate estimated views
        predicted = base_views * title_factor * desc_factor * tag_factor * niche_factor

        # CTR estimate (same heuristic factors; not a measured click rate)
        predicted_ctr = min(0.15, 0.05 * title_factor * niche_factor)

        # Growth rate (views per day in first week, per the model's 30% rule)
        growth_rate = predicted * 0.3  # 30% of views in first week

        # Time to peak (model rule, not an observation)
        time_to_peak = 48.0 if niche_factor > 1.2 else 72.0

        prediction = ViewPrediction(
            title=title,
            predicted_views=int(predicted),
            predicted_ctr=predicted_ctr,
            growth_rate=growth_rate,
            confidence=None,
            time_to_peak=time_to_peak,
            data_status="estimated_from_inputs",
            basis=(
                "Heuristic estimate, not a measured forecast: base = "
                f"{_BASE_VIEW_FRACTION:.0%} of channel_subscribers "
                f"({channel_subscribers}) x title_factor {title_factor:.3f} "
                f"x description_factor {desc_factor:.3f} x tag_factor "
                f"{tag_factor:.3f} x niche_factor {niche_factor:.3f}. "
                "CTR assumes a 5% base scaled by the title/niche factors. "
                "competitor_avg_views is accepted but not used by the model. "
                "confidence is null: the model is not calibrated against "
                "measured channel outcomes."
            ),
        )

        self._predictions.append(prediction)
        return prediction

    # ── Retention Modelling ────────────────────────────────────────────────

    def forecast_retention(
        self,
        title: str,
        video_length: float,  # seconds
        estimated_quality: float = 0.5,  # 0-1, caller-supplied
        estimated_hook_strength: float = 0.5,  # 0-1, caller-supplied
        estimated_viewers: int | None = None,
    ) -> RetentionForecast:
        """Model a retention curve for a video, deterministically.

        The curve is a fixed decline model over the caller's quality/hook
        estimates — identical inputs always give the identical curve (the
        previous implementation added random jitter to a reported number).

        Watch hours are only computed when the caller supplies
        ``estimated_viewers``: watch_hours = mean retention x video hours x
        viewers. Without a viewer estimate the value is None (no_data) —
        the previous silent "x 100 viewers" constant is gone.
        """
        # Generate modelled retention curve
        segments = min(50, int(video_length / 5))  # 5-second segments
        curve = []

        # Initial retention (first 30 seconds)
        initial_retention = 0.7 + estimated_hook_strength * 0.2
        curve.append(initial_retention)

        # Decline rate based on quality
        decline_rate = 0.02 + (1.0 - estimated_quality) * 0.03

        for i in range(1, segments):
            # Slower decline for high quality
            segment_decline = decline_rate * (0.5 + (1.0 - estimated_quality) * 0.5)

            retention = curve[-1] - segment_decline
            retention = max(0.1, min(1.0, retention))
            curve.append(retention)

        # Estimate watch hours — only from a caller-supplied viewer estimate
        if estimated_viewers is None:
            watch_hours = None
            watch_note = (
                "estimated_watch_hours is null: no viewer estimate was "
                "supplied, and watch hours cannot be derived without one."
            )
        else:
            mean_retention = sum(curve) / len(curve) if curve else 0.0
            watch_hours = mean_retention * (video_length / 3600.0) * estimated_viewers
            watch_note = (
                f"estimated_watch_hours = mean retention {mean_retention:.3f} "
                f"x video length {video_length / 3600.0:.3f}h x caller-supplied "
                f"estimated_viewers {estimated_viewers}."
            )

        # Find drop-off points (big declines)
        drop_offs = []
        for i in range(1, len(curve)):
            if curve[i-1] - curve[i] > 0.05:
                drop_offs.append(i * 5)  # Convert to seconds

        # Engagement score
        engagement_score = sum(curve) / len(curve) * estimated_quality if curve else 0.0

        forecast = RetentionForecast(
            title=title,
            predicted_retention_curve=curve,
            estimated_watch_hours=watch_hours,
            drop_off_points=drop_offs,
            engagement_score=engagement_score,
            data_status="estimated_from_inputs" if estimated_viewers is not None else "no_data",
            basis=(
                "Deterministic decline model over caller-supplied quality "
                f"({estimated_quality}) and hook strength ({estimated_hook_strength}): "
                f"initial retention {initial_retention:.3f}, per-segment decline "
                f"derived from decline_rate {decline_rate:.4f}. No randomness. "
                + watch_note
            ),
        )

        self._forecasts.append(forecast)
        return forecast

    # ── Video Performance Scoring ───────────────────────────────────────────

    def score_video(
        self,
        title: str,
        description: str,
        tags: list[str],
        thumbnail_description: str,
        video_length: float,
        channel_subscribers: int,
    ) -> dict[str, Any]:
        """Score a video's likely performance before publishing.

        The score is a weighted blend of simple input ratios and the two
        heuristic models above; it is labelled as such and carries no
        confidence claim.
        """
        prediction = self.predict_views(
            title=title,
            description=description,
            tags=tags,
            channel_subscribers=channel_subscribers,
        )

        forecast = self.forecast_retention(
            title=title,
            video_length=video_length,
        )

        # Overall score
        title_score = min(1.0, len(title) / 60.0)
        desc_score = min(1.0, len(description) / 300.0)
        tag_score = min(1.0, len(tags) / 10.0)
        retention_score = forecast.engagement_score

        # The previous blend included the fabricated confidence figure as a
        # 10% term; that term is removed and the remaining weights are
        # renormalized (they now sum to 1.0 over the four real inputs).
        overall_score = (
            title_score * 0.28 +
            desc_score * 0.17 +
            tag_score * 0.17 +
            retention_score * 0.38
        )

        return {
            "title": title,
            "overall_score": overall_score * 100,
            "predicted_views": prediction.predicted_views,
            "predicted_ctr": prediction.predicted_ctr,
            "retention_score": retention_score,
            "title_score": title_score,
            "description_score": desc_score,
            "tag_score": tag_score,
            "recommendation": (
                "Publish immediately" if overall_score > 0.7 else
                "Optimize and republish" if overall_score > 0.4 else
                "Significant improvements needed"
            ),
            "data_status": "estimated_from_inputs",
            "basis": (
                "Heuristic score: title/description/tag length ratios and the "
                "retention model's engagement score, weighted 0.28/0.17/0.17/0.38. "
                "The recommendation is a threshold rule over that score, not "
                "measured performance advice. " + prediction.basis
            ),
        }

    # ── Channel Growth Projection ────────────────────────────────────────────

    def model_channel_growth(
        self,
        channel_name: str,
        current_subscribers: int,
        upload_frequency: float,  # videos per week
        avg_views: int,
        engagement_rate: float,
        months: int = 6,
    ) -> ChannelGrowthModel:
        """Project channel growth as a compound-growth scenario.

        The monthly rate is assembled from the stated heuristic assumptions
        in the result (5% base, engagement and upload terms, 30% cap) and
        compounded over ``months``. It is a scenario, not a forecast:
        confidence is null because nothing here is calibrated.
        """
        # Growth rate based on engagement and upload frequency
        base_growth = 0.05  # 5% monthly base growth (assumption)

        # Engagement boost
        engagement_boost = engagement_rate * 2.0  # 0-2
        upload_boost = min(0.5, upload_frequency * 0.1)  # More uploads = more growth

        monthly_growth = base_growth + engagement_boost * 0.02 + upload_boost

        # Cap growth
        monthly_growth = min(0.3, monthly_growth)

        # Project subscribers
        predicted = current_subscribers * (1.0 + monthly_growth) ** months

        # Risk factors
        risk_factors = []
        if engagement_rate < 0.03:
            risk_factors.append("Low engagement rate may slow growth")
        if upload_frequency < 1.0:
            risk_factors.append("Low upload frequency limits growth")
        if avg_views < 1000:
            risk_factors.append("Low average views indicate content issues")

        assumptions = [
            "Base monthly growth assumed at 5%.",
            f"Engagement term: engagement_rate {engagement_rate} x 2 x 0.02 = {engagement_boost * 0.02:.4f}.",
            f"Upload term: min(0.5, upload_frequency {upload_frequency} x 0.1) = {upload_boost:.4f}.",
            "Monthly growth capped at 30%; compounded monthly over the projection window.",
        ]

        model = ChannelGrowthModel(
            channel_name=channel_name,
            current_subscribers=current_subscribers,
            predicted_subscribers=int(predicted),
            growth_rate=monthly_growth,
            projected_months=months,
            confidence=None,
            risk_factors=risk_factors,
            data_status="estimated_from_inputs",
            basis=(
                "Compound-growth scenario over stated heuristic assumptions, "
                "not a measured forecast; confidence is null (no calibration "
                "against real channel outcomes)."
            ),
            assumptions=assumptions,
        )

        self._growth_models[channel_name] = model
        return model

    # ── Competitor Analysis ──────────────────────────────────────────────────

    def analyze_competitor(
        self,
        competitor_name: str,
        total_videos: int,
        avg_views: int,
        upload_frequency: float,
        top_topics: list[str],
        engagement_rate: float,
        subscriber_growth: float,
        your_channel_subscribers: int = 0,
    ) -> CompetitorInsight:
        """Analyze a competitor channel and identify gaps.

        All figures are the caller's own inputs, echoed unchanged — VyralX
        fetches no competitor data here. The gap notes are threshold rules
        over those inputs.
        """
        # Gap analysis
        gaps = []

        if engagement_rate > 0.05:
            gaps.append(f"Competitor has high engagement ({engagement_rate:.1%}). Focus on engagement boosting.")

        if upload_frequency > 2.0:
            gaps.append(f"Competitor uploads {upload_frequency}x/week. Consider increasing frequency.")

        if avg_views > 10000:
            gaps.append(f"Competitor averages {avg_views} views. Analyze their content strategy.")

        gap_analysis = "; ".join(gaps) if gaps else "No significant gaps detected"

        insight = CompetitorInsight(
            competitor_name=competitor_name,
            total_videos=total_videos,
            avg_views=avg_views,
            upload_frequency=upload_frequency,
            top_topics=top_topics,
            engagement_rate=engagement_rate,
            subscriber_growth=subscriber_growth,
            gap_analysis=gap_analysis,
        )

        self._competitor_insights[competitor_name] = insight
        return insight

    # ── Trend Detection ─────────────────────────────────────────────────────

    def detect_trends(
        self,
        search_results: list[dict],
        niche: str = "",
    ) -> list[dict]:
        """Detect frequent keywords in caller-supplied search results.

        Frequencies are measured from the supplied titles — this is a count
        over the caller's data, not a platform trend signal. (The previous
        implementation reported ``trend_score = count * 0.2``, an arbitrary
        scaling presented as a score; it is replaced by the raw frequency
        and its share of the supplied results.)
        """
        trends = []

        title_keywords: dict[str, int] = {}

        for result in search_results:
            title = result.get("title", "")

            # Count keywords
            for word in title.split():
                if len(word) > 3:
                    title_keywords[word.lower()] = title_keywords.get(word.lower(), 0) + 1

        # Find most frequent keywords
        sorted_keywords = sorted(
            title_keywords.items(),
            key=lambda x: -x[1]
        )

        total = len(search_results)
        for keyword, count in sorted_keywords[:10]:
            if count >= 3:  # Must appear at least 3 times
                trends.append({
                    "keyword": keyword,
                    "frequency": count,
                    "share_of_results": (count / total) if total else 0.0,
                    "suggestion": f"Consider creating content about '{keyword}'",
                    "data_status": "measured_from_inputs",
                    "basis": "Keyword frequency counted over the caller-supplied search result titles.",
                })

        return trends

    # ── Reporting ──────────────────────────────────────────────────────────

    def get_analytics_report(self) -> dict[str, Any]:
        """Summarize this predictor instance's heuristic estimates."""
        return {
            "total_predictions": len(self._predictions),
            "total_forecasts": len(self._forecasts),
            "growth_models": len(self._growth_models),
            "competitor_insights": len(self._competitor_insights),
            "avg_predicted_views": (
                sum(p.predicted_views for p in self._predictions) / len(self._predictions)
                if self._predictions else 0
            ),
            "data_status": "estimated_from_inputs",
            "data_note": (
                "Counts and averages describe this process's heuristic "
                "estimates (see AnalyticsPredictor docstring); they are not "
                "measured channel analytics."
            ),
        }
