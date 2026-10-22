"""
Context Window and Execution State Manager for Project FORGE.
Tracks workspace changes, terminal outputs, and file diffs with token budgeting and automatic summarization.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.core.logging import get_logger

logger = get_logger("core.context")


class TerminalLogEntry(BaseModel):
    command: str
    exit_code: int
    stdout: str
    stderr: str
    role: str = "developer"


class ContextManager:
    """
    Manages task context windows, file summaries, execution logs, and diff histories.
    Automatically condenses and summarizes context when exceeding token limits.
    """

    def __init__(self, default_token_limit: int = 4000):
        self.default_token_limit = default_token_limit
        self._terminal_logs: dict[str, list[TerminalLogEntry]] = {}
        self._diff_history: dict[str, list[str]] = {}
        self._step_history: dict[str, list[dict[str, Any]]] = {}

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Estimate token count based on ~4 characters per token."""
        if not text:
            return 0
        return max(1, len(text) // 4)

    def summarize_text(
        self,
        text: str,
        max_tokens: int = 1000,
        head_ratio: float = 0.3,
    ) -> str:
        """
        Intelligently condense text that exceeds token budget by preserving head and tail context.
        """
        if not text:
            return ""

        current_tokens = self.estimate_tokens(text)
        if current_tokens <= max_tokens:
            return text

        max_chars = max_tokens * 4
        head_chars = int(max_chars * head_ratio)
        tail_chars = max_chars - head_chars

        head_part = text[:head_chars]
        tail_part = text[-tail_chars:] if tail_chars > 0 else ""
        omitted_chars = len(text) - (head_chars + tail_chars)

        return (
            f"{head_part}\n\n"
            f"... [Context truncated: omitted {omitted_chars} chars (~{omitted_chars // 4} tokens)] ...\n\n"
            f"{tail_part}"
        )

    def record_terminal_output(
        self,
        task_id: str,
        command: str,
        exit_code: int,
        stdout: str,
        stderr: str,
        role: str = "developer",
    ) -> None:
        """Record command execution output for a task."""
        if task_id not in self._terminal_logs:
            self._terminal_logs[task_id] = []
        self._terminal_logs[task_id].append(
            TerminalLogEntry(
                command=command,
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                role=role,
            )
        )

    def record_diff(self, task_id: str, diff_text: str) -> None:
        """Record git or file diff snapshot."""
        if not diff_text or not diff_text.strip():
            return
        if task_id not in self._diff_history:
            self._diff_history[task_id] = []
        self._diff_history[task_id].append(diff_text)

    def record_step_result(
        self,
        task_id: str,
        node_id: str,
        role_name: str,
        result: dict[str, Any],
    ) -> None:
        """Record a completed node execution step."""
        if task_id not in self._step_history:
            self._step_history[task_id] = []
        self._step_history[task_id].append(
            {"node_id": node_id, "role": role_name, "result": result}
        )

    def get_recent_terminal_logs(
        self, task_id: str, max_entries: int = 3, max_tokens: int = 1500
    ) -> str:
        """Retrieve recent terminal logs formatted and summarized for prompt context."""
        logs = self._terminal_logs.get(task_id, [])
        if not logs:
            return "No recent terminal logs."

        recent = logs[-max_entries:]
        parts = []
        for entry in recent:
            status_str = "SUCCESS" if entry.exit_code == 0 else f"FAILED (exit {entry.exit_code})"
            out_preview = entry.stdout.strip()
            err_preview = entry.stderr.strip()
            combined = f"Command: {entry.command} [{status_str}]\n"
            if out_preview:
                combined += f"STDOUT:\n{out_preview}\n"
            if err_preview:
                combined += f"STDERR:\n{err_preview}\n"
            parts.append(combined)

        raw_joined = "\n---\n".join(parts)
        return self.summarize_text(raw_joined, max_tokens=max_tokens)

    # Alias for recovery engine
    get_terminal_context = get_recent_terminal_logs

    def get_recent_diffs(self, task_id: str, max_tokens: int = 1500) -> str:
        """Retrieve recent diff history condensed to fit token budget."""
        diffs = self._diff_history.get(task_id, [])
        if not diffs:
            return "No recent file diffs."

        latest_diff = diffs[-1]
        return self.summarize_text(latest_diff, max_tokens=max_tokens)

    def get_workspace_file_tree(self, task_id: str, engine, max_files: int = 50) -> str:
        """Generate a concise string representation of existing workspace files."""
        try:
            files = engine.fs.search_files(task_id=task_id, pattern="*")
            if not files:
                return "Workspace project directory is currently empty."

            tree_lines = [f"- {f}" for f in files[:max_files]]
            if len(files) > max_files:
                tree_lines.append(f"... ({len(files) - max_files} additional files omitted)")
            return "\n".join(tree_lines)
        except Exception as e:
            logger.debug(f"Failed to read workspace file tree: {e}")
            return "Could not inspect workspace directory."

    def build_agent_context(
        self,
        task_id: str,
        role_name: str,
        node_title: str,
        base_context: dict[str, Any],
        engine,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """
        Assemble rich, token-budgeted context for an agent role.
        Includes workspace file tree, existing relevant files, terminal logs, and diffs.
        """
        token_limit = max_tokens or self.default_token_limit
        goal = base_context.get("goal", "")
        file_tree = self.get_workspace_file_tree(task_id, engine)

        context_payload: dict[str, Any] = {
            "goal": goal,
            "node_title": node_title,
            "file_tree": file_tree,
            "metadata": base_context.get("metadata", {}),
        }

        # Role-specific context enrichment
        if role_name in ["debugger", "tester"]:
            term_logs = self.get_recent_terminal_logs(task_id, max_tokens=token_limit // 2)
            context_payload["terminal_logs"] = term_logs
            if "error" in base_context:
                context_payload["error"] = self.summarize_text(
                    str(base_context["error"]), max_tokens=800
                )

        elif role_name in ["code_reviewer", "security_reviewer"]:
            diffs = self.get_recent_diffs(task_id, max_tokens=token_limit // 2)
            context_payload["recent_diffs"] = diffs

        # Include contents of existing key files if under token limit
        try:
            existing_files = engine.fs.search_files(task_id=task_id, pattern="*.py")
            key_files_content: dict[str, str] = {}
            tokens_used = self.estimate_tokens(str(context_payload))

            for fpath in existing_files[:5]:
                if tokens_used > token_limit * 0.75:
                    break
                try:
                    content = engine.fs.read_file(
                        task_id=task_id, relative_path=fpath, role=role_name
                    )
                    condensed = self.summarize_text(content, max_tokens=600)
                    key_files_content[fpath] = condensed
                    tokens_used += self.estimate_tokens(condensed)
                except Exception:
                    continue

            if key_files_content:
                context_payload["existing_files"] = key_files_content
        except Exception:
            pass

        return context_payload


context_manager = ContextManager()
