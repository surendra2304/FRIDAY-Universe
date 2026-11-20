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
# TASK-VYR-022: the coordinator's full watch of cycle 2's four renders
# (jobs 801-804) found (1) her framing captions stacked over the
# source's own captions in the lower third, (2) job 804's payoff
# inventing a "safety sign" and a "folder" that are nowhere in the
# footage, (3) job 803's title promising a journal-strip tear the
# excerpt never shows (and a payoff ending on like-bait), and (4) job
# 802's excerpt ending on an unrelated reaction still. These tests pin
# the four fixes.
# --------------------------------------------------------------------------- #
import shutil
import subprocess

import pytest


# --- (1) caption collision: her band, and no duplicated words -------- #
def test_framed_cues_mark_framing_lines():
    cues = viral_framing.framed_cues(
        [{"start": 5.0, "end": 8.0, "text": "the source speaks here"}],
        excerpt_start=0.0, excerpt_seconds=20.0,
        hook="Watch this moment closely", hook_seconds=2.0,
        payoff="And that is the trick", payoff_seconds=2.5,
    )
    by_text = {cue["text"]: cue for cue in cues}
    assert by_text["Watch this moment closely"]["framing"] is True
    assert by_text["And that is the trick"]["framing"] is True
    assert "framing" not in by_text["the source speaks here"]
    assert by_text["the source speaks here"]["speech"] is True


def test_framed_cues_drop_speech_cue_duplicating_the_payoff():
    # Job 801's shape: her payoff quotes the source's final line, and
    # the Whisper cue for that line lands inside the payoff window —
    # the words were captioned twice at once. The duplicate speech
    # cue is dropped; a different speech cue in the same window and
    # the duplicated words OUTSIDE the window both stay.
    speech = [
        {"start": 1.0, "end": 3.0, "text": "some of them faint"},
        {"start": 16.0, "end": 17.5, "text": "some of them faint"},
        {"start": 17.5, "end": 19.0, "text": "a different closing remark"},
    ]
    cues = viral_framing.framed_cues(
        speech,
        excerpt_start=0.0, excerpt_seconds=20.0,
        hook="Watch the interview turn", hook_seconds=2.0,
        payoff="A tiny graphic flashes. Some of them faint.", payoff_seconds=4.0,
    )
    faint = [cue for cue in cues if cue["text"] == "some of them faint"]
    assert len(faint) == 1 and faint[0]["start"] == 1.0  # only the early one
    assert any(cue["text"] == "a different closing remark" for cue in cues)


def test_write_ass_puts_framing_cues_in_their_own_top_band(tmp_path):
    # The fixture carries a lower-third source speech cue (the default
    # bottom style) plus her framing line: the framing text must land
    # in the dedicated top band (alignment 8, opaque box), never in
    # the source caption zone.
    cues = [
        {"start": 1.0, "end": 3.0, "text": "the source speaks", "speech": True},
        {"start": 0.0, "end": 2.0, "text": "watch this moment", "framing": True},
    ]
    ass_path = viral_remix._write_ass(cues, tmp_path / "caps.ass")
    text = ass_path.read_text(encoding="utf-8")
    assert "Style: AntonFraming" in text
    framing_style = next(
        line for line in text.splitlines() if line.startswith("Style: AntonFraming")
    )
    # BorderStyle 3 (opaque box) and Alignment 8 (top-centre).
    assert ",3,12.0,0,8,50,50,150,1" in framing_style
    framing_dialogue = next(
        line for line in text.splitlines() if "WATCH THIS MOMENT" in line
    )
    speech_dialogue = next(
        line for line in text.splitlines() if "THE SOURCE SPEAKS" in line
    )
    assert ",AntonFraming," in framing_dialogue
    assert ",AntonBold," in speech_dialogue


def test_write_ass_without_framing_cues_is_byte_identical(tmp_path):
    # The commentary renderers share _write_ass and must see no
    # change at all when no cue asks for the framing band.
    cues = [{"start": 1.0, "end": 3.0, "text": "plain commentary line"}]
    ass_path = viral_remix._write_ass(cues, tmp_path / "caps.ass")
    text = ass_path.read_text(encoding="utf-8")
    assert "AntonFraming" not in text
    assert text.startswith(viral_remix._ASS_HEADER)


# --- (2)+(3) grounding: invented objects, promised actions, bait ---- #
_PARK_TRANSCRIPT = (
    "people say my wife is on the wrong side it is my safe side rule "
    "I keep her on my safe side when we walk leave my wife alone over "
    "here I am fine stop"
)
_PARK_SCENE = (
    "1) A couple walks hand in hand along a park path. "
    "2) The man switches sides so his wife walks on his safe side."
)
_PARK_RECORD = {
    "event_arc": "a couple walks in a park and the man switches sides",
    "beats": [{
        "setting": "park path", "time_of_day": "day",
        "summary": "A couple walks hand in hand along a park path; the "
                   "man switches sides so his wife is on his safe side.",
        "objects": ["path"],
        "subjects": [{
            "hair": "", "clothing": "", "posture": "standing",
            "action": "walking and switching sides", "emotion": "smiling",
        }],
    }],
}


def _grounding(**overrides):
    base = {
        "hook": "Watch the man keep his wife on the safe side.",
        "payoff": "He switches sides so she walks beside him.",
        "title": "His Safe Side Rule on a Park Walk #Shorts",
        "transcript": _PARK_TRANSCRIPT,
        "scene": _PARK_SCENE,
        "record": _PARK_RECORD,
    }
    base.update(overrides)
    return viral_framing.framing_grounding_violations(**base)


def test_grounding_accepts_lines_built_from_the_evidence():
    assert _grounding() == []


def test_grounding_rejects_the_invented_sign_and_folder():
    # Job 804's actual payoff: neither object exists in the footage.
    violations = _grounding(
        payoff="He flips the safety sign, then hands over the folder "
               "with a grin."
    )
    kinds = {(v.kind, v.field) for v in violations}
    assert ("framing_ungrounded", "payoff") in kinds
    detail = next(v.detail for v in violations if v.kind == "framing_ungrounded")
    assert "'folder'" in detail and "'sign'" in detail


def test_grounding_rejects_a_single_invented_object():
    violations = _grounding(payoff="He switches sides holding a trophy.")
    assert any(
        v.kind == "framing_ungrounded" and v.field == "payoff"
        for v in violations
    )


def test_grounding_tolerates_one_paraphrase_word():
    # Her real job-804 hook says "stroll" where the record says
    # "walking": ordinary rewording must not trip the gate.
    assert _grounding(
        hook="Watch his weird safe-side rule as they stroll together."
    ) == []


def test_grounding_rejects_two_invented_specifics_in_the_title():
    violations = _grounding(title="He Juggles a Pineapple on a Rooftop #Shorts")
    assert any(v.kind == "title_ungrounded" for v in violations)


def test_title_action_must_be_shown_by_the_record():
    # Job 803's shape: the source TALKS about strips (the transcript
    # mentions them) but the camera only ever opens the journal — the
    # title may not promise the tear.
    record = {
        "event_arc": "hands open a journal and turn its pages",
        "beats": [{
            "setting": "desk", "time_of_day": "day",
            "summary": "Hands hold a paperback journal and flip "
                       "through its printed pages.",
            "objects": ["journal", "pages"],
            "subjects": [{
                "hair": "", "clothing": "", "posture": "",
                "action": "holding and opening a journal", "emotion": "",
            }],
        }],
    }
    transcript = (
        "it is called wreck this journal it gives you a new way to "
        "ruin it every day you crack the spine you spill your drink "
        "and strips of paper"
    )
    violations = viral_framing.framing_grounding_violations(
        hook="", payoff="", title="Tear the Journal Strip #Shorts",
        transcript=transcript,
        scene="1) Hands hold a paperback journal and flip through its pages.",
        record=record,
    )
    assert any(v.kind == "title_action_ungrounded" for v in violations)
    grounded = viral_framing.framing_grounding_violations(
        hook="", payoff="", title="He Opens the Journal Pages #Shorts",
        transcript=transcript,
        scene="1) Hands hold a paperback journal and flip through its pages.",
        record=record,
    )
    assert grounded == []


def test_grounding_object_not_grounded_by_prefix_cousin():
    # Review C1 probe (PR #1053): the 5-char prefix backstop grounded
    # an invented "poster" in the evidence word "posted".
    violations = viral_framing.framing_grounding_violations(
        hook="", payoff="He points at the poster.", title="",
        transcript="she posted it online yesterday for everyone",
        scene="", record=None,
    )
    assert any(
        v.kind == "framing_ungrounded" and v.field == "payoff"
        for v in violations
    )


def test_grounding_object_not_grounded_by_generated_stem():
    # Review C1 probe: "folding" spawns the stem form "folde", whose
    # 5-char prefix grounded an invented "folder".
    violations = viral_framing.framing_grounding_violations(
        hook="", payoff="He opens the folder.", title="",
        transcript="folding laundry all afternoon at home",
        scene="", record=None,
    )
    assert any(
        v.kind == "framing_ungrounded" and v.field == "payoff"
        for v in violations
    )


def test_grounding_object_not_grounded_by_stem_cousin():
    # Review C1 probe: _word_forms("signing") contains "sign", so
    # stem intersection grounded the invented object (a sign) in a
    # man signing (the verb) autographs.
    violations = viral_framing.framing_grounding_violations(
        hook="", payoff="He holds the sign.", title="",
        transcript="a man signing autographs for fans at the park",
        scene="", record=None,
    )
    assert any(
        v.kind == "framing_ungrounded" and v.field == "payoff"
        for v in violations
    )


def test_grounding_object_not_grounded_by_compound_cousin():
    # "basketball" shares a 6-char prefix with "basket" — the ball
    # game cannot vouch for the object.
    violations = viral_framing.framing_grounding_violations(
        hook="Watch the basket.", payoff="", title="",
        transcript="basketball practice runs all afternoon long",
        scene="", record=None,
    )
    assert any(
        v.kind == "framing_ungrounded" and v.field == "hook"
        for v in violations
    )


def test_grounding_object_not_grounded_by_derived_form():
    # "enveloped" is a verb form, not the object "envelope".
    violations = viral_framing.framing_grounding_violations(
        hook="Watch the envelope.", payoff="", title="",
        transcript="enveloped in mist the valley sleeps",
        scene="", record=None,
    )
    assert any(
        v.kind == "framing_ungrounded" and v.field == "hook"
        for v in violations
    )


def test_grounding_object_not_grounded_by_shared_stem_word():
    # "microscope" and "microphone" share the 5-char prefix "micro";
    # neither can vouch for the other.
    violations = viral_framing.framing_grounding_violations(
        hook="Watch the microphone.", payoff="", title="",
        transcript="the microscope reveals tiny cells today",
        scene="", record=None,
    )
    assert any(
        v.kind == "framing_ungrounded" and v.field == "hook"
        for v in violations
    )


def test_grounding_object_grounded_by_its_own_plural():
    # The strict route still accepts the object's own inflections:
    # evidence naming "trophies" vouches for a claimed "trophy".
    assert viral_framing.framing_grounding_violations(
        hook="", payoff="And the trophy comes out.", title="",
        transcript="the trophies come out at the ceremony",
        scene="", record=None,
    ) == []


def test_grounding_plural_object_claim_is_still_an_object():
    # "folders" names the listed object "folder": the single-object
    # rule is about the object, not the spelling. Every other word
    # of the line is grounded in the park evidence, so only the
    # object can flag it.
    violations = _grounding(payoff="He switches sides with the folders.")
    assert any(
        v.kind == "framing_ungrounded" and v.field == "payoff"
        for v in violations
    )


def test_title_action_rule_covers_shatter_after_c2():
    # Review C2 probe (PR #1053): "shatters" was off the closed verb
    # list, so this title promised job 803 an action the footage
    # never shows and passed both title rules.
    record = {
        "event_arc": "hands open a journal and turn its pages",
        "beats": [{
            "setting": "desk", "time_of_day": "day",
            "summary": "Hands hold a paperback journal and flip "
                       "through its printed pages.",
            "objects": ["journal", "pages"],
            "subjects": [{
                "hair": "", "clothing": "", "posture": "",
                "action": "holding and opening a journal", "emotion": "",
            }],
        }],
    }
    transcript = (
        "it is called wreck this journal it gives you a new way to "
        "ruin it every day you crack the spine you spill your drink "
        "and strips of paper"
    )
    violations = viral_framing.framing_grounding_violations(
        hook="", payoff="", title="He Shatters the Journal Strip #Shorts",
        transcript=transcript, scene="", record=record,
    )
    assert any(v.kind == "title_action_ungrounded" for v in violations)
    # And a shatter the record DOES show passes the rule.
    shown = {
        "event_arc": "hands shatter a glass pane on the desk",
        "beats": [{
            "setting": "desk", "time_of_day": "day",
            "summary": "Hands shatter a glass pane into pieces.",
            "objects": ["glass", "pane"],
            "subjects": [{
                "hair": "", "clothing": "", "posture": "",
                "action": "shattering a glass pane", "emotion": "",
            }],
        }],
    }
    assert viral_framing.framing_grounding_violations(
        hook="", payoff="", title="He Shatters the Glass #Shorts",
        transcript="", scene="", record=shown,
    ) == []


def test_payoff_engagement_bait_is_a_violation():
    violations = viral_framing.framing_violations(
        hook="Watch the keeper dive at it",
        payoff="The save lands clean. If you leave a like.",
        title="Keeper Save #Shorts",
        description="A keeper save.",
        record=None,
        excerpt_seconds=20.0,
    )
    assert any(v.kind == "payoff_engagement_bait" for v in violations)


def test_grounding_fallback_only_for_ungrounded_lines():
    from app.services.viral_quality import Violation

    assert viral_framing.grounding_fallback_fields([
        Violation("framing_ungrounded", "hook", "x"),
        Violation("framing_ungrounded", "payoff", "y"),
    ]) == {"hook", "payoff"}
    # A title problem or any other gate's violation blocks substitution.
    assert viral_framing.grounding_fallback_fields([
        Violation("framing_ungrounded", "payoff", "y"),
        Violation("title_action_ungrounded", "title", "z"),
    ]) is None
    assert viral_framing.grounding_fallback_fields([
        Violation("unseen_colour", "commentary", "z"),
    ]) is None
    assert viral_framing.grounding_fallback_fields([]) is None


def test_generic_fallback_lines_are_claim_free():
    # The substitutes must pass the grounding gate against any
    # evidence — they promise nothing about the footage.
    assert viral_framing.framing_grounding_violations(
        hook=viral_framing._GENERIC_HOOK,
        payoff=viral_framing._GENERIC_PAYOFF,
        title="",
        transcript=_PARK_TRANSCRIPT,
        scene=_PARK_SCENE,
        record=_PARK_RECORD,
    ) == []


def test_framing_violations_full_package_still_passes():
    # The whole gate suite (consistency + grounding + structure) on a
    # package built from the evidence: no violations.
    assert viral_framing.framing_violations(
        hook="Watch the man keep his wife on the safe side.",
        payoff="He switches sides so she walks beside him.",
        title="His Safe Side Rule on a Park Walk #Shorts",
        description="A couple in a park.",
        record=_PARK_RECORD,
        excerpt_seconds=20.0,
        transcript=_PARK_TRANSCRIPT,
        scene=_PARK_SCENE,
    ) == []


# --- (4a) tail trim --------------------------------------------------- #
def test_detect_tail_still_finds_the_insert_after_a_cut():
    # Motion, then a hard cut, then a frozen picture to the end.
    changes = [0.03, 0.04, 0.12, 0.001, 0.001, 0.001, 0.002]
    assert viral_framing.detect_tail_still(changes, interval_seconds=0.667) == 2.001


def test_detect_tail_still_leaves_a_quiet_ending_alone():
    # No cut at all: the main scene simply settles — not an insert.
    assert viral_framing.detect_tail_still([0.001] * 6, interval_seconds=0.667) is None
    # A cut followed by real motion again is a scene change, not a still.
    assert viral_framing.detect_tail_still(
        [0.03, 0.12, 0.001, 0.001, 0.05, 0.04], interval_seconds=0.667
    ) is None
    # A still too brief to be the ending is left alone.
    assert viral_framing.detect_tail_still(
        [0.03, 0.12, 0.001], interval_seconds=0.667
    ) is None


def _make_video(path: Path, segments: list[tuple[str, float]]):
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y"]
    for kind, seconds in segments:
        if kind == "motion":
            cmd += ["-f", "lavfi", "-i",
                    f"testsrc2=duration={seconds}:size=320x568:rate=10"]
        else:
            cmd += ["-f", "lavfi", "-i",
                    f"color=c=red:duration={seconds}:size=320x568:rate=10"]
    streams = "".join(f"[{i}:v]" for i in range(len(segments)))
    cmd += [
        "-filter_complex", f"{streams}concat=n={len(segments)}:v=1:a=0",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        str(path),
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=120)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not available")
def test_measure_tail_trim_on_a_generated_still_insert(tmp_path):
    video = tmp_path / "insert.mp4"
    _make_video(video, [("motion", 10.0), ("still", 4.0)])
    new_seconds, reason = viral_framing.measure_tail_trim(video, 14.0)
    assert reason == "trimmed"
    assert new_seconds is not None and 9.0 <= new_seconds <= 10.6


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not available")
def test_measure_tail_trim_on_a_plain_moving_clip(tmp_path):
    video = tmp_path / "plain.mp4"
    _make_video(video, [("motion", 12.0)])
    new_seconds, reason = viral_framing.measure_tail_trim(video, 12.0)
    assert new_seconds is None and reason == "no_still_tail"


# --------------------------------------------------------------------------- #
# TASK-VYR-023: the excerpt cut gets the same render-fit treatment.
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
# TASK-VYR-023: the framed path gains the commentary path's
# description-question repair. Cycle-2 diagnosis: script_unverifiable
# was the largest skip class (5/12); the only violation kind the
# cycle record documents more than once is question_ungrounded, and
# the framed path — running the identical description check on the
# identical mandated question format — had no deterministic escape
# from it, while the commentary path has repaired exactly that class
# since TASK-VYR-014 (the TASK-VYR-022 grounding fallback covers
# ungrounded hook/payoff lines, not the description's question).
# The repair must fire ONLY for question-kind violations and the
# repaired package must re-pass every gate.
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


# --- TASK-VYR-024: cycle-5 watch fixes -------------------------------- #
# (1) The 823/824 title<->footage pairing: production's own records
# (publish_jobs, render_jobs, assets, sources, video_projects, the
# loop manifest, the physical files' names and probed durations) all
# agree — the pairing crossed outside the pipeline. The pins below
# prove the title grounding gate rejects each job's title against the
# OTHER job's evidence and accepts it against its own, using the two
# jobs' real transcripts and production descriptions as the evidence:
# a title that had actually crossed inside production could not have
# survived the gate. The render-binding tests pin the new in-pipeline
# assertion that keeps the job<->render binding provable by key.
# (2)+(3) The visible-text defects: the vision record now reports a
# creator watermark and burned-in caption pile-ups, and both
# production paths reject such candidates before any render.
from app.services import scene_analysis


def _record_payload(**overrides):
    payload = {
        "beats": [{
            "setting": "roadside", "time_of_day": "day",
            "subjects": [], "objects": ["motorcycle"],
            "summary": "A rider sits beside a stopped motorcycle.",
        }],
        "event_arc": "an officer speaks with the rider",
        "static": False,
    }
    payload.update(overrides)
    return payload


def test_record_carries_watermark_text_and_caption_overlap():
    record = scene_analysis._coerce_record(_record_payload(
        watermark_text="@WARPATROL", caption_overlap=True,
    ))
    assert record is not None
    assert record["watermark_text"] == "@WARPATROL"
    assert record["caption_overlap"] is True


def test_record_defaults_clean_when_vision_omits_text_fields():
    record = scene_analysis._coerce_record(_record_payload())
    assert record is not None
    assert record["watermark_text"] == ""
    assert record["caption_overlap"] is False


def test_visual_defects_flag_watermark_and_caption_overlap():
    assert scene_analysis.record_visual_defects(
        {"watermark_text": "@WARPATROL", "caption_overlap": False}
    ) == ["watermark_visible"]
    assert scene_analysis.record_visual_defects(
        {"watermark_text": "", "caption_overlap": True}
    ) == ["caption_overlap"]
    assert scene_analysis.record_visual_defects(
        {"watermark_text": "@WARPATROL", "caption_overlap": True}
    ) == ["watermark_visible", "caption_overlap"]
    assert scene_analysis.record_visual_defects(
        {"watermark_text": "", "caption_overlap": False}
    ) == []
    assert scene_analysis.record_visual_defects(None) == []


def test_render_binding_accepts_the_matching_render():
    # Job 823's real binding: the PLGSvGqLyc4 render, probed at exactly
    # the excerpt length production cut for it.
    assert viral_framing.render_binding_violations(
        video_id="PLGSvGqLyc4",
        render_name="framed-PLGSvGqLyc4-b983b8.mp4",
        render_duration=43.93,
        excerpt_seconds=43.93,
    ) == []


def test_render_binding_rejects_the_other_jobs_render():
    # The crossed pairing the watch was shown: job 823's excerpt
    # (43.93s) against job 824's render file (PMMg1GbeJHA, 23.03s).
    problems = viral_framing.render_binding_violations(
        video_id="PLGSvGqLyc4",
        render_name="framed-PMMg1GbeJHA-52e6fe.mp4",
        render_duration=23.03,
        excerpt_seconds=43.93,
    )
    assert len(problems) == 2


def test_render_binding_rejects_a_duration_mismatch_and_a_missing_probe():
    assert viral_framing.render_binding_violations(
        video_id="PLGSvGqLyc4",
        render_name="framed-PLGSvGqLyc4-b983b8.mp4",
        render_duration=23.03,
        excerpt_seconds=43.93,
    )
    assert viral_framing.render_binding_violations(
        video_id="PLGSvGqLyc4",
        render_name="framed-PLGSvGqLyc4-b983b8.mp4",
        render_duration=0.0,
        excerpt_seconds=43.93,
    )


# The two jobs' real evidence. Transcripts are the sources' own words
# (from the renders' subtitle tracks, source cues only); the scene
# lines are the jobs' production descriptions, which the pipeline
# generated from each job's own vision record.
_C5_NEWS_TITLE = "Crazy India News Bombardment Clip 😱🚀 #Shorts"
_C5_NEWS_TRANSCRIPT = (
    "One thing I find so funny is the contrast between literally every "
    "other country's news channels and then whatever the hell they got "
    "going on in India. For example let's just take a quick look at BBC "
    "News. Everything looks pretty normal right? Then over on CNN same "
    "kind of vibe. Everything's pretty chill down. Here's Al Jazeera "
    "also very similar very chill very basic. But then let's go over to "
    "India. They got fighter jets flying across the screen. Another "
    "AI-generated video of some sort of like missile dropping down. "
    "Here's another one of a fighter jet dropping a bunch of bombs. "
    "Then they got this graphic of Trump and Netanyahu on the front "
    "page. Explosions everywhere. I mean genuinely guys this looks more "
    "like a meme page and it does like legitimate state news. It's "
    "mind blowing."
)
_C5_NEWS_SCENE = (
    "The clip shows a young man speaking while a female anchor overlays "
    "intense war visuals. Fighter jets, explosions and a breaking "
    "banner dominate the broadcast."
)
_C5_POLICE_TITLE = "Police Car Stops Biker, Boots on Dirt 😱 #Shorts"
_C5_POLICE_TRANSCRIPT = (
    "I'm gonna get you. It's a public place sir. Sir why is it a "
    "public place? I'm gonna get you."
)
_C5_POLICE_SCENE = (
    "A police car pulls up next to a stopped motorcycle and the rider "
    "sits on the dirt, showing his boots. The officer repeats his "
    "warning as the scene unfolds."
)


def _title_violations(title, transcript, scene):
    return [
        violation
        for violation in viral_framing.framing_grounding_violations(
            hook="", payoff="", title=title,
            transcript=transcript, scene=scene, record=None,
        )
        if violation.field == "title"
    ]


def test_cycle5_titles_ground_against_their_own_footage():
    assert _title_violations(_C5_NEWS_TITLE, _C5_NEWS_TRANSCRIPT, _C5_NEWS_SCENE) == []
    assert _title_violations(_C5_POLICE_TITLE, _C5_POLICE_TRANSCRIPT, _C5_POLICE_SCENE) == []


def test_cycle5_swapped_titles_are_rejected_by_the_grounding_gate():
    news_on_police = _title_violations(
        _C5_NEWS_TITLE, _C5_POLICE_TRANSCRIPT, _C5_POLICE_SCENE
    )
    police_on_news = _title_violations(
        _C5_POLICE_TITLE, _C5_NEWS_TRANSCRIPT, _C5_NEWS_SCENE
    )
    assert any(v.kind == "title_ungrounded" for v in news_on_police)
    assert any(v.kind == "title_ungrounded" for v in police_on_news)


# --- TASK-VYR-025: the source-captioned gate --------------------------- #
# Cycle 6, job 841: the mascot-race source already carried a complete
# word-by-word burned-in caption track, and the render added VyralX's
# own caption track carrying the same narration out of sync — two
# tracks doubling for the whole video (the pattern the owner rejected
# in cycle-5 job 823). VYR-024's caption_overlap could not see it: the
# source's captions never overlapped EACH OTHER. The record now
# reports per-beat caption presence; a strict majority of beats means
# the source is already captioned and the candidate is skipped with
# reason source_captioned before any render work.


def _captioned_payload(flags):
    return {
        "beats": [{
            "setting": "running track", "time_of_day": "day",
            "subjects": [], "objects": ["mascot costume"],
            "summary": "A mascot races a runner down the track.",
            "captions_present": flag,
        } for flag in flags],
        "event_arc": "the race is run",
        "static": False,
    }


def test_caption_track_majority_rule():
    assert scene_analysis.source_caption_track(3, 3) is True
    assert scene_analysis.source_caption_track(2, 3) is True
    assert scene_analysis.source_caption_track(1, 3) is False
    assert scene_analysis.source_caption_track(0, 3) is False
    assert scene_analysis.source_caption_track(1, 2) is False
    assert scene_analysis.source_caption_track(2, 2) is True
    assert scene_analysis.source_caption_track(0, 0) is False


def test_record_flags_a_full_caption_track():
    record = scene_analysis._coerce_record(_captioned_payload([True, True, True]))
    assert record is not None
    assert record["caption_beats"] == 3
    assert record["source_caption_track"] is True


def test_record_flags_a_majority_caption_track():
    record = scene_analysis._coerce_record(_captioned_payload([True, False, True]))
    assert record is not None
    assert record["caption_beats"] == 2
    assert record["source_caption_track"] is True


def test_record_ignores_a_single_captioned_beat():
    # One beat with a title card or a single captioned moment is not a
    # track — the skip is final for the cycle, so it must not fire.
    record = scene_analysis._coerce_record(_captioned_payload([True, False, False]))
    assert record is not None
    assert record["caption_beats"] == 1
    assert record["source_caption_track"] is False


def test_record_defaults_clean_when_vision_omits_caption_flags():
    record = scene_analysis._coerce_record(_record_payload())
    assert record is not None
    assert record["caption_beats"] == 0
    assert record["source_caption_track"] is False


def test_visual_defects_flag_source_captioned():
    assert scene_analysis.record_visual_defects(
        {"watermark_text": "", "caption_overlap": False,
         "source_caption_track": True}
    ) == ["source_captioned"]
    assert scene_analysis.record_visual_defects(
        {"watermark_text": "", "caption_overlap": False,
         "source_caption_track": False}
    ) == []
    # Stable order alongside the VYR-024 kinds: the paths skip with the
    # first defect, so a watermarked AND captioned source still reports
    # watermark_visible as its reason, with source_captioned recorded.
    assert scene_analysis.record_visual_defects(
        {"watermark_text": "@WARPATROL", "caption_overlap": True,
         "source_caption_track": True}
    ) == ["watermark_visible", "caption_overlap", "source_captioned"]


def test_framed_path_skips_a_captioned_source_before_editorial(monkeypatch, tmp_path):
    from types import SimpleNamespace

    from app.services import viral_quality as vq
    from app.services import viral_remix as vr

    monkeypatch.setattr(viral_framing, "get_settings", lambda: SimpleNamespace(
        prepare_directories=lambda: None,
        render_dir=tmp_path / "renders",
        media_dir=tmp_path / "media",
        ffmpeg_bin="ffmpeg",
        viral_quality_gates_enabled=True,
        viral_max_source_seconds=58.0,
    ))
    monkeypatch.setattr(vr, "download_audio_only",
                        lambda video_id, dest: tmp_path / "probe.webm")
    monkeypatch.setattr(vr, "detect_speech", lambda path: SimpleNamespace(
        has_speech=True,
        cues=[{"start": 0.0, "end": 1.0, "text": "go"}],
        text="go go go",
    ))
    monkeypatch.setattr(vr, "download_source_video",
                        lambda video_id, dest: tmp_path / "source.mp4")
    monkeypatch.setattr(vr, "probe_media", lambda path: SimpleNamespace(
        duration=30.0, width=1080, height=1920, has_audio=True))
    monkeypatch.setattr(viral_framing, "_cut_excerpt",
                        lambda *a, **k: tmp_path / "excerpt.mp4")
    monkeypatch.setattr(viral_framing, "measure_tail_trim",
                        lambda *a, **k: (None, ""))
    monkeypatch.setattr(vq, "measure_event_arc", lambda *a, **k: None)
    record = scene_analysis._coerce_record(_captioned_payload([True, True, False]))
    monkeypatch.setattr(viral_framing, "analyze_scene", lambda *a, **k: record)
    editorial_calls = []
    monkeypatch.setattr(viral_framing, "generate_framing",
                        lambda *a, **k: editorial_calls.append(1) or {})

    candidate = SimpleNamespace(
        video_id="Pfxp6mysc90", title="Can You Beat The Fastest Mascot?",
        channel="BoltMotivation", duration=30.0, category="SPORTS",
    )
    result = viral_framing.produce_framed_short(candidate, None, publish=False)
    assert result["status"] == "SKIPPED"
    assert result["reason"] == "source_captioned"
    assert result["visual_defects"] == ["source_captioned"]
    assert editorial_calls == []  # rejected before any editorial/render work


# --- TASK-VYR-026: vision rate-limit hardening ------------------------ #
# Cycles 6/7 lost 14/24 and 22/24 attempts to vision_unavailable: the
# single Groq scene call hit HTTP 429 (free-tier token limits), the
# code made one attempt, discarded the 429 body/headers, and returned
# None. The pins below cover the client half of the fix: failures are
# logged WITH the rate-limit headers and body (fix 0), only 429 is
# retried — Retry-After honoured, 30/60/120s fallback ladder, bounded
# total wait (fix 1) — the pacing clock keeps calls apart (fix 2's
# client half), and the token estimator the loop budgets with is
# deterministic. All clocks/sleeps are faked: no test here sleeps.
import httpx
from types import SimpleNamespace

from app.services import scene_analysis as _sa026


class _FakeClock:
    """Deterministic stand-in for the time module in scene_analysis."""

    def __init__(self):
        self.now = 1000.0
        self.epoch = 1_763_000_000.0
        self.sleeps: list[float] = []

    def monotonic(self):
        return self.now

    def time(self):
        return self.epoch

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds
        self.epoch += seconds


class _VisionResponse:
    def __init__(self, status_code=200, payload=None, headers=None, text=""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.headers = headers or {}
        self.text = text

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"Client error '{self.status_code}'", request=None, response=self
            )


_RECORD_JSON = json.dumps({
    "beats": [{
        "setting": "roadside", "time_of_day": "day", "subjects": [],
        "objects": ["motorcycle"],
        "summary": "A rider sits beside a stopped motorcycle.",
    }],
    "event_arc": "an officer speaks with the rider",
    "static": False,
})


def _ok_payload():
    return {"choices": [{"message": {"content": _RECORD_JSON}}]}


@pytest.fixture()
def vision_env(tmp_path, monkeypatch):
    clock = _FakeClock()
    monkeypatch.setattr(_sa026, "time", clock, raising=False)
    monkeypatch.setattr(_sa026, "_VISION_OUTCOME", {
        "seq": 0, "status": None, "rate_limit_exhausted": False,
        "attempts": 0, "estimated_tokens": 0, "called_at": None,
    }, raising=False)
    monkeypatch.setattr(_sa026, "_LAST_VISION_REQUEST_MONO", None, raising=False)
    settings = SimpleNamespace(
        vision_api_key="test-key",
        vision_base_url="https://api.groq.com/openai/v1",
        vision_model="qwen/qwen3.8-27b",
        vision_timeout_seconds=90,
        vision_max_retries=3,
        vision_retry_wait_cap_seconds=240,
        ffmpeg_bin="ffmpeg",
    )
    monkeypatch.setattr(_sa026, "get_settings", lambda: settings)

    def fake_extract(source, seconds, destination):
        destination.write_bytes(b"\xff\xd8\xff" + b"0" * 2048)
        return True

    monkeypatch.setattr(_sa026, "_extract_frame", fake_extract)
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"fake video bytes")
    return SimpleNamespace(clock=clock, settings=settings, source=source)


def _post_script(monkeypatch, responses):
    calls = []

    def fake_post(url, **kwargs):
        calls.append(url)
        index = min(len(calls) - 1, len(responses) - 1)
        return responses[index]

    monkeypatch.setattr(_sa026.httpx, "post", fake_post)
    return calls


def test_vision_retry_recovers_after_429(vision_env, monkeypatch):
    calls = _post_script(monkeypatch, [
        _VisionResponse(429, headers={"retry-after": "30"}),
        _VisionResponse(200, payload=_ok_payload()),
    ])
    record = _sa026.analyze_scene(vision_env.source, 30.0)
    assert record is not None
    assert record["beats"][0]["summary"].startswith("A rider sits")
    assert len(calls) == 2
    outcome = _sa026.last_vision_outcome()
    assert outcome["status"] == 200
    assert outcome["attempts"] == 2
    assert outcome["rate_limit_exhausted"] is False


def test_vision_retry_honours_retry_after_header(vision_env, monkeypatch):
    _post_script(monkeypatch, [
        _VisionResponse(429, headers={"retry-after": "45"}),
        _VisionResponse(200, payload=_ok_payload()),
    ])
    record = _sa026.analyze_scene(vision_env.source, 30.0)
    assert record is not None
    assert vision_env.clock.sleeps == [45.0]


def test_vision_retry_fallback_ladder_without_retry_after(vision_env, monkeypatch):
    _post_script(monkeypatch, [
        _VisionResponse(429),
        _VisionResponse(429),
        _VisionResponse(200, payload=_ok_payload()),
    ])
    record = _sa026.analyze_scene(vision_env.source, 30.0)
    assert record is not None
    assert vision_env.clock.sleeps == [30.0, 60.0]


def test_vision_retries_exhausted_returns_none_and_marks_outcome(vision_env, monkeypatch):
    calls = _post_script(monkeypatch, [_VisionResponse(429)])
    record = _sa026.analyze_scene(vision_env.source, 30.0)
    assert record is None
    assert len(calls) == 4  # first attempt + 3 retries, then it stops
    assert vision_env.clock.sleeps == [30.0, 60.0, 120.0]
    outcome = _sa026.last_vision_outcome()
    assert outcome["status"] == 429
    assert outcome["attempts"] == 4
    assert outcome["rate_limit_exhausted"] is True


def test_vision_non_429_error_does_not_retry(vision_env, monkeypatch):
    calls = _post_script(monkeypatch, [_VisionResponse(500, text="server error")])
    record = _sa026.analyze_scene(vision_env.source, 30.0)
    assert record is None
    assert len(calls) == 1
    assert vision_env.clock.sleeps == []
    outcome = _sa026.last_vision_outcome()
    assert outcome["status"] == 500
    assert outcome["rate_limit_exhausted"] is False


def test_vision_wait_cap_stops_retrying(vision_env, monkeypatch):
    # Retry-After of 300s exceeds the 240s per-call cap: no sleep, no
    # retry — the call gives up exhausted instead of stalling.
    calls = _post_script(monkeypatch, [
        _VisionResponse(429, headers={"retry-after": "300"}),
    ])
    record = _sa026.analyze_scene(vision_env.source, 30.0)
    assert record is None
    assert len(calls) == 1
    assert vision_env.clock.sleeps == []
    assert _sa026.last_vision_outcome()["rate_limit_exhausted"] is True


def test_vision_failure_logs_rate_limit_headers_and_body(vision_env, monkeypatch, caplog):
    vision_env.settings.vision_max_retries = 0
    _post_script(monkeypatch, [_VisionResponse(
        429,
        headers={
            "x-ratelimit-limit-tokens": "8000",
            "x-ratelimit-remaining-tokens": "0",
            "x-ratelimit-reset-tokens": "12s",
            "retry-after": "12",
        },
        text='{"error":{"message":"Rate limit reached"}}',
    )])
    with caplog.at_level("WARNING", logger="vyralx.scene_analysis"):
        record = _sa026.analyze_scene(vision_env.source, 30.0)
    assert record is None
    assert "HTTP 429" in caplog.text
    assert "x-ratelimit-limit-tokens" in caplog.text
    assert "'8000'" in caplog.text
    assert "Rate limit reached" in caplog.text


def test_describe_scene_also_retries_429(vision_env, monkeypatch):
    payload = {"choices": [{"message": {
        "content": "1) a rider waits\n2) an officer arrives\n3) they talk",
    }}]}
    _post_script(monkeypatch, [
        _VisionResponse(429, headers={"retry-after": "10"}),
        _VisionResponse(200, payload=payload),
    ])
    text = _sa026.describe_scene(vision_env.source, 30.0)
    assert "a rider waits" in text
    assert vision_env.clock.sleeps == [10.0]


def test_vision_pacing_waits_for_min_interval(vision_env, monkeypatch):
    _post_script(monkeypatch, [_VisionResponse(200, payload=_ok_payload())])
    record = _sa026.analyze_scene(vision_env.source, 30.0)
    assert record is not None
    # The call landed at fake-monotonic 1000; 30s later a 65s interval
    # still owes 35s.
    vision_env.clock.now += 30.0
    waited = _sa026.wait_for_vision_pacing(65.0)
    assert waited == 35.0
    assert vision_env.clock.sleeps[-1] == 35.0
    # Long after the interval, no wait.
    vision_env.clock.now += 600.0
    assert _sa026.wait_for_vision_pacing(65.0) == 0.0


def test_vision_pacing_seed_from_persisted_epoch(vision_env):
    # A previous process's call 20s ago (by the wall clock) still
    # paces this process: seeding converts the epoch onto the
    # monotonic clock.
    _sa026.seed_vision_clock(vision_env.clock.epoch - 20.0)
    waited = _sa026.wait_for_vision_pacing(65.0)
    assert waited == 45.0


def test_estimate_vision_tokens_is_deterministic():
    body = {
        "model": "qwen/qwen3.8-27b",
        "max_tokens": 1100,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": "x" * 300},
            {"type": "image_url", "image_url": {"url": "data:..."}},
            {"type": "image_url", "image_url": {"url": "data:..."}},
            {"type": "image_url", "image_url": {"url": "data:..."}},
        ]}],
    }
    # 300 chars / 3 = 100 text + 3 x 1000 images + 1100 max_tokens.
    assert _sa026.estimate_vision_tokens(body) == 4200


# === BEGIN VYR-028 SHIPPED BLOCK ===

# --- TASK-VYR-028: Gemini vision fail-over (fix 4) -------------------- #
# Cycle 8 stopped vision_rate_limited: Groq's 200k/day TPD was ~99%
# used before the cycle's last candidates, and the OTPM sizing fault
# (max_tokens 1100 vs the 1000 limit) 429s deterministically. The
# fail-over below covers the client half: after the VYR-026 retries
# are spent on HTTP 429 — and only on 429 — _vision_request makes
# exactly one attempt against the VISION_FAILOVER_* endpoint (Gemini's
# OpenAI-compatible endpoint + a flash-lite-class model, both from
# env) with the same body except the model, and the reply is parsed
# and validated exactly like a Groq one. All clocks/sleeps are faked:
# no test here sleeps. Placeholder keys only — never a real key.
_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"


def _failover_post_script(monkeypatch, responses):
    """Fake httpx.post serving responses in order; records (url, body, headers)."""
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs.get("json") or {}, kwargs.get("headers") or {}))
        index = min(len(calls) - 1, len(responses) - 1)
        return responses[index]

    monkeypatch.setattr(_sa026.httpx, "post", fake_post)
    return calls


def _enable_failover(vision_env, model=None):
    vision_env.settings.vision_failover_base_url = _GEMINI_BASE_URL
    vision_env.settings.vision_failover_api_key = "failover-fake-key"
    if model is not None:
        vision_env.settings.vision_failover_model = model


def test_vision_failover_after_groq_429_exhaustion(vision_env, monkeypatch):
    _enable_failover(vision_env)
    calls = _failover_post_script(monkeypatch, [
        _VisionResponse(429),
        _VisionResponse(429),
        _VisionResponse(429),
        _VisionResponse(429),
        _VisionResponse(200, payload=_ok_payload()),
    ])
    record = _sa026.analyze_scene(vision_env.source, 30.0)
    assert record is not None
    assert len(calls) == 5  # 1 + 3 Groq retries, then exactly one Gemini attempt
    groq_calls = [c for c in calls if c[0].startswith("https://api.groq.com")]
    gemini_calls = [c for c in calls if c[0].startswith(_GEMINI_BASE_URL)]
    assert len(groq_calls) == 4
    assert len(gemini_calls) == 1
    assert gemini_calls[0][1]["model"] == "gemini-3.5-flash-lite"  # model default
    assert gemini_calls[0][1]["max_tokens"] == 1100  # same body as Groq
    assert gemini_calls[0][2]["Authorization"] == "Bearer " + vision_env.settings.vision_failover_api_key
    assert groq_calls[0][2]["Authorization"] == "Bearer " + vision_env.settings.vision_api_key
    assert gemini_calls[0][2]["Authorization"] != groq_calls[0][2]["Authorization"]  # per-endpoint keys
    assert vision_env.clock.sleeps == [30.0, 60.0, 120.0]  # VYR-026 ladder kept
    outcome = _sa026.last_vision_outcome()
    assert outcome["status"] == 200
    assert outcome["attempts"] == 5  # 4 primary + 1 fail-over
    assert outcome["rate_limit_exhausted"] is False
    # A Gemini success produces a record identical in shape to a Groq
    # success (same coercion, same gates downstream).
    calls2 = _failover_post_script(monkeypatch, [
        _VisionResponse(200, payload=_ok_payload()),
    ])
    record_groq = _sa026.analyze_scene(vision_env.source, 30.0)
    assert record == record_groq
    assert len(calls2) == 1


def test_vision_failover_gemini_failure_returns_none(vision_env, monkeypatch):
    _enable_failover(vision_env)
    calls = _failover_post_script(monkeypatch, [
        _VisionResponse(429),
        _VisionResponse(429),
        _VisionResponse(429),
        _VisionResponse(429),
        _VisionResponse(429, text='{"error":{"message":"quota exceeded"}}'),
    ])
    record = _sa026.analyze_scene(vision_env.source, 30.0)
    assert record is None  # vision_unavailable, exactly as without fail-over
    assert len(calls) == 5
    gemini_calls = [c for c in calls if c[0].startswith(_GEMINI_BASE_URL)]
    assert len(gemini_calls) == 1  # tried once, never retried
    outcome = _sa026.last_vision_outcome()
    assert outcome["status"] == 429
    assert outcome["attempts"] == 5
    assert outcome["rate_limit_exhausted"] is True


def test_vision_no_failover_when_groq_succeeds(vision_env, monkeypatch):
    _enable_failover(vision_env)
    calls = _failover_post_script(monkeypatch, [
        _VisionResponse(200, payload=_ok_payload()),
    ])
    record = _sa026.analyze_scene(vision_env.source, 30.0)
    assert record is not None
    assert len(calls) == 1
    assert calls[0][0].startswith("https://api.groq.com")
    assert calls[0][1]["model"] == "qwen/qwen3.8-27b"


def test_vision_failover_non_429_does_not_failover(vision_env, monkeypatch):
    _enable_failover(vision_env)
    calls = _failover_post_script(monkeypatch, [
        _VisionResponse(500, text="server error"),
    ])
    record = _sa026.analyze_scene(vision_env.source, 30.0)
    assert record is None
    assert len(calls) == 1  # 429-only: a 500 never reaches the fail-over
    assert vision_env.clock.sleeps == []


def test_vision_failover_disabled_when_unconfigured(vision_env, monkeypatch):
    # The plain fixture carries no fail-over attributes at all: the
    # VYR-026 behaviour (and its tests) must be untouched by default.
    calls = _failover_post_script(monkeypatch, [_VisionResponse(429)])
    record = _sa026.analyze_scene(vision_env.source, 30.0)
    assert record is None
    assert len(calls) == 4  # 1 + 3 retries, then it stops — no Gemini call
    assert all(not url.startswith(_GEMINI_BASE_URL) for url, _, _ in calls)
    assert _sa026.last_vision_outcome()["rate_limit_exhausted"] is True


def test_vision_failover_needs_both_url_and_key(vision_env, monkeypatch):
    vision_env.settings.vision_failover_base_url = _GEMINI_BASE_URL
    vision_env.settings.vision_failover_api_key = ""  # URL without a key
    calls = _failover_post_script(monkeypatch, [_VisionResponse(429)])
    record = _sa026.analyze_scene(vision_env.source, 30.0)
    assert record is None
    assert len(calls) == 4
    assert all(not url.startswith(_GEMINI_BASE_URL) for url, _, _ in calls)


def test_vision_failover_after_wait_cap_give_up(vision_env, monkeypatch):
    # Retry-After 300s exceeds the 240s cap: the primary gives up
    # without sleeping — and the fail-over is still attempted.
    _enable_failover(vision_env, model="gemini-3.5-flash-lite")
    calls = _failover_post_script(monkeypatch, [
        _VisionResponse(429, headers={"retry-after": "300"}),
        _VisionResponse(200, payload=_ok_payload()),
    ])
    record = _sa026.analyze_scene(vision_env.source, 30.0)
    assert record is not None
    assert record["beats"][0]["summary"].startswith("A rider sits")
    assert len(calls) == 2
    assert calls[1][0].startswith(_GEMINI_BASE_URL)
    assert calls[1][1]["model"] == "gemini-3.5-flash-lite"  # env model honoured
    assert vision_env.clock.sleeps == []


def test_vision_failover_does_not_log_keys(vision_env, monkeypatch, caplog):
    _enable_failover(vision_env)
    vision_env.settings.vision_max_retries = 0  # 1 Groq 429, then Gemini 429
    calls = _failover_post_script(monkeypatch, [
        _VisionResponse(429, text='{"error":{"message":"Rate limit reached"}}'),
        _VisionResponse(429, text='{"error":{"message":"quota exceeded"}}'),
    ])
    with caplog.at_level("INFO", logger="vyralx.scene_analysis"):
        record = _sa026.analyze_scene(vision_env.source, 30.0)
    assert record is None
    assert len(calls) == 2
    assert "fail-over" in caplog.text  # the attempt itself is logged
    assert _GEMINI_BASE_URL in caplog.text  # the endpoint is named
    assert vision_env.settings.vision_api_key not in caplog.text
    assert "failover-fake-key" not in caplog.text


def test_describe_scene_also_fails_over(vision_env, monkeypatch):
    _enable_failover(vision_env)
    payload = {"choices": [{"message": {
        "content": "1) a rider waits\n2) an officer arrives\n3) they talk",
    }}]}
    calls = _failover_post_script(monkeypatch, [
        _VisionResponse(429, headers={"retry-after": "10"}),
        _VisionResponse(429),
        _VisionResponse(429),
        _VisionResponse(429),
        _VisionResponse(200, payload=payload),
    ])
    text = _sa026.describe_scene(vision_env.source, 30.0)
    assert "a rider waits" in text
    assert len(calls) == 5  # 4 Groq attempts, then exactly one Gemini attempt
    assert calls[4][0].startswith(_GEMINI_BASE_URL)
    assert vision_env.clock.sleeps == [10.0, 60.0, 120.0]
