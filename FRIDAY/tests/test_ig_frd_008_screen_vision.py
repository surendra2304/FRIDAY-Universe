"""TASK-IG-FRD-008 — laptop screen-vision tool tests (fake bridge + vision)."""

from __future__ import annotations

import base64
from types import SimpleNamespace

from friday.core.types import ToolResult
from friday.tools.builtin.laptop_screen_vision import LaptopDescribeScreenTool

# 1x1 white JPEG.
_JPEG = base64.b64encode(
    bytes.fromhex(
        "ffd8ffe000104a46494600010100000100010000ffdb004300"
        "080606070605080707070909080a0c140d0c0b0b0c1912130f"
        "141d1a1f1e1d1a1c1c20242e2720222c231c1c2837292c3031"
        "3434341f27393d38323c30333134434b344141313939373839"
        "42424d43413536363137393936414134343434343434343434"
        "34343434343434343434343434343434343434343434343434"
        "3434343434343434343434343434ffc000110800010001030111"
        "00021101031101ffc40015000101000000000000000000000000"
        "00000000000affc4001410010000000000000000000000000000"
        "0000000000000000ffc400141101000000000000000000000000"
        "000000000000000000ffda000c03010002110311003f00b2c0"
        "7fff9d9bf270ffd9"
    )
).decode()


def _evidence():
    return {
        "ok": True,
        "laptop_id": "boss-laptop",
        "attachment": {"base64": _JPEG, "width": 1, "height": 1},
    }


class FakeVision:
    def __init__(self, result=None, exc=None):
        self._result = result
        self._exc = exc
        self.prompts = []

    def analyze_image(self, image_data, mime_type="image/png", prompt=""):
        self.prompts.append(prompt)
        if self._exc:
            raise self._exc
        return self._result


def _tool(vision):
    tool = LaptopDescribeScreenTool(vision_provider=vision)
    tool._dispatch = lambda args, laptop_id=None: (_evidence(), None)
    return tool


def test_describes_screen_with_vision():
    vision = FakeVision(
        result=SimpleNamespace(
            is_error=False,
            description="A terminal showing a finished build.",
            text="",
            model="gemini-test",
        )
    )
    result = _tool(vision).execute(question="did the build finish?")
    assert result.is_error is False
    assert "finished build" in result.content
    assert result.metadata["vision"] is True
    assert vision.prompts == ["did the build finish?"]


def test_vision_error_falls_back_to_labelled_ocr():
    vision = FakeVision(
        result=SimpleNamespace(is_error=True, error_message="quota", description="", text="", model="m")
    )
    tool = _tool(vision)
    tool._ocr_text = staticmethod(lambda raw: "some visible words")
    result = tool.execute()
    assert "Vision unavailable" in result.content
    assert "OCR only" in result.content
    assert "some visible words" in result.content
    assert result.metadata["vision"] is False
    assert result.metadata["ocr_only"] is True


def test_vision_exception_and_no_ocr_is_honest():
    vision = FakeVision(exc=RuntimeError("boom"))
    tool = _tool(vision)
    tool._ocr_text = staticmethod(lambda raw: "")
    result = tool.execute()
    assert "Vision unavailable" in result.content
    assert "won't guess" in result.content or "can't describe" in result.content


def test_no_laptop_error_passthrough():
    tool = LaptopDescribeScreenTool(vision_provider=FakeVision())
    error = ToolResult(name="laptop_describe_screen", content="No laptop is connected", is_error=True)
    tool._dispatch = lambda args, laptop_id=None: (None, error)
    result = tool.execute()
    assert result is error


def test_missing_image_data_is_an_error():
    tool = LaptopDescribeScreenTool(vision_provider=FakeVision())
    tool._dispatch = lambda args, laptop_id=None: ({"ok": True, "laptop_id": "x", "attachment": {}}, None)
    result = tool.execute()
    assert result.is_error is True
    assert "no image data" in result.content
