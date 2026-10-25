"""
tools/universe_workflow_engine.py — Multi-agent workflow orchestration.

Provides:
- Workflow definition and execution
- Capability discovery between agents
- Task templates for common workflows
- Real HTTP inter-agent communication
- Workflow monitoring and status tracking

Priority 1-5: Making agents work together as a real system
"""
import importlib.util
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

# Add all paths
for p in [
    ROOT / "FRIDAY/apps/core/src",
    ROOT / "Cortex/apps/api/src",
    ROOT / "Inference",
    ROOT / "Memora/apps/api",
    ROOT / "Forge",
    ROOT / "VyralX",
    ROOT / "IntelX",
    ROOT / "Sentinel/sentinel/apps/api/src",
    ROOT / "Stratex",
    ROOT / "Futuris",
]:
    p = str(p)
    if p not in sys.path:
        sys.path.insert(0, p)


def _load(name, relpath):
    """Load a module directly from file."""
    path = str(ROOT / relpath)
    full_name = f"_wf_{name}"
    spec = importlib.util.spec_from_file_location(full_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _eng(name, relpath):
    mod = _load(name, relpath)
    return mod.engine if hasattr(mod, "engine") else mod


# ── Agent Capability Registry ────────────────────────────────────────────────

@dataclass
class AgentCapability:
    """An agent's capabilities."""
    agent_name: str
    capabilities: list[str] = field(default_factory=list)
    endpoints: dict[str, str] = field(default_factory=dict)
    health_url: str = ""
    base_url: str = ""
    status: str = "unknown"
    last_checked: float = 0.0


class CapabilityRegistry:
    """Registry of all agent capabilities for discovery."""

    def __init__(self):
        self._agents: dict[str, AgentCapability] = {}
        self._load_from_config()

    def _load_from_config(self):
        """Load agent capabilities from the config engine."""
        try:
            config = _eng("config", "FRIDAY/apps/core/src/friday_core/universe_config.py")
            for agent in config.get_all_agents():
                name = agent.agent_name if hasattr(agent, "agent_name") else str(agent)
                caps = getattr(agent, "capabilities", [])
                base_url = getattr(agent, "base_url", "")
                health_url = getattr(agent, "health_url", "")
                port = getattr(agent, "port", 0)
                self._agents[name] = AgentCapability(
                    agent_name=name,
                    capabilities=list(caps),
                    endpoints={"health": health_url},
                    base_url=base_url,
                    health_url=health_url,
                )
        except Exception as e:
            print(f"Warning: Could not load config: {e}")

    def register(self, agent_name: str, capabilities: list[str], base_url: str = "",
                 health_url: str = "", endpoints: dict[str, str] = None):
        """Register or update an agent's capabilities."""
        agent = self._agents.get(agent_name, AgentCapability(agent_name=agent_name))
        agent.capabilities = capabilities
        agent.base_url = base_url
        agent.health_url = health_url
        if endpoints:
            agent.endpoints.update(endpoints)
        agent.status = "registered"
        agent.last_checked = time.time()
        self._agents[agent_name] = agent

    def discover(self, capability: str) -> list[str]:
        """Find all agents that have a specific capability."""
        return [name for name, agent in self._agents.items()
                if capability in agent.capabilities]

    def discover_all(self) -> dict[str, list[str]]:
        """Find all capabilities and which agents have them."""
        result = {}
        for name, agent in self._agents.items():
            for cap in agent.capabilities:
                if cap not in result:
                    result[cap] = []
                result[cap].append(name)
        return result

    def get_agent(self, name: str) -> AgentCapability | None:
        return self._agents.get(name)

    def all_agents(self) -> list[AgentCapability]:
        return list(self._agents.values())

    def health_check(self) -> dict:
        """Check health of all registered agents."""
        results = {}
        for name, agent in self._agents.items():
            results[name] = {
                "status": agent.status,
                "capabilities": agent.capabilities,
                "base_url": agent.base_url,
                "health_url": agent.health_url,
            }
        return results


# ── Workflow Step ─────────────────────────────────────────────────────────────

@dataclass
class WorkflowStep:
    """A single step in a workflow."""
    step_id: str
    name: str
    agent: str
    action: str
    payload: dict = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    status: str = "pending"
    result: Any = None
    error: str = ""
    started_at: float = 0.0
    completed_at: float = 0.0


# ── Workflow ─────────────────────────────────────────────────────────────────

@dataclass
class Workflow:
    """A multi-agent workflow."""
    workflow_id: str
    name: str
    description: str = ""
    steps: list[WorkflowStep] = field(default_factory=list)
    status: str = "pending"
    created_at: float = field(default_factory=time.time)
    completed_at: float = 0.0


# ── Workflow Engine ───────────────────────────────────────────────────────────

class UniverseWorkflowEngine:
    """Engine for orchestrating multi-agent workflows."""

    def __init__(self):
        self._workflows: dict[str, Workflow] = {}
        self._capabilities = CapabilityRegistry()
        self._dispatch_bus = _eng("dispatch_bus", "FRIDAY/apps/core/src/friday_core/universe_dispatch_bus.py")

    # ── Capability Discovery ──────────────────────────────────────────────

    def discover_capability(self, capability: str) -> list[str]:
        """Find agents with a specific capability."""
        return self._capabilities.discover(capability)

    def discover_all(self) -> dict[str, list[str]]:
        """Find all capabilities across all agents."""
        return self._capabilities.discover_all()

    def get_agent_info(self, agent_name: str) -> dict:
        """Get info about a specific agent."""
        agent = self._capabilities.get_agent(agent_name)
        if not agent:
            return {"error": f"Agent {agent_name} not found"}
        return {
            "agent_name": agent.agent_name,
            "capabilities": agent.capabilities,
            "base_url": agent.base_url,
            "health_url": agent.health_url,
            "status": agent.status,
            "endpoints": agent.endpoints,
        }

    # ── Workflow Management ───────────────────────────────────────────────

    def create_workflow(self, name: str, description: str = "") -> Workflow:
        """Create a new workflow."""
        wf_id = f"wf_{uuid.uuid4().hex[:12]}"
        workflow = Workflow(workflow_id=wf_id, name=name, description=description)
        self._workflows[wf_id] = workflow
        return workflow

    def add_step(self, workflow_id: str, name: str, agent: str, action: str,
                 payload: dict = None, depends_on: list[str] = None) -> WorkflowStep:
        """Add a step to a workflow."""
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")
        step = WorkflowStep(
            step_id=f"step_{uuid.uuid4().hex[:8]}",
            name=name, agent=agent, action=action,
            payload=payload or {}, depends_on=depends_on or [],
        )
        workflow.steps.append(step)
        return step

    def execute_workflow(self, workflow_id: str) -> Workflow:
        """Execute a workflow step by step."""
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")
        workflow.status = "running"

        for step in workflow.steps:
            step.status = "running"
            step.started_at = time.time()
            try:
                # Execute via dispatch bus
                receipt = self._dispatch_bus.dispatch(step.agent, step.action, step.payload)
                step.status = "completed" if receipt.status == "completed" else "failed"
                step.result = receipt.result
                step.completed_at = time.time()
            except Exception as e:
                step.status = "failed"
                step.error = str(e)
                step.completed_at = time.time()

        workflow.status = "completed" if all(s.status == "completed" for s in workflow.steps) else "failed"
        workflow.completed_at = time.time()
        return workflow

    def get_workflow(self, workflow_id: str) -> Workflow | None:
        return self._workflows.get(workflow_id)

    def get_all_workflows(self) -> list[Workflow]:
        return list(self._workflows.values())

    # ── Pre-defined Workflow Templates ─────────────────────────────────────

    def run_trading_analysis(self) -> Workflow:
        """Workflow: Inference analyzes → Stratex trades → Cortex decides."""
        wf = self.create_workflow("Trading Analysis", "Analyze market and make trading decision")
        self.add_step(wf.workflow_id, "Analyze signals", "Inference", "analyze",
                      {"query": "market signals"}, depends_on=[])
        self.add_step(wf.workflow_id, "Execute trade", "Stratex", "trade",
                      {"symbol": "BTC", "action": "buy"}, depends_on=[wf.steps[0].step_id])
        self.add_step(wf.workflow_id, "Decide strategy", "Cortex", "decide",
                      {"decision": "trade_executed"}, depends_on=[wf.steps[1].step_id])
        return self.execute_workflow(wf.workflow_id)

    def run_security_scan(self) -> Workflow:
        """Workflow: Sentinel scans → IntelX analyzes → Cortex decides."""
        wf = self.create_workflow("Security Scan", "Scan for threats and respond")
        self.add_step(wf.workflow_id, "Scan for threats", "Sentinel", "scan",
                      {"scope": "full"}, depends_on=[])
        self.add_step(wf.workflow_id, "Analyze threats", "IntelX", "analyze",
                      {"threats": "detected"}, depends_on=[wf.steps[0].step_id])
        self.add_step(wf.workflow_id, "Decide response", "Cortex", "decide",
                      {"response": "block"}, depends_on=[wf.steps[1].step_id])
        return self.execute_workflow(wf.workflow_id)

    def run_content_creation(self) -> Workflow:
        """Workflow: VyralX creates → Inference scripts → Memora stores."""
        wf = self.create_workflow("Content Creation", "Create and store content")
        self.add_step(wf.workflow_id, "Create content", "VyralX", "create",
                      {"type": "video", "topic": "tech"}, depends_on=[])
        self.add_step(wf.workflow_id, "Script content", "Inference", "reason",
                      {"query": "script for video"}, depends_on=[wf.steps[0].step_id])
        self.add_step(wf.workflow_id, "Store content", "Memora", "recall",
                      {"action": "store"}, depends_on=[wf.steps[1].step_id])
        return self.execute_workflow(wf.workflow_id)

    def run_code_development(self) -> Workflow:
        """Workflow: Forge builds → Sentinel scans → Cortex approves."""
        wf = self.create_workflow("Code Development", "Build, scan, and approve code")
        self.add_step(wf.workflow_id, "Build code", "Forge", "build",
                      {"project": "test"}, depends_on=[])
        self.add_step(wf.workflow_id, "Scan code", "Sentinel", "scan",
                      {"type": "security"}, depends_on=[wf.steps[0].step_id])
        self.add_step(wf.workflow_id, "Approve code", "Cortex", "decide",
                      {"approval": "requested"}, depends_on=[wf.steps[1].step_id])
        return self.execute_workflow(wf.workflow_id)

    def run_forecast_pipeline(self) -> Workflow:
        """Workflow: Futuris forecasts → Stratex trades → Memora stores."""
        wf = self.create_workflow("Forecast Pipeline", "Forecast and trade on forecast")
        self.add_step(wf.workflow_id, "Forecast market", "Futuris", "forecast",
                      {"market": "crypto"}, depends_on=[])
        self.add_step(wf.workflow_id, "Execute trade", "Stratex", "trade",
                      {"based_on": "forecast"}, depends_on=[wf.steps[0].step_id])
        self.add_step(wf.workflow_id, "Store results", "Memora", "recall",
                      {"action": "store"}, depends_on=[wf.steps[1].step_id])
        return self.execute_workflow(wf.workflow_id)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== FRIDAY Universe Workflow Engine ===\n")

    engine = UniverseWorkflowEngine()

    # Capability discovery
    print("Capability Discovery:")
    all_caps = engine.discover_all()
    for cap, agents in sorted(all_caps.items()):
        print(f"  {cap}: {', '.join(agents)}")

    print(f"\nTotal agents registered: {len(engine._capabilities.all_agents())}")
    print(f"Total capabilities: {len(all_caps)}")

    # Run workflows
    print("\nRunning Workflows:")
    workflows = [
        ("Trading Analysis", engine.run_trading_analysis),
        ("Security Scan", engine.run_security_scan),
        ("Content Creation", engine.run_content_creation),
        ("Code Development", engine.run_code_development),
        ("Forecast Pipeline", engine.run_forecast_pipeline),
    ]
    for name, func in workflows:
        wf = func()
        completed = sum(1 for s in wf.steps if s.status == "completed")
        print(f"  {name}: {completed}/{len(wf.steps)} steps completed ({wf.status})")

    print("\n=== Workflow Engine Ready ===")
