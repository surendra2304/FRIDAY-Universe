"""Natural-language control of the OWNER's browser, on his laptop.

TASK-IG-LAP-04, from corpus item Dc3pMkakrid (browser-use). The repo
card's verdict binds: browser-use the library is **adapt** — MIT, but it
requires Python 3.11+ and the fleet runs 3.10, so the pattern is adopted
and the library is not vendored (it remains a documented laptop-side
option for the owner). FRIDAY already drives a server-side browser
(``real_browser_agent``); what it could not do is operate the browser on
the owner's own laptop — the one holding his logins. This module is
that loop, over the LAP-001 laptop bridge:

    observe  screenshot_data -> OCR words grouped into text lines,
             each with a clickable centre (the browser equivalent of
             the phone planner's UI hierarchy)
    decide   FRIDAY's configured LLM picks ONE action as strict JSON
    gate     code-level safety checks (below), not prompt wishes
    act      open_url / click / type_text through the bridge

Safety gates, enforced in code:

* Instructions that ask for credentials (passwords, OTPs, card
  numbers, authenticator codes) are refused before the first action.
* Typing is refused when the visible page looks like a credential
  form (a "password"-labelled element together with a sign-in context).
  OCR is a weaker signal than the phone's structural hierarchy, so
  this gate is deliberately conservative and says it is a heuristic.
* If the visible text indicates a banking/payment context, the task
  stops before acting.
* Only allowlisted actions can execute; two consecutive unparsable
  decisions end the task; the step budget is a hard stop reported as
  NOT done.

The ``execute`` callable (command, args) -> evidence dict is injected,
which keeps the loop testable without a laptop — the same harness
discipline as LAP-001. The sibling phone planner
(``friday.remote.phone_ui_agent``) shares this shape by design; the
small decision parser is duplicated rather than imported so each lane
PR stands alone.
"""

from __future__ import annotations

import base64
import json
import re
import time
from typing import Any, Callable

from friday.core.logging import get_logger

logger = get_logger("remote.laptop_browser_agent")

ExecuteFn = Callable[[str, dict[str, Any]], dict[str, Any]]
DecideFn = Callable[[dict[str, Any]], dict[str, Any]]
OcrLinesFn = Callable[[bytes], list[dict[str, Any]]]

ACTIONS = frozenset({"open_url", "click", "type_text", "wait", "done", "fail"})
MAX_ELEMENTS = 60
DEFAULT_MAX_STEPS = 10

_CREDENTIAL_INSTRUCTION = re.compile(
    r"(type|enter|input|fill|give|use|tell|share|reveal|send|read out)\b[^.]{0,60}"
    r"\b(password|passcode|otp|one[- ]time code|cvv|card number|pin code|"
    r"authenticator|recovery code|seed phrase)\b",
    re.IGNORECASE,
)
_BANKING_TEXT = re.compile(
    r"(account balance|internet banking|net ?banking|ifsc|upi id|"
    r"wallet balance|card ending|credit card number|debit card)",
    re.IGNORECASE,
)
_PASSWORD_LABEL = re.compile(r"\b(password|passcode)\b", re.IGNORECASE)
_SIGNIN_CONTEXT = re.compile(
    r"\b(sign in|log in|login|username|user name|email|forgot)\b", re.IGNORECASE
)

_SYSTEM_PROMPT = """You operate the owner's web browser on his laptop for FRIDAY.
You see the visible text of the current page as numbered lines with
click centres. Reply with EXACTLY ONE JSON object and nothing else:

{"action": "open_url", "url": "https://..."}
{"action": "click", "element": <line number>}
{"action": "click", "x": <int>, "y": <int>}
{"action": "type_text", "text": "..."}
{"action": "wait", "seconds": 1}
{"action": "done", "note": "what was accomplished, with any answer found"}
{"action": "fail", "note": "why the task cannot be completed"}

Rules:
- Prefer clicking a numbered line over raw coordinates.
- To submit a form or search, type the text ending with a newline is NOT
  needed; click the page's submit/search control after typing.
- NEVER type passwords, one-time codes, card numbers or any credential;
  if the task needs one, use "fail" and say the owner must enter it.
- If a login wall blocks the task and no session is active, "fail" with
  that reason instead of guessing credentials.
- When the goal information is visible on screen, answer with "done"
  and quote it in the note."""


# ---------------------------------------------------------------------------
# Observation: OCR words -> clickable lines
# ---------------------------------------------------------------------------


def group_ocr_lines(
    words: list[tuple[str, tuple[int, int, int, int]]],
) -> list[dict[str, Any]]:
    """Group OCR (word, bbox) pairs into lines with click centres.

    Words join a line when their vertical ranges overlap by more than
    half the smaller height. Output elements carry ``text``, ``bbox``
    and ``center`` — the same shape the phone planner uses for nodes.
    """
    lines: list[dict[str, Any]] = []
    ordered = sorted(words, key=lambda item: (item[1][1], item[1][0]))
    for text, box in ordered:
        left, top, right, bottom = box
        placed = False
        for line in lines:
            overlap = min(line["bottom"], bottom) - max(line["top"], top)
            smaller = min(line["bottom"] - line["top"], bottom - top)
            if smaller > 0 and overlap > 0.5 * smaller:
                line["words"].append((text, box))
                line["top"] = min(line["top"], top)
                line["bottom"] = max(line["bottom"], bottom)
                placed = True
                break
        if not placed:
            lines.append({"top": top, "bottom": bottom, "words": [(text, box)]})
    elements: list[dict[str, Any]] = []
    for line in lines[:MAX_ELEMENTS]:
        line_words = sorted(line["words"], key=lambda item: item[1][0])
        left = min(box[0] for _text, box in line_words)
        right = max(box[2] for _text, box in line_words)
        top = min(box[1] for _text, box in line_words)
        bottom = max(box[3] for _text, box in line_words)
        elements.append(
            {
                "text": " ".join(text for text, _box in line_words),
                "bbox": [left, top, right, bottom],
                "center": [(left + right) // 2, (top + bottom) // 2],
            }
        )
    return elements


def default_ocr_lines(image_bytes: bytes) -> list[dict[str, Any]]:
    """OCR a screenshot into clickable lines via the fleet's screen_ocr."""
    import io

    from PIL import Image

    from friday.tools.builtin.screen_ocr import _run_ocr

    words = _run_ocr(Image.open(io.BytesIO(image_bytes)))
    return group_ocr_lines(words)


def observe(
    execute: ExecuteFn, ocr_lines_fn: OcrLinesFn | None = None
) -> dict[str, Any]:
    """One screenshot_data round-trip -> observation dict."""
    evidence = execute("screenshot_data", {})
    if not evidence.get("ok"):
        detail = evidence.get("error") or evidence.get("output") or "capture failed"
        raise RuntimeError(f"screenshot_data failed: {detail}")
    attachment = evidence.get("attachment") or {}
    encoded = attachment.get("base64")
    if not encoded:
        raise RuntimeError("screenshot_data returned no image data")
    image_bytes = base64.b64decode(encoded)
    ocr = ocr_lines_fn or default_ocr_lines
    try:
        elements = ocr(image_bytes)
        ocr_note = ""
    except Exception as exc:  # OCR is best-effort; the loop can still fail honestly
        elements = []
        ocr_note = f"OCR unavailable on the FRIDAY host ({type(exc).__name__})."
    return {
        "width": attachment.get("width"),
        "height": attachment.get("height"),
        "elements": elements,
        "visible_text": " ".join(element["text"] for element in elements),
        "ocr_note": ocr_note,
    }


# ---------------------------------------------------------------------------
# Decisions and gates
# ---------------------------------------------------------------------------


def parse_decision(raw: Any) -> dict[str, Any]:
    """Extract and validate one planner decision (same rules as the
    phone planner: strict JSON object, allowlisted action)."""
    if isinstance(raw, dict):
        candidate = raw
    elif isinstance(raw, str):
        text = raw.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:].lstrip()
        candidate = None
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                candidate = parsed
        except (ValueError, TypeError):
            pass
        if candidate is None:
            start = text.find("{")
            if start >= 0:
                try:
                    parsed, _end = json.JSONDecoder().raw_decode(text[start:])
                    if isinstance(parsed, dict):
                        candidate = parsed
                except ValueError:
                    pass
        if candidate is None:
            raise ValueError("planner reply contained no JSON object")
    else:
        raise ValueError(f"planner reply must be text or an object, got {type(raw).__name__}")
    action = str(candidate.get("action") or "").strip().lower()
    if action not in ACTIONS:
        raise ValueError(f"planner chose unsupported action '{action}'")
    candidate["action"] = action
    return candidate


def check_instruction_allowed(instruction: str) -> str | None:
    """Refusal reason for credential-seeking instructions, else None."""
    if _CREDENTIAL_INSTRUCTION.search(instruction or ""):
        return (
            "Refused: the instruction asks for a credential (password, OTP, "
            "card number or code). FRIDAY never types or handles credentials; "
            "the owner enters those himself."
        )
    return None


def looks_like_credential_form(observation: dict[str, Any]) -> bool:
    """Heuristic: a password-labelled element in a sign-in context."""
    texts = [element.get("text", "") for element in observation.get("elements", [])]
    has_password = any(_PASSWORD_LABEL.search(text) for text in texts)
    has_signin = any(_SIGNIN_CONTEXT.search(text) for text in texts)
    return has_password and has_signin


def validate_action(
    decision: dict[str, Any], observation: dict[str, Any]
) -> dict[str, Any]:
    """Decision -> {command, args} for the bridge, or ValueError."""
    action = decision["action"]
    if action == "open_url":
        url = str(decision.get("url") or "").strip()
        if not url.lower().startswith(("http://", "https://")):
            raise ValueError("open_url needs an absolute http(s) URL")
        return {"command": "open_url", "args": {"url": url}}
    if action == "click":
        elements = observation.get("elements", [])
        element = decision.get("element")
        if element is not None:
            try:
                index = int(element)
            except (TypeError, ValueError):
                raise ValueError("click 'element' must be a line number") from None
            if not 0 <= index < len(elements):
                raise ValueError(f"click element {index} is out of range")
            x, y = elements[index]["center"]
            return {"command": "click", "args": {"x": int(x), "y": int(y)}}
        try:
            x, y = int(decision.get("x")), int(decision.get("y"))
        except (TypeError, ValueError):
            raise ValueError("click needs an 'element' number or x/y") from None
        width, height = observation.get("width"), observation.get("height")
        if x < 0 or y < 0 or (width and x > int(width)) or (height and y > int(height)):
            raise ValueError("click coordinates are outside the captured screen")
        return {"command": "click", "args": {"x": x, "y": y}}
    if action == "type_text":
        text = decision.get("text")
        if not isinstance(text, str) or not text:
            raise ValueError("type_text needs non-empty 'text'")
        if len(text) > 4096:
            raise ValueError("type_text is limited to 4096 characters per step")
        return {"command": "type_text", "args": {"text": text}}
    if action == "wait":
        try:
            seconds = float(decision.get("seconds", 1))
        except (TypeError, ValueError):
            seconds = 1.0
        return {"command": "wait", "args": {"seconds": max(0.0, min(seconds, 10.0))}}
    raise ValueError(f"action '{action}' is terminal and has no bridge command")


def _render_observation(observation: dict[str, Any], step: int) -> str:
    lines = [f"Step {step}. Screen {observation.get('width')}x{observation.get('height')}."]
    for index, element in enumerate(observation.get("elements", [])):
        lines.append(f"[{index}] {element['text']}  (click centre {element['center']})")
    if observation.get("ocr_note"):
        lines.append(observation["ocr_note"])
    if not observation.get("elements"):
        lines.append("(no readable text on screen)")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# The loop
# ---------------------------------------------------------------------------


def run_browser_task(
    execute: ExecuteFn,
    instruction: str,
    decide: DecideFn,
    max_steps: int = DEFAULT_MAX_STEPS,
    ocr_lines_fn: OcrLinesFn | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Drive the owner's browser until done / impossible / out of steps.

    Returns {ok, summary, stop_reason, steps} with stop_reason one of
    done | fail | max_steps | refused | disconnected. A task that runs
    out of steps reports ok=False — never a partial success story.
    """
    refusal = check_instruction_allowed(instruction)
    if refusal:
        return {"ok": False, "summary": refusal, "stop_reason": "refused", "steps": []}

    steps: list[dict[str, Any]] = []
    parse_failures = 0
    for step in range(1, max_steps + 1):
        try:
            observation = observe(execute, ocr_lines_fn)
        except Exception as exc:
            return {
                "ok": False,
                "summary": f"Lost the laptop screen feed: {exc}",
                "stop_reason": "disconnected",
                "steps": steps,
            }
        observation["step"] = step
        observation["instruction"] = instruction

        if _BANKING_TEXT.search(observation.get("visible_text", "")):
            return {
                "ok": False,
                "summary": (
                    "Stopped: the visible page looks like a banking/payment "
                    "context. FRIDAY does not operate banking or payment "
                    "pages; the owner drives those himself."
                ),
                "stop_reason": "refused",
                "steps": steps,
            }

        try:
            decision = parse_decision(decide(observation))
        except Exception as exc:
            parse_failures += 1
            steps.append({"step": step, "error": f"unparsable decision: {exc}"})
            if parse_failures >= 2:
                return {
                    "ok": False,
                    "summary": "The planner produced two unusable decisions in a row; task stopped.",
                    "stop_reason": "fail",
                    "steps": steps,
                }
            continue
        parse_failures = 0
        action = decision["action"]

        if action == "done":
            note = str(decision.get("note") or "Task completed.")
            steps.append({"step": step, "action": "done", "note": note})
            return {"ok": True, "summary": note, "stop_reason": "done", "steps": steps}
        if action == "fail":
            note = str(decision.get("note") or "Task cannot be completed.")
            steps.append({"step": step, "action": "fail", "note": note})
            return {"ok": False, "summary": note, "stop_reason": "fail", "steps": steps}

        if action == "type_text" and looks_like_credential_form(observation):
            return {
                "ok": False,
                "summary": (
                    "Stopped before typing: the page looks like a sign-in "
                    "form (password field visible). FRIDAY never types into "
                    "credential forms; the owner signs in himself, then "
                    "FRIDAY can continue."
                ),
                "stop_reason": "refused",
                "steps": steps,
            }

        try:
            plan = validate_action(decision, observation)
        except ValueError as exc:
            parse_failures += 1
            steps.append({"step": step, "action": action, "error": str(exc)})
            if parse_failures >= 2:
                return {
                    "ok": False,
                    "summary": "The planner produced two invalid actions in a row; task stopped.",
                    "stop_reason": "fail",
                    "steps": steps,
                }
            continue

        record: dict[str, Any] = {"step": step, "action": action, "args": plan["args"]}
        if plan["command"] == "wait":
            sleep_fn(float(plan["args"]["seconds"]))
            record["output"] = f"waited {plan['args']['seconds']}s"
            steps.append(record)
            continue
        try:
            evidence = execute(plan["command"], plan["args"])
        except Exception as exc:
            record["error"] = f"{type(exc).__name__}: {exc}"
            steps.append(record)
            continue
        record["ok"] = bool(evidence.get("ok"))
        record["output"] = str(evidence.get("output") or evidence.get("error") or "")[:300]
        steps.append(record)

    return {
        "ok": False,
        "summary": f"Step budget exhausted ({max_steps}); the task is NOT complete.",
        "stop_reason": "max_steps",
        "steps": steps,
    }


def make_llm_decider(provider: Any | None = None) -> DecideFn:
    """Build the production decider on FRIDAY's configured LLM provider."""
    if provider is None:
        from friday.core.config import Settings
        from friday.llm.factory import create_llm_provider

        provider = create_llm_provider(Settings())

    def decide(observation: dict[str, Any]) -> Any:
        from friday.core.types import Message, Role

        user = (
            f"Instruction: {observation.get('instruction', '')}\n\n"
            + _render_observation(observation, int(observation.get("step", 1)))
        )
        response = provider.generate(
            [
                Message(role=Role.SYSTEM, content=_SYSTEM_PROMPT),
                Message(role=Role.USER, content=user),
            ]
        )
        return getattr(response, "content", response)

    return decide
