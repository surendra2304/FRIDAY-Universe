"""Screen-vision for the voice agent (TASK-IG-FRD-008).

Pattern source: IG corpus item ``DfEoqPfClGT`` — the assistant can
*see* the screen it is helping with. This tool composes two things
FRIDAY already has: the LAP-001 laptop bridge's ``screenshot_data``
capture, and the Gemini vision stack (``GeminiVisionProvider``).

``laptop_describe_screen`` answers "what is on my laptop screen?" (or a
specific question about it) with a real vision-model description. The
fallback is honest: if vision is unavailable or errors, it returns the
screenshot OCR text labelled as OCR-only — it never invents a
description of a screen it could not see.
"""

from __future__ import annotations

import base64
from typing import Any, Optional

from friday.core.types import SafetyLevel, ToolResult
from friday.tools.builtin.laptop_control import _LaptopTool

_DEFAULT_PROMPT = (
    "Describe what is visible on this computer screen in detail: the "
    "active application or window, the main content, any visible text "
    "that matters, and anything that looks like an error or a finished "
    "task. Be concrete and brief."
)


class LaptopDescribeScreenTool(_LaptopTool):
    """Describe the owner's laptop screen with the vision model."""

    name = "laptop_describe_screen"
    description = (
        "See and describe the owner's laptop screen: captures it through "
        "the laptop bridge and describes it with the vision model. Use "
        "when the user asks what is on their screen, whether something "
        "on the laptop finished, or to look at an error on the laptop. "
        "Accepts an optional question to focus the description. If vision "
        "is unavailable it falls back to OCR text and says so."
    )
    safety_level = SafetyLevel.SAFE
    command = "screenshot_data"
    default_timeout = 45.0
    parameters = {
        "type": "object",
        "properties": {
            "laptop_id": {
                "type": "string",
                "description": "Optional laptop id when more than one is connected.",
            },
            "question": {
                "type": "string",
                "description": "Optional question to focus the description, e.g. 'did the build finish?'.",
            },
        },
        "required": [],
    }

    def __init__(self, vision_provider: Any = None) -> None:
        super().__init__()
        self._vision_provider = vision_provider

    def _vision(self) -> Any:
        if self._vision_provider is None:
            from friday.vision.gemini_vision import GeminiVisionProvider

            self._vision_provider = GeminiVisionProvider()
        return self._vision_provider

    @staticmethod
    def _ocr_text(raw: bytes) -> str:
        try:
            import io

            from PIL import Image

            from friday.tools.builtin.screen_ocr import _run_ocr

            words = _run_ocr(Image.open(io.BytesIO(raw)))
            return " ".join(word for word, _box in words)[:4000]
        except Exception:
            return ""

    def execute(self, laptop_id: str = "", question: str = "", **kwargs: Any) -> ToolResult:
        evidence, error = self._dispatch({}, laptop_id or None)
        if error is not None:
            return error
        if not evidence.get("ok"):
            return self._evidence_result(evidence, "")
        attachment = evidence.get("attachment")
        if not attachment or not attachment.get("base64"):
            return self._error(
                "The laptop reported a successful capture but sent no image data; "
                "there is nothing to describe."
            )
        try:
            raw = base64.b64decode(attachment["base64"])
        except Exception as exc:
            return self._error(f"The screenshot image data was undecodable: {exc}")

        prompt = (question or "").strip() or _DEFAULT_PROMPT
        vision_error: Optional[str] = None
        try:
            result = self._vision().analyze_image(
                raw, mime_type="image/jpeg", prompt=prompt
            )
            if getattr(result, "is_error", False):
                vision_error = getattr(result, "error_message", "") or "vision provider error"
            else:
                description = (
                    getattr(result, "description", "") or getattr(result, "text", "")
                ).strip()
                if description:
                    return ToolResult(
                        name=self.name,
                        content=(
                            f"On laptop '{evidence.get('laptop_id')}' screen: {description}"
                        ),
                        is_error=False,
                        safety_level=self.safety_level,
                        metadata={
                            "laptop_id": evidence.get("laptop_id"),
                            "vision": True,
                            "model": getattr(result, "model", ""),
                            "question": question or None,
                        },
                    )
                vision_error = "vision provider returned an empty description"
        except Exception as exc:
            vision_error = f"{type(exc).__name__}: {exc}"

        # Honest fallback: OCR text, labelled as OCR-only.
        ocr = self._ocr_text(raw)
        if ocr:
            content = (
                f"Vision unavailable ({vision_error}) — OCR only. "
                f"Text visible on laptop '{evidence.get('laptop_id')}' screen: {ocr}"
            )
        else:
            content = (
                f"Vision unavailable ({vision_error}) and OCR extracted no text "
                f"from laptop '{evidence.get('laptop_id')}' screen. I can't describe "
                "this screen right now — I won't guess at what it shows."
            )
        return ToolResult(
            name=self.name,
            content=content,
            is_error=False,
            safety_level=self.safety_level,
            metadata={
                "laptop_id": evidence.get("laptop_id"),
                "vision": False,
                "vision_error": vision_error,
                "ocr_only": True,
            },
        )


__all__ = ["LaptopDescribeScreenTool"]
