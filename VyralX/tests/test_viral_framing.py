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
