"""
FORGE Specialized Ecosystem Adapter for Memora
Provides high-level methods for software engineering, architectural decision tracking,
and project coding constraint retrieval.
"""
from typing import Optional, Dict, Any, List
import logging

from adapters.base_adapter import BaseAgentAdapter
from core.memory.session_needles import classify_needle

logger = logging.getLogger(__name__)

#: Provenance marker for observations recorded through this adapter.
NEEDLE_PATTERN_TAG = "claude-mem-needles"

class ForgeAdapter(BaseAgentAdapter):
    """
    Specialized adapter for FORGE, the software engineering and code generation agent.
    """
    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: Optional[str] = None,
        default_namespace: str = "memora://forge/private",
        http_client: Optional[Any] = None
    ):
        super().__init__(
            agent_name="forge",
            base_url=base_url,
            api_key=api_key,
            default_namespace=default_namespace,
            role="worker",
            http_client=http_client
        )

    def save_architecture_decision(
        self,
        decision_text: str,
        project_id: str,
        confidence: float = 1.0,
        importance: float = 0.9,
        provenance: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Saves an architectural or design decision into the project namespace memora://forge/projects/{project_id}.
        """
        target_namespace = f"memora://forge/projects/{project_id}"
        prov = {
            **(provenance or {}),
            "category": "architecture_decision",
            "project_id": project_id,
            "recorded_by": "forge_engine"
        }
        return self.write_memory(
            content_text=decision_text,
            memory_type="decision",
            target_namespace_path=target_namespace,
            confidence=confidence,
            importance=importance,
            provenance=prov,
            purpose=f"Architectural decision for project {project_id}"
        )

    def record_session_observation(
        self,
        session_id: str,
        content: str,
        kind: str = "observation",
        project_id: Optional[str] = None,
        confidence: float = 0.9,
        importance: float = 0.6,
    ) -> Dict[str, Any]:
        """Record one Forge session observation with its claude-mem needle kind.

        TASK-MEM-031: the Memora-side Forge wire for the needle taxonomy.
        The content is classified (``core.memory.session_needles``) and
        the needle kind is stored in provenance. A ``sensitive`` needle
        is awareness-only — the content is never stored; a placeholder
        marks the session and kind, exactly as claude-mem treats
        sensitive observations.
        """
        needle_kind = classify_needle(content or "")
        if project_id:
            target_namespace = f"memora://forge/projects/{project_id}"
        else:
            target_namespace = self.default_namespace
        provenance = {
            "pattern": NEEDLE_PATTERN_TAG,
            "session_id": session_id,
            "event_kind": kind,
            "needle_kind": needle_kind,
        }
        if needle_kind == "sensitive":
            stored_text = f"[sensitive observation withheld — session {session_id}]"
            provenance["withheld"] = True
        else:
            stored_text = content
        return self.write_memory(
            content_text=stored_text,
            memory_type="episodic",
            target_namespace_path=target_namespace,
            confidence=confidence,
            importance=importance,
            provenance=provenance,
            purpose=f"Forge session observation for session {session_id}",
        )

    def get_coding_constraints(
        self,
        project_id: str,
        query: str = "decision architecture constraint guidelines",
        include_shared: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Retrieves procedural coding constraints and architectural decision memories for a specific project.
        Checks both project-scoped and shared remediation namespaces.
        """
        constraints = []
        
        # 1. Query project-specific decisions
        project_ns = f"memora://forge/projects/{project_id}"
        try:
            forge_res = self.search_memories(
                query=query,
                namespace_path=project_ns,
                limit=15,
                min_score=0.0,
                purpose=f"Retrieving coding constraints for project {project_id}"
            )
            constraints.extend(forge_res)
        except Exception as e:
            logger.debug(f"No private project decisions found for {project_id}: {e}")

        # 2. Query shared project remediations/policies if requested
        if include_shared:
            shared_ns = f"memora://shared/projects/{project_id}"
            try:
                shared_res = self.search_memories(
                    query=query,
                    namespace_path=shared_ns,
                    limit=15,
                    min_score=0.0,
                    purpose=f"Retrieving shared security constraints for project {project_id}"
                )
                constraints.extend(shared_res)
            except Exception as e:
                logger.debug(f"No shared security constraints found for {project_id}: {e}")

        return constraints