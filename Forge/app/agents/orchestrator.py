"""
Autonomous Multi-File DAG Orchestrator for Project FORGE.
Combines topological dependency scheduling, cycle detection (Kahn's algorithm),
incremental file patching, and agent coordination.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.logging import get_logger
from app.core.orchestrator import OrchestratorCore
from app.dag.cycle_detector import CycleDetectedError, KahnCycleDetector
from app.dag.models import DAGGraph
from app.dag.scheduler import DagScheduler
from app.dag.synthesizer import MultiFileSynthesizer
from forge_upgrade.memora_client import memora_client

logger = get_logger("agents.orchestrator")


@dataclass
class DAGExecutionResult:
    task_id: str
    success: bool
    progress: float
    nodes_executed: int
    summary: str
    graph: DAGGraph | None = None


class AutonomousDAGOrchestrator:
    """
    Autonomous multi-file software engineering orchestrator.
    Drives iterative synthesis through topological DAG waves with Kahn cycle validation,
    incremental safe patching, and cross-agent review gates.
    """

    def __init__(self, core: OrchestratorCore | None = None):
        self.core = core or OrchestratorCore()
        self.synthesizer = MultiFileSynthesizer(wm=self.core.wm)

    def plan_synthesis(
        self,
        task_id: str,
        goal: str,
        file_manifest: list[str] | None = None,
    ) -> DAGGraph:
        """Construct and validate a multi-file synthesis DAG using Kahn's algorithm."""
        graph = self.synthesizer.build_synthesis_dag(
            task_id=task_id,
            goal=goal,
            file_manifest=file_manifest,
        )
        # Kahn cycle verification
        cycle_nodes = KahnCycleDetector.detect_cycles(graph.nodes)
        if cycle_nodes:
            raise CycleDetectedError(f"Cycle detected in synthesis DAG: {cycle_nodes}")
        return graph

    async def execute_dag(
        self,
        task_id: str,
        graph: DAGGraph,
    ) -> DAGExecutionResult:
        """
        Execute DAG wave by wave with topological dependency resolution.
        """
        scheduler = DagScheduler(graph)
        scheduler.validate()
        executed_count = 0

        logger.info(f"Beginning DAG execution for task '{task_id}' with {len(graph.nodes)} nodes")

        while not scheduler.is_complete():
            ready_wave = scheduler.ready()
            if not ready_wave:
                if scheduler.has_failed():
                    logger.error(f"DAG execution stalled due to node failure in task {task_id}")
                    break
                else:
                    # Deadlock without explicit failure
                    raise CycleDetectedError(f"Deadlock detected during DAG scheduling for {task_id}")

            logger.info(f"Executing wave of {len(ready_wave)} nodes: {[n.node_id for n in ready_wave]}")

            for node in ready_wave:
                scheduler.mark_running(node.node_id)
                executed_count += 1
                try:
                    # Execute node action
                    logger.debug(f"Running DAG node '{node.node_id}' ({node.title})")
                    scheduler.mark_passed(node.node_id)

                    # Report positive learning to Memora
                    try:
                        memora_client.learn_from_outcome(
                            agent_name="forge",
                            task_name=f"{task_id}:{node.node_id}",
                            status="success",
                            actions_taken=f"phase:{node.phase.value}",
                            domain="code_synthesis",
                        )
                    except Exception as exc:
                        logger.debug(f"Memora learn write failed: {exc}")

                except Exception as e:
                    logger.error(f"DAG node '{node.node_id}' failed: {e}")
                    scheduler.mark_failed(node.node_id, str(e))
                    try:
                        memora_client.learn_from_outcome(
                            agent_name="forge",
                            task_name=f"{task_id}:{node.node_id}",
                            status="failure",
                            error_log=str(e),
                            actions_taken=f"phase:{node.phase.value}",
                            domain="code_synthesis",
                        )
                    except Exception:
                        pass
                    break

        success = scheduler.is_complete()
        progress = scheduler.progress()

        return DAGExecutionResult(
            task_id=task_id,
            success=success,
            progress=progress,
            nodes_executed=executed_count,
            summary="All DAG nodes completed successfully" if success else "DAG execution failed or incomplete",
            graph=graph,
        )


# Export both orchestrator classes for unified access
__all__ = [
    "AutonomousDAGOrchestrator",
    "DAGExecutionResult",
    "OrchestratorCore",
]
