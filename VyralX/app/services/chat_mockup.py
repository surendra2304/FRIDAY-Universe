"""VyralX chat-mockup frame generator (TASK-IG-VYR-09).

IG corpus item Dc8-IwtR2N1 shows a chat-mockup generator: fake
chat conversations rendered as video frames for skit/story
content — a real format in the history lane (a "conversation"
between historical figures is a story device, and chat reveals
pace a narration beat by beat).

This module renders that format with Pillow: given a scripted
conversation (speaker side + text), it produces one PNG frame per
message reveal — frame k shows the first k messages — ready for
the renderer to hold each frame for its beat. The mockup is
visibly a *mockup*: the header names it a dramatised conversation
and every manifest states the conversation is scripted fiction —
a chat mockup must never be presentable as a real screenshot of a
real conversation (that would be fabrication, and it is also how
scam content is made; the corpus's NONE-classified items include
exactly that pattern).

Deterministic layout, no network, no fonts beyond Pillow's
built-in default. Python 3.10.
"""
from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

MOCKUP_VERSION = "ig-vyr09-1"
_BG = (24, 24, 28)
_BUBBLE_LEFT = (52, 52, 60)
_BUBBLE_RIGHT = (24, 96, 60)
_TEXT = (240, 240, 240)
_HEADER = (16, 16, 20)
_WRAP = 540
_WIDTH = 540
_MARGIN = 24
_BUBBLE_MAX_W = 360
_LINE_CHARS = 30


def _wrap(text: str) -> list[str]:
    return textwrap.wrap(str(text), width=_LINE_CHARS) or [""]


def _bubble_height(lines: list[str]) -> int:
    return 18 + 15 * len(lines)


def render_conversation(messages: list[dict[str, Any]], out_dir: str,
                        title: str = "Dramatised conversation",
                        width: int = _WIDTH) -> dict[str, Any]:
    """Render one frame per message reveal; return the manifest.

    ``messages``: [{"side": "left"|"right", "speaker": str,
    "text": str}, ...]. Frames land in ``out_dir`` as
    frame_001.png ... The final frame is the full conversation.
    """
    if not messages:
        raise ValueError("a chat mockup needs at least one message")
    for msg in messages:
        if msg.get("side") not in ("left", "right"):
            raise ValueError(f"message side must be left/right: {msg!r}")
        if not str(msg.get("text") or "").strip():
            raise ValueError(f"message text must not be empty: {msg!r}")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    font = ImageFont.load_default()
    wrapped = [_wrap(m["text"]) for m in messages]
    total_h = 64 + sum(_bubble_height(w) + 12 for w in wrapped) + 16
    frames = []
    for upto in range(1, len(messages) + 1):
        img = Image.new("RGB", (width, total_h), _BG)
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 0, width, 48], fill=_HEADER)
        draw.text((_MARGIN, 10), title, fill=_TEXT, font=font)
        draw.text((_MARGIN, 28), "Scripted dramatisation — not a real "
                                 "conversation", fill=(170, 170, 170),
                  font=font)
        y = 64
        for idx in range(upto):
            msg = messages[idx]
            lines = wrapped[idx]
            h = _bubble_height(lines)
            if msg["side"] == "left":
                x0 = _MARGIN
            else:
                x0 = width - _MARGIN - _BUBBLE_MAX_W
            colour = _BUBBLE_LEFT if msg["side"] == "left" else _BUBBLE_RIGHT
            draw.rounded_rectangle([x0, y, x0 + _BUBBLE_MAX_W, y + h],
                                   radius=10, fill=colour)
            draw.text((x0 + 10, y + 5), str(msg.get("speaker") or ""),
                      fill=(190, 190, 190), font=font)
            for j, line in enumerate(lines):
                draw.text((x0 + 10, y + 18 + 15 * j), line,
                          fill=_TEXT, font=font)
            y += h + 12
        path = out / f"frame_{upto:03d}.png"
        img.save(path, format="PNG")
        frames.append(str(path))
    return {
        "kind": "chat_mockup",
        "mockup_version": MOCKUP_VERSION,
        "title": title,
        "messages": len(messages),
        "frames": frames,
        "frame_count": len(frames),
        "scripted_fiction": True,
        "disclaimer_on_every_frame": "Scripted dramatisation — not a "
                                     "real conversation",
        "status": "pending_review",
    }
