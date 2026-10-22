"""
Patch Synthesizer & Applicator for Project FORGE Recovery Subsystem.
Formulates and applies minimal surgical patches to failing workspace code.
"""

from pydantic import BaseModel

from app.core.logging import get_logger
from app.execution.engine import ExecutionEngine, execution_engine

logger = get_logger("recovery.repair")


class RepairPatch(BaseModel):
    """A surgical repair patch to fix a diagnosed failure."""

    target_file: str
    original_snippet: str | None = None
    replacement_snippet: str
    explanation: str
    patch_type: str = "edit"  # edit, rewrite, create


class PatchApplicator:
    """Applies surgical patches to the workspace sandbox via the ExecutionEngine."""

    def __init__(self, engine: ExecutionEngine | None = None):
        self.engine = engine or execution_engine

    def apply_patch(self, task_id: str, patch: RepairPatch, role: str = "debugger") -> bool:
        """
        Apply patch to target file inside the task sandbox.
        """
        try:
            if patch.patch_type == "create":
                self.engine.fs.create_file(
                    task_id=task_id,
                    relative_path=patch.target_file,
                    content=patch.replacement_snippet,
                    role=role,
                )
                logger.info(f"Applied patch (create) to {patch.target_file} in task {task_id}")
                return True

            if patch.patch_type == "edit" and patch.original_snippet:
                self.engine.fs.edit_file(
                    task_id=task_id,
                    relative_path=patch.target_file,
                    target_content=patch.original_snippet,
                    replacement_content=patch.replacement_snippet,
                    role=role,
                )
                logger.info(
                    f"Applied surgical patch (edit) to {patch.target_file} in task {task_id}"
                )
                return True

            # Fallback: rewrite file content
            self.engine.fs.create_file(
                task_id=task_id,
                relative_path=patch.target_file,
                content=patch.replacement_snippet,
                role=role,
            )
            logger.info(f"Applied patch (rewrite) to {patch.target_file} in task {task_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to apply patch to {patch.target_file} in task {task_id}: {e}")
            return False


patch_applicator = PatchApplicator()
