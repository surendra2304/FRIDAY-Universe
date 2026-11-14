"""
Cortex/apps/api/src/cortex_api/multi_channel_attribution.py — Cortex Multi-Channel Attribution Modeler.

Model attribution across multiple marketing channels: first-touch, last-touch,
linear, time-decay, position-based (U-shaped), data-driven (Markov), and
custom attribution models with channel contribution analysis.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter()


@dataclass
class CustomerJourney:
    """A customer journey through marketing channels."""
    journey_id: str
    customer_id: str
    touches: list[dict] = field(default_factory=list)  # [{channel, timestamp, campaign, action}]
    conversion_value: float = 0.0
    conversion_timestamp: float = 0.0
    total_touches: int = 0
    channels_touched: list[str] = field(default_factory=list)


@dataclass
class ChannelContribution:
    """Contribution of a channel to conversions."""
    channel: str
    first_touch_credit: float = 0.0
    last_touch_credit: float = 0.0
    linear_credit: float = 0.0
    time_decay_credit: float = 0.0
    position_credit: float = 0.0
    data_driven_credit: float = 0.0
    avg_credit: float = 0.0
    assists: int = 0
    conversions: int = 0


@dataclass
class AttributionModel:
    """An attribution model configuration."""
    model_id: str
    name: str
    model_type: str  # first_touch, last_touch, linear, time_decay, position_based, data_driven, custom
    weights: dict = field(default_factory=dict)
    decay_factor: float = 0.5
    description: str = ""
    created_at: float = 0.0


@dataclass
class AttributionResult:
    """Result of attribution analysis."""
    model_id: str
    model_name: str
    model_type: str
    channel_contributions: list[ChannelContribution] = field(default_factory=list)
    total_attributed_value: float = 0.0
    conversions_analyzed: int = 0
    journeys_analyzed: int = 0
    avg_touches_per_conversion: float = 0.0
    top_channel: str = ""
    data_status: str = "measured"
    data_note: str = ""


@dataclass
class MarkovGraph:
    """Markov chain graph for data-driven attribution."""
    graph_id: str
    nodes: list[str] = field(default_factory=list)
    edges: dict = field(default_factory=dict)  # source → {target: probability}
    removal_effects: dict = field(default_factory=dict)  # channel → removal effect
    conversion_rate: float | None = None
    data_status: str = "no_data"
    data_note: str = ""


@dataclass
class AttributionComparison:
    """Comparison between attribution models."""
    journey_id: str
    models: dict = field(default_factory=dict)  # model_name → channel credits
    differences: dict = field(default_factory=dict)  # channel → difference across models


class MultiChannelAttributionModeler:
    """Multi-channel attribution modeling engine."""

    def __init__(self):
        self._journeys: dict[str, CustomerJourney] = {}
        self._models: dict[str, AttributionModel] = {}
        self._results: dict[str, AttributionResult] = {}
        self._markov_graphs: dict[str, MarkovGraph] = {}

        # Register default attribution models
        self._register_models()

    def _register_models(self):
        """Register default attribution models."""
        self._create_model("first_touch", "First Touch", "first_touch", description="100% credit to first interaction")
        self._create_model("last_touch", "Last Touch", "last_touch", description="100% credit to last interaction")
        self._create_model("linear", "Linear", "linear", description="Equal credit across all touches")
        self._create_model("time_decay", "Time Decay", "time_decay", description="Exponentially more credit to recent touches", decay_factor=0.5)
        self._create_model("position_based", "Position Based", "position_based", description="40% first, 40% last, 20% middle")

    def _create_model(
        self,
        model_type: str,
        name: str,
        mtype: str,
        description: str = "",
        decay_factor: float = 0.5,
    ) -> AttributionModel:
        """Create an attribution model."""
        model = AttributionModel(
            model_id=hashlib.md5(
                f"model:{model_type}:{time.time()}".encode()
            ).hexdigest()[:12],
            name=name,
            model_type=mtype,
            description=description,
            created_at=time.time(),
            decay_factor=decay_factor,
        )

        if mtype == "position_based":
            model.weights = {"first": 0.4, "middle": 0.2, "last": 0.4}
        elif mtype == "linear":
            model.weights = {"equal": 1.0}
        elif mtype == "time_decay":
            model.weights = {"decay": decay_factor}

        self._models[model.model_id] = model
        return model

    def add_journey(
        self,
        customer_id: str,
        touches: list[dict],
        conversion_value: float = 0.0,
        conversion_timestamp: float = 0.0,
    ) -> CustomerJourney:
        """Add a customer journey."""
        journey = CustomerJourney(
            journey_id=hashlib.md5(
                f"journey:{customer_id}:{time.time()}".encode()
            ).hexdigest()[:12],
            customer_id=customer_id,
            touches=touches,
            conversion_value=conversion_value,
            conversion_timestamp=conversion_timestamp or time.time(),
            total_touches=len(touches),
            channels_touched=list(set(t.get("channel", "") for t in touches)),
        )
        self._journeys[journey.journey_id] = journey
        return journey

    def attribute(
        self,
        model_type: str = "data_driven",
        journey_ids: list[str] | None = None,
    ) -> AttributionResult:
        """Run attribution analysis."""
        model = None
        for m in self._models.values():
            if m.model_type == model_type:
                model = m
                break

        if not model:
            # Create data-driven model
            model = self._create_model("data_driven", "Data Driven (Markov)", "data_driven", description="Markov chain based attribution")

        journeys = [
            self._journeys[jid] for jid in (journey_ids or list(self._journeys.keys()))
            if jid in self._journeys
        ]

        # Real data-driven weights: Markov removal effects computed from the
        # stored journeys (see build_markov_graph). Empty when no journey
        # data exists — data-driven credit is then honestly zero/unavailable
        # instead of a copy of the linear split. (TASK-REL-020)
        markov = self.build_markov_graph()
        removal_effects = markov.removal_effects
        total_effect = sum(removal_effects.values())
        removal_shares = (
            {ch: eff / total_effect for ch, eff in removal_effects.items()}
            if total_effect > 0
            else {}
        )

        # Aggregate channel contributions
        channel_stats: dict[str, dict] = {}

        for journey in journeys:
            for i, touch in enumerate(journey.touches):
                channel = touch.get("channel", "unknown")
                if channel not in channel_stats:
                    channel_stats[channel] = {
                        "first_touch": 0.0,
                        "last_touch": 0.0,
                        "linear": 0.0,
                        "time_decay": 0.0,
                        "position": 0.0,
                        "data_driven": 0.0,
                        "assists": 0,
                        "conversions": 0,
                        "touches": 0,
                    }

                # First touch
                if i == 0:
                    channel_stats[channel]["first_touch"] += journey.conversion_value

                # Last touch
                if i == len(journey.touches) - 1:
                    channel_stats[channel]["last_touch"] += journey.conversion_value

                # Linear
                channel_stats[channel]["linear"] += journey.conversion_value / max(1, len(journey.touches))

                # Time decay
                decay_weight = model.decay_factor ** (len(journey.touches) - i - 1)
                total_decay = sum(model.decay_factor ** (len(journey.touches) - j - 1) for j in range(len(journey.touches)))
                channel_stats[channel]["time_decay"] += journey.conversion_value * decay_weight / max(1, total_decay)

                # Position based
                if i == 0:
                    channel_stats[channel]["position"] += journey.conversion_value * 0.4
                elif i == len(journey.touches) - 1:
                    channel_stats[channel]["position"] += journey.conversion_value * 0.4
                else:
                    channel_stats[channel]["position"] += journey.conversion_value * 0.2 / max(1, len(journey.touches) - 2)

                channel_stats[channel]["assists"] += 1

                channel_stats[channel]["touches"] += 1

            # Data driven (Markov removal effects): distribute this
            # journey's conversion value across its channels in proportion
            # to their removal-effect shares.
            if journey.conversion_value > 0 and removal_shares:
                journey_channels = [
                    ch for ch in journey.channels_touched if ch in removal_shares
                ]
                denom = sum(removal_shares[ch] for ch in journey_channels)
                if denom > 0:
                    for ch in journey_channels:
                        channel_stats[ch]["data_driven"] += (
                            journey.conversion_value * removal_shares[ch] / denom
                        )

            # Mark conversions
            if journey.channels_touched:
                for ch in journey.channels_touched:
                    if ch in channel_stats:
                        channel_stats[ch]["conversions"] += 1

        # Build contributions
        contributions = []
        for channel, stats in channel_stats.items():
            avg_credit = sum([
                stats["first_touch"],
                stats["last_touch"],
                stats["linear"],
                stats["time_decay"],
                stats["position"],
                stats["data_driven"],
            ]) / 6

            contributions.append(ChannelContribution(
                channel=channel,
                first_touch_credit=stats["first_touch"],
                last_touch_credit=stats["last_touch"],
                linear_credit=stats["linear"],
                time_decay_credit=stats["time_decay"],
                position_credit=stats["position"],
                data_driven_credit=stats["data_driven"],
                avg_credit=avg_credit,
                assists=stats["assists"],
                conversions=stats["conversions"],
            ))

        contributions.sort(key=lambda c: -c.avg_credit)

        total_value = sum(c.avg_credit for c in contributions)
        avg_touches = sum(j.total_touches for j in journeys) / max(1, len(journeys))

        if removal_shares:
            dd_status = "estimated_from_inputs"
            dd_note = (
                "data_driven credit uses Markov removal effects computed "
                "from the stored journeys."
            )
        else:
            dd_status = "no_data"
            dd_note = (
                "data_driven (Markov removal-effect) credit unavailable: "
                "no stored journeys with conversions, so data_driven "
                "credits are 0. Other models are computed from the stored "
                "journeys."
            )

        result = AttributionResult(
            model_id=model.model_id,
            model_name=model.name,
            model_type=model.model_type,
            channel_contributions=contributions,
            total_attributed_value=total_value,
            conversions_analyzed=len(journeys),
            journeys_analyzed=len(journeys),
            avg_touches_per_conversion=avg_touches,
            top_channel=contributions[0].channel if contributions else "",
            data_status=dd_status if model_type == "data_driven" else "measured",
            data_note=dd_note if model_type == "data_driven" else (
                "Credits computed from the stored journeys."
            ),
        )

        self._results[result.model_id] = result
        return result

    # ── Markov helpers (TASK-REL-020: real removal effects) ──────────────
    _START = "__START__"
    _CONV = "__CONVERSION__"
    _NULL = "__NULL__"

    @staticmethod
    def _journey_path(journey: CustomerJourney, exclude_channel: str | None = None) -> list[str]:
        """State path for a journey: START, channels..., terminal.

        A journey counts as converted when it carries a conversion value
        (the only conversion signal in the stored data model).

        Removal-effect convention (the standard Markov attribution one):
        when a channel is excluded, any journey that passed through it is
        treated as lost — its path truncates just before the channel and
        ends in NULL.
        """
        cls = MultiChannelAttributionModeler
        channels: list[str] = []
        for t in journey.touches:
            channel = t.get("channel", "unknown")
            if exclude_channel is not None and channel == exclude_channel:
                return [cls._START, *channels, cls._NULL]
            channels.append(channel)
        terminal = cls._CONV if journey.conversion_value > 0 else cls._NULL
        return [cls._START, *channels, terminal]

    def _transition_probs(self, exclude_channel: str | None = None) -> dict[str, dict[str, float]]:
        """Empirical transition probabilities over journey paths."""
        counts: dict[str, dict[str, int]] = {}
        for journey in self._journeys.values():
            path = self._journey_path(journey, exclude_channel)
            for src, dst in zip(path, path[1:]):
                row = counts.setdefault(src, {})
                row[dst] = row.get(dst, 0) + 1
        probs: dict[str, dict[str, float]] = {}
        for src, row in counts.items():
            total = sum(row.values())
            if total > 0:
                probs[src] = {dst: c / total for dst, c in row.items()}
        return probs

    def _conversion_probability(self, probs: dict[str, dict[str, float]]) -> float:
        """Probability that a path starting at START ends in CONVERSION.

        Solved by value iteration over the transient states.
        """
        transient = [st for st in probs if st not in (self._CONV, self._NULL)]
        values = {st: 0.0 for st in transient}
        for _ in range(1000):
            delta = 0.0
            new_values = {}
            for st in transient:
                v = 0.0
                for dst, prob in probs[st].items():
                    if dst == self._CONV:
                        v += prob
                    elif dst == self._NULL:
                        continue
                    else:
                        v += prob * values.get(dst, 0.0)
                new_values[st] = v
                delta = max(delta, abs(v - values[st]))
            values = new_values
            if delta < 1e-10:
                break
        start_row = probs.get(self._START, {})
        total = 0.0
        for dst, prob in start_row.items():
            if dst == self._CONV:
                total += prob
            elif dst != self._NULL:
                total += prob * values.get(dst, 0.0)
        return total

    def build_markov_graph(self) -> MarkovGraph:
        """Build a Markov chain graph for data-driven attribution.

        Transition probabilities, the conversion rate and the removal
        effects are all computed from the stored journeys. A channel's
        removal effect is 1 - P(convert without the channel) /
        P(convert with all channels), the standard Markov attribution
        definition. (TASK-REL-020: removal effects were previously
        derived from an md5 hash of the channel name and the conversion
        rate was a hardcoded 0.05.)
        """
        nodes = list(set(
            t.get("channel", "unknown")
            for j in self._journeys.values()
            for t in j.touches
        ))

        # Channel-to-channel transition probabilities (for display)
        edges = {n: {} for n in nodes}
        for journey in self._journeys.values():
            for i in range(len(journey.touches) - 1):
                src = journey.touches[i].get("channel", "unknown")
                dst = journey.touches[i + 1].get("channel", "unknown")
                if src in edges:
                    edges[src][dst] = edges[src].get(dst, 0) + 1
        for src in edges:
            total = sum(edges[src].values())
            if total > 0:
                edges[src] = {k: v / total for k, v in edges[src].items()}

        total_journeys = len(self._journeys)
        if total_journeys == 0:
            graph = MarkovGraph(
                graph_id=hashlib.md5(f"markov:{time.time()}".encode()).hexdigest()[:12],
                nodes=nodes,
                edges=edges,
                removal_effects={},
                conversion_rate=None,
                data_status="no_data",
                data_note=(
                    "No journeys are stored, so transition probabilities, "
                    "removal effects and the conversion rate cannot be "
                    "computed."
                ),
            )
            self._markov_graphs[graph.graph_id] = graph
            return graph

        converted = sum(1 for j in self._journeys.values() if j.conversion_value > 0)
        conversion_rate = converted / total_journeys

        base_probs = self._transition_probs()
        p_with = self._conversion_probability(base_probs)

        removal_effects = {}
        for channel in nodes:
            if p_with <= 0:
                removal_effects[channel] = 0.0
            else:
                p_without = self._conversion_probability(
                    self._transition_probs(exclude_channel=channel)
                )
                removal_effects[channel] = max(0.0, 1.0 - p_without / p_with)

        graph = MarkovGraph(
            graph_id=hashlib.md5(
                f"markov:{time.time()}".encode()
            ).hexdigest()[:12],
            nodes=nodes,
            edges=edges,
            removal_effects=removal_effects,
            conversion_rate=conversion_rate,
            data_status="estimated_from_inputs",
            data_note=(
                "Transition probabilities, conversion rate and removal "
                "effects computed from the stored journeys; a journey "
                "counts as converted when it carries a conversion value, "
                "and journeys through a removed channel count as lost."
            ),
        )

        self._markov_graphs[graph.graph_id] = graph
        return graph

    def compare_models(
        self,
        journey_id: str,
    ) -> AttributionComparison:
        """Compare attribution models for a journey."""
        journey = self._journeys.get(journey_id)
        if not journey:
            raise HTTPException(404, f"Journey {journey_id} not found")

        model_comparison = {}
        all_channels = journey.channels_touched

        # Markov removal-effect shares for the data_driven model, computed
        # from all stored journeys (TASK-REL-020: the fallback previously
        # duplicated the linear split under the data-driven name).
        _effects = self.build_markov_graph().removal_effects
        _total_effect = sum(_effects.values())
        _removal_shares = (
            {ch: e / _total_effect for ch, e in _effects.items()}
            if _total_effect > 0
            else {}
        )

        for model in self._models.values():
            credits = {}

            for i, touch in enumerate(journey.touches):
                channel = touch.get("channel", "unknown")

                if model.model_type == "first_touch":
                    credit = journey.conversion_value if i == 0 else 0
                elif model.model_type == "last_touch":
                    credit = journey.conversion_value if i == len(journey.touches) - 1 else 0
                elif model.model_type == "linear":
                    credit = journey.conversion_value / len(journey.touches)
                elif model.model_type == "time_decay":
                    decay = model.decay_factor ** (len(journey.touches) - i - 1)
                    total = sum(model.decay_factor ** (len(journey.touches) - j - 1) for j in range(len(journey.touches)))
                    credit = journey.conversion_value * decay / total
                elif model.model_type == "position_based":
                    if i == 0:
                        credit = journey.conversion_value * 0.4
                    elif i == len(journey.touches) - 1:
                        credit = journey.conversion_value * 0.4
                    else:
                        credit = journey.conversion_value * 0.2 / max(1, len(journey.touches) - 2)
                else:
                    # data_driven is credited at journey level below.
                    credit = 0.0

                credits[channel] = credits.get(channel, 0) + credit

            if model.model_type == "data_driven" and journey.conversion_value > 0 and _removal_shares:
                denom = sum(
                    _removal_shares[ch]
                    for ch in journey.channels_touched
                    if ch in _removal_shares
                )
                if denom > 0:
                    for ch in journey.channels_touched:
                        if ch in _removal_shares:
                            credits[ch] = credits.get(ch, 0) + (
                                journey.conversion_value * _removal_shares[ch] / denom
                            )

            model_comparison[model.name] = credits

        # Calculate differences
        differences = {}
        for channel in all_channels:
            values = [m.get(channel, 0) for m in model_comparison.values()]
            differences[channel] = max(values) - min(values) if values else 0

        return AttributionComparison(
            journey_id=journey_id,
            models=model_comparison,
            differences=differences,
        )

    def get_report(self) -> dict:
        """Get attribution modeler report."""
        return {
            "total_journeys": len(self._journeys),
            "total_models": len(self._models),
            "total_results": len(self._results),
            "total_markov_graphs": len(self._markov_graphs),
            "models": [
                {
                    "name": m.name,
                    "type": m.model_type,
                    "description": m.description,
                }
                for m in self._models.values()
            ],
            "channels": list(set(
                t.get("channel", "")
                for j in self._journeys.values()
                for t in j.touches
            )),
        }


# Module-level singleton
attribution_modeler = MultiChannelAttributionModeler()


# ── API Routes ──────────────────────────────────────────────────────────────


@router.post("/api/v1/cortex/attribution/journeys")
async def add_journey(payload: dict):
    """Add a customer journey."""
    journey = attribution_modeler.add_journey(
        customer_id=payload["customer_id"],
        touches=payload["touches"],
        conversion_value=payload.get("conversion_value", 0.0),
        conversion_timestamp=payload.get("conversion_timestamp", 0.0),
    )
    return {"journey_id": journey.journey_id, "touches": journey.total_touches, "status": "added"}


@router.post("/api/v1/cortex/attribution/attribute")
async def attribute(payload: dict | None = None):
    """Run attribution analysis."""
    model_type = (payload or {}).get("model_type", "data_driven")
    result = attribution_modeler.attribute(model_type)
    return {
        "model_name": result.model_name,
        "model_type": result.model_type,
        "data_status": result.data_status,
        "data_note": result.data_note,
        "total_attributed_value": result.total_attributed_value,
        "conversions_analyzed": result.conversions_analyzed,
        "top_channel": result.top_channel,
        "channel_contributions": [
            {
                "channel": c.channel,
                "avg_credit": c.avg_credit,
                "first_touch": c.first_touch_credit,
                "last_touch": c.last_touch_credit,
                "linear": c.linear_credit,
                "time_decay": c.time_decay_credit,
                "position": c.position_credit,
                "data_driven": c.data_driven_credit,
            }
            for c in result.channel_contributions
        ],
    }


@router.post("/api/v1/cortex/attribution/markov-graph")
async def build_markov_graph():
    """Build Markov chain graph."""
    graph = attribution_modeler.build_markov_graph()
    return {
        "graph_id": graph.graph_id,
        "nodes": graph.nodes,
        "removal_effects": graph.removal_effects,
        "conversion_rate": graph.conversion_rate,
        "data_status": graph.data_status,
        "data_note": graph.data_note,
    }


@router.get("/api/v1/cortex/attribution/journeys/{journey_id}/compare")
async def compare_models(journey_id: str):
    """Compare attribution models for a journey."""
    comparison = attribution_modeler.compare_models(journey_id)
    return {
        "journey_id": comparison.journey_id,
        "models": comparison.models,
        "differences": comparison.differences,
    }


@router.get("/api/v1/cortex/attribution/report")
async def get_report():
    """Get attribution modeler report."""
    return attribution_modeler.get_report()
