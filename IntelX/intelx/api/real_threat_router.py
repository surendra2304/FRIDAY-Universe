"""
IntelX — Real Threat Intel & Graph Router

Wires real_graph_analytics, real_advanced_threat_intel,
real_deep_threat_intel, and real_threat_intel_engine into the IntelX API.

TASK-REL-017: this router existed but was never mounted, and three of its
four handlers called the engines with wrong arguments (a string where a
dict was required, a positional list where (threat_type, historical) was
required, and a non-existent ``analyze()`` method guarded into returning
a hollow ok). It is now mounted with honest adapters: every engine here
computes only over caller-supplied data or the persistent indicator
store, and every response names that data source in its payload.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

real_threat_router = APIRouter(tags=["Real Threat Intel"], prefix="/v1/real-threat-intel")


def _import_mods():
    mods: dict[str, Any] = {}
    # Graph analytics lives in app/agents/ (the paths this router
    # originally tried — intelx.services / services — do not exist, which
    # is why the graph engine never loaded).
    for graph_path in (
        "app.agents.real_graph_analytics",
        "IntelX.app.agents.real_graph_analytics",
        "intelx.services.real_graph_analytics",
        "services.real_graph_analytics",
    ):
        try:
            import importlib

            mod = importlib.import_module(graph_path)
            mods["graph"] = {
                "graph": mod.Graph, "pagerank": mod.PageRankAnalyzer,
                "community": mod.CommunityDetector,
                "shortest_path": mod.ShortestPathFinder,
                "centrality": mod.CentralityAnalyzer,
                "influence": mod.InfluenceSpreadAnalyzer,
            }
            break
        except Exception:
            continue
    try:
        from intelx.services.real_advanced_threat_intel import (
            DarkWebMonitor, PredictiveThreatAnalyzer, AdversaryEmulationEngine,
        )
        mods["advanced_threat"] = {
            "darkweb": DarkWebMonitor, "predictive": PredictiveThreatAnalyzer,
            "adversary": AdversaryEmulationEngine,
        }
    except Exception:
        try:
            from services.real_advanced_threat_intel import (
                DarkWebMonitor, PredictiveThreatAnalyzer, AdversaryEmulationEngine,
            )
            mods["advanced_threat"] = {
                "darkweb": DarkWebMonitor, "predictive": PredictiveThreatAnalyzer,
                "adversary": AdversaryEmulationEngine,
            }
        except Exception:
            pass
    try:
        from intelx.services.real_deep_threat_intel import (
            ThreatForecastEngine, ThreatIntelQualityEvaluator,
            DisinformationDetector, SupplyChainThreatMapper,
        )
        mods["deep_threat"] = {
            "forecast": ThreatForecastEngine, "quality": ThreatIntelQualityEvaluator,
            "disinfo": DisinformationDetector, "supply_chain": SupplyChainThreatMapper,
        }
    except Exception:
        try:
            from services.real_deep_threat_intel import (
                ThreatForecastEngine, ThreatIntelQualityEvaluator,
                DisinformationDetector, SupplyChainThreatMapper,
            )
            mods["deep_threat"] = {
                "forecast": ThreatForecastEngine, "quality": ThreatIntelQualityEvaluator,
                "disinfo": DisinformationDetector, "supply_chain": SupplyChainThreatMapper,
            }
        except Exception:
            pass
    try:
        import importlib

        engine_mod = None
        for engine_path in (
            "intelx.services.real_threat_intel_engine",
            "services.real_threat_intel_engine",
        ):
            try:
                engine_mod = importlib.import_module(engine_path)
                break
            except Exception:
                continue
        if engine_mod is not None:
            mods["threat_engine"] = {
                "indicator": engine_mod.ThreatIndicator,
                "campaign": engine_mod.ThreatCampaign,
                "report": engine_mod.IntelReport,
                "engine": engine_mod.ThreatIntelEngine,
                # The module-level singleton persists indicators to disk;
                # use it so analysis reflects the real stored state
                # instead of a fresh empty engine per request.
                "instance": getattr(engine_mod, "engine", None),
            }
    except Exception:
        pass
    return mods


_MODS: dict[str, Any] = {}


def get_mods():
    if not _MODS:
        _MODS.update(_import_mods())
    return _MODS


@real_threat_router.get("/status")
def engines_status():
    mods = get_mods()
    return {
        "status": "ok",
        "engines": [
            {"name": name, "classes": sorted(k for k in m.keys() if k != "instance"), "loaded": True}
            for name, m in mods.items()
        ],
    }


@real_threat_router.post("/graph/pagerank")
def graph_pagerank(body: dict):
    """Compute PageRank over a caller-supplied graph.

    Body: {"graph": {"nodes": [...], "edges": [[src, tgt, weight?], ...]
    or [{"source": ..., "target": ..., "weight": ...}, ...]}}
    """
    mods = get_mods()
    if "graph" not in mods:
        raise HTTPException(503, "Graph analytics not available")
    data = body.get("graph", {})
    if not isinstance(data, dict):
        raise HTTPException(422, "graph must be an object with nodes/edges")
    graph_cls = mods["graph"]["graph"]
    graph = graph_cls()
    for node in data.get("nodes", []):
        graph.add_node(str(node))
    for edge in data.get("edges", []):
        if isinstance(edge, dict):
            src, tgt = edge.get("source"), edge.get("target")
            weight = float(edge.get("weight", 1.0))
        elif isinstance(edge, (list, tuple)) and len(edge) >= 2:
            src, tgt = edge[0], edge[1]
            weight = float(edge[2]) if len(edge) > 2 else 1.0
        else:
            continue
        if src is not None and tgt is not None:
            graph.add_edge(str(src), str(tgt), weight)
    analyzer = mods["graph"]["pagerank"]()
    result = analyzer.compute(graph)
    return {"status": "ok", "data_source": "caller_supplied_graph", "result": result}


@real_threat_router.post("/advanced/darkweb")
def advanced_darkweb(body: dict):
    """Format caller-supplied dark-web source data into findings.

    No live dark-web feed is connected: the engine formats findings ONLY
    from flags the caller asserts in ``source_data`` (has_credentials /
    has_exploits / has_data_leak, counts, indicators). Nothing is fetched
    or discovered by this endpoint.
    """
    mods = get_mods()
    if "advanced_threat" not in mods:
        raise HTTPException(503, "Advanced threat intel not available")
    source_data = body.get("source_data")
    if not isinstance(source_data, dict):
        source_data = {
            k: body[k]
            for k in (
                "source", "has_credentials", "has_exploits", "has_data_leak",
                "count", "records", "confidence", "indicators",
            )
            if k in body
        }
    monitor = mods["advanced_threat"]["darkweb"]()
    result = monitor.scan(source_data)
    return {
        "status": "ok",
        "data_source": "caller_supplied_source_data",
        "live_feed_connected": False,
        "result": result,
    }


@real_threat_router.post("/deep/forecast")
def deep_forecast(body: dict):
    """Forecast from caller-supplied historical events.

    Body: {"threat_type": str, "historical": [{"timestamp": ...}, ...],
    "horizon_days": float}. The forecast is time-series math over the
    supplied events only; with no history the engine returns its explicit
    low-confidence baseline.
    """
    mods = get_mods()
    if "deep_threat" not in mods:
        raise HTTPException(503, "Deep threat intel not available")
    historical = body.get("historical")
    if not isinstance(historical, list):
        historical = body.get("data") if isinstance(body.get("data"), list) else []
    engine = mods["deep_threat"]["forecast"]()
    result = engine.forecast(
        str(body.get("threat_type", "")),
        historical,
        float(body.get("horizon_days", 7.0)),
    )
    return {"status": "ok", "data_source": "caller_supplied_history", "result": result}


@real_threat_router.post("/engine/analyze")
def threat_engine_analyze(body: dict):
    """Analyse the persistent threat-intel store.

    ThreatIntelEngine has no ``analyze()`` method (the previous handler
    guarded that fact into returning a hollow ``{"report": {}}`` success).
    This handler runs the engine's real reads over its persisted state:
    store statistics, the current threat feed, and — when
    ``indicator_ids`` are supplied — their recorded correlations.
    """
    mods = get_mods()
    if "threat_engine" not in mods:
        raise HTTPException(503, "Threat intel engine not available")
    engine = mods["threat_engine"].get("instance") or mods["threat_engine"]["engine"]()
    result: dict[str, Any] = {
        "stats": engine.get_stats(),
        "threat_feed": engine.get_threat_feed(limit=int(body.get("limit", 20))),
    }
    indicator_ids = body.get("indicator_ids")
    if isinstance(indicator_ids, list) and indicator_ids:
        result["correlations"] = engine.correlate_indicators(
            [str(i) for i in indicator_ids]
        )
    return {"status": "ok", "data_source": "intelx_persistent_indicator_store", "result": result}
