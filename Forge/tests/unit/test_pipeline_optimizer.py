"""
Unit tests for Pipeline Optimizer, Cache, and Parallel File Synthesis.
"""

import asyncio

import pytest

from app.core.pipeline_optimizer import (
    PipelineOptimizer,
    SynthesisCache,
)


def test_synthesis_cache():
    cache = SynthesisCache(max_size=3, ttl_seconds=10.0)
    cache.set("prompt1", "response1")
    cache.set("prompt2", "response2")

    assert cache.get("prompt1") == "response1"
    assert cache.get("prompt2") == "response2"
    assert cache.get("missing") is None


def test_cost_estimation():
    optimizer = PipelineOptimizer()
    estimate = optimizer.estimate_cost(
        goal="Build full stack platform",
        file_manifest=["index.html", "style.css", "app.js", "main.py", "test_main.py"],
        max_budget_usd=10.0,
    )
    assert estimate.manifest_files_count == 5
    assert estimate.estimated_ai_calls == 12
    assert estimate.estimated_cost_usd > 0.0
    assert estimate.exceeds_threshold is False


@pytest.mark.asyncio
async def test_parallel_synthesis():
    optimizer = PipelineOptimizer()
    files = ["file1.py", "file2.py", "file3.py"]

    async def mock_synth(filename: str) -> str:
        await asyncio.sleep(0.01)
        return f"content of {filename}"

    results = await optimizer.execute_parallel_synthesis(files, mock_synth, concurrency_limit=2)
    assert len(results) == 3
    assert results[0] == "content of file1.py"
    assert results[1] == "content of file2.py"
    assert results[2] == "content of file3.py"


def test_incremental_diff():
    optimizer = PipelineOptimizer()
    manifest = ["main.py", "style.css", "index.html"]
    prev_files = {"main.py": "print('hello')", "style.css": "body { margin: 0; }"}
    new_files = {
        "main.py": "print('hello')",
        "style.css": "body { margin: 10px; }",
        "index.html": "<h1>New</h1>",
    }

    changed = optimizer.compute_incremental_diff(manifest, prev_files, new_files)
    assert "style.css" in changed
    assert "index.html" in changed
    assert "main.py" not in changed
