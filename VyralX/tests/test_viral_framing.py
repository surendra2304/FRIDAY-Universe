"""TASK-VYR-019: framed production's pure pieces — excerpt windows,
caption timing, the framing gate suite, and the editorial parser.
The owner's rules under test: short excerpts only; subtitles always,
on measured timings; the hook obeys the production 18-word cap; a
line that cannot fit its duck window is a gate violation, not a ship.
"""
from __future__ import annotations

import json

from app.services import viral_framing


def test_excerpt_window_short_source_used_whole():
    assert viral_framing.excerpt_window(30.0, None) == (0.0, 30.0)
    assert viral_framing.excerpt_window(58.0, 0.5) == (0.0, 58.0)


def test_excerpt_window_long_source_centres_on_peak():
    start, end = viral_framing.excerpt_window(300.0, 0.5)
    assert end - start == 40.0
    assert start == 130.0  # peak at 150s, window centred on it
    start, end = viral_framing.excerpt_window(300.0, None)
    assert (start, end) == (130.0, 170.0)  # no arc -> middle


def test_excerpt_window_clamps_to_source_edges():
    start, end = viral_framing.excerpt_window(300.0, 0.0)
    assert (start, end) == (0.0, 40.0)
    start, end = viral_framing.excerpt_window(300.0, 1.0)
    assert (start, end) == (260.0, 300.0)


def test_framed_cues_shift_clip_and_frame():
    speech = [
        {"start": 100.0, "end": 104.0, "text": "before the window"},
        {"start": 132.0, "end": 136.5, "text": "the moment lands"},
        {"start": 168.0, "end": 172.0, "text": "straddling the edge"},
        {"start": 171.0, "end": 175.0, "text": "after the window"},
    ]
    cues = viral_framing.framed_cues(
        speech,
        excerpt_start=130.0, excerpt_seconds=40.0,
        hook="Watch what she does next", hook_seconds=2.5,
        payoff="And that is the whole trick", payoff_seconds=3.0,
    )
    texts = [cue["text"] for cue in cues]
    assert "before the window" not in texts
    assert "after the window" not in texts
    moment = next(cue for cue in cues if cue["text"] == "the moment lands")
    assert moment["start"] == 2.0 and moment["end"] == 6.5
    assert moment["speech"] is True
    # A cue that starts inside the excerpt but runs past its end is
    # clipped to the excerpt, never stretched beyond it.
    straddle = next(cue for cue in cues if cue["text"] == "straddling the edge")
    assert straddle["start"] == 38.0 and straddle["end"] == 40.0
    hook_cue = cues[0]
    assert hook_cue["start"] == 0.0 and hook_cue["end"] == 2.5
    payoff_cue = next(cue for cue in cues if cue["text"] == "And that is the whole trick")
    assert payoff_cue["start"] == 37.0 and payoff_cue["end"] == 40.0


def _violations(**overrides):
    base = {
        "hook": "Watch this keeper somehow keep it out",
        "payoff": "That save wins the match on its own",
        "title": "Keeper Pulls Off Impossible Save #Shorts",
        "description": "An impossible save. #Shorts",
        "record": None,
        "excerpt_seconds": 40.0,
    }
    base.update(overrides)
    return viral_framing.framing_violations(**base)


def test_framing_gates_accept_a_clean_package():
    assert _violations() == []


def test_framing_gates_hook_cap_and_missing_payoff():
    kinds = {v.kind for v in _violations(hook=" ".join(["word"] * 19))}
    assert "hook_too_long" in kinds
    kinds = {v.kind for v in _violations(payoff="")}
    assert "payoff_missing" in kinds
    kinds = {v.kind for v in _violations(hook="")}
    assert "hook_missing" in kinds


def test_framing_gates_window_fit():
    # A 7-word hook needs ~2.9s; a 12s excerpt gives it a 3.6s window: fine.
    assert _violations(excerpt_seconds=12.0) == []
    # The same hook cannot fit a 6s excerpt's 1.8s window.
    kinds = {v.kind for v in _violations(excerpt_seconds=6.0)}
    assert "hook_overruns_window" in kinds


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_generate_framing_parses_the_package(monkeypatch):
    package = {
        "title": "Keeper Pulls Off Impossible Save #Shorts",
        "hook": "Watch this keeper somehow keep it out.",
        "payoff": "That save wins the match on its own.",
        "description": "An impossible save.\n\nDrop your answer below!",
    }
    payload = {"choices": [{"message": {"content": json.dumps(package)}}]}
    monkeypatch.setattr(
        viral_framing.httpx, "post", lambda *a, **k: _Response(payload)
    )
    result = viral_framing.generate_framing(
        "SPORTS", "Original title", "Channel", "transcript text", scene="a keeper dives"
    )
    assert result["hook"] == package["hook"]
    assert result["payoff"] == package["payoff"]
    assert result["title"] == package["title"]


def test_generate_framing_rejects_taken_titles(monkeypatch):
    package = {
        "title": "Keeper Pulls Off Impossible Save #Shorts",
        "hook": "Watch this keeper somehow keep it out.",
        "payoff": "That save wins the match on its own.",
        "description": "desc",
    }
    payload = {"choices": [{"message": {"content": json.dumps(package)}}]}
    monkeypatch.setattr(
        viral_framing.httpx, "post", lambda *a, **k: _Response(payload)
    )
    result = viral_framing.generate_framing(
        "SPORTS", "t", "c", "x",
        taken_titles={"keeper pulls off impossible save #shorts"},
    )
    assert result == {}


# --------------------------------------------------------------------------- #
# TASK-VYR-021: the render-fit profile is pinned. The first supervised
# cycle lost both framed renders to the 2,400s production timeout at
# the old 1080x1920/veryfast profile (70.5 CPU-s per 40s render on one
# core, 378MB peak RSS — measured). These tests capture the exact
# ffmpeg command render_framed builds so the profile cannot silently
# regress to the heavy one, and so the locked rules riding in the same
# command (captions burned, source ducked to 0.22 under her lines,
# loudnorm target, BGM bed in the mix) cannot be lost with it.
# --------------------------------------------------------------------------- #
from pathlib import Path

from app.services import viral_remix


def _capture_render(monkeypatch, tmp_path, *, with_bed=True):
    captured = {}

    def fake_run(cmd, *, timeout=600):
        captured["cmd"] = [str(part) for part in cmd]
        captured["timeout"] = timeout

    monkeypatch.setattr(viral_remix, "_run", fake_run)
    cues = [
        {"start": 1.0, "end": 2.5, "text": "the moment lands", "speech": True},
        {"start": 0.0, "end": 4.0, "text": "watch what he does next"},
    ]
    viral_framing.render_framed(
        tmp_path / "source.mp4",
        tmp_path / "out.mp4",
        excerpt_start=9.0,
        excerpt_seconds=40.0,
        hook_audio=tmp_path / "hook.mp3",
        hook_seconds=4.0,
        payoff_audio=tmp_path / "payoff.mp3",
        payoff_seconds=6.0,
        cues=cues,
        category="VIRAL",
        music_bed_path=(tmp_path / "bed.wav") if with_bed else None,
    )
    return captured


def _filter_complex(cmd):
    return cmd[cmd.index("-filter_complex") + 1]


def _flag_value(cmd, flag):
    return cmd[cmd.index(flag) + 1]


def test_render_framed_uses_render_fit_profile(monkeypatch, tmp_path):
    captured = _capture_render(monkeypatch, tmp_path)
    cmd = captured["cmd"]
    chain = _filter_complex(cmd)
    # The fit profile: 720x1280, frames capped at 30fps before scaling.
    assert "fps=30" in chain
    assert "scale=720:1280:force_original_aspect_ratio=increase" in chain
    assert "crop=720:1280" in chain
    assert "scale=1080:1920" not in chain
    assert _flag_value(cmd, "-preset") == "ultrafast"
    assert _flag_value(cmd, "-crf") == "23"
    assert _flag_value(cmd, "-threads") == "2"
    # The production timeout is NOT the fix — it stays 2,400s and the
    # encode is made to fit inside it.
    assert captured["timeout"] == 2400


def test_render_framed_keeps_locked_rules_in_the_same_command(monkeypatch, tmp_path):
    chain = _filter_complex(_capture_render(monkeypatch, tmp_path)["cmd"])
    # Subtitles are burned, always.
    assert "subtitles=" in chain
    # Her lines duck the source to the production level, at both ends.
    assert chain.count("volume=0.22:enable='between(t,") == 2
    # The BGM bed is in the mix (3-way amix) and the loudnorm target
    # is the production one.
    assert "amix=inputs=3" in chain
    assert "loudnorm=I=-14:LRA=9:TP=-1.5" in chain


def test_render_framed_without_bed_keeps_profile(monkeypatch, tmp_path):
    captured = _capture_render(monkeypatch, tmp_path, with_bed=False)
    chain = _filter_complex(captured["cmd"])
    assert "scale=720:1280" in chain
    assert "fps=30" in chain
    assert "amix=inputs=2" in chain
    assert _flag_value(captured["cmd"], "-preset") == "ultrafast"


def test_base_video_filter_defaults_are_the_channel_format():
    # The commentary renderers share this helper and must keep the
    # historical 1080x1920 chain byte-for-byte; only the framed
    # renderer opts into the smaller profile.
    ass_path = Path("captions.ass")
    expected = (
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,eq=contrast=1.06:saturation=1.12,"
        f"subtitles='{viral_remix._escape_filter_path(ass_path)}'"
        f":fontsdir='{viral_remix._escape_filter_path(Path('data/fonts'))}'"
    )
    assert viral_remix._base_video_filter([], "VIRAL", ass_path) == expected


def test_render_fit_profile_constants_are_the_measured_ones():
    assert (viral_framing._RENDER_WIDTH, viral_framing._RENDER_HEIGHT) == (720, 1280)
    assert viral_framing._RENDER_MAX_FPS == 30
    assert viral_framing._X264_PRESET == "ultrafast"
    assert viral_framing._X264_CRF == "23"
    assert viral_framing._X264_THREADS == "2"


# --------------------------------------------------------------------------- #
# TASK-VYR-022: the excerpt cut gets the same render-fit treatment.
# Supervised cycle 2 lost 3 of 12 attempts to TimeoutExpired on this
# step alone (veryfast/crf18 at full source resolution, under the
# 600s _run default) while every composition the #1026 profile
# touched finished in ~1-2 minutes. The excerpt is analysis-only —
# the event-arc probe reads 96x170 gray frames and the vision record
# extracts frames at scale=640:-2 — so it is capped to the render
# fit (720x1280 box, fps 30, ultrafast/crf23, threads 2), aspect
# preserved, never upscaled, never cropped. These tests pin the
# exact command so the heavy profile cannot silently return, and pin
# that the fix is the encode, NOT a longer timeout.
# --------------------------------------------------------------------------- #
def _capture_excerpt(monkeypatch, tmp_path):
    captured = {}

    def fake_run(cmd, *, timeout=600):
        captured["cmd"] = [str(part) for part in cmd]
        captured["timeout"] = timeout

    monkeypatch.setattr(viral_remix, "_run", fake_run)
    viral_framing._cut_excerpt(
        tmp_path / "source.mp4", tmp_path / "excerpt.mp4", 12.5, 23.64
    )
    return captured


def test_cut_excerpt_uses_excerpt_fit_profile(monkeypatch, tmp_path):
    captured = _capture_excerpt(monkeypatch, tmp_path)
    cmd = captured["cmd"]
    chain = _flag_value(cmd, "-vf")
    assert chain == viral_framing._excerpt_video_filter()
    assert "fps=30" in chain
    assert "min(720,iw)" in chain and "min(1280,ih)" in chain
    assert _flag_value(cmd, "-preset") == "ultrafast"
    assert _flag_value(cmd, "-crf") == "23"
    assert _flag_value(cmd, "-threads") == "2"
    # The old heavy profile is gone.
    assert "veryfast" not in cmd
    assert _flag_value(cmd, "-crf") != "18"
    # The window mechanics are unchanged: input-side seek, exact -t,
    # silent (the excerpt feeds vision, not audio analysis).
    assert _flag_value(cmd, "-ss") == "12.500"
    assert _flag_value(cmd, "-t") == "23.640"
    assert "-an" in cmd
    # The timeout is NOT the fix — the 600s _run default stays and
    # the encode is made to fit inside it.
    assert captured["timeout"] == 600


def test_excerpt_filter_preserves_frame_and_never_upscales():
    chain = viral_framing._excerpt_video_filter()
    # No crop: the vision record must see the whole frame.
    assert "crop" not in chain
    # Aspect preserved by construction, dimensions divisible by 2
    # for libx264, and the min() caps forbid upscaling small sources.
    assert "force_original_aspect_ratio=decrease" in chain
    assert "force_divisible_by=2" in chain


def test_excerpt_fit_profile_constants_match_the_render_fit():
    assert (viral_framing._EXCERPT_WIDTH, viral_framing._EXCERPT_HEIGHT) == (720, 1280)
    assert viral_framing._EXCERPT_MAX_FPS == 30
    assert viral_framing._EXCERPT_PRESET == "ultrafast"
    assert viral_framing._EXCERPT_CRF == "23"
    assert viral_framing._EXCERPT_THREADS == "2"
    # The excerpt never exceeds what the final render itself uses.
    assert viral_framing._EXCERPT_WIDTH == viral_framing._RENDER_WIDTH
    assert viral_framing._EXCERPT_HEIGHT == viral_framing._RENDER_HEIGHT
    assert viral_framing._EXCERPT_MAX_FPS == viral_framing._RENDER_MAX_FPS


# --------------------------------------------------------------------------- #
# TASK-VYR-022: the framed path gains the commentary path's
# description-question repair. Cycle-2 diagnosis: script_unverifiable
# was the largest skip class (5/12); the only violation kind the
# cycle record documents more than once is question_ungrounded, and
# the framed path — running the identical description check on the
# identical mandated question format — had no deterministic escape
# from it, while the commentary path has repaired exactly that class
# since TASK-VYR-014. The repair must fire ONLY for question-kind
# violations and the repaired package must re-pass every gate.
# --------------------------------------------------------------------------- #
_REPAIR_BEAT = {
    "setting": "kitchen", "time_of_day": "day",
    "subjects": [{
        "hair": "brown hair", "clothing": "red shirt",
        "posture": "standing", "action": "holding a trophy",
        "emotion": "smiling", "eyes": "open",
    }],
    "objects": ["trophy", "table"],
    "summary": "A man holds a trophy in a kitchen",
}
_REPAIR_RECORD = {
    "beats": [dict(_REPAIR_BEAT) for _ in range(3)],
    "event_arc": "A man lifts a trophy and smiles",
    "static": False,
}
_REPAIR_HOOK = "He lifts the trophy and smiles at the table."
_REPAIR_PAYOFF = "The trophy stays high while he keeps smiling."
_REPAIR_TITLE = "Man Lifts Trophy In Kitchen #Shorts"
_UNGROUNDED_DESCRIPTION = (
    "He lifts the trophy in the kitchen while everyone watches the table.\n\n"
    "🤔 What did the elephant whisper? Drop your answer below!\n\n"
    "#Shorts #viral"
)


def _repair(framing, violations):
    return viral_framing.repair_framing_description(
        framing, violations,
        hook=_REPAIR_HOOK, payoff=_REPAIR_PAYOFF,
        record=_REPAIR_RECORD, excerpt_seconds=20.0,
    )


def test_framing_description_question_repair_rescues_grounded_package():
    framing = {
        "title": _REPAIR_TITLE, "hook": _REPAIR_HOOK, "payoff": _REPAIR_PAYOFF,
        "description": _UNGROUNDED_DESCRIPTION,
    }
    violations = viral_framing.framing_violations(
        hook=_REPAIR_HOOK, payoff=_REPAIR_PAYOFF, title=_REPAIR_TITLE,
        description=_UNGROUNDED_DESCRIPTION, record=_REPAIR_RECORD,
        excerpt_seconds=20.0,
    )
    assert [v.kind for v in violations] == ["question_ungrounded"]
    repaired_framing, remaining, repaired = _repair(framing, violations)
    assert repaired is True
    assert remaining == []
    # The ungrounded question is gone; the record's own grounded
    # question (about the trophy, a recorded object) replaced it.
    assert "elephant" not in repaired_framing["description"]
    assert "trophy" in repaired_framing["description"]
    # Factual fields are never touched by the repair.
    assert repaired_framing["title"] == framing["title"]
    assert repaired_framing["hook"] == framing["hook"]


def test_framing_description_repair_refuses_factual_violations():
    # A title claiming an unverified garment colour is a factual
    # defect: the package must still die as script_unverifiable,
    # never be edited into compliance — even though it ALSO carries
    # a repairable question violation.
    framing = {
        "title": "Man In Blue Shirt Lifts Trophy #Shorts",
        "hook": _REPAIR_HOOK, "payoff": _REPAIR_PAYOFF,
        "description": _UNGROUNDED_DESCRIPTION,
    }
    violations = viral_framing.framing_violations(
        hook=_REPAIR_HOOK, payoff=_REPAIR_PAYOFF, title=framing["title"],
        description=_UNGROUNDED_DESCRIPTION, record=_REPAIR_RECORD,
        excerpt_seconds=20.0,
    )
    kinds = {v.kind for v in violations}
    assert "unverified_garment_colour" in kinds
    assert "question_ungrounded" in kinds
    repaired_framing, remaining, repaired = _repair(framing, violations)
    assert repaired is False
    assert repaired_framing is framing
    assert remaining == violations


def test_framing_description_repair_is_noop_without_violations():
    framing = {
        "title": _REPAIR_TITLE, "hook": _REPAIR_HOOK, "payoff": _REPAIR_PAYOFF,
        "description": "He lifts the trophy in the kitchen.",
    }
    repaired_framing, remaining, repaired = _repair(framing, [])
    assert repaired is False
    assert repaired_framing is framing
    assert remaining == []
