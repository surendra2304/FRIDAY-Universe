"""
StateStore: Memory and state persistence interface for FORGE.

Handles projects, tasks, task graphs, checkpoints, audit events, and artifact
records. Every statement targets Oracle Autonomous Database and uses named
``:bind`` parameters; upserts use ``MERGE`` and row limits use
``FETCH FIRST :row_limit ROWS ONLY``.
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


# Columns that Oracle returns as LOB objects. They must be read before being
# parsed/returned; ``str(lob)`` would produce a repr instead of the payload.
_CLOB_COLUMNS = (
    "goal",
    "requirements",
    "error_message",
    "metadata",
    "description",
    "config",
    "payload",
    "nodes",
    "edges",
    "state_data",
)


def _as_text(value: Any) -> Any:
    """Read an Oracle CLOB/LOB value (or pass a plain value through)."""
    if value is None:
        return None
    read = getattr(value, "read", None)
    if callable(read):
        return read()
    return value


def _loads(value: Any, default: Any) -> Any:
    """Parse a JSON CLOB, tolerating NULL/empty and legacy malformed rows."""
    text_value = _as_text(value)
    if text_value is None or text_value == "":
        return default
    try:
        return json.loads(text_value)
    except (TypeError, ValueError):
        return default


def _text(value: str | None) -> str | None:
    """Normalise optional text for a nullable column.

    Oracle stores ``''`` as ``NULL``, so an empty string written to a nullable
    column already comes back as ``None``. Converting on write keeps the
    round-trip identical.
    """
    if value is None:
        return None
    return value or None


def _required_text(value: str | None, default: str) -> str:
    """Normalise text bound to a ``NOT NULL`` column.

    An empty string would be inserted as ``NULL`` on Oracle and rejected with
    ``ORA-01400``, so a documented placeholder is used instead of failing the
    whole write.
    """
    if value is None or value == "":
        return default
    return value


class StateStore:
    """Provides high-level state persistence methods over Oracle."""

    def __init__(self, db: DatabaseManager | None = None):
        self.db = db or db_manager

    @property
    def _is_oracle(self) -> bool:
        # False only for the explicit test-only SQLite backend.
        return bool(getattr(self.db, "is_oracle", True))

    # --- Project Management ---

    async def create_project(self, project: ProjectWorkspace) -> ProjectWorkspace:
        """Persist a new project workspace."""
        async with self.db.connection() as conn:
            await conn.execute(
                """
                INSERT INTO projects (id, name, description, workspace_path, config, created_at, updated_at)
                VALUES (:id, :name, :description, :workspace_path, :config, :created_at, :updated_at)
                """,
                {
                    "id": project.id,
                    "name": _required_text(project.name, "untitled-project"),
                    "description": _text(project.description),
                    "workspace_path": _required_text(project.workspace_path, "."),
                    "config": json.dumps(project.config),
                    "created_at": project.created_at.isoformat(),
                    "updated_at": project.updated_at.isoformat(),
                },
                clob_params=("description", "config"),
            )
            await conn.commit()
        logger.debug(f"Saved project: {project.id} ({project.name})")
        return project

    async def get_project(self, project_id: str) -> ProjectWorkspace | None:
        """Retrieve project workspace by ID."""
        async with self.db.connection() as conn:
            async with conn.execute(
                "SELECT id, name, description, workspace_path, config, created_at, updated_at "
                "FROM projects WHERE id = :id",
                {"id": project_id},
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None
                return ProjectWorkspace(
                    id=row["id"],
                    name=row["name"],
                    description=_as_text(row["description"]),
                    workspace_path=row["workspace_path"],
                    config=_loads(row["config"], {}),
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                )

    async def list_projects(self) -> list[ProjectWorkspace]:
        """List all project workspaces."""
        async with self.db.connection() as conn:
            async with conn.execute(
                "SELECT * FROM projects ORDER BY created_at DESC"
            ) as cursor:
                rows = await cursor.fetchall()
                return [
                    ProjectWorkspace(
                        id=row["id"],
                        name=row["name"],
                        description=_as_text(row["description"]),
                        workspace_path=row["workspace_path"],
                        config=_loads(row["config"], {}),
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
                INSERT INTO tasks (id, goal, requirements, run_mode, workspace_path, max_budget, budget_consumed, state, progress_percentage, error_message, metadata, created_at, updated_at)
                VALUES (:id, :goal, :requirements, :run_mode, :workspace_path, :max_budget, :budget_consumed, :state, :progress_percentage, :error_message, :metadata, :created_at, :updated_at)
                """,
                {
                    "id": task.id,
                    "goal": _required_text(task.goal, "(empty goal)"),
                    "requirements": json.dumps(task.requirements),
                    "run_mode": task.mode.value,
                    "workspace_path": _required_text(task.workspace_path, "."),
                    "max_budget": task.max_budget,
                    "budget_consumed": task.budget_consumed,
                    "state": task.state.value,
                    "progress_percentage": task.progress_percentage,
                    "error_message": _text(task.error_message),
                    "metadata": json.dumps(task.metadata),
                    "created_at": task.created_at.isoformat(),
                    "updated_at": task.updated_at.isoformat(),
                },
                clob_params=("goal", "requirements", "error_message", "metadata"),
            )
            await conn.commit()
        logger.debug(f"Created task: {task.id}")
        return task

    def _task_from_row(self, row: Any) -> TaskEntity:
        return TaskEntity(
            id=row["id"],
            goal=_as_text(row["goal"]),
            requirements=_loads(row["requirements"], []),
            mode=TaskMode(row["run_mode"]),
            workspace_path=row["workspace_path"],
            max_budget=row["max_budget"],
            budget_consumed=row["budget_consumed"],
            state=TaskState(row["state"]),
            progress_percentage=row["progress_percentage"],
            error_message=_as_text(row["error_message"]),
            metadata=_loads(row["metadata"], {}),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    async def get_task(self, task_id: str) -> TaskEntity | None:
        """Retrieve task entity by ID."""
        async with (
            self.db.connection() as conn,
            conn.execute("SELECT * FROM tasks WHERE id = :id", {"id": task_id}) as cursor,
        ):
            row = await cursor.fetchone()
            if not row:
                return None
            return self._task_from_row(row)

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
            async with conn.execute(
                "SELECT * FROM tasks WHERE id = :id", {"id": task_id}
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None

            new_progress = (
                progress_percentage
                if progress_percentage is not None
                else row["progress_percentage"]
            )
            # Oracle returns NUMBER columns as decimal.Decimal; adding a float
            # budget increment to one raises TypeError, so coerce first.
            new_budget = float(row["budget_consumed"] or 0.0) + budget_increment

            await conn.execute(
                """
                UPDATE tasks
                SET state = :state, progress_percentage = :progress_percentage,
                    error_message = :error_message, budget_consumed = :budget_consumed,
                    updated_at = :updated_at
                WHERE id = :id
                """,
                {
                    "state": state.value,
                    "progress_percentage": new_progress,
                    "error_message": _text(error_message),
                    "budget_consumed": new_budget,
                    "updated_at": now,
                    "id": task_id,
                },
                clob_params=("error_message",),
            )
            await conn.commit()

        return await self.get_task(task_id)

    async def save_task(self, task: TaskEntity) -> TaskEntity:
        """Upsert a task entity (Oracle ``MERGE``)."""
        now = datetime.now(UTC).isoformat()
        params = {
            "id": task.id,
            "goal": _required_text(task.goal, "(empty goal)"),
            "requirements": json.dumps(task.requirements),
            "run_mode": task.mode.value,
            "workspace_path": _required_text(task.workspace_path, "."),
            "max_budget": task.max_budget,
            "budget_consumed": task.budget_consumed,
            "state": task.state.value,
            "progress_percentage": task.progress_percentage,
            "error_message": _text(task.error_message),
            "metadata": json.dumps(task.metadata),
            "created_at": task.created_at.isoformat(),
            "updated_at": now,
        }
        clob_params = ("goal", "requirements", "error_message", "metadata")

        async with self.db.connection() as conn:
            if self._is_oracle:
                await conn.execute(
                    """
                    MERGE INTO tasks t
                    USING (SELECT :id AS id FROM dual) src
                    ON (t.id = src.id)
                    WHEN MATCHED THEN UPDATE SET
                        t.goal = :goal,
                        t.requirements = :requirements,
                        t.run_mode = :run_mode,
                        t.workspace_path = :workspace_path,
                        t.max_budget = :max_budget,
                        t.budget_consumed = :budget_consumed,
                        t.state = :state,
                        t.progress_percentage = :progress_percentage,
                        t.error_message = :error_message,
                        t.metadata = :metadata,
                        t.updated_at = :updated_at
                    WHEN NOT MATCHED THEN INSERT
                        (id, goal, requirements, run_mode, workspace_path, max_budget,
                         budget_consumed, state, progress_percentage, error_message,
                         metadata, created_at, updated_at)
                    VALUES
                        (:id, :goal, :requirements, :run_mode, :workspace_path,
                         :max_budget, :budget_consumed, :state, :progress_percentage,
                         :error_message, :metadata, :created_at, :updated_at)
                    """,
                    params,
                    clob_params=clob_params,
                )
            else:
                # Explicit test-only SQLite backend (app.memory.sqlite_test_backend).
                async with conn.execute(
                    "SELECT id FROM tasks WHERE id = :id", {"id": task.id}
                ) as cursor:
                    exists = await cursor.fetchone()
                if exists:
                    await conn.execute(
                        """
                        UPDATE tasks
                        SET goal = :goal, requirements = :requirements,
                            run_mode = :run_mode, workspace_path = :workspace_path,
                            max_budget = :max_budget, budget_consumed = :budget_consumed,
                            state = :state, progress_percentage = :progress_percentage,
                            error_message = :error_message, metadata = :metadata,
                            updated_at = :updated_at
                        WHERE id = :id
                        """,
                        params,
                    )
                else:
                    await conn.execute(
                        """
                        INSERT INTO tasks (id, goal, requirements, run_mode, workspace_path, max_budget, budget_consumed, state, progress_percentage, error_message, metadata, created_at, updated_at)
                        VALUES (:id, :goal, :requirements, :run_mode, :workspace_path, :max_budget, :budget_consumed, :state, :progress_percentage, :error_message, :metadata, :created_at, :updated_at)
                        """,
                        params,
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
        params: dict[str, Any] = {}
        conditions: list[str] = []
        if state is not None:
            conditions.append("state = :state")
            params["state"] = state.value
        if since_timestamp is not None:
            conditions.append("updated_at >= :since_timestamp")
            params["since_timestamp"] = since_timestamp.isoformat()
        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY created_at DESC " + self.db.row_limit_clause()
        params["row_limit"] = limit

        async with self.db.connection() as conn:
            async with conn.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [self._task_from_row(row) for row in rows]

    async def count_tasks(self) -> int:
        """Count total tasks in the store."""
        async with self.db.connection() as conn:
            async with conn.execute("SELECT COUNT(*) AS cnt FROM tasks") as cursor:
                row = await cursor.fetchone()
                return int(row["cnt"]) if row else 0

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
                VALUES (:id, :task_id, :event_type, :payload, :timestamp)
                """,
                {
                    "id": event.id,
                    "task_id": event.task_id,
                    "event_type": _required_text(event.event_type, "unknown"),
                    "payload": json.dumps(event.payload),
                    "timestamp": event.timestamp.isoformat(),
                },
                clob_params=("payload",),
            )
            await conn.commit()
        logger.debug(f"Audit event recorded [{event_type}] for task {task_id}")
        return event

    async def get_audit_trail(self, task_id: str) -> list[AuditEvent]:
        """Retrieve chronological audit trail for a task/run."""
        async with (
            self.db.connection() as conn,
            conn.execute(
                "SELECT * FROM audit_events WHERE task_id = :task_id ORDER BY timestamp ASC",
                {"task_id": task_id},
            ) as cursor,
        ):
            rows = await cursor.fetchall()
            return [
                AuditEvent(
                    id=row["id"],
                    task_id=row["task_id"],
                    event_type=row["event_type"],
                    payload=_loads(row["payload"], {}),
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
                VALUES (:id, :task_id, :name, :path, :file_type, :size_bytes, :checksum, :created_at)
                """,
                {
                    "id": artifact.id,
                    "task_id": artifact.task_id,
                    "name": _required_text(artifact.name, "unnamed-artifact"),
                    "path": _required_text(artifact.path, "."),
                    "file_type": _required_text(artifact.file_type, "text/plain"),
                    "size_bytes": artifact.size_bytes,
                    "checksum": _text(artifact.checksum),
                    "created_at": artifact.created_at.isoformat(),
                },
            )
            await conn.commit()
        logger.debug(f"Recorded artifact: {artifact.id} ({artifact.name})")
        return artifact

    async def get_artifact(self, artifact_id: str) -> ArtifactRecord | None:
        """Retrieve artifact record by ID."""
        async with self.db.connection() as conn:
            async with conn.execute(
                "SELECT * FROM artifacts WHERE id = :id", {"id": artifact_id}
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
                "SELECT * FROM artifacts WHERE task_id = :task_id ORDER BY created_at ASC",
                {"task_id": task_id},
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
        """Upsert a task graph (Oracle ``MERGE``)."""
        graph.updated_at = datetime.now(UTC)
        nodes_json = json.dumps({k: v.model_dump(mode="json") for k, v in graph.nodes.items()})
        edges_json = json.dumps([e.model_dump(mode="json") for e in graph.edges])
        params = {
            "id": graph.id,
            "project_id": _required_text(graph.project_id, "unspecified"),
            "goal": _required_text(graph.goal, "(empty goal)"),
            "nodes": nodes_json,
            "edges": edges_json,
            "status": graph.status.value,
            "current_node_id": _text(graph.current_node_id),
            "created_at": graph.created_at.isoformat(),
            "updated_at": graph.updated_at.isoformat(),
        }
        clob_params = ("goal", "nodes", "edges")

        async with self.db.connection() as conn:
            if self._is_oracle:
                await conn.execute(
                    """
                    MERGE INTO task_graphs t
                    USING (SELECT :id AS id FROM dual) src
                    ON (t.id = src.id)
                    WHEN MATCHED THEN UPDATE SET
                        t.goal = :goal,
                        t.nodes = :nodes,
                        t.edges = :edges,
                        t.status = :status,
                        t.current_node_id = :current_node_id,
                        t.updated_at = :updated_at
                    WHEN NOT MATCHED THEN INSERT
                        (id, project_id, goal, nodes, edges, status, current_node_id,
                         created_at, updated_at)
                    VALUES
                        (:id, :project_id, :goal, :nodes, :edges, :status,
                         :current_node_id, :created_at, :updated_at)
                    """,
                    params,
                    clob_params=clob_params,
                )
            else:
                # Explicit test-only SQLite backend (app.memory.sqlite_test_backend).
                async with conn.execute(
                    "SELECT id FROM task_graphs WHERE id = :id", {"id": graph.id}
                ) as cursor:
                    exists = await cursor.fetchone()
                if exists:
                    await conn.execute(
                        """
                        UPDATE task_graphs
                        SET goal = :goal, nodes = :nodes, edges = :edges,
                            status = :status, current_node_id = :current_node_id,
                            updated_at = :updated_at
                        WHERE id = :id
                        """,
                        params,
                    )
                else:
                    await conn.execute(
                        """
                        INSERT INTO task_graphs (id, project_id, goal, nodes, edges, status, current_node_id, created_at, updated_at)
                        VALUES (:id, :project_id, :goal, :nodes, :edges, :status, :current_node_id, :created_at, :updated_at)
                        """,
                        params,
                    )
            await conn.commit()
        return graph

    async def get_task_graph(self, graph_id: str) -> TaskGraph | None:
        """Load a task graph by ID."""
        async with self.db.connection() as conn:
            async with conn.execute(
                "SELECT id, project_id, goal, nodes, edges, status, current_node_id, "
                "created_at, updated_at FROM task_graphs WHERE id = :id",
                {"id": graph_id},
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None

                raw_nodes = _loads(row["nodes"], {})
                nodes = {k: TaskNode(**v) for k, v in raw_nodes.items()}
                raw_edges = _loads(row["edges"], [])

                return TaskGraph(
                    id=row["id"],
                    project_id=row["project_id"],
                    goal=_as_text(row["goal"]),
                    nodes=nodes,
                    edges=raw_edges,
                    status=TaskState(row["status"]),
                    current_node_id=row["current_node_id"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                )

    async def get_latest_task_graph_for_project(self, project_id: str) -> TaskGraph | None:
        """Fetch the most recent task graph for a project or task."""
        async with self.db.connection() as conn:
            query = (
                "SELECT id FROM task_graphs WHERE project_id = :project_id "
                "ORDER BY created_at DESC " + self.db.row_limit_clause()
            )
            async with conn.execute(
                query, {"project_id": project_id, "row_limit": 1}
            ) as cursor:
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
                VALUES (:id, :project_id, :task_id, :step_number, :state_data, :checksum, :timestamp, :description)
                """,
                {
                    "id": checkpoint.id,
                    "project_id": _required_text(checkpoint.project_id, "unspecified"),
                    "task_id": _text(checkpoint.task_id),
                    "step_number": checkpoint.step_number,
                    "state_data": json.dumps(checkpoint.state_data),
                    "checksum": _text(checkpoint.checksum),
                    "timestamp": checkpoint.timestamp.isoformat(),
                    "description": _text(checkpoint.description),
                },
                clob_params=("state_data", "description"),
            )
            await conn.commit()
        logger.debug(
            f"Saved checkpoint {checkpoint.id} for task/project {checkpoint.project_id} (step {checkpoint.step_number})"
        )
        return checkpoint

    def _checkpoint_from_row(self, row: Any) -> Checkpoint:
        return Checkpoint(
            id=row["id"],
            project_id=row["project_id"],
            task_id=row["task_id"],
            step_number=row["step_number"],
            state_data=_loads(row["state_data"], {}),
            checksum=row["checksum"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            description=_as_text(row["description"]),
        )

    async def list_checkpoints(self, project_id: str) -> list[Checkpoint]:
        """List checkpoints for a task or project ordered by step number."""
        async with self.db.connection() as conn:
            async with conn.execute(
                "SELECT * FROM checkpoints WHERE project_id = :project_id "
                "ORDER BY step_number ASC, timestamp ASC",
                {"project_id": project_id},
            ) as cursor:
                rows = await cursor.fetchall()
                return [self._checkpoint_from_row(row) for row in rows]

    async def get_latest_checkpoint(self, project_id: str) -> Checkpoint | None:
        """Retrieve the most recent checkpoint for a task or project."""
        async with self.db.connection() as conn:
            query = (
                "SELECT * FROM checkpoints WHERE project_id = :project_id "
                "ORDER BY step_number DESC, timestamp DESC " + self.db.row_limit_clause()
            )
            async with conn.execute(
                query, {"project_id": project_id, "row_limit": 1}
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None
                return self._checkpoint_from_row(row)
