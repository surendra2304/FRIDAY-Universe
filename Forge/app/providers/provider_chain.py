"""
Multi-Provider Fallback Chain for Project FORGE.
Implements a 3-tier synthesis hierarchy (AI-Universe -> Direct Provider -> Deterministic Templates)
with full execution provenance accounting per file and task.
"""

import re
from enum import Enum
from typing import Any

from pydantic import BaseModel

from app.agents.project_types import detect_project_type
from app.core.logging import get_logger
from app.integrations.ai_universe_client import get_ai_universe_client
from app.providers.base import BaseModelProvider

logger = get_logger("providers.provider_chain")


class ProviderTier(str, Enum):
    AI_UNIVERSE = "ai_universe"
    DIRECT = "direct"
    TEMPLATE = "template"


class ProviderChainResult(BaseModel):
    """Result of file synthesis through the fallback chain."""

    filename: str
    code: str
    tier_used: ProviderTier
    confidence: float = 1.0
    run_id: str | None = None
    reason: str | None = None


class ProviderChain:
    """Orchestrates 3-tier synthesis fallback and tracks generation provenance."""

    def __init__(self, primary_client=None, fallback_provider: BaseModelProvider | None = None):
        self.primary_client = primary_client or get_ai_universe_client()
        self.fallback_provider = fallback_provider

    async def synthesize_file(
        self,
        filename: str,
        goal: str,
        requirements: list[str] | None = None,
        workspace_summary: str = "",
    ) -> ProviderChainResult:
        """Synthesize code for a file, cascading through AI Universe -> Direct Provider -> Templates."""
        # --- Tier 1: AI Universe ---
        try:
            prompt = (
                f"Write the complete code for {filename} based on the overall architecture: {goal}.\n"
                f"Security requirements: Input validation on user inputs, parameterized SQL (never string concatenation), "
                f"clean error handling without stack trace leaks, secure default configurations, authentication checks on protected endpoints, "
                f"and CSRF / secure headers where applicable. Return ONLY the raw code."
            )
            ai_res = await self.primary_client.ask(question=prompt, mode="auto")
            if ai_res and ai_res.confidence >= 0.70 and ai_res.answer and ai_res.answer.strip():
                clean_code = self._clean_markdown_fences(ai_res.answer, filename)
                logger.info(
                    f"File '{filename}' synthesized via AI-Universe (confidence={ai_res.confidence:.2f})"
                )
                return ProviderChainResult(
                    filename=filename,
                    code=clean_code,
                    tier_used=ProviderTier.AI_UNIVERSE,
                    confidence=ai_res.confidence,
                    run_id=ai_res.run_id,
                    reason="High confidence AI Universe synthesis",
                )
            else:
                conf = ai_res.confidence if ai_res else 0.0
                logger.warning(
                    f"AI Universe returned low confidence ({conf:.2f}) for '{filename}'. Falling back to Tier 2."
                )
        except Exception as e:
            logger.warning(
                f"AI Universe call failed for '{filename}' ({e}). Falling back to Tier 2."
            )

        # --- Tier 2: Direct / Configured LLM Provider ---
        if self.fallback_provider:
            try:
                llm_prompt = (
                    f"Objective: {goal}\n"
                    f"Implement complete code for file: {filename}\n"
                    f"{workspace_summary}\n\n"
                    f"Please output complete implementation delimited by '### File: {filename}'."
                )
                llm_res = await self.fallback_provider.generate(llm_prompt)
                if llm_res and llm_res.content and "### File:" in llm_res.content:
                    extracted_code = self._extract_file_content(llm_res.content, filename)
                    if extracted_code:
                        logger.info(f"File '{filename}' synthesized via Direct/LLM Provider.")
                        return ProviderChainResult(
                            filename=filename,
                            code=extracted_code,
                            tier_used=ProviderTier.DIRECT,
                            confidence=0.85,
                            reason="Direct/LLM Provider synthesis",
                        )
            except Exception as e:
                logger.warning(
                    f"Direct Provider call failed for '{filename}' ({e}). Falling back to Tier 3."
                )

        # --- Tier 3: Deterministic Template Synthesis ---
        builder = detect_project_type(goal, requirements)
        starter_files = builder.synthesize_starter_files()
        template_code = starter_files.get(filename)

        if not template_code:
            # Fallback default code
            if filename.endswith(".py"):
                template_code = f'"""\n{goal}\n"""\n\ndef main():\n    print("Executing {filename}")\n    return 0\n\nif __name__ == "__main__":\n    main()\n'
            elif filename.endswith(".html"):
                template_code = f"<!DOCTYPE html>\n<html><head><title>{goal}</title></head><body><h1>{goal}</h1></body></html>"
            elif filename.endswith(".css"):
                template_code = "body { font-family: sans-serif; margin: 0; padding: 2rem; }\n"
            elif filename.endswith(".js"):
                template_code = 'console.log("Initialized Project FORGE web script");\n'
            else:
                template_code = f"# {goal}\n\nFile: {filename}\n"

        logger.info(f"File '{filename}' synthesized via Deterministic Template.")
        return ProviderChainResult(
            filename=filename,
            code=template_code,
            tier_used=ProviderTier.TEMPLATE,
            confidence=0.80,
            reason="Deterministic template fallback",
        )

    def _clean_markdown_fences(self, text: str, filename: str) -> str:
        """Strip enclosing markdown code fences if present."""
        clean = text.strip()
        if clean.startswith("```"):
            lines = clean.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            clean = "\n".join(lines)
        return clean

    def _extract_file_content(self, text: str, filename: str) -> str | None:
        """Extract delimited content from LLM output."""
        pattern = (
            rf"###\s*File:\s*{re.escape(filename)}[\s\S]*?```[a-zA-Z0-9_\-]*\r?\n([\s\S]*?)```"
        )
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
        fence_match = re.search(r"```[a-zA-Z0-9_\-]*\r?\n([\s\S]*?)```", text)
        if fence_match:
            return fence_match.group(1).strip()
        return text.strip() if text else None

    @classmethod
    def calculate_provenance(cls, results: list[ProviderChainResult]) -> dict[str, Any]:
        """Calculate percentage breakdown of provider tiers used."""
        if not results:
            return {
                "ai_universe_percentage": 0.0,
                "direct_percentage": 0.0,
                "template_percentage": 0.0,
                "summary": "No files synthesized",
                "tier_breakdown": {},
            }

        total = len(results)
        ai_count = sum(1 for r in results if r.tier_used == ProviderTier.AI_UNIVERSE)
        direct_count = sum(1 for r in results if r.tier_used == ProviderTier.DIRECT)
        template_count = sum(1 for r in results if r.tier_used == ProviderTier.TEMPLATE)

        ai_pct = round((ai_count / total) * 100, 1)
        direct_pct = round((direct_count / total) * 100, 1)
        template_pct = round((template_count / total) * 100, 1)

        summary = f"Generated via: AI-Universe ({ai_pct}%), Direct ({direct_pct}%), Template ({template_pct}%)"

        return {
            "ai_universe_percentage": ai_pct,
            "direct_percentage": direct_pct,
            "template_percentage": template_pct,
            "summary": summary,
            "tier_breakdown": {r.filename: r.tier_used.value for r in results},
        }
