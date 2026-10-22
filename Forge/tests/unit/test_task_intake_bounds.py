"""
Regression test for unbounded `goal`/`requirements` in task intake.

Found via live adversarial usage (2026-10-07): the only size guard on task
creation was the 8 MB whole-request-body middleware limit. A single oversized
`goal` string reached the server fine and took ~7 seconds for *task intake
alone* (before any synthesis/execution started) -- goal classification,
keyword matching, and template detection all scan the raw text repeatedly.
A client submitting even a handful of such requests concurrently could
starve the entire process. `TaskCreateRequest.goal` now has an explicit
`max_length`.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.api.schemas import TaskCreateRequest


def test_goal_rejects_oversized_input():
    with pytest.raises(ValidationError):
        TaskCreateRequest(goal="A" * 20_001)


def test_goal_accepts_reasonable_length():
    req = TaskCreateRequest(goal="A" * 20_000)
    assert len(req.goal) == 20_000


def test_requirements_list_is_bounded():
    with pytest.raises(ValidationError):
        TaskCreateRequest(goal="Build something", requirements=["req"] * 201)

    req = TaskCreateRequest(goal="Build something", requirements=["req"] * 200)
    assert len(req.requirements) == 200
