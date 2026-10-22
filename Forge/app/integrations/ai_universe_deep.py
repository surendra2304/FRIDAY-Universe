"""
Deep AI Universe Multi-Agent Intelligence Integration for Project FORGE.
Implements agent-specific routing, multi-agent debate code review, token/cost accounting,
and dynamic provider health awareness with automatic recovery.
"""

import re
from collections import defaultdict
from enum import Enum

from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.integrations.ai_universe_client import (
    AIUniverseClient,
    AIUniverseResponse,
    get_ai_universe_client,
)

logger = get_logger("integrations.ai_universe_deep")


class SpecializedAgentRole(str, Enum):
    ARCHITECT = "Architect"
    CODER = "Coder"
    DEBUGGER = "Debugger"
    SECURITY_ANALYST = "Security Analyst"
    TESTER = "Tester"


class CodeReviewResult(BaseModel):
    """Result from multi-agent debate code review."""

    original_code: str
    refined_code: str | None = None
    applied_auto_fix: bool = False
    confidence: float = 0.0
    suggestions: list[str] = Field(default_factory=list)
    review_run_id: str | None = None


class AIUniverseUsageStats(BaseModel):
    """Token and call consumption stats for a task."""

    task_id: str
    total_calls: int = 0
    estimated_input_tokens: int = 0
    estimated_output_tokens: int = 0
    total_estimated_tokens: int = 0

    @property
    def summary(self) -> str:
        return f"AI-Universe usage: {self.total_calls} calls, ~{self.total_estimated_tokens} tokens"


class DeepAIUniverseIntegration:
    """Enhanced AI Universe integration managing specialized agent routing and debate reviews."""

    def __init__(self, client: AIUniverseClient | None = None):
        self.client = client or get_ai_universe_client()
        self.usage_records: dict[str, AIUniverseUsageStats] = defaultdict(
            lambda: AIUniverseUsageStats(task_id="default")
        )
        self._is_healthy = True

    def _track_usage(self, task_id: str, prompt: str, response_text: str):
        """Track call count and approximate token usage."""
        stats = self.usage_records[task_id]
        stats.task_id = task_id
        stats.total_calls += 1
        # Approx 4 chars per token rule of thumb
        in_tokens = max(1, len(prompt) // 4)
        out_tokens = max(1, len(response_text) // 4)
        stats.estimated_input_tokens += in_tokens
        stats.estimated_output_tokens += out_tokens
        stats.total_estimated_tokens += in_tokens + out_tokens

    def get_usage(self, task_id: str) -> AIUniverseUsageStats:
        """Retrieve token and call statistics for task."""
        return self.usage_records.get(task_id, AIUniverseUsageStats(task_id=task_id))

    async def route_ask(
        self,
        task_id: str,
        question: str,
        role: SpecializedAgentRole = SpecializedAgentRole.CODER,
    ) -> AIUniverseResponse | None:
        """Route reasoning prompt specifically targetted to specialist AI Universe agents."""
        prompt = f"[Target Role: {role.value}]\n{question}"
        try:
            res = await self.client.ask(question=prompt, mode="auto")
            self._is_healthy = True
            if res:
                self._track_usage(task_id, prompt, res.answer)
            return res
        except Exception as e:
            logger.warning(f"AI Universe specialized query for {role.value} failed: {e}")
            self._is_healthy = False
            return None

    async def debate_code_review(
        self,
        task_id: str,
        code: str,
        filename: str = "main.py",
        goal: str = "",
    ) -> CodeReviewResult:
        """
        Submit generated code to AI Universe debate (Coder + Critic + Security Analyst).
        Consensus confidence > 0.8: Auto-apply suggested fixes.
        0.5 - 0.8: Log suggestions for review.
        < 0.5 or fails: Proceed with original code.
        """
        debate_prompt = (
            f"Review this code for bugs, security issues, and improvements in file '{filename}' for goal: {goal}.\n\n"
            f"Code:\n```\n{code}\n```\n\n"
            f"Provide consensus review. If fixes are required, return ONLY the full revised raw code."
        )

        try:
            res = await self.client.debate(question=debate_prompt, max_agents=3)
            if not res:
                return CodeReviewResult(original_code=code, confidence=0.0)

            self._track_usage(task_id, debate_prompt, res.answer)

            # Check confidence tier
            if res.confidence >= 0.80 and res.answer and len(res.answer.strip()) > 20:
                refined = self._clean_code(res.answer)
                logger.info(
                    f"AI-Universe debate code review applied auto-fix for '{filename}' (confidence={res.confidence:.2f})"
                )
                return CodeReviewResult(
                    original_code=code,
                    refined_code=refined,
                    applied_auto_fix=True,
                    confidence=res.confidence,
                    suggestions=res.key_evidence,
                    review_run_id=res.run_id,
                )
            elif 0.50 <= res.confidence < 0.80:
                logger.info(
                    f"AI-Universe debate code review logged suggestions for '{filename}' (confidence={res.confidence:.2f})"
                )
                return CodeReviewResult(
                    original_code=code,
                    refined_code=None,
                    applied_auto_fix=False,
                    confidence=res.confidence,
                    suggestions=res.key_evidence,
                    review_run_id=res.run_id,
                )
            else:
                logger.debug(
                    f"AI-Universe debate review low confidence ({res.confidence:.2f}); retaining original code."
                )
                return CodeReviewResult(
                    original_code=code,
                    confidence=res.confidence,
                    suggestions=res.unresolved_disagreements,
                    review_run_id=res.run_id,
                )
        except Exception as e:
            logger.warning(
                f"AI Universe debate code review failed ({e}). Proceeding with original code."
            )
            return CodeReviewResult(original_code=code, confidence=0.0)

    def _clean_code(self, text: str) -> str:
        """Strip markdown fences if response wrapped in ```."""
        clean = text.strip()
        fence_match = re.search(r"```[a-zA-Z0-9_\-]*\r?\n([\s\S]*?)```", clean)
        if fence_match:
            return fence_match.group(1).strip()
        return clean

    def check_health(self) -> bool:
        """Return cached health status of AI Universe integration."""
        return self._is_healthy


deep_ai_universe = DeepAIUniverseIntegration()
