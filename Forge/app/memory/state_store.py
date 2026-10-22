"""
StateStore: Memory and state persistence interface for FORGE.
Handles projects, tasks, task graphs, checkpoints, audit events, and artifact records.
"""

import json
from datetime import UTC, datetime
from typing import Any

from app.core.logging import get_logger
from app.memory.db import DatabaseManager, db_manager
from app.memory.models import (
    ArtifactRecord,
    AuditEvent,
    Checkpoint,
    ProjectWorkspace,
    TaskEntity,
    TaskGraph,
    TaskMode,
    TaskNode,
    TaskState,
)

logger = get_logger("memory.state_store")


class StateStore:
    """Provides high-level state persistence methods over SQLite."""

    def __init__(self, db: DatabaseManager | None = None):
        self.db = db or db_manager

    # --- Project Management ---

    async def create_project(self, project: ProjectWorkspace) -> ProjectWorkspace:
        """Persist a new project workspace."""
        async with self.db.connection() as conn:
            await conn.execute(
                """
                INSERT INTO projects (id, name, description, workspace_path, config, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project.id,
                    project.name,
                    project.description,
                    project.workspace_path,
                    json.dumps(project.config),
                    project.created_at.isoformat(),
                    project.updated_at.isoformat(),
                ),
            )
            await conn.commit()
        logger.debug(f"Saved project: {project.id} ({project.name})")
        return project

    async def get_project(self, project_id: str) -> ProjectWorkspace | None:
        """Retrieve project workspace by ID."""
        async with self.db.connection() as conn:
            async with conn.execute(
                "SELECT id, name, description, workspace_path, config, created_at, updated_at FROM projects WHERE id = ?",
                (project_id,),
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None
                return ProjectWorkspace(
                    id=row["id"],
                    name=row["name"],
                    description=row["description"],
                    workspace_path=row["workspace_path"],
                    config=json.loads(row["config"]),
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                )

    async def list_projects(self) -> list[ProjectWorkspace]:
        """List all project workspaces."""
        async with self.db.connection() as conn:
            async with conn.execute("SELECT * FROM projects ORDER BY created_at DESC") as cursor:
                rows = await cursor.fetchall()
                return [
                    ProjectWorkspace(
                        id=row["id"],
                        name=row["name"],
                        description=row["description"],
                        workspace_path=row["workspace_path"],
                        config=json.loads(row["config"]),
                        created_at=datetime.fromisoformat(row["created_at"]),
                        updated_at=datetime.fromisoformat(row["updated_at"]),
                    )
                    for row in rows
                ]

    # --- Task Management ---

    async def create_task(self, task: TaskEntity) -> TaskEntity:
        """Persist a new task entity."""
        async with self.db.connection() as conn:
            await conn.execute(
                """
                INSERT INTO tasks (id, goal, requirements, mode, workspace_path, max_budget, budget_consumed, state, progress_percentage, error_message, metadata, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.id,
                    task.goal,
                    json.dumps(task.requirements),
                    task.mode.value,
                    task.workspace_path,
                    task.max_budget,
                    task.budget_consumed,
                    task.state.value,
                    task.progress_percentage,
                    task.error_message,
                    json.dumps(task.metadata),
                    task.created_at.isoformat(),
                    task.updated_at.isoformat(),
                ),
            )
            await conn.commit()
        logger.debug(f"Created task: {task.id}")
        return task

    async def get_task(self, task_id: str) -> TaskEntity | None:
        """Retrieve task entity by ID."""
        async with (
            self.db.connection() as conn,
            conn.execute(
                "SELECT * FROM tasks WHERE id = ?",
                (task_id,),
            ) as cursor,
        ):
            row = await cursor.fetchone()
            if not row:
                return None
            metadata = {}
            if "metadata" in row.keys() and row["metadata"]:
                try:
                    metadata = json.loads(row["metadata"])
                except Exception:
                    metadata = {}
            return TaskEntity(
                id=row["id"],
                goal=row["goal"],
                requirements=json.loads(row["requirements"]),
                mode=TaskMode(row["mode"]),
                workspace_path=row["workspace_path"],
                max_budget=row["max_budget"],
                budget_consumed=row["budget_consumed"],
                state=TaskState(row["state"]),
                progress_percentage=row["progress_percentage"],
                error_message=row["error_message"],
                metadata=metadata,
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )

    async def update_task_state(
        self,
        task_id: str,
        state: TaskState,
        progress_percentage: int | None = None,
        error_message: str | None = None,
        budget_increment: float = 0.0,
    ) -> TaskEntity | None:
        """Update task state, progress, and budget consumed."""
        now = datetime.now(UTC).isoformat()
        async with self.db.connection() as conn:
            async with conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None

            new_progress = (
                progress_percentage
                if progress_percentage is not None
                else row["progress_percentage"]
            )
            new_budget = row["budget_consumed"] + budget_increment

            await conn.execute(
                """
                UPDATE tasks
                SET state = ?, progress_percentage = ?, error_message = ?, budget_consumed = ?, updated_at = ?
                WHERE id = ?
                """,
                (state.value, new_progress, error_message, new_budget, now, task_id),
            )
            await conn.commit()

        return await self.get_task(task_id)

    async def save_task(self, task: TaskEntity) -> TaskEntity:
        """Upsert a task entity."""
        now = datetime.now(UTC).isoformat()
        async with self.db.connection() as conn:
            async with conn.execute("SELECT id FROM tasks WHERE id = ?", (task.id,)) as cursor:
                row = await cursor.fetchone()
            if row:
                await conn.execute(
                    """
                    UPDATE tasks
                    SET goal = ?, requirements = ?, mode = ?, workspace_path = ?, max_budget = ?,
                        budget_consumed = ?, state = ?, progress_percentage = ?, error_message = ?, metadata = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        task.goal,
                        json.dumps(task.requirements),
                        task.mode.value,
                        task.workspace_path,
                        task.max_budget,
                        task.budget_consumed,
                        task.state.value,
                        task.progress_percentage,
                        task.error_message,
                        json.dumps(task.metadata),
                        now,
                        task.id,
                    ),
                )
            else:
                await conn.execute(
                    """
                    INSERT INTO tasks (id, goal, requirements, mode, workspace_path, max_budget, budget_consumed, state, progress_percentage, error_message, metadata, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        task.id,
                        task.goal,
                        json.dumps(task.requirements),
                        task.mode.value,
                        task.workspace_path,
                        task.max_budget,
                        task.budget_consumed,
                        task.state.value,
                        task.progress_percentage,
                        task.error_message,
                        json.dumps(task.metadata),
                        task.created_at.isoformat(),
                        now,
                    ),
                )
            await conn.commit()
        return task

    async def list_tasks(
        self,
        state: TaskState | None = None,
        limit: int = 50,
        since_timestamp: datetime | None = None,
    ) -> list[TaskEntity]:
        """List tasks ordered by created_at DESC with optional state/time filters."""
        query = "SELECT * FROM tasks"
        params: list[Any] = []
        conditions: list[str] = []
        if state is not None:
            conditions.append("state = ?")
            params.append(state.value)
        if since_timestamp is not None:
            conditions.append("updated_at >= ?")
            params.append(since_timestamp.isoformat())
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        async with self.db.connection() as conn, conn.execute(query, tuple(params)) as cursor:
            rows = await cursor.fetchall()
            results = []
            for row in rows:
                metadata = {}
                if "metadata" in row.keys() and row["metadata"]:
                    try:
                        metadata = json.loads(row["metadata"])
                    except Exception:
                        metadata = {}
                results.append(
                    TaskEntity(
                        id=row["id"],
                        goal=row["goal"],
                        requirements=json.loads(row["requirements"]),
                        mode=TaskMode(row["mode"]),
                        workspace_path=row["workspace_path"],
                        max_budget=row["max_budget"],
                        budget_consumed=row["budget_consumed"],
                        state=TaskState(row["state"]),
                        progress_percentage=row["progress_percentage"],
                        error_message=row["error_message"],
                        metadata=metadata,
                        created_at=datetime.fromisoformat(row["created_at"]),
                        updated_at=datetime.fromisoformat(row["updated_at"]),
                    )
                )
            return results

    async def count_tasks(self) -> int:
        """Count total tasks in the store."""
        async with self.db.connection() as conn, conn.execute("SELECT COUNT(*) as cnt FROM tasks") as cursor:
            row = await cursor.fetchone()
            return row["cnt"] if row else 0

    # --- Audit Events ---

    async def record_event(
        self, task_id: str, event_type: str, payload: dict[str, Any] | None = None
    ) -> AuditEvent:
        """Record an audit / telemetry event for a task."""
        event = AuditEvent(
            task_id=task_id,
            event_type=event_type,
            payload=payload or {},
        )
        async with self.db.connection() as conn:
            await conn.execute(
                """
                INSERT INTO audit_events (id, task_id, event_type, payload, timestamp)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    event.id,
                    event.task_id,
                    event.event_type,
                    json.dumps(event.payload),
                    event.timestamp.isoformat(),
                ),
            )
            await conn.commit()
        logger.debug(f"Audit event recorded [{event_type}] for task {task_id}")
        return event

    async def get_audit_trail(self, task_id: str) -> list[AuditEvent]:
        """Retrieve chronological audit trail for a task/run."""
        async with (
            self.db.connection() as conn,
            conn.execute(
                "SELECT * FROM audit_events WHERE task_id = ? ORDER BY timestamp ASC",
                (task_id,),
            ) as cursor,
        ):
            rows = await cursor.fetchall()
            return [
                AuditEvent(
                    id=row["id"],
                    task_id=row["task_id"],
                    event_type=row["event_type"],
                    payload=json.loads(row["payload"]),
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                )
                for row in rows
            ]

    # --- Artifact Records ---

    async def record_artifact(self, artifact: ArtifactRecord) -> ArtifactRecord:
        """Persist an artifact metadata record."""
        async with self.db.connection() as conn:
            await conn.execute(
                """
                INSERT INTO artifacts (id, task_id, name, path, file_type, size_bytes, checksum, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact.id,
                    artifact.task_id,
                    artifact.name,
                    artifact.path,
                    artifact.file_type,
                    artifact.size_bytes,
                    artifact.checksum,
                    artifact.created_at.isoformat(),
                ),
            )
            await conn.commit()
        logger.debug(f"Recorded artifact: {artifact.id} ({artifact.name})")
        return artifact

    async def get_artifact(self, artifact_id: str) -> ArtifactRecord | None:
        """Retrieve artifact record by ID."""
        async with self.db.connection() as conn:
            async with conn.execute(
                "SELECT * FROM artifacts WHERE id = ?", (artifact_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None
                return ArtifactRecord(
                    id=row["id"],
                    task_id=row["task_id"],
                    name=row["name"],
                    path=row["path"],
                    file_type=row["file_type"],
                    size_bytes=row["size_bytes"],
                    checksum=row["checksum"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                )

    async def list_artifacts_for_task(self, task_id: str) -> list[ArtifactRecord]:
        """List all artifacts generated by a task."""
        async with (
            self.db.connection() as conn,
            conn.execute(
                "SELECT * FROM artifacts WHERE task_id = ? ORDER BY created_at ASC", (task_id,)
            ) as cursor,
        ):
            rows = await cursor.fetchall()
            return [
                ArtifactRecord(
                    id=row["id"],
                    task_id=row["task_id"],
                    name=row["name"],
                    path=row["path"],
                    file_type=row["file_type"],
                    size_bytes=row["size_bytes"],
                    checksum=row["checksum"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
                for row in rows
            ]

    # --- Task Graph Persistence ---

    async def save_task_graph(self, graph: TaskGraph) -> TaskGraph:
        """Upsert a task graph."""
        graph.updated_at = datetime.now(UTC)
        nodes_json = json.dumps({k: v.model_dump(mode="json") for k, v in graph.nodes.items()})
        edges_json = json.dumps([e.model_dump(mode="json") for e in graph.edges])

        async with self.db.connection() as conn:
            await conn.execute(
                """
                INSERT INTO task_graphs (id, project_id, goal, nodes, edges, status, current_node_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    goal = excluded.goal,
                    nodes = excluded.nodes,
                    edges = excluded.edges,
                    status = excluded.status,
                    current_node_id = excluded.current_node_id,
                    updated_at = excluded.updated_at
                """,
                (
                    graph.id,
                    graph.project_id,
                    graph.goal,
                    nodes_json,
                    edges_json,
                    graph.status.value,
                    graph.current_node_id,
                    graph.created_at.isoformat(),
                    graph.updated_at.isoformat(),
                ),
            )
            await conn.commit()
        return graph

    async def get_task_graph(self, graph_id: str) -> TaskGraph | None:
        """Load a task graph by ID."""
        async with self.db.connection() as conn:
            async with conn.execute(
                "SELECT id, project_id, goal, nodes, edges, status, current_node_id, created_at, updated_at FROM task_graphs WHERE id = ?",
                (graph_id,),
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None

                raw_nodes = json.loads(row["nodes"])
                nodes = {k: TaskNode(**v) for k, v in raw_nodes.items()}
                raw_edges = json.loads(row["edges"])

                return TaskGraph(
                    id=row["id"],
                    project_id=row["project_id"],
                    goal=row["goal"],
                    nodes=nodes,
                    edges=raw_edges,
                    status=TaskState(row["status"]),
                    current_node_id=row["current_node_id"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                )

    async def get_latest_task_graph_for_project(self, project_id: str) -> TaskGraph | None:
        """Fetch the most recent task graph for a project or task."""
        async with (
            self.db.connection() as conn,
            conn.execute(
                "SELECT id FROM task_graphs WHERE project_id = ? ORDER BY created_at DESC LIMIT 1",
                (project_id,),
            ) as cursor,
        ):
            row = await cursor.fetchone()
            if not row:
                return None
            return await self.get_task_graph(row["id"])

    # --- Checkpoints ---

    async def save_checkpoint(self, checkpoint: Checkpoint) -> Checkpoint:
        """Persist a state checkpoint."""
        async with self.db.connection() as conn:
            await conn.execute(
                """
                INSERT INTO checkpoints (id, project_id, task_id, step_number, state_data, checksum, timestamp, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    checkpoint.id,
                    checkpoint.project_id,
                    checkpoint.task_id,
                    checkpoint.step_number,
                    json.dumps(checkpoint.state_data),
                    checkpoint.checksum,
                    checkpoint.timestamp.isoformat(),
                    checkpoint.description,
                ),
            )
            await conn.commit()
        logger.debug(
            f"Saved checkpoint {checkpoint.id} for task/project {checkpoint.project_id} (step {checkpoint.step_number})"
        )
        return checkpoint

    async def list_checkpoints(self, project_id: str) -> list[Checkpoint]:
        """List checkpoints for a task or project ordered by step number."""
        async with self.db.connection() as conn:
            async with conn.execute(
                "SELECT * FROM checkpoints WHERE project_id = ? ORDER BY step_number ASC, timestamp ASC",
                (project_id,),
            ) as cursor:
                rows = await cursor.fetchall()
                return [
                    Checkpoint(
                        id=row["id"],
                        project_id=row["project_id"],
                        task_id=row["task_id"],
                        step_number=row["step_number"],
                        state_data=json.loads(row["state_data"]),
                        checksum=row["checksum"],
                        timestamp=datetime.fromisoformat(row["timestamp"]),
                        description=row["description"],
                    )
                    for row in rows
                ]

    async def get_latest_checkpoint(self, project_id: str) -> Checkpoint | None:
        """Retrieve the most recent checkpoint for a task or project."""
        async with self.db.connection() as conn:
            async with conn.execute(
                "SELECT * FROM checkpoints WHERE project_id = ? ORDER BY step_number DESC, timestamp DESC LIMIT 1",
                (project_id,),
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None
                return Checkpoint(
                    id=row["id"],
                    project_id=row["project_id"],
                    task_id=row["task_id"],
                    step_number=row["step_number"],
                    state_data=json.loads(row["state_data"]),
                    checksum=row["checksum"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    description=row["description"],
                )
