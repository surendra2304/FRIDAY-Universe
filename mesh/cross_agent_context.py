"""
mesh/cross_agent_context.py — FRIDAY Universe Cross-Agent Context Sharing.

Automatically shares context between agents through Memora. When an agent
completes a task, relevant context is shared with other agents that might
need it.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter()


@dataclass
class ContextShare:
    """A context share between agents."""
    share_id: str
    from_agent: str
    to_agent: str
    content: str
    category: str = "general"  # task_result, knowledge, insight, alert, memory
    importance: float = 0.5
    scope: str = "shared"  # private, shared, universal
    tags: list[str] = field(default_factory=list)
    shared_at: float = 0.0
    acknowledged: bool = False


@dataclass
class ContextRequest:
    """A context request from an agent."""
    request_id: str
    from_agent: str
    to_agent: str
    query: str
    category: str = "general"
    priority: int = 1
    status: str = "pending"  # pending, fulfilled, rejected, expired
    fulfilled_content: str = ""
    created_at: float = 0.0
    fulfilled_at: float = 0.0


@dataclass
class ContextGraph:
    """A graph of context relationships between agents."""
    nodes: list[str] = field(default_factory=list)
    edges: list[tuple[str, str, float]] = field(default_factory=list)  # (from, to, weight)
    last_updated: float = 0.0


@dataclass
class ContextImpact:
    """Impact assessment of context sharing."""
    from_agent: str
    to_agent: str
    shares_count: int
    avg_importance: float
    knowledge_gain: float
    recommendation: str


class CrossAgentContextEngine:
    """Cross-agent context sharing engine."""

    def __init__(self):
        self._shares: list[ContextShare] = []
        self._requests: dict[str, ContextRequest] = {}
        self._graph = ContextGraph()
        self._impacts: dict[str, ContextImpact] = {}

    def share_context(
        self,
        from_agent: str,
        to_agent: str,
        content: str,
        category: str = "general",
        importance: float = 0.5,
        scope: str = "shared",
        tags: list[str] | None = None,
    ) -> ContextShare:
        """Share context from one agent to another via Memora."""
        share = ContextShare(
            share_id=hashlib.md5(
                f"share:{from_agent}:{to_agent}:{content}:{time.time()}".encode()
            ).hexdigest()[:12],
            from_agent=from_agent,
            to_agent=to_agent,
            content=content[:2000],
            category=category,
            importance=importance,
            scope=scope,
            tags=tags or [],
            shared_at=time.time(),
        )

        self._shares.append(share)

        # Update context graph
        self._update_graph(from_agent, to_agent, importance)

        # Store in Memora (Universal scope = all agents, Shared = allowlisted)
        memora_scope = "universal" if scope == "universal" else "shared"
        memora_namespace = f"{from_agent}_context"

        # In actual deployment, this would call Memora's API
        # For now, track locally
        return share

    def _update_graph(self, from_agent: str, to_agent: str, weight: float):
        """Update the context graph with a new edge."""
        if from_agent not in self._graph.nodes:
            self._graph.nodes.append(from_agent)
        if to_agent not in self._graph.nodes:
            self._graph.nodes.append(to_agent)

        # Check if edge exists
        for i, (a, b, w) in enumerate(self._graph.edges):
            if (a == from_agent and b == to_agent) or (a == to_agent and b == from_agent):
                # Update weight (average)
                self._graph.edges[i] = (from_agent, to_agent, (w + weight) / 2)
                break
        else:
            self._graph.edges.append((from_agent, to_agent, weight))

        self._graph.last_updated = time.time()

    def request_context(
        self,
        from_agent: str,
        to_agent: str,
        query: str,
        category: str = "general",
        priority: int = 1,
    ) -> ContextRequest:
        """Request context from another agent."""
        request = ContextRequest(
            request_id=hashlib.md5(
                f"request:{from_agent}:{to_agent}:{query}:{time.time()}".encode()
            ).hexdigest()[:12],
            from_agent=from_agent,
            to_agent=to_agent,
            query=query,
            category=category,
            priority=priority,
            created_at=time.time(),
        )

        self._requests[request.request_id] = request
        return request

    def fulfill_request(self, request_id: str, content: str) -> ContextRequest:
        """Fulfill a context request."""
        request = self._requests.get(request_id)
        if not request:
            raise HTTPException(404, f"Request {request_id} not found")

        request.status = "fulfilled"
        request.fulfilled_content = content
        request.fulfilled_at = time.time()

        # Also share the content back
        self.share_context(
            from_agent=request.to_agent,
            to_agent=request.from_agent,
            content=content,
            category=request.category,
            importance=0.8,
        )

        return request

    def get_relevant_context(
        self,
        agent_name: str,
        query: str,
        category: str | None = None,
    ) -> list[ContextShare]:
        """Get relevant context for an agent."""
        relevant = []
        query_words = set(query.lower().split())

        for share in self._shares:
            if share.to_agent != agent_name:
                continue

            if category and share.category != category:
                continue

            # Check content relevance
            content_words = set(share.content.lower().split())
            overlap = len(query_words & content_words)

            if overlap > 0:
                share_relevance = overlap / max(1, len(query_words)) * 0.5 + share.importance * 0.5
                relevant.append((share_relevance, share))

        # Sort by relevance
        relevant.sort(key=lambda x: -x[0])
        return [share for _, share in relevant[:10]]

    def get_context_graph(self) -> ContextGraph:
        """Get the context sharing graph."""
        return self._graph

    def assess_impact(self, from_agent: str, to_agent: str) -> ContextImpact:
        """Assess the impact of context sharing between two agents."""
        shares = [
            s for s in self._shares
            if s.from_agent == from_agent and s.to_agent == to_agent
        ]

        if not shares:
            return ContextImpact(
                from_agent=from_agent,
                to_agent=to_agent,
                shares_count=0,
                avg_importance=0.0,
                knowledge_gain=0.0,
                recommendation="No context shares between these agents",
            )

        avg_importance = sum(s.importance for s in shares) / len(shares)

        # Knowledge gain: based on categories shared
        categories = set(s.category for s in shares)
        knowledge_gain = len(categories) * 0.2 + avg_importance * 0.8

        # Recommendation
        if knowledge_gain > 0.6:
            recommendation = "Strong context sharing. Consider increasing frequency."
        elif knowledge_gain > 0.3:
            recommendation = "Moderate context sharing. Good coverage."
        else:
            recommendation = "Low context sharing. Consider sharing more insights."

        impact = ContextImpact(
            from_agent=from_agent,
            to_agent=to_agent,
            shares_count=len(shares),
            avg_importance=avg_importance,
            knowledge_gain=knowledge_gain,
            recommendation=recommendation,
        )

        self._impacts[f"{from_agent}->{to_agent}"] = impact
        return impact

    def broadcast_context(
        self,
        from_agent: str,
        content: str,
        category: str = "alert",
        importance: float = 0.8,
        tags: list[str] | None = None,
    ) -> list[ContextShare]:
        """Broadcast context to all agents."""
        all_agents = [
            "friday", "inference", "memora", "stratex", "forge",
            "cortex", "sentinel", "intelx", "futuris", "vyralx"
        ]

        shares = []
        for agent in all_agents:
            if agent == from_agent:
                continue

            share = self.share_context(
                from_agent=from_agent,
                to_agent=agent,
                content=content,
                category=category,
                importance=importance,
                scope="universal",
                tags=tags,
            )
            shares.append(share)

        return shares

    def get_context_report(self) -> dict:
        """Get context sharing report."""
        impacts = list(self._impacts.values())

        return {
            "total_shares": len(self._shares),
            "total_requests": len(self._requests),
            "fulfilled_requests": sum(1 for r in self._requests.values() if r.status == "fulfilled"),
            "pending_requests": sum(1 for r in self._requests.values() if r.status == "pending"),
            "graph_nodes": len(self._graph.nodes),
            "graph_edges": len(self._graph.edges),
            "top_impacts": [
                {
                    "from": i.from_agent,
                    "to": i.to_agent,
                    "shares": i.shares_count,
                    "knowledge_gain": i.knowledge_gain,
                    "recommendation": i.recommendation,
                }
                for i in sorted(impacts, key=lambda x: -x.knowledge_gain)[:5]
            ],
        }


# Module-level singleton
cross_agent_context = CrossAgentContextEngine()


# ── API Routes ──────────────────────────────────────────────────────────────


@router.post("/api/v1/mesh/context/share")
async def share_context(payload: dict):
    """Share context between agents."""
    share = cross_agent_context.share_context(
        from_agent=payload["from_agent"],
        to_agent=payload["to_agent"],
        content=payload["content"],
        category=payload.get("category", "general"),
        importance=payload.get("importance", 0.5),
        scope=payload.get("scope", "shared"),
        tags=payload.get("tags", []),
    )
    return share.__dict__


@router.post("/api/v1/mesh/context/broadcast")
async def broadcast_context(payload: dict):
    """Broadcast context to all agents."""
    shares = cross_agent_context.broadcast_context(
        from_agent=payload["from_agent"],
        content=payload["content"],
        category=payload.get("category", "alert"),
        importance=payload.get("importance", 0.8),
        tags=payload.get("tags", []),
    )
    return {"shared_with": len(shares), "shares": [s.__dict__ for s in shares]}


@router.post("/api/v1/mesh/context/request")
async def request_context(payload: dict):
    """Request context from another agent."""
    request = cross_agent_context.request_context(
        from_agent=payload["from_agent"],
        to_agent=payload["to_agent"],
        query=payload["query"],
        category=payload.get("category", "general"),
        priority=payload.get("priority", 1),
    )
    return request.__dict__


@router.post("/api/v1/mesh/context/requests/{request_id}/fulfill")
async def fulfill_request(request_id: str, payload: dict):
    """Fulfill a context request."""
    request = cross_agent_context.fulfill_request(
        request_id,
        payload["content"],
    )
    return request.__dict__


@router.get("/api/v1/mesh/context/relevant")
async def get_relevant_context(agent_name: str, query: str, category: str = ""):
    """Get relevant context for an agent."""
    shares = cross_agent_context.get_relevant_context(agent_name, query, category or None)
    return [s.__dict__ for s in shares]


@router.get("/api/v1/mesh/context/graph")
async def get_context_graph():
    """Get context sharing graph."""
    graph = cross_agent_context.get_context_graph()
    return {
        "nodes": graph.nodes,
        "edges": [list(e) for e in graph.edges],
        "last_updated": graph.last_updated,
    }


@router.get("/api/v1/mesh/context/impact")
async def assess_impact(from_agent: str, to_agent: str):
    """Assess context sharing impact."""
    impact = cross_agent_context.assess_impact(from_agent, to_agent)
    return impact.__dict__


@router.get("/api/v1/mesh/context/report")
async def get_context_report():
    """Get context sharing report."""
    return cross_agent_context.get_context_report()
