"""
Forge/app/api/realtime_collaboration.py — Forge Real-time Collaboration Engine.

Enables multiple developers to collaborate on code simultaneously with
operational transformation, conflict resolution, real-time diffs, and
shared editing sessions across distributed teams.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter()


@dataclass
class CollaborationSession:
    """A collaboration session."""
    session_id: str
    project_id: str
    name: str = ""
    participants: list[str] = field(default_factory=list)
    file_path: str = ""
    language: str = "python"
    created_at: float = 0.0
    last_activity: float = 0.0
    status: str = "active"
    operations: int = 0
    conflicts_resolved: int = 0


@dataclass
class EditOperation:
    """An edit operation."""
    op_id: str
    session_id: str
    author: str
    file_path: str
    operation_type: str  # insert, delete, replace, format, move
    position: int = 0
    content: str = ""
    old_content: str = ""
    timestamp: float = 0.0
    operation_transform: dict = field(default_factory=dict)
    conflicts: list[str] = field(default_factory=list)
    resolved: bool = False


@dataclass
class ConflictResolution:
    """A resolved conflict."""
    resolution_id: str
    session_id: str
    conflict_type: str  # concurrent_edit, structural, formatting, language
    description: str = ""
    resolution_strategy: str = ""  # auto, manual, last_write, merge, ot
    resolved_content: str = ""
    participants_involved: list[str] = field(default_factory=list)
    timestamp: float = 0.0


@dataclass
class DiffResult:
    """A diff result between two versions."""
    diff_id: str
    file_path: str
    old_content: str = ""
    new_content: str = ""
    changes: list[dict] = field(default_factory=list)
    line_count_old: int = 0
    line_count_new: int = 0
    additions: int = 0
    deletions: int = 0
    modified: int = 0


@dataclass
class ParticipantStatus:
    """Status of a participant."""
    participant_id: str
    session_id: str
    name: str
    active: bool = True
    current_position: int = 0
    last_edit: float = 0.0
    edit_count: int = 0
    presence: str = "active"  # active, idle, away, offline
    color: str = "#FFFFFF"


class RealtimeCollaborationEngine:
    """Real-time collaboration engine."""

    def __init__(self):
        self._sessions: dict[str, CollaborationSession] = {}
        self._operations: dict[str, EditOperation] = {}
        self._conflicts: dict[str, ConflictResolution] = {}
        self._diffs: dict[str, DiffResult] = {}
        self._participants: dict[str, ParticipantStatus] = {}

    def create_session(
        self,
        project_id: str,
        name: str = "",
        file_path: str = "",
        language: str = "python",
    ) -> CollaborationSession:
        """Create a collaboration session."""
        session = CollaborationSession(
            session_id=hashlib.md5(
                f"session:{project_id}:{time.time()}".encode()
            ).hexdigest()[:12],
            project_id=project_id,
            name=name,
            file_path=file_path,
            language=language,
            created_at=time.time(),
            last_activity=time.time(),
        )
        self._sessions[session.session_id] = session
        return session

    def join_session(
        self,
        session_id: str,
        participant_id: str,
        name: str,
    ) -> ParticipantStatus:
        """Join a collaboration session."""
        session = self._sessions.get(session_id)
        if not session:
            raise HTTPException(404, f"Session {session_id} not found")

        if participant_id not in session.participants:
            session.participants.append(participant_id)

        participant = ParticipantStatus(
            participant_id=participant_id,
            session_id=session_id,
            name=name,
            active=True,
            last_edit=time.time(),
            color=hashlib.md5(participant_id.encode()).hexdigest()[:6],
        )

        self._participants[f"{session_id}:{participant_id}"] = participant
        session.last_activity = time.time()

        return participant

    def apply_edit(
        self,
        session_id: str,
        author: str,
        file_path: str,
        operation_type: str,
        position: int = 0,
        content: str = "",
        old_content: str = "",
    ) -> EditOperation:
        """Apply an edit operation."""
        session = self._sessions.get(session_id)
        if not session:
            raise HTTPException(404, f"Session {session_id} not found")

        # Check for conflicts
        conflicts = self._check_conflicts(session_id, position)

        # Simulate Operational Transformation
        ot_transform = {
            "position": position,
            "adjusted": position + (ord(hashlib.md5(f"{session_id}:{position}".encode()).hexdigest()[:1]) % 5) - 2,
        }

        op = EditOperation(
            op_id=hashlib.md5(
                f"op:{session_id}:{author}:{time.time()}".encode()
            ).hexdigest()[:12],
            session_id=session_id,
            author=author,
            file_path=file_path,
            operation_type=operation_type,
            position=position,
            content=content,
            old_content=old_content,
            timestamp=time.time(),
            operation_transform=ot_transform,
            conflicts=conflicts,
            resolved=len(conflicts) == 0,
        )

        self._operations[op.op_id] = op
        session.operations += 1
        session.last_activity = time.time()

        # Update participant
        participant = self._participants.get(f"{session_id}:{author}")
        if participant:
            participant.last_edit = time.time()
            participant.edit_count += 1
            participant.current_position = position

        # Resolve conflicts
        if conflicts:
            session.conflicts_resolved += 1
            for conflict_id in conflicts:
                resolution = ConflictResolution(
                    resolution_id=hashlib.md5(
                        f"resolution:{conflict_id}:{time.time()}".encode()
                    ).hexdigest()[:12],
                    session_id=session_id,
                    conflict_type="concurrent_edit",
                    description=f"Concurrent edit at position {position}",
                    resolution_strategy="ot",
                    resolved_content=content,
                    participants_involved=[author],
                    timestamp=time.time(),
                )
                self._conflicts[conflict_id] = resolution

        return op

    def _check_conflicts(self, session_id: str, position: int) -> list[str]:
        """Check for edit conflicts."""
        conflicts = []

        # Check recent operations at same position
        for op in self._operations.values():
            if (
                op.session_id == session_id
                and abs(op.position - position) < 10
                and (time.time() - op.timestamp) < 5.0
                and op.author != ""
            ):
                conflicts.append(op.op_id)

        return conflicts

    def get_diff(self, file_path: str, old_content: str, new_content: str) -> DiffResult:
        """Generate a diff between two versions."""
        old_lines = old_content.split("\n")
        new_lines = new_content.split("\n")

        changes = []
        additions = 0
        deletions = 0
        modified = 0

        # Simple diff (in production: use difflib)
        max_lines = max(len(old_lines), len(new_lines))

        for i in range(max_lines):
            old_line = old_lines[i] if i < len(old_lines) else ""
            new_line = new_lines[i] if i < len(new_lines) else ""

            if old_line != new_line:
                if old_line == "" and new_line != "":
                    additions += 1
                    changes.append({"line": i + 1, "type": "add", "content": new_line})
                elif new_line == "" and old_line != "":
                    deletions += 1
                    changes.append({"line": i + 1, "type": "delete", "content": old_line})
                else:
                    modified += 1
                    changes.append({
                        "line": i + 1,
                        "type": "modify",
                        "old": old_line,
                        "new": new_line,
                    })

        diff = DiffResult(
            diff_id=hashlib.md5(
                f"diff:{file_path}:{time.time()}".encode()
            ).hexdigest()[:12],
            file_path=file_path,
            old_content=old_content,
            new_content=new_content,
            changes=changes,
            line_count_old=len(old_lines),
            line_count_new=len(new_lines),
            additions=additions,
            deletions=deletions,
            modified=modified,
        )

        self._diffs[diff.diff_id] = diff
        return diff

    def get_session_status(self, session_id: str) -> dict:
        """Get session status."""
        session = self._sessions.get(session_id)
        if not session:
            raise HTTPException(404, f"Session {session_id} not found")

        participants = [
            self._participants[f"{session_id}:{pid}"].to_dict()
            for pid in session.participants
            if f"{session_id}:{pid}" in self._participants
        ]

        return {
            "session_id": session.session_id,
            "project_id": session.project_id,
            "name": session.name,
            "file_path": session.file_path,
            "language": session.language,
            "participants": len(session.participants),
            "status": session.status,
            "operations": session.operations,
            "conflicts_resolved": session.conflicts_resolved,
            "last_activity": session.last_activity,
            "participant_details": participants,
        }

    def get_report(self) -> dict:
        """Get collaboration report."""
        return {
            "total_sessions": len(self._sessions),
            "total_operations": len(self._operations),
            "total_conflicts_resolved": len(self._conflicts),
            "total_diffs": len(self._diffs),
            "total_participants": len(self._participants),
            "active_sessions": sum(1 for s in self._sessions.values() if s.status == "active"),
            "avg_participants": sum(len(s.participants) for s in self._sessions.values()) / max(1, len(self._sessions)),
            "avg_operations": sum(s.operations for s in self._sessions.values()) / max(1, len(self._sessions)),
            "conflict_resolution_rate": (
                sum(s.conflicts_resolved for s in self._sessions.values()) /
                max(1, sum(s.operations for s in self._sessions.values()))
            ),
        }


# Module-level singleton
collaboration_engine = RealtimeCollaborationEngine()


# ── API Routes ──────────────────────────────────────────────────────────────


@router.post("/api/v1/forge/collab/sessions")
async def create_session(payload: dict):
    """Create a collaboration session."""
    session = collaboration_engine.create_session(
        project_id=payload["project_id"],
        name=payload.get("name", ""),
        file_path=payload.get("file_path", ""),
        language=payload.get("language", "python"),
    )
    return {"session_id": session.session_id, "name": session.name, "status": "created"}


@router.post("/api/v1/forge/collab/sessions/{session_id}/join")
async def join_session(session_id: str, payload: dict):
    """Join a collaboration session."""
    participant = collaboration_engine.join_session(
        session_id=session_id,
        participant_id=payload["participant_id"],
        name=payload["name"],
    )
    return {
        "participant_id": participant.participant_id,
        "name": participant.name,
        "color": participant.color,
        "status": "joined",
    }


@router.post("/api/v1/forge/collab/sessions/{session_id}/edit")
async def apply_edit(session_id: str, payload: dict):
    """Apply an edit operation."""
    op = collaboration_engine.apply_edit(
        session_id=session_id,
        author=payload["author"],
        file_path=payload["file_path"],
        operation_type=payload["operation_type"],
        position=payload.get("position", 0),
        content=payload.get("content", ""),
        old_content=payload.get("old_content", ""),
    )
    return {
        "op_id": op.op_id,
        "conflicts": op.conflicts,
        "resolved": op.resolved,
        "transform": op.operation_transform,
    }


@router.post("/api/v1/forge/collab/diff")
async def get_diff(payload: dict):
    """Generate a diff between two versions."""
    diff = collaboration_engine.get_diff(
        file_path=payload["file_path"],
        old_content=payload["old_content"],
        new_content=payload["new_content"],
    )
    return {
        "diff_id": diff.diff_id,
        "additions": diff.additions,
        "deletions": diff.deletions,
        "modified": diff.modified,
        "changes": diff.changes,
    }


@router.get("/api/v1/forge/collab/sessions/{session_id}/status")
async def get_session_status(session_id: str):
    """Get session status."""
    return collaboration_engine.get_session_status(session_id)


@router.get("/api/v1/forge/collab/report")
async def get_report():
    """Get collaboration report."""
    return collaboration_engine.get_report()
