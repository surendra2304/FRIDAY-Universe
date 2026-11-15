"""TASK-IG-VYR-05: natural-language video editing (IG corpus cluster).

Behaviour pinned here:

* the parser compiles a defined command set into an EDL and
  reports unknown instructions as errors — never silently dropped,
  never guessed;
* trims/cuts resolve to exact keep-segments; validation catches
  out-of-range times, inverted ranges, overlapping cuts and
  absurd speed factors;
* the ffmpeg plan is built, not executed, by default; its argv
  implements the keep segments, and range-local ops ride as
  labelled renderer steps;
* a guarded real render of a trim+cut plan works on a synthetic
  video (skipped without ffmpeg).

On clean main every test fails: app.services.nl_editor does not
exist.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from app.services import nl_editor as ne

SCRIPT = """trim the first 2 seconds
cut from 0:10 to 0:14; mute from 20 to 25
speed up from 30 to 40 by 2x, then add captions
add lower third 'NASA footage' at 5
insert b-roll L1-001 at 45
make it more cinematic please"""


def test_parser_compiles_defined_set_and_reports_unknown():
    out = ne.parse_instructions(SCRIPT)
    ops = [o["op"] for o in out["edl"]]
    assert ops == ["trim_start", "cut", "mute", "speed", "captions",
                   "lower_third", "insert_broll"]
    assert out["status"] == "pending_review"
    assert len(out["errors"]) == 1
    assert "cinematic" in out["errors"][0]["instruction"]


def test_parser_time_formats_and_speed_direction():
    out = ne.parse_instructions(
        "cut from 1:30 to 95; slow down from 0 to 10 by 2x")
    cut, speed = out["edl"]
    assert cut["start"] == 90.0 and cut["end"] == 95.0
    assert speed["factor"] == 0.5


def test_keep_segments_math():
    edl = [{"op": "trim_start", "seconds": 2.0},
           {"op": "cut", "start": 10.0, "end": 14.0},
           {"op": "trim_end", "seconds": 5.0}]
    assert ne.keep_segments(edl, 60.0) == [(2.0, 10.0), (14.0, 55.0)]
    assert ne.keep_segments(
        [{"op": "trim_start", "seconds": 70.0}], 60.0) == []


def test_validation_catches_problems():
    edl = [{"op": "cut", "start": 50.0, "end": 40.0},
           {"op": "cut", "start": 55.0, "end": 58.0},
           {"op": "cut", "start": 57.0, "end": 59.0},
           {"op": "speed", "start": 0.0, "end": 5.0, "factor": 9.0},
           {"op": "punch_in", "at": 99.0}]
    problems = ne.validate_edl(edl, 60.0)
    text = " | ".join(problems)
    assert "end must be after start" in text
    assert "overlapping cuts" in text
    assert "outside 0.25..4.0" in text
    assert "outside 0..60" in text
    assert ne.validate_edl([], None) == [
        "source duration unknown — ranges cannot be validated"]


def test_ffmpeg_plan_structure():
    parsed = ne.parse_instructions("trim the first 2 seconds; "
                                   "cut from 10 to 14")
    plan = ne.ffmpeg_plan("in.mp4", parsed["edl"], 60.0, "out.mp4")
    assert plan["keep_segments"] == [(2.0, 10.0), (14.0, 60.0)]
    assert plan["executed"] is False
    assert plan["status"] == "pending_review"
    argv = plan["argv"]
    assert argv[0] == "ffmpeg" and "concat=n=2" in argv[argv.index(
        "-filter_complex") + 1]


def test_plan_refuses_empty_result():
    try:
        ne.ffmpeg_plan("in.mp4",
                       [{"op": "trim_start", "seconds": 70.0}],
                       60.0, "out.mp4")
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")


@pytest.mark.skipif(shutil.which("ffmpeg") is None,
                    reason="ffmpeg not available")
def test_real_render_of_trim_cut_plan(tmp_path):
    src = tmp_path / "src.mp4"
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "lavfi", "-i", "testsrc=duration=6:size=320x240:rate=10",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=6",
         "-shortest", str(src)], check=True, capture_output=True,
        timeout=60)
    parsed = ne.parse_instructions("trim the first 1 seconds; "
                                   "cut from 3 to 4")
    plan = ne.ffmpeg_plan(str(src), parsed["edl"], 6.0,
                          str(tmp_path / "out.mp4"))
    result = ne.execute_plan(plan)
    assert result["executed"] is True, result
    assert Path(result["output"]).stat().st_size > 0
