"""
Base Agent Definition for Project FORGE.
An agent is a role/state package, strictly decoupled from the underlying interchangeable LLM provider.
"""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.execution.permissions import (
    DEFAULT_ROLE_PERMISSIONS,
    ToolPermission,
)
from app.providers.base import BaseModelProvider, ProviderResponse
from app.providers.direct import DirectProvider

logger = get_logger("agents.base")


class AgentState(BaseModel):
    """Encapsulates persistent working memory and scratchpad for an agent role."""

    role_name: str
    current_node_id: str | None = None
    scratchpad: dict[str, Any] = Field(default_factory=dict)
    history: list[dict[str, str]] = Field(default_factory=list)
    tokens_consumed: int = 0
    budget_consumed: float = 0.0


class BaseAgent(ABC):
    """
    Abstract base for all specialized FORGE engineering agents.
    Represents role responsibilities, assigned permissions, and state memory,
    with an interchangeable model provider.
    """

    def __init__(
        self,
        role_name: str,
        display_name: str,
        system_prompt: str,
        provider: BaseModelProvider | None = None,
        permissions: set[ToolPermission] | None = None,
    ):
        self.role_name = role_name
        self.display_name = display_name
        self.system_prompt = system_prompt
        # Interchangeable model provider (DirectProvider, OpenAI, Claude, Gemini, etc.)
        self.provider = provider or DirectProvider(model_name=f"direct-{role_name}")
        self.permissions = permissions or DEFAULT_ROLE_PERMISSIONS.get(role_name.lower(), set())
        self.state = AgentState(role_name=role_name)

    def set_provider(self, provider: BaseModelProvider) -> None:
        """Dynamically swap the underlying model provider at runtime."""
        self.provider = provider
        logger.info(f"Swapped provider on agent '{self.role_name}' to {provider.model_name}")

    async def prompt_model(
        self, prompt: str, system_override: str | None = None, temperature: float = 0.2
    ) -> ProviderResponse:
        """Query the underlying interchangeable model provider with agent persona context."""
        sys_prompt = system_override or self.system_prompt
        # Inject self-upgraded operational guidelines from Memora Experience memory
        try:
            from forge_upgrade.memora_client import memora_client
            guidelines = memora_client.build_self_upgrade_context("forge", prompt[:120], domain="code_synthesis")
            if guidelines:
                sys_prompt = f"{sys_prompt}\n\n{guidelines}"
        except Exception:
            pass

        response = await self.provider.generate(
            prompt=prompt, system_prompt=sys_prompt, temperature=temperature
        )
        self.state.tokens_consumed += response.usage.total_tokens
        self.state.budget_consumed += response.usage.estimated_cost_usd
        self.state.history.append({"prompt": prompt[:200], "response": response.content[:200]})
        return response

    def _synthesize_offline(
        self,
        task_id: str,
        goal: str,
        requirements: list[str],
        file_manifest: list[str],
        engine,
    ) -> list[str]:
        """Write a deterministic, working project for `goal` and report the paths.

        Returns the paths actually written, or an empty list when synthesis
        produced nothing usable. Only invoked when no model provider was able to
        author code, so it is the difference between "the agent built nothing" and
        "the agent built something that works".
        """
        try:
            from app.agents.synthesis import synthesize_files_for_goal

            produced = synthesize_files_for_goal(
                goal, manifest=file_manifest, requirements=requirements
            )
        except Exception as exc:
            logger.warning(f"Deterministic synthesis failed for '{goal[:60]}': {exc}")
            return []

        if not produced:
            return []

        written: list[str] = []
        for rel_path, content in produced.items():
            if not rel_path or not isinstance(content, str) or not content.strip():
                continue
            try:
                engine.fs.create_file(
                    task_id=task_id,
                    relative_path=rel_path,
                    content=content,
                    role=self.role_name,
                )
                written.append(rel_path)
            except Exception as exc:
                logger.warning(f"Could not write synthesised file {rel_path}: {exc}")
        return written

    def apply_extracted_files(
        self,
        task_id: str,
        response_text: str,
        engine,
        default_filename: str | None = None,
    ) -> list[str]:
        """
        Extract code blocks and files from LLM response text and write them to the workspace sandbox.
        """
        from app.agents.parser import LLMResponseParser

        extracted = LLMResponseParser.extract_files(
            response_text, default_filename=default_filename
        )
        written_paths: list[str] = []

        for file_item in extracted:
            try:
                rel_path = engine.fs.create_file(
                    task_id=task_id,
                    relative_path=file_item.relative_path,
                    content=file_item.content,
                    role=self.role_name,
                )
                written_paths.append(rel_path)
                logger.info(
                    f"Agent '{self.role_name}' applied file '{rel_path}' to workspace in task {task_id}"
                )
            except Exception as e:
                logger.error(
                    f"Failed to write extracted file '{file_item.relative_path}' for agent '{self.role_name}': {e}"
                )
                try:
                    from forge_upgrade.memora_client import memora_client
                    memora_client.learn_from_outcome(
                        agent_name="forge",
                        task_name=f"write_{file_item.relative_path}",
                        status="failure",
                        error_log=str(e),
                        actions_taken=f"role:{self.role_name}",
                        domain="code_synthesis"
                    )
                except Exception:
                    pass

        return written_paths

    def get_workspace_summary(self, task_id: str, engine, max_files: int = 30) -> str:
        """Summarize existing files in workspace project sandbox."""
        try:
            files = engine.fs.search_files(task_id=task_id, pattern="*", role=self.role_name)
            if not files:
                return "Workspace is empty."
            return "Current workspace files:\n" + "\n".join([f"- {f}" for f in files[:max_files]])
        except Exception:
            return "Workspace files could not be listed."

    @abstractmethod
    async def execute_step(
        self, task_id: str, node_title: str, context: dict[str, Any], engine
    ) -> dict[str, Any]:
        """Execute a unit of work within the task graph."""
