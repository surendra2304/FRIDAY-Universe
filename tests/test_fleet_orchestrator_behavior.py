from __future__ import annotations

import unittest

from mesh.fleet_orchestrator import (
    AgentCapability,
    AgentStatus,
    ConsensusEngine,
    FleetRegistry,
    FleetSupervisor,
    FleetTask,
    TaskRouter,
)


class FakeResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code


class FakeHttpClient:
    def __init__(self, statuses: dict[str, int]):
        self.statuses = statuses

    async def get(self, url: str) -> FakeResponse:
        status = self.statuses.get(url)
        if status is None:
            raise OSError("unreachable")
        return FakeResponse(status)


class FakeTransport:
    def __init__(self, status: str = "ACCEPTED_HTTP"):
        self.status = status
        self.published = []

    async def publish(self, envelope):
        self.published.append(envelope)
        return {"status": self.status}


class FleetOrchestratorBehaviorTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.registry = FleetRegistry()
        for agent in self.registry.all_agents():
            self.registry.update_status(agent.name, AgentStatus.ONLINE)

    def test_task_router_requires_every_capability(self):
        router = TaskRouter(self.registry)
        task = FleetTask(
            id="task-1",
            description="trade with reasoning review",
            capabilities_required=[AgentCapability.TRADING, AgentCapability.REASONING],
        )
        routed = router.route_task(task)
        self.assertEqual([agent.name for agent in routed], ["STRATEX"])

    async def test_health_check_reports_observed_status(self):
        supervisor = FleetSupervisor()
        friday = supervisor.registry.get_agent("FRIDAY")
        cortex = supervisor.registry.get_agent("CORTEX")
        self.assertIsNotNone(friday)
        self.assertIsNotNone(cortex)
        client = FakeHttpClient({
            friday.health_endpoint: 200,
            cortex.health_endpoint: 503,
        })

        results = await supervisor.health_check(client=client)

        self.assertEqual(results["FRIDAY"], "ONLINE")
        self.assertEqual(results["CORTEX"], "DEGRADED")
        self.assertEqual(results["INFERENCE"], "OFFLINE")
        self.assertEqual(supervisor.registry.get_agent("FRIDAY").status, AgentStatus.ONLINE)
        self.assertEqual(supervisor.registry.get_agent("CORTEX").status, AgentStatus.DEGRADED)
        self.assertEqual(supervisor.registry.get_agent("INFERENCE").status, AgentStatus.OFFLINE)

    async def test_delivery_ack_is_not_treated_as_a_consensus_vote(self):
        transport = FakeTransport(status="ACCEPTED_HTTP")
        engine = ConsensusEngine(self.registry, transport)

        result = await engine.gather_consensus(
            "Should action be approved?",
            ["approve", "reject"],
            required_agents=["FRIDAY", "INFERENCE"],
        )

        self.assertEqual(result.decision, "")
        self.assertEqual(result.confidence, 0.0)
        self.assertEqual(result.agreeing_agents, [])
        self.assertEqual(len(transport.published), 2)
        self.assertFalse(any(item.get("vote_received") for item in result.evidence))

    async def test_consensus_uses_valid_votes_and_enforces_quorum(self):
        async def provider(agent, question, options):
            return {
                "option": "approve" if agent.name in {"FRIDAY", "INFERENCE"} else "reject",
                "confidence": 0.9,
            }

        engine = ConsensusEngine(self.registry, FakeTransport(), vote_provider=provider)
        result = await engine.gather_consensus(
            "Should action be approved?",
            ["approve", "reject"],
            required_agents=["FRIDAY", "INFERENCE", "STRATEX"],
            min_confidence=0.6,
            min_votes=2,
        )

        self.assertEqual(result.decision, "approve")
        self.assertEqual(set(result.agreeing_agents), {"FRIDAY", "INFERENCE"})
        self.assertEqual(result.dissenting_agents, ["STRATEX"])
        self.assertGreaterEqual(result.confidence, 0.6)

    async def test_consensus_rejects_malformed_vote_confidence(self):
        async def provider(agent, question, options):
            return {"option": "approve", "confidence": float("nan")}

        engine = ConsensusEngine(self.registry, FakeTransport(), vote_provider=provider)
        result = await engine.gather_consensus(
            "Should action be approved?",
            ["approve", "reject"],
            required_agents=["FRIDAY", "INFERENCE"],
        )

        self.assertEqual(result.decision, "")
        self.assertEqual(result.confidence, 0.0)
        self.assertTrue(any("invalid_or_unavailable_vote" in item.get("reason", "") for item in result.evidence))


if __name__ == "__main__":
    unittest.main()
