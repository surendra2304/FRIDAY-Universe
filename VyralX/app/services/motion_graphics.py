"""VyralX motion-graphics planning + HTML composition export (TASK-IG-VYR-09).

Two corpus threads meet here. The motion-graphics tooling items
(DbI_v6gMDW1 — Raylight motion graphics; Dad5GH3vi8y) point at
programmatic title cards, lower-thirds and kinetic text. The repo
pass verified **HyperFrames** (heygen-com/hyperframes, Apache-2.0,
verdict: adapt) — HTML/CSS compositions rendered to video via
headless Chrome — with one binding constraint: **headless-Chrome
rendering is far too heavy for the ~1 GB fleet servers**, so
compositions are produced as artifacts and rendered on the
owner's machine or post-ARM, never on the fleet.

This module therefore produces *plans and artifacts*, not renders:

* :func:`title_card_plan` / :func:`lower_third_plan` — timed
  overlay specs the existing renderer can execute;
* :func:`kinetic_text_plan` — word-by-word reveal timing derived
  from a narration line and its duration;
* :func:`hyperframes_export` — a single self-contained HTML file
  (no external references) encoding the composition timeline as
  data, stamped as an off-fleet render artifact with the reason.

Everything stays ``pending_review``. No network. Python 3.10.
"""
from __future__ import annotations

import html
import json
from typing import Any

MOTION_VERSION = "ig-vyr09-1"


def title_card_plan(text: str, at: float = 0.0, hold: float = 2.5) -> dict[str, Any]:
    if not str(text).strip():
        raise ValueError("title card text must not be empty")
    return {
        "kind": "title_card",
        "motion_version": MOTION_VERSION,
        "text": text,
        "at": at, "hold_seconds": hold,
        "animation": "fade_in_scale_0.96_to_1.0",
        "position": "centre",
        "status": "pending_review",
    }


def lower_third_plan(text: str, at: float, hold: float = 4.0) -> dict[str, Any]:
    if not str(text).strip():
        raise ValueError("lower-third text must not be empty")
    return {
        "kind": "lower_third",
        "motion_version": MOTION_VERSION,
        "text": text,
        "at": at, "hold_seconds": hold,
        "animation": "slide_in_from_left",
        "position": "lower_left",
        "status": "pending_review",
    }


def kinetic_text_plan(line: str, start: float, duration: float) -> dict[str, Any]:
    """Word-by-word reveal timing for one narration line."""
    words = str(line).split()
    if not words:
        raise ValueError("kinetic text line must not be empty")
    if duration <= 0:
        raise ValueError("duration must be positive")
    per = duration / len(words)
    return {
        "kind": "kinetic_text",
        "motion_version": MOTION_VERSION,
        "line": line,
        "start": start,
        "duration": duration,
        "words": [{"word": w, "at": round(start + i * per, 3),
                   "hold_until": round(start + (i + 1) * per, 3)}
                  for i, w in enumerate(words)],
        "status": "pending_review",
    }


def hyperframes_export(title: str, elements: list[dict[str, Any]],
                       width: int = 1080, height: int = 1920) -> str:
    """A self-contained HTML composition (HyperFrames pattern).

    The timeline is embedded as JSON data; a headless-Chrome
    renderer on a capable machine turns it into video. The file
    references NOTHING external. The artifact states on its face
    that it is not to be rendered on the fleet servers.
    """
    safe_title = html.escape(str(title))
    payload = json.dumps({"title": title, "elements": elements,
                          "width": width, "height": height},
                         ensure_ascii=False)
    cards = "\n".join(
        f'      <section class="card" data-at="{e.get("at", 0)}" '
        f'data-kind="{html.escape(str(e.get("kind", "text")))}">'
        f'{html.escape(str(e.get("text", "")))}</section>'
        for e in elements)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{safe_title} — VyralX motion composition (OFF-FLEET RENDER ARTIFACT)</title>
<style>
  body {{ margin:0; background:#0b0b10; color:#f2f2f2;
         font-family: system-ui, sans-serif; }}
  .stage {{ position:relative; width:{width}px; height:{height}px;
           overflow:hidden; }}
  .card {{ position:absolute; left:6%; right:6%; top:38%;
          font-size:64px; font-weight:700; text-align:center;
          opacity:0; }}
  .note {{ position:absolute; bottom:12px; left:12px; font-size:14px;
          color:#9a9aa5; }}
</style>
</head>
<body>
<div class="stage" id="stage">
{cards}
  <div class="note">VyralX motion composition {MOTION_VERSION} — render
  OFF the fleet servers (headless Chrome exceeds the ~1 GB fleet RAM);
  render on the owner's machine or post-ARM.</div>
</div>
<script type="application/json" id="timeline">{payload}</script>
<script>
  // Deterministic reveal: a renderer drives window.__seek(t); the
  // preview fallback steps through cards on a timer.
  const data = JSON.parse(document.getElementById('timeline').textContent);
  const cards = [...document.querySelectorAll('.card')];
  window.__seek = (t) => {{
    cards.forEach((c, i) => {{
      const at = parseFloat(c.dataset.at || 0);
      c.style.opacity = (t >= at && (i === cards.length - 1 ||
        t < parseFloat(cards[i + 1].dataset.at || 1e9))) ? 1 : 0;
    }});
  }};
  let step = 0;
  setInterval(() => {{ if (cards.length) {{
    window.__seek(parseFloat(cards[step % cards.length].dataset.at || 0));
    step++; }} }}, 1200);
</script>
</body>
</html>
"""
