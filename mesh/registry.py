"""Agent registration, manifest validation, and ecosystem discovery for all 10 subsystems."""
from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any, Optional


MANIFEST_SCHEMA_PATH = Path(__file__).resolve().parent / "config" / "agent-manifest.schema.json"

DEFAULT_ECOSYSTEM_AGENTS = [
    {
        "agent_id": "a1000000-0000-4000-8000-000000000001",
        "name": "FRIDAY",
        "description": "Central multimodal OS, voice assistant, and master orchestrator",
        "capabilities": [
            "orchestration", "voice", "desktop_control", "task_planning",
            "cognitive_reflection", "browser_automation", "agent_harness",
            "tool_permissions", "output_verification", "context_compaction",
        ],
        "intents": [
            "launch", "control", "research", "orchestrate", "voice_stream",
            "browse", "verify", "plan_task",
        ],
        "trust_level": 5,
        "health_endpoint": "/health",
        "heartbeat_interval": 30,
        "version": "6.10.0",
        "url": "http://friday:10000",
    },
    {
        "agent_id": "a2000000-0000-4000-8000-000000000002",
        "name": "INFERENCE",
        "description": "Dynamic multi-model gateway and API key pooler",
        "capabilities": [
            "routing", "key_pooling", "llm_gateway", "failover",
            "latency_optimization", "scientific_skills", "statistical_analysis",
            "research_planning", "evidence_audit",
        ],
        "intents": ["route", "model_select", "complete", "stream", "research_plan", "analyse"],
        "trust_level": 4,
        "health_endpoint": "/health",
        "heartbeat_interval": 30,
        "version": "2.1.0",
        "url": "http://inference:8000",
    },
    {
        "agent_id": "a3000000-0000-4000-8000-000000000003",
        "name": "MEMORA",
        "description": "3-tiered shared memory fabric with episodic-to-procedural distillation",
        "capabilities": [
            "agent_memory", "group_memory", "universal_memory",
            "vector_embeddings", "lesson_distillation", "viking_context",
            "layered_recall", "session_commit", "memory_wiki",
        ],
        "intents": [
            "record", "load", "distill", "query", "consolidate",
            "context_read", "commit_session",
        ],
        "trust_level": 5,
        "health_endpoint": "/health",
        "heartbeat_interval": 30,
        "version": "3.0.0",
        "url": "http://memora:8000",
    },
    {
        "agent_id": "a4000000-0000-4000-8000-000000000004",
        "name": "STRATEX",
        "description": "24/7 Binance Futures algorithmic execution engine",
        "capabilities": ["futures_trading", "risk_management", "signal_generation", "order_execution"],
        "intents": ["execute", "execute_trade", "signal", "risk_gate", "position_check"],
        "trust_level": 4,
        "health_endpoint": "/health",
        "heartbeat_interval": 30,
        "version": "2.4.0",
        "url": "http://stratex:8000",
    },
    {
        "agent_id": "a5000000-0000-4000-8000-000000000005",
        "name": "INTELX",
        "description": "Deep multi-source research, citation extraction & contradiction resolution",
        "capabilities": ["web_crawling", "citation_analysis", "contradiction_detection", "document_synthesis"],
        "intents": ["research", "synthesize", "contradiction", "scrape"],
        "trust_level": 4,
        "health_endpoint": "/health",
        "heartbeat_interval": 30,
        "version": "2.0.0",
        "url": "http://intelx:8000",
    },
    {
        "agent_id": "a6000000-0000-4000-8000-000000000006",
        "name": "FUTURIS",
        "description": "Calibrated probabilistic forecasting & ecosystem threat prediction",
        "capabilities": ["probabilistic_forecasting", "threat_modeling", "brier_calibration", "regime_detection"],
        "intents": ["predict", "threat", "brier", "regime_model"],
        "trust_level": 3,
        "health_endpoint": "/health",
        "heartbeat_interval": 30,
        "version": "1.5.0",
        "url": "http://futuris:8000",
    },
    {
        "agent_id": "a7000000-0000-4000-8000-000000000007",
        "name": "CORTEX",
        "description": "Autonomous web operations, visitor telemetry & lead qualification",
        "capabilities": ["telemetry_processing", "lead_scoring", "crm_automation", "visitor_analytics"],
        "intents": ["qualify", "manage", "deploy", "track_event"],
        "trust_level": 3,
        "health_endpoint": "/health",
        "heartbeat_interval": 30,
        "version": "1.8.0",
        "url": "http://cortex:8000",
    },
    {
        "agent_id": "a8000000-0000-4000-8000-000000000008",
        "name": "FORGE",
        "description": "Autonomous software engineer building full-stack apps and 3D web applications",
        "capabilities": ["code_synthesis", "3d_web_dev", "playwright_testing", "pytest_runner", "patch_synthesis"],
        "intents": ["develop", "synthesize", "verify", "test_app", "build_ui"],
        "trust_level": 4,
        "health_endpoint": "/health",
        "heartbeat_interval": 30,
        "version": "3.2.0",
        "url": "http://forge:8000",
    },
    {
        "agent_id": "a9000000-0000-4000-8000-000000000009",
        "name": "SENTINEL",
        "description": "Real-time cybersecurity shield, vulnerability scanner & self-healing gatekeeper",
        "capabilities": [
            "ast_policy_gate", "vulnerability_scan", "secret_redaction",
            "self_healing", "audit_logging", "security_audit", "attack_mapping",
            "incident_playbook", "csf_assessment", "detection_coverage",
        ],
        "intents": [
            "audit", "gate", "reboot", "scan_code", "quarantine",
            "triage", "playbook", "coverage",
        ],
        "trust_level": 5,
        "health_endpoint": "/health",
        "heartbeat_interval": 30,
        "version": "4.0.0",
        "url": "http://sentinel:8000",
    },
    {
        "agent_id": "a1000000-0000-4000-8000-000000000010",
        "name": "VyralX",
        "description": "Autonomous video production, licensed asset import, render, and multi-channel distribution",
        "capabilities": [
            "video_discovery", "script_generation", "licensed_asset_import",
            "voiceover", "render_pipeline", "youtube_distribution",
            "provenance_audit", "diagram_design", "explainer_generation",
        ],
        "intents": [
            "discover", "script", "render", "publish", "measure",
            "audit_publish", "diagram", "explain",
        ],
        "trust_level": 4,
        "health_endpoint": "/health",
        "heartbeat_interval": 30,
        "version": "0.2.0",
        "url": "http://vyralx:8000",
    },
]


class ManifestError(Exception):
    pass


class AgentManifest:
    def __init__(self, data: dict[str, Any]):
        self.raw = data
        self.agent_id: str = data.get("agent_id", "")
        self.name: str = data.get("name", "")
        self.description: str = data.get("description", "")
        self.capabilities: list[str] = data.get("capabilities", [])
        self.intents: list[str] = data.get("intents", [])
        self.trust_level: int = data.get("trust_level", 1)
        self.health_endpoint: str = data.get("health_endpoint", "/health")
        self.heartbeat_interval: int = data.get("heartbeat_interval", 60)
        self.version: str = data.get("version", "0.0.0")
        self.url: str = data.get("url", "")
        self.last_updated: Optional[str] = data.get("last_updated")

    def validate(self) -> tuple[bool, str]:
        if not re.fullmatch(r"[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89aAbB][a-f0-9]{3}-[a-f0-9]{12}", self.agent_id):
            return False, f"agent_id '{self.agent_id}' is not a valid UUID v4 format"
        if not self.name or len(self.name) < 3 or len(self.name) > 50:
            return False, f"name '{self.name}' must be 3-50 chars"
        if not isinstance(self.capabilities, list) or len(self.capabilities) < 1:
            return False, "capabilities must be a non-empty array"
        if not isinstance(self.intents, list):
            return False, "intents must be an array"
        if not isinstance(self.trust_level, int) or self.trust_level < 1 or self.trust_level > 5:
            return False, "trust_level must be integer 1-5"
        if not self.health_endpoint.startswith("/"):
            return False, "health_endpoint must start with /"
        if not isinstance(self.heartbeat_interval, int) or self.heartbeat_interval < 10 or self.heartbeat_interval > 300:
            return False, "heartbeat_interval must be 10-300 seconds"
        if not re.fullmatch(r"\d+\.\d+\.\d+", self.version):
            return False, f"version '{self.version}' must match semver"
        return True, ""


class AgentRegistry:
    def __init__(self, load_defaults: bool = True) -> None:
        self.manifests: dict[str, AgentManifest] = {}
        self._name_index: dict[str, str] = {}
        if load_defaults:
            self._load_defaults()

    def _load_defaults(self) -> None:
        for agent_data in DEFAULT_ECOSYSTEM_AGENTS:
            manifest = AgentManifest(agent_data)
            self.register(manifest)

    def register(self, manifest: AgentManifest) -> bool:
        ok, msg = manifest.validate()
        if not ok:
            raise ManifestError(msg)
        self.manifests[manifest.agent_id] = manifest
        self._name_index[manifest.name.upper()] = manifest.agent_id
        return True

    def get(self, agent_id: str) -> Optional[AgentManifest]:
        return self.manifests.get(agent_id)

    def get_by_name(self, name: str) -> Optional[AgentManifest]:
        agent_id = self._name_index.get(name.upper())
        if agent_id:
            return self.manifests.get(agent_id)
        return None

    def list_all(self) -> list[AgentManifest]:
        return list(self.manifests.values())

    def discover_by_capability(self, capability: str) -> list[AgentManifest]:
        return [m for m in self.manifests.values() if capability in m.capabilities]

    def discover_by_intent(self, intent: str) -> list[AgentManifest]:
        return [m for m in self.manifests.values() if intent in m.intents]


class AgentDiscovery:
    def __init__(self, registry: AgentRegistry):
        self.registry = registry

    def find_agent(self, agent_id: str) -> Optional[AgentManifest]:
        return self.registry.get(agent_id)

    def find_by_name(self, name: str) -> Optional[AgentManifest]:
        return self.registry.get_by_name(name)

    def find_agents_for_intent(self, intent: str) -> list[str]:
        return [m.agent_id for m in self.registry.discover_by_intent(intent)]

    def find_agents_for_capability(self, capability: str) -> list[str]:
        return [m.agent_id for m in self.registry.discover_by_capability(capability)]


def create_default_registry() -> AgentRegistry:
    """Create and return an AgentRegistry pre-populated with all 10 sovereign agents."""
    return AgentRegistry(load_defaults=True)

