"""TASK-IG-LAP-04 — owner-browser planner tests.

The loop is driven through an injected execute callable + scripted
decider + scripted OCR lines; the tool is driven with the laptop
bridge's async executor stubbed. No laptop, no browser — the LAP-001
harness pattern.
"""

from __future__ import annotations

import asyncio
import base64
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from friday.remote.laptop_browser_agent import (  # noqa: E402
    group_ocr_lines,
    run_browser_task,
)

_PNG_B64 = base64.b64encode(
    base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
        "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )
).decode()


def _el(text: str, center: list[int]) -> dict[str, Any]:
    return {"text": text, "bbox": [center[0] - 10, center[1] - 5, center[0] + 10, center[1] + 5],
            "center": center}


class FakeExecute:
    def __init__(self) -> None:
        self.executed: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, command: str, args: dict[str, Any]) -> dict[str, Any]:
        if command == "screenshot_data":
            return {"ok": True, "attachment": {"base64": _PNG_B64, "width": 1280, "height": 800}}
        self.executed.append((command, args))
        return {"ok": True, "output": f"{command} done"}


def _scripted_ocr(screens: list[list[dict[str, Any]]]):
    state = {"i": 0}

    def fn(_image: bytes) -> list[dict[str, Any]]:
        screen = screens[min(state["i"], len(screens) - 1)]
        state["i"] += 1
        return screen

    return fn


_HOME = [_el("Search the web", [200, 40]), _el("News", [200, 90])]
_RESULTS = [_el("FRIDAY Universe - GitHub", [300, 60]), _el("Search the web", [200, 40])]


def test_group_ocr_lines_merges_words_into_lines():
    words = [
        ("Hello", (0, 0, 50, 20)),
        ("world", (60, 2, 120, 22)),
        ("Next", (0, 40, 40, 60)),
        ("line", (50, 41, 90, 61)),
    ]
    elements = group_ocr_lines(words)
    assert [e["text"] for e in elements] == ["Hello world", "Next line"]
    assert elements[0]["center"] == [60, 11]


def test_browser_task_happy_path():
    execute = FakeExecute()
    ocr = _scripted_ocr([_HOME, _HOME, _RESULTS, _RESULTS])

    def decide(observation: dict[str, Any]) -> dict[str, Any]:
        step = observation["step"]
        if step == 1:
            return {"action": "open_url", "url": "https://example.com"}
        if step == 2:
            return {"action": "click", "element": 0}
        if step == 3:
            return {"action": "type_text", "text": "friday universe"}
        return {"action": "done", "note": "Found: FRIDAY Universe - GitHub"}

    result = run_browser_task(execute, "find the FRIDAY repo", decide, ocr_lines_fn=ocr)
    assert result["ok"] and result["stop_reason"] == "done"
    commands = [command for command, _args in execute.executed]
    assert commands == ["open_url", "click", "type_text"]
    click_args = execute.executed[1][1]
    assert click_args == {"x": 200, "y": 40}  # the Search line's centre


def test_browser_task_refuses_credential_instruction_without_touching_laptop():
    execute = FakeExecute()
    result = run_browser_task(
        execute, "type my password into the login form",
        lambda obs: {"action": "done", "note": "x"},
        ocr_lines_fn=_scripted_ocr([_HOME]),
    )
    assert not result["ok"] and result["stop_reason"] == "refused"
    assert execute.executed == []


def test_browser_task_stops_at_signin_form_before_typing():
    execute = FakeExecute()
    form = [_el("Email", [100, 100]), _el("Password", [100, 160]), _el("Sign in", [100, 220])]
    result = run_browser_task(
        execute, "log in and check my orders",
        lambda obs: {"action": "type_text", "text": "anything"},
        ocr_lines_fn=_scripted_ocr([form]),
    )
    assert not result["ok"] and result["stop_reason"] == "refused"
    assert execute.executed == []


def test_browser_task_stops_on_banking_page():
    execute = FakeExecute()
    bank = [_el("Account balance $5,000", [300, 100]), _el("Transfer", [300, 160])]
    result = run_browser_task(
        execute, "check the news",
        lambda obs: {"action": "click", "element": 1},
        ocr_lines_fn=_scripted_ocr([bank]),
    )
    assert not result["ok"] and result["stop_reason"] == "refused"
    assert execute.executed == []


def test_browser_task_two_bad_decisions_end_it():
    execute = FakeExecute()
    result = run_browser_task(
        execute, "do something",
        lambda obs: {"action": "teleport"},
        ocr_lines_fn=_scripted_ocr([_HOME]),
    )
    assert not result["ok"] and result["stop_reason"] == "fail"
    assert execute.executed == []


def test_browser_task_step_budget_is_not_success():
    execute = FakeExecute()
    result = run_browser_task(
        execute, "wait around",
        lambda obs: {"action": "wait", "seconds": 0},
        max_steps=3, ocr_lines_fn=_scripted_ocr([_HOME]), sleep_fn=lambda s: None,
    )
    assert not result["ok"] and result["stop_reason"] == "max_steps"


def test_browser_task_disconnection_is_reported():
    def dead_execute(command: str, args: dict[str, Any]) -> dict[str, Any]:
        raise ConnectionError("tunnel down")

    result = run_browser_task(
        dead_execute, "anything",
        lambda obs: {"action": "done", "note": "x"},
        ocr_lines_fn=_scripted_ocr([_HOME]),
    )
    assert not result["ok"] and result["stop_reason"] == "disconnected"


def test_tool_runs_loop_with_stubbed_bridge(monkeypatch):
    import friday.remote.laptop_browser_agent as agent_mod
    from friday.tools.builtin import laptop_browser_control as tool_mod

    executed: list[str] = []

    async def fake_execute_on_laptop(command, args, timeout, laptop_id):
        if command == "screenshot_data":
            return {"ok": True, "attachment": {"base64": _PNG_B64, "width": 1280, "height": 800}}
        executed.append(command)
        return {"ok": True, "output": "done", "laptop_id": "lap-1"}

    monkeypatch.setattr(tool_mod, "_execute_on_laptop", fake_execute_on_laptop)
    monkeypatch.setattr(tool_mod, "_run", lambda factory: asyncio.run(factory()))
    monkeypatch.setattr(agent_mod, "default_ocr_lines", lambda b: _HOME)

    calls = {"n": 0}

    def decide(observation):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"action": "open_url", "url": "https://example.com"}
        return {"action": "done", "note": "Opened the page."}

    monkeypatch.setattr(tool_mod, "make_llm_decider", lambda: decide)
    tool = tool_mod.LaptopBrowserTaskTool()
    assert str(tool.safety_level).upper().endswith("SENSITIVE")
    result = tool.execute(instruction="open example.com")
    assert not result.is_error
    assert "Opened the page." in result.content
    assert executed == ["open_url"]
    assert result.metadata["stop_reason"] == "done"
