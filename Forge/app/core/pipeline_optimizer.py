"""
Build Pipeline Optimizer for Project FORGE.
Implements parallel file synthesis, AI-Universe response caching, incremental diff builds,
and pre-synthesis cost estimation.
"""

import asyncio
import hashlib
import time
from collections import OrderedDict
from collections.abc import Callable, Coroutine
from typing import Any

from pydantic import BaseModel

from app.core.logging import get_logger

logger = get_logger("core.pipeline_optimizer")


class CostEstimate(BaseModel):
    """Estimated resource and token consumption before task execution."""

    task_goal: str
    manifest_files_count: int
    estimated_ai_calls: int
    estimated_tokens: int
    estimated_cost_usd: float
    exceeds_threshold: bool = False
    warning_message: str | None = None


class SynthesisCache:
    """In-memory LRU cache for identical prompts with TTL."""

    def __init__(self, max_size: int = 256, ttl_seconds: float = 3600.0):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, tuple[str, float]] = OrderedDict()

    def _hash_key(self, prompt: str) -> str:
        return hashlib.sha256(prompt.strip().encode("utf-8")).hexdigest()

    def get(self, prompt: str) -> str | None:
        key = self._hash_key(prompt)
        if key not in self._cache:
            return None
        value, timestamp = self._cache[key]
        if (time.time() - timestamp) > self.ttl_seconds:
            del self._cache[key]
            return None
        self._cache.move_to_end(key)
        return value

    def set(self, prompt: str, value: str):
        key = self._hash_key(prompt)
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = (value, time.time())
        if len(self._cache) > self.max_size:
            self._cache.popitem(last=False)


class PipelineOptimizer:
    """Optimizes execution pipeline with parallel synthesis, caching, and incremental change detection."""

    def __init__(self):
        self.cache = SynthesisCache()

    def estimate_cost(
        self,
        goal: str,
        file_manifest: list[str],
        max_budget_usd: float = 10.0,
    ) -> CostEstimate:
        """Estimate token and call expenditure prior to launching synthesis."""
        file_count = len(file_manifest)
        # Avg ~2 AI calls per file (synthesis + review) + 2 for planning/architecture
        est_calls = (file_count * 2) + 2
        # Avg ~800 tokens per call
        est_tokens = est_calls * 800
        # Estimated cost ~ $0.002 per 1k tokens
        est_cost = (est_tokens / 1000.0) * 0.002

        exceeds = est_cost > (max_budget_usd * 0.8)
        warning = None
        if exceeds:
            warning = f"Estimated cost (${est_cost:.4f}) approaches or exceeds 80% of max budget (${max_budget_usd:.2f})."

        return CostEstimate(
            task_goal=goal,
            manifest_files_count=file_count,
            estimated_ai_calls=est_calls,
            estimated_tokens=est_tokens,
            estimated_cost_usd=round(est_cost, 4),
            exceeds_threshold=exceeds,
            warning_message=warning,
        )

    async def execute_parallel_synthesis(
        self,
        files: list[str],
        synthesis_func: Callable[[str], Coroutine[Any, Any, Any]],
        concurrency_limit: int = 4,
    ) -> list[Any]:
        """Synthesize independent files concurrently with semaphore throttling."""
        semaphore = asyncio.Semaphore(concurrency_limit)

        async def worker(filename: str):
            async with semaphore:
                logger.info(f"Synthesizing file in parallel: {filename}")
                return await synthesis_func(filename)

        tasks = [worker(f) for f in files]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results

    def compute_incremental_diff(
        self,
        current_manifest: list[str],
        previous_files: dict[str, str],
        new_files: dict[str, str],
    ) -> set[str]:
        """Identify files that have changed and require regeneration."""
        changed = set()
        for f in current_manifest:
            old_code = previous_files.get(f)
            new_code = new_files.get(f)
            if old_code is None or old_code != new_code:
                changed.add(f)
        return changed


pipeline_optimizer = PipelineOptimizer()
