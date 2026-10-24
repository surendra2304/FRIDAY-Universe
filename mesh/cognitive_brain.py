"""Cognitive Brain Architecture for FRIDAY Universe.

Phase 3: Cognitive Reflection Loop & Self-Developing Brain.
Implements:
- 4-Layer Cognitive Architecture (Episodes, Lessons, Policy, Meta-Learning)
- Auto-Fix Zones (Free, Informed, Guarded, Forbidden)
- Reflection Loop: Perception -> Deliberation -> Action -> Outcome -> Reflection -> Lesson
"""
from __future__ import annotations

import logging
import time
from enum import Enum
from typing import Any, Dict, List, Optional

from mesh.memory_fabric import UniversalMemoryFabric, fabric, lesson_distiller
from mesh.envelope import AgentEnvelope

logger = logging.getLogger("cognitive_brain")


class AutoFixZone(str, Enum):
    FREE = "free"          # Read/Think
    INFORMED = "informed"  # Self-heal (code edits)
    GUARDED = "guarded"    # Config changes (requires human sign-off)
    FORBIDDEN = "forbidden" # Data deletion / fund transfers


class CognitiveLayer(str, Enum):
    EPISODES = "episodes"
    LESSONS = "lessons"
    POLICY = "policy"
    META_LEARNING = "meta_learning"


# Action types that are allowed in each Auto-Fix Zone.
_FORBIDDEN_ACTIONS = {
    "delete",
    "drop",
    "destroy",
    "transfer",
    "fund_transfer",
    "withdraw",
    "deploy_production",
    "force_push",
    "reset_database",
}
_GUARDED_ACTIONS = {
    "config_change",
    "deploy",
    "release",
    "rollback",
    "scale",
    "environment_change",
    "secret_rotation",
}
_INFORMED_ACTIONS = {
    "code_edit",
    "self_heal",
    "fix",
    "patch",
    "refactor",
    "test_fix",
}


class CognitiveDecision:
    """A lightweight decision object produced by perception/deliberation."""

    def __init__(
        self,
        layer: CognitiveLayer,
        action: str,
        confidence: float = 0.5,
        zone: AutoFixZone = AutoFixZone.INFORMED,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.layer = layer
        self.action = action
        self.confidence = float(confidence)
        self.zone = zone
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "layer": self.layer.value,
            "action": self.action,
            "confidence": self.confidence,
            "zone": self.zone.value,
            "metadata": self.metadata,
        }


class CognitiveBrain:
    """Core Cognitive Engine driving self-improvement and autonomous recovery."""

    def __init__(self, fabric: UniversalMemoryFabric = fabric):
        self.fabric = fabric
        self.distiller = lesson_distiller

    def process_perception(self, observation: Dict[str, Any]) -> CognitiveDecision:
        """Analyze incoming data to determine the cognitive phase."""
        status = str(observation.get("status", "")).lower()
        action = str(observation.get("action", observation.get("intent", "deliberate")))
        error = observation.get("error") or observation.get("error_log") or ""

        if status in {"failed", "error", "failure"} or error:
            layer = CognitiveLayer.LESSONS
            action = "distill_failure"
        elif observation.get("policy") or observation.get("rule"):
            layer = CognitiveLayer.POLICY
            action = "apply_policy"
        elif observation.get("meta") or observation.get("pattern") or observation.get("recurring"):
            layer = CognitiveLayer.META_LEARNING
            action = "update_meta_model"
        else:
            layer = CognitiveLayer.EPISODES

        zone = self._determine_zone({"action": action, **observation})
        confidence = 0.75 if layer == CognitiveLayer.LESSONS else 0.65
        return CognitiveDecision(layer=layer, action=action, confidence=confidence, zone=zone)

    def deliberate(self, state: CognitiveDecision) -> Dict[str, Any]:
        """Perform reasoning based on observation and existing policies."""
        memories = self.fabric.recall(
            query=state.action,
            agent_name="FRIDAY_COGNITIVE_BRAIN",
            limit=5,
        )
        lessons = self.distiller.get_applied_lessons(
            agent_name="FRIDAY_COGNITIVE_BRAIN",
            domain="cognitive_loop",
        )

        confidence = state.confidence
        if memories:
            confidence = min(0.95, confidence + 0.10)
        if lessons:
            confidence = min(0.98, confidence + 0.05)

        suggested_action = state.action
        if state.zone == AutoFixZone.FORBIDDEN:
            suggested_action = "blocked"
        elif state.zone == AutoFixZone.GUARDED:
            suggested_action = "request_human_signoff"

        return {
            "suggested_action": suggested_action,
            "confidence": confidence,
            "layer": state.layer.value,
            "zone": state.zone.value,
            "recalled_memories": [m.to_dict() for m in memories],
            "lessons": [l.to_dict() for l in lessons],
        }

    def execute_with_guardrails(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute action within assigned Auto-Fix Zones."""
        zone = self._determine_zone(action)
        action_name = str(action.get("action", action.get("intent", "unknown"))).lower()

        if zone == AutoFixZone.FORBIDDEN:
            return {
                "status": "BLOCKED",
                "reason": "Zone Forbidden",
                "zone": zone.value,
                "action": action_name,
            }

        if zone == AutoFixZone.GUARDED:
            approved = action.get("approved") or action.get("human_signoff")
            if not approved:
                return {
                    "status": "PENDING_HUMAN_SIGNOFF",
                    "reason": "Guarded action requires explicit human approval",
                    "zone": zone.value,
                    "action": action_name,
                }
            # Approved guarded actions still record the decision in the fabric.
            self.fabric.record_auto_ingested_event(
                agent_name="FRIDAY_COGNITIVE_BRAIN",
                action=action_name,
                status="approved",
                payload_summary=str(action),
            )
            return {
                "status": "SUCCESS",
                "zone": zone.value,
                "action": action_name,
                "approved": True,
            }

        # INFORMED and FREE actions are allowed. INFORMED self-heal actions are
        # recorded as ecosystem lessons so future runs can recall them.
        self.fabric.record_auto_ingested_event(
            agent_name="FRIDAY_COGNITIVE_BRAIN",
            action=action_name,
            status="executed",
            payload_summary=str(action),
        )
        return {
            "status": "SUCCESS",
            "zone": zone.value,
            "action": action_name,
        }

    def reflect_and_distill(self, outcome: Dict[str, Any]) -> None:
        """Close the loop: Learn from outcomes to update procedural memory."""
        status = str(outcome.get("status", "")).upper()
        task = outcome.get("task", outcome.get("action", "unknown"))
        error = outcome.get("error", outcome.get("error_log", ""))

        if status in {"FAILED", "ERROR"}:
            self.distiller.distill_from_failure(
                agent_name="FRIDAY_COGNITIVE_BRAIN",
                task_name=task,
                error_log=error,
                domain="cognitive_loop",
            )
        else:
            self.fabric.record_auto_ingested_event(
                agent_name="FRIDAY_COGNITIVE_BRAIN",
                action=task,
                status=status or "completed",
                payload_summary=str(outcome),
            )

    def _determine_zone(self, action: Dict[str, Any]) -> AutoFixZone:
        action_name = str(action.get("action", action.get("intent", ""))).lower()
        if action_name in _FORBIDDEN_ACTIONS:
            return AutoFixZone.FORBIDDEN
        if action_name in _GUARDED_ACTIONS:
            return AutoFixZone.GUARDED
        if action_name in _INFORMED_ACTIONS:
            return AutoFixZone.INFORMED
        return AutoFixZone.FREE

    def process_envelope(self, envelope: AgentEnvelope) -> CognitiveDecision:
        """Turn an inbound mesh envelope into a cognitive decision."""
        observation = {
            "status": envelope.payload.get("status", ""),
            "action": envelope.intent or envelope.payload.get("action", ""),
            "error": envelope.payload.get("error", ""),
            **{k: v for k, v in envelope.payload.items() if k not in {"status", "action", "error"}},
        }
        return self.process_perception(observation)
