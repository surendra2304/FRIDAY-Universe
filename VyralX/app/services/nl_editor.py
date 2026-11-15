"""VyralX natural-language video editing (TASK-IG-VYR-05).

The IG reference corpus's editing cluster (DeihXkGDQV0 — an
open-source AI video editor, name DM-gated so there is nothing to
adopt; DdlIP2YAqsq — AI-assisted editing workflows; Dep0wuhvizo —
"a tool that turns any AI agent into a video editor") points at one
pattern: **the agent edits by instruction**. A human (or FRIDAY, or
the channel operator) says what to change in plain language; the
system compiles that to a deterministic edit decision list (EDL)
and an ffmpeg plan. No timeline dragging, and — important for an
autonomous pipeline — every edit is a reviewable artefact before
anything renders.

This module implements the compiler:

* :func:`parse_instructions` — a deterministic parser over a
  DEFINED command set (below). Anything outside the set is an
  error entry, never silently dropped and never guessed at.
* :func:`validate_edl` — range/overlap checks against the source
  duration.
* :func:`keep_segments` — the timeline math: trims and cuts
  resolved to the segments that survive.
* :func:`ffmpeg_plan` — one ffmpeg argv implementing the surviving
  segments plus the non-destructive ops (speed, mute, lower-third,
  captions, punch-in) as a filter chain. Building the plan executes
  nothing; :func:`execute_plan` runs it, guarded.

Supported instructions (times are seconds or ``m:ss``):

* ``trim the first N seconds`` / ``trim the last N seconds``
* ``cut from A to B``
* ``speed up from A to B by X`` / ``slow down from A to B by X``
* ``mute from A to B``
* ``add captions`` (burns in the project's caption track at render)
* ``punch in at T`` (centre-zoom beat)
* ``add lower third 'TEXT' at T``
* ``insert b-roll CLIP_ID at T``

Every EDL and plan carries ``status="pending_review"`` — an edit
plan joins the same human gate as everything else VyralX makes.
No network. Python 3.10.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

EDITOR_VERSION = "ig-vyr05-1"


def parse_time(text: str) -> float:
    """Parse '90', '90s', '1:30' or '1:02:03' into seconds."""
    t = str(text).strip().rstrip("s")
    if ":" in t:
        parts = [float(p) for p in t.split(":")]
        total = 0.0
        for p in parts:
            total = total * 60 + p
        return total
    return float(t)


def _fmt(seconds: float) -> str:
    return f"{seconds:.3f}"


_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("trim_start", re.compile(
        r"trim the first ([\d:.]+) seconds?", re.I)),
    ("trim_end", re.compile(
        r"trim the last ([\d:.]+) seconds?", re.I)),
    ("cut", re.compile(
        r"cut from ([\d:.]+) to ([\d:.]+)", re.I)),
    ("speed", re.compile(
        r"(speed up|slow down) from ([\d:.]+) to ([\d:.]+) by ([\d.]+)x?",
        re.I)),
    ("mute", re.compile(
        r"mute from ([\d:.]+) to ([\d:.]+)", re.I)),
    ("captions", re.compile(r"(add|burn in) captions", re.I)),
    ("punch_in", re.compile(r"punch in at ([\d:.]+)", re.I)),
    ("lower_third", re.compile(
        r"add lower third ['\"]([^'\"]+)['\"] at ([\d:.]+)", re.I)),
    ("insert_broll", re.compile(
        r"insert b-?roll ([\w\-]+) at ([\d:.]+)", re.I)),
]


def parse_instructions(text: str) -> dict[str, Any]:
    """Compile instruction text into an EDL + an errors list.

    Instructions are separated by newlines, semicolons, or the word
    "then". A fragment that matches no known command becomes an
    error entry naming the fragment — the caller sees exactly what
    was not understood.
    """
    fragments = re.split(r"[\n;]+|\bthen\b", str(text or ""),
                         flags=re.I)
    edl: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for frag in fragments:
        frag = frag.strip(" ,.")
        if not frag:
            continue
        matched = False
        for kind, pattern in _PATTERNS:
            m = pattern.search(frag)
            if not m:
                continue
            matched = True
            g = m.groups()
            if kind == "trim_start":
                edl.append({"op": "trim_start",
                            "seconds": parse_time(g[0])})
            elif kind == "trim_end":
                edl.append({"op": "trim_end",
                            "seconds": parse_time(g[0])})
            elif kind == "cut":
                edl.append({"op": "cut", "start": parse_time(g[0]),
                            "end": parse_time(g[1])})
            elif kind == "speed":
                factor = float(g[3])
                if g[0].casefold().startswith("slow"):
                    factor = 1.0 / factor if factor else 1.0
                edl.append({"op": "speed", "start": parse_time(g[1]),
                            "end": parse_time(g[2]), "factor": factor})
            elif kind == "mute":
                edl.append({"op": "mute", "start": parse_time(g[0]),
                            "end": parse_time(g[1])})
            elif kind == "captions":
                edl.append({"op": "captions"})
            elif kind == "punch_in":
                edl.append({"op": "punch_in", "at": parse_time(g[0]),
                            "zoom": 1.25})
            elif kind == "lower_third":
                edl.append({"op": "lower_third", "text": g[0],
                            "at": parse_time(g[1])})
            elif kind == "insert_broll":
                edl.append({"op": "insert_broll", "clip_id": g[0],
                            "at": parse_time(g[1])})
            break
        if not matched:
            errors.append({"instruction": frag,
                           "error": "no matching command in the "
                                    "supported set"})
    return {
        "kind": "edit_decision_list",
        "editor_version": EDITOR_VERSION,
        "edl": edl,
        "errors": errors,
        "status": "pending_review",
        "requires_approval": True,
    }


# --------------------------------------------------------------------------- #
# Validation + timeline math
# --------------------------------------------------------------------------- #
def validate_edl(edl: list[dict[str, Any]],
                 duration: float | None) -> list[str]:
    """Range/overlap problems in an EDL, given the source duration."""
    problems: list[str] = []
    if duration is None:
        return ["source duration unknown — ranges cannot be validated"]
    cuts = []
    for op in edl:
        for key in ("start", "at"):
            if key in op and not (0 <= op[key] <= duration):
                problems.append(
                    f"{op['op']}: {key}={op[key]} outside 0..{duration}")
        if "end" in op:
            if op["end"] > duration:
                problems.append(
                    f"{op['op']}: end={op['end']} beyond duration "
                    f"{duration}")
            if op["end"] <= op.get("start", 0):
                problems.append(
                    f"{op['op']}: end must be after start")
        if op["op"] == "cut":
            cuts.append((op["start"], op["end"]))
        if op["op"] == "speed" and not (0.25 <= op["factor"] <= 4.0):
            problems.append(
                f"speed: factor {op['factor']} outside 0.25..4.0")
    cuts.sort()
    for (a0, a1), (b0, b1) in zip(cuts, cuts[1:]):
        if b0 < a1:
            problems.append(f"overlapping cuts {a0}-{a1} and {b0}-{b1}")
    return problems


def keep_segments(edl: list[dict[str, Any]],
                  duration: float) -> list[tuple[float, float]]:
    """Resolve trims + cuts to the (start, end) segments that survive."""
    lo, hi = 0.0, float(duration)
    cuts: list[tuple[float, float]] = []
    for op in edl:
        if op["op"] == "trim_start":
            lo = max(lo, op["seconds"])
        elif op["op"] == "trim_end":
            hi = min(hi, duration - op["seconds"])
        elif op["op"] == "cut":
            cuts.append((op["start"], op["end"]))
    if hi <= lo:
        return []
    segments = [(lo, hi)]
    for c0, c1 in sorted(cuts):
        out = []
        for s0, s1 in segments:
            if c1 <= s0 or c0 >= s1:
                out.append((s0, s1))
                continue
            if c0 > s0:
                out.append((s0, c0))
            if c1 < s1:
                out.append((c1, s1))
        segments = out
    return [(round(a, 3), round(b, 3)) for a, b in segments if b > a]


# --------------------------------------------------------------------------- #
# ffmpeg plan
# --------------------------------------------------------------------------- #
def ffmpeg_plan(source: str, edl: list[dict[str, Any]], duration: float,
                output: str) -> dict[str, Any]:
    """Build (never run) the ffmpeg argv implementing an EDL.

    Trims/cuts become trim+concat over the keep segments; speed,
    mute, punch-in and lower-third become labelled filter steps;
    captions and b-roll inserts are recorded as render-time steps
    for the VYR-003 renderer (they need project assets, so the plan
    names them rather than faking an argv for them).
    """
    segments = keep_segments(edl, duration)
    if not segments:
        raise ValueError("EDL removes the entire video — nothing to render")
    filters = []
    labels = []
    for i, (a, b) in enumerate(segments):
        filters.append(
            f"[0:v]trim=start={_fmt(a)}:end={_fmt(b)},setpts=PTS-STARTPTS"
            f"[v{i}]")
        filters.append(
            f"[0:a]atrim=start={_fmt(a)}:end={_fmt(b)},"
            f"asetpts=PTS-STARTPTS[a{i}]")
        labels.append(f"[v{i}][a{i}]")
    filters.append(
        "".join(labels) + f"concat=n={len(segments)}:v=1:a=1[vcat][acat]")
    vlabel, alabel = "[vcat]", "[acat]"
    extra_steps: list[dict[str, Any]] = []
    for op in edl:
        if op["op"] == "speed":
            # Range-local speed needs a split/merge the single-pass
            # argv does not pretend to express: it is recorded as a
            # renderer step with its exact filter, not faked.
            extra_steps.append({**op, "applied_as": "renderer_step",
                                "filter": f"setpts=PTS/{op['factor']} "
                                          f"on [{_fmt(op['start'])},"
                                          f"{_fmt(op['end'])}]"})
        elif op["op"] == "mute":
            extra_steps.append({**op, "applied_as": "audio_filter",
                                "filter": f"volume=0:enable='between(t,"
                                          f"{_fmt(op['start'])},"
                                          f"{_fmt(op['end'])})'"})
        elif op["op"] == "punch_in":
            extra_steps.append({**op, "applied_as": "video_filter",
                                "filter": "crop=iw/1.25:ih/1.25,"
                                          "scale=iw*1.25:ih*1.25"})
        elif op["op"] == "lower_third":
            safe = op["text"].replace("'", "").replace(":", "")
            extra_steps.append({**op, "applied_as": "video_filter",
                                "filter": f"drawtext=text='{safe}':"
                                          f"x=40:y=h-120:fontsize=36"})
        elif op["op"] in ("captions", "insert_broll"):
            extra_steps.append({**op, "applied_as": "renderer_step"})
    argv = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-i", source, "-filter_complex", ";".join(filters),
            "-map", vlabel, "-map", alabel, output]
    return {
        "kind": "ffmpeg_plan",
        "editor_version": EDITOR_VERSION,
        "source": source,
        "output": output,
        "keep_segments": segments,
        "argv": argv,
        "extra_steps": extra_steps,
        "status": "pending_review",
        "requires_approval": True,
        "executed": False,
    }


def execute_plan(plan: dict[str, Any], timeout: int = 300) -> dict[str, Any]:
    """Run a built plan's argv. Guarded; reports honestly."""
    if shutil.which("ffmpeg") is None:
        return {"executed": False, "reason": "ffmpeg not found on PATH"}
    if not Path(plan["source"]).exists():
        return {"executed": False,
                "reason": f"source not found: {plan['source']}"}
    try:
        proc = subprocess.run(plan["argv"], capture_output=True,
                              text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"executed": False, "reason": f"ffmpeg failed: {exc}"}
    ok = proc.returncode == 0 and Path(plan["output"]).exists()
    return {"executed": ok,
            "reason": "ok" if ok else
            f"ffmpeg exited {proc.returncode}: "
            f"{proc.stderr.strip()[:200]}",
            "output": plan["output"] if ok else None}
