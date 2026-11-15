"""Natural-language Android UI automation — the planner loop (TASK-IG-LAP-01).

The phone bridge (TASK-PHONE-001) moves single commands; this module is
the ARTEMIS-pattern brain on top of it:

    observe (ui_dump hierarchy + screenshot OCR)
      -> decide (an LLM picks ONE action as strict JSON)
      -> validate + safety-gate the action in code
      -> act through the bridge -> observe again ...

until the decider reports the instruction done, reports it impossible,
or the step budget runs out. Every step is recorded, and the result
states plainly which of those endings happened — a task that hit the
step cap is a failure, never a quiet "success".

The decider is injectable: production wires FRIDAY's own LLM provider
(:func:`make_llm_decider`); tests drive the loop with a scripted decider
and a fake bridge, so the whole loop is provable with zero hardware.

Safety gates live in code, not in the prompt (the prompt repeats them,
but code is what enforces them):

* typing is refused when the focused field is a password field;
* the task refuses up front if the instruction asks for credentials
  (password / OTP / CVV / authenticator codes);
* if the observed screen belongs to a banking / payments / authenticator
  package, the task stops before acting;
* only the allowlisted actions can execute — a decider that invents an
  action, or returns prose instead of JSON, fails the step, and two
  consecutive unparsable replies end the task.
"""

from __future__ import annotations

import json
import time
from typing import Any, Callable

from friday.core.logging import get_logger

logger = get_logger("remote.phone_ui_agent")

ALLOWED_ACTIONS = frozenset(
    {"tap", "swipe", "type_text", "press_key", "open_app", "wait", "done", "fail"}
)

# Packages the planner will not act inside. Substrings, matched against
# the package names the UI dump reports.
BLOCKED_PACKAGE_HINTS = (
    "bank",
    "paytm",
    "gpay",
    "paisa",  # Google Pay's package is com.google.android.apps.nbu.paisa.user
    "phonepe",
    "bhim",
    "upi",
    "wallet",
    "authenticator",
    "keepass",
    "bitwarden",
    "lastpass",
    "1password",
)

_CREDENTIAL_INSTRUCTION_HINTS = ("password", "otp", "cvv", "authenticator code", "one-time code")

MAX_STEPS_DEFAULT = 12
_MAX_TEXT_CHARS = 4096

Decider = Callable[[dict[str, Any]], dict[str, Any]]


class UiTaskRefused(RuntimeError):
    """The task was refused by a code-level safety gate before acting."""


# ---------------------------------------------------------------------------
# Decision parsing
# ---------------------------------------------------------------------------


def parse_decision(text: str) -> dict[str, Any]:
    """Parse one decider reply into a validated action dict.

    Accepts a bare JSON object or one wrapped in a markdown fence / prose.
    Raises ValueError on anything that is not exactly one JSON object with
    an allowlisted ``action`` — the loop never guesses at prose.
    """
    if not text or not text.strip():
        raise ValueError("decider returned an empty reply")
    candidate = text.strip()
    if "```" in candidate:
        parts = candidate.split("```")
        for part in parts:
            stripped = part.strip()
            if stripped.startswith("{"):
                candidate = stripped
                break
            if stripped.startswith("json") and stripped[4:].strip().startswith("{"):
                candidate = stripped[4:].strip()
                break
    start = candidate.find("{")
    if start < 0:
        raise ValueError("decider reply contains no JSON object")
    try:
        parsed, _ = json.JSONDecoder().raw_decode(candidate[start:])
    except json.JSONDecodeError as exc:
        raise ValueError(f"decider reply is not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("decider reply is not a JSON object")
    action = str(parsed.get("action") or "").strip().lower()
    if action not in ALLOWED_ACTIONS:
        raise ValueError(
            f"decider chose unsupported action '{action or '(missing)'}'; "
            f"allowed: {', '.join(sorted(ALLOWED_ACTIONS))}"
        )
    parsed["action"] = action
    return parsed


def _coerce_int(value: Any, field: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"action field '{field}' must be an integer, got {value!r}")
    if number < 0 or number > 20000:
        raise ValueError(f"action field '{field}' is out of range: {number}")
    return number


def validate_action(decision: dict[str, Any], observation: dict[str, Any]) -> dict[str, Any]:
    """Validate/coerce a parsed decision into bridge args for its command.

    Returns {"command": <bridge command>, "args": {...}} for acting
    actions, or {"command": <action>} for wait/done/fail. A ``node``
    index (into the observation's node list) resolves to that node's
    centre coordinates for tap.
    """
    action = decision["action"]
    if action in {"done", "fail"}:
        return {"command": action, "note": str(decision.get("note") or "")[:500]}
    if action == "wait":
        try:
            seconds = float(decision.get("seconds") or 1.0)
        except (TypeError, ValueError):
            seconds = 1.0
        return {"command": "wait", "seconds": max(0.0, min(10.0, seconds))}
    if action == "tap":
        if decision.get("node") is not None:
            nodes = observation.get("nodes") or []
            try:
                index = int(decision["node"])
            except (TypeError, ValueError):
                raise ValueError("tap 'node' must be an integer index")
            if not 0 <= index < len(nodes):
                raise ValueError(f"tap 'node' index {index} is out of range ({len(nodes)} nodes)")
            center = nodes[index].get("center")
            if not center:
                raise ValueError(f"tap 'node' {index} has no centre coordinates")
            return {"command": "tap", "args": {"x": int(center[0]), "y": int(center[1])}}
        return {
            "command": "tap",
            "args": {"x": _coerce_int(decision.get("x"), "x"), "y": _coerce_int(decision.get("y"), "y")},
        }
    if action == "swipe":
        args = {
            key: _coerce_int(decision.get(key), key) for key in ("x1", "y1", "x2", "y2")
        }
        if decision.get("duration_ms") is not None:
            args["duration_ms"] = max(50, min(3000, _coerce_int(decision["duration_ms"], "duration_ms")))
        return {"command": "swipe", "args": args}
    if action == "type_text":
        text = str(decision.get("text") or "")
        if not text:
            raise ValueError("type_text requires non-empty 'text'")
        if len(text) > _MAX_TEXT_CHARS:
            raise ValueError(f"type_text is limited to {_MAX_TEXT_CHARS} characters")
        return {"command": "type_text", "args": {"text": text}}
    if action == "press_key":
        key = str(decision.get("key") or "").strip()
        if not key:
            raise ValueError("press_key requires a 'key'")
        return {"command": "press_key", "args": {"key": key}}
    if action == "open_app":
        app = str(decision.get("app") or "").strip()
        if not app:
            raise ValueError("open_app requires an 'app'")
        return {"command": "open_app", "args": {"app": app}}
    raise ValueError(f"unsupported action '{action}'")  # pragma: no cover - parse_decision guards


# ---------------------------------------------------------------------------
# Safety gates
# ---------------------------------------------------------------------------


def check_instruction_allowed(instruction: str) -> None:
    lowered = instruction.lower()
    for hint in _CREDENTIAL_INSTRUCTION_HINTS:
        if hint in lowered:
            raise UiTaskRefused(
                f"The instruction asks for a credential ('{hint}'). FRIDAY will not "
                "type passwords, OTPs or card security codes into a phone; do that step "
                "yourself and ask FRIDAY for the rest."
            )


def blocked_package(observation: dict[str, Any]) -> str | None:
    packages = {str(n.get("package") or "") for n in observation.get("nodes") or []}
    foreground = str(observation.get("foreground") or "")
    if foreground:
        packages.add(foreground)
    for package in packages:
        lowered = package.lower()
        for hint in BLOCKED_PACKAGE_HINTS:
            if hint in lowered:
                return package
    return None


def focused_password_field(observation: dict[str, Any]) -> bool:
    return any(
        n.get("focused") and n.get("password") for n in observation.get("nodes") or []
    )


# ---------------------------------------------------------------------------
# Observation
# ---------------------------------------------------------------------------


def _evidence_output(evidence: dict[str, Any]) -> Any:
    output = evidence.get("output")
    if isinstance(output, str):
        try:
            return json.loads(output)
        except (ValueError, TypeError):
            return output
    return output


def default_ocr(png_bytes: bytes) -> str:
    """OCR a screenshot the same way the laptop screenshot tool does."""
    import io

    from PIL import Image

    from friday.tools.builtin.screen_ocr import _run_ocr

    words = _run_ocr(Image.open(io.BytesIO(png_bytes)))
    return " ".join(word for word, _box in words)[:4000]


def observe(
    bridge: Any,
    device_id: str,
    *,
    ocr_fn: Callable[[bytes], str] | None = None,
) -> dict[str, Any]:
    """Collect one observation: UI hierarchy (if served) + screenshot OCR."""
    observation: dict[str, Any] = {"nodes": [], "screen_text": "", "foreground": None}
    try:
        evidence = bridge.execute_sync(device_id, "ui_dump", timeout=30.0, args={})
        if evidence.get("ok"):
            payload = _evidence_output(evidence)
            if isinstance(payload, dict):
                observation["nodes"] = payload.get("nodes") or []
                observation["node_count"] = payload.get("count")
    except Exception as exc:  # executor may not serve ui_dump — observe by OCR only
        logger.info("ui_dump unavailable for %s: %s", device_id, type(exc).__name__)
    try:
        evidence = bridge.execute_sync(device_id, "screenshot", timeout=30.0, args={})
        if evidence.get("ok"):
            import base64

            raw = base64.b64decode(str(_evidence_output(evidence) or ""))
            if raw:
                try:
                    observation["screen_text"] = (ocr_fn or default_ocr)(raw)
                except Exception as exc:
                    logger.info("screenshot OCR unavailable: %s", type(exc).__name__)
                    observation["screen_text"] = ""
    except Exception as exc:
        logger.info("screenshot unavailable for %s: %s", device_id, type(exc).__name__)
    return observation


# ---------------------------------------------------------------------------
# The loop
# ---------------------------------------------------------------------------


def run_ui_task(
    bridge: Any,
    device_id: str,
    instruction: str,
    decide: Decider,
    *,
    max_steps: int = MAX_STEPS_DEFAULT,
    ocr_fn: Callable[[bytes], str] | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Run one natural-language instruction against the phone's UI.

    ``bridge`` is anything with the PhoneBridge ``execute_sync`` shape.
    Returns {"ok", "summary", "stop_reason", "steps"} — ``ok`` is True
    only when the decider confirmed the instruction complete.
    """
    instruction = (instruction or "").strip()
    if not instruction:
        return {"ok": False, "summary": "No instruction was provided.",
                "stop_reason": "fail", "steps": []}
    try:
        check_instruction_allowed(instruction)
    except UiTaskRefused as exc:
        return {"ok": False, "summary": str(exc), "stop_reason": "refused", "steps": []}

    max_steps = max(1, min(30, int(max_steps or MAX_STEPS_DEFAULT)))
    steps: list[dict[str, Any]] = []
    parse_failures = 0
    comm_failures = 0

    for step_no in range(1, max_steps + 1):
        observation = observe(bridge, device_id, ocr_fn=ocr_fn)
        observation["instruction"] = instruction
        observation["step"] = step_no
        observation["history"] = steps[-6:]

        package = blocked_package(observation)
        if package:
            summary = (
                f"Stopped before acting: the phone is showing '{package}', which is a "
                "banking/payments/authenticator app. FRIDAY does not operate those."
            )
            steps.append({"step": step_no, "action": "refused", "ok": False, "detail": summary})
            return {"ok": False, "summary": summary, "stop_reason": "refused", "steps": steps}

        try:
            decision = decide(observation)
            if isinstance(decision, str):
                decision = parse_decision(decision)
            plan = validate_action(decision, observation)
            parse_failures = 0
        except ValueError as exc:
            parse_failures += 1
            steps.append({"step": step_no, "action": "invalid_decision", "ok": False,
                          "detail": str(exc)})
            if parse_failures >= 2:
                summary = f"The planner produced two unusable decisions in a row; stopped. Last: {exc}"
                return {"ok": False, "summary": summary, "stop_reason": "fail", "steps": steps}
            continue

        command = plan["command"]
        if command == "done":
            note = plan.get("note") or "Instruction complete."
            steps.append({"step": step_no, "action": "done", "ok": True, "detail": note})
            return {"ok": True, "summary": note, "stop_reason": "done", "steps": steps}
        if command == "fail":
            note = plan.get("note") or "The planner reported the instruction cannot be completed."
            steps.append({"step": step_no, "action": "fail", "ok": False, "detail": note})
            return {"ok": False, "summary": note, "stop_reason": "fail", "steps": steps}
        if command == "wait":
            sleep_fn(plan["seconds"])
            steps.append({"step": step_no, "action": "wait", "ok": True,
                          "detail": f"waited {plan['seconds']}s"})
            continue

        if command == "type_text" and focused_password_field(observation):
            summary = (
                "Stopped: the focused field on the phone is a password field. "
                "FRIDAY will not type into password fields; enter it yourself."
            )
            steps.append({"step": step_no, "action": "refused", "ok": False, "detail": summary})
            return {"ok": False, "summary": summary, "stop_reason": "refused", "steps": steps}

        try:
            evidence = bridge.execute_sync(
                device_id, command, timeout=60.0, args=plan.get("args") or {}
            )
        except Exception as exc:
            comm_failures += 1
            steps.append({"step": step_no, "action": command, "ok": False,
                          "detail": f"{type(exc).__name__}: {exc}"})
            if comm_failures >= 2:
                summary = f"The phone stopped answering the bridge; stopped. Last: {exc}"
                return {"ok": False, "summary": summary, "stop_reason": "disconnected",
                        "steps": steps}
            continue
        comm_failures = 0
        ok = bool(evidence.get("ok"))
        detail = str(evidence.get("output") or evidence.get("error") or "")[:300]
        steps.append({"step": step_no, "action": command, "ok": ok, "detail": detail})

    summary = (
        f"Step budget exhausted ({max_steps} steps) before the instruction was "
        "confirmed complete; treating the task as not done."
    )
    return {"ok": False, "summary": summary, "stop_reason": "max_steps", "steps": steps}


# ---------------------------------------------------------------------------
# Production decider (FRIDAY's own LLM)
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """You operate the owner's Android phone by choosing ONE UI action per reply.

Reply with exactly one JSON object and nothing else. Actions:
{"action": "open_app", "app": "settings"} - open an app by name or package
{"action": "tap", "node": 3} - tap the centre of UI node index 3 from the observation
{"action": "tap", "x": 500, "y": 800} - tap raw pixel coordinates
{"action": "swipe", "x1": 500, "y1": 1400, "x2": 500, "y2": 500} - swipe (e.g. to scroll)
{"action": "type_text", "text": "..."} - type into the currently focused field
{"action": "press_key", "key": "back"} - home, back, enter, tab, delete, dpad_up/down/left/right, app_switch
{"action": "wait", "seconds": 2} - wait for the screen to settle
{"action": "done", "note": "what was accomplished"} - the instruction is fully complete
{"action": "fail", "note": "why it cannot be done"} - the instruction is impossible from this screen

Rules:
- Prefer tapping a node by index over raw coordinates.
- After opening an app or tapping, the next observation shows the new screen; keep going until the instruction is actually complete, then answer done.
- Never invent nodes, text or screens that are not in the observation.
- NEVER type passwords, OTPs, PINs or card details, and never act inside banking, payment or authenticator apps. If the task needs one of those, answer fail and say so.
- If a confirmation inside the phone asks about sending a message, placing a call, deleting data or paying, answer fail and describe it - the owner confirms those himself."""


def _render_observation(observation: dict[str, Any]) -> str:
    lines = [f"Instruction: {observation.get('instruction', '')}", f"Step: {observation.get('step')}"]
    nodes = observation.get("nodes") or []
    if nodes:
        lines.append(f"UI nodes ({len(nodes)} shown):")
        for index, node in enumerate(nodes):
            label = node.get("text") or node.get("desc") or node.get("id") or "(unlabelled)"
            extras = []
            if node.get("clickable"):
                extras.append("clickable")
            if node.get("focused"):
                extras.append("focused")
            if node.get("password"):
                extras.append("PASSWORD FIELD")
            suffix = f" [{', '.join(extras)}]" if extras else ""
            lines.append(f"  {index}: {label!r} ({node.get('class', '')}) centre={node.get('center')}{suffix}")
    else:
        lines.append("UI nodes: (hierarchy unavailable)")
    screen_text = (observation.get("screen_text") or "").strip()
    if screen_text:
        lines.append(f"Screen text (OCR): {screen_text[:1500]}")
    history = observation.get("history") or []
    if history:
        lines.append("Recent steps:")
        for record in history:
            lines.append(f"  - {record.get('action')}: ok={record.get('ok')} {record.get('detail', '')[:120]}")
    return "\n".join(lines)


def make_llm_decider(provider: Any | None = None) -> Decider:
    """Build the production decider on FRIDAY's own LLM provider.

    Raises RuntimeError with a plain explanation when no provider can be
    constructed — the caller surfaces that instead of faking actions.
    """
    if provider is None:
        try:
            from friday.core.config import Settings
            from friday.llm.factory import create_llm_provider

            provider = create_llm_provider(Settings())
        except Exception as exc:
            raise RuntimeError(
                f"FRIDAY's LLM provider is unavailable, so the phone UI planner "
                f"cannot run: {type(exc).__name__}: {exc}"
            ) from exc

    from friday.core.types import Message, Role

    def decide(observation: dict[str, Any]) -> dict[str, Any]:
        reply = provider.generate(
            [
                Message(role=Role.SYSTEM, content=_SYSTEM_PROMPT),
                Message(role=Role.USER, content=_render_observation(observation)),
            ]
        )
        return parse_decision(getattr(reply, "content", "") or "")

    return decide


__all__ = [
    "ALLOWED_ACTIONS",
    "BLOCKED_PACKAGE_HINTS",
    "Decider",
    "UiTaskRefused",
    "check_instruction_allowed",
    "blocked_package",
    "focused_password_field",
    "make_llm_decider",
    "observe",
    "parse_decision",
    "run_ui_task",
    "validate_action",
]
