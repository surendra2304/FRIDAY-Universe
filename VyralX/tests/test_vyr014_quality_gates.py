"""TASK-VYR-014: fail-closed quality gates for the viral autopilot.

The fixtures are the six full-watch records of 2026-11-17 (jobs 683, 701,
721, 741, 761, 781 — graded BROKEN/WEAK, zero GOOD) reduced to the vision
records and copy the old pipeline actually shipped. Every defect the owner
watched must trip a named gate; a grounded package must pass all of them.

On clean main every test here fails: app.services.viral_quality does not
exist and produce_viral_short has no gates to skip with.
"""
from __future__ import annotations

import shutil
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services import viral_quality as vq
from app.services import viral_remix as vr
from app.services.scene_analysis import _coerce_record, scene_text


def kinds(violations) -> set[str]:
    return {violation.kind for violation in violations}


# --------------------------------------------------------------------------- #
# vision records mirroring the watched videos
# --------------------------------------------------------------------------- #
RECORD_741 = {
    "beats": [
        {
            "setting": "tiled room with white tiles and a plain wall",
            "time_of_day": "indoor",
            "subjects": [
                {"hair": "dark short", "clothing": "blue shirt", "posture": "lying",
                 "action": "lying on the tiles holding a phone", "emotion": "calm",
                 "eyes": "open"},
                {"hair": "light brown long", "clothing": "black top and pink gloves",
                 "posture": "leaning", "action": "pressing her face toward the wall",
                 "emotion": "unknown", "eyes": "unknown"},
            ],
            "objects": ["phone", "pink mat", "red handprint"],
            "summary": "A man in a blue shirt lies on white tiles holding a phone "
                       "while a woman in pink gloves leans toward the wall beside "
                       "a red handprint.",
        },
        {
            "setting": "same tiled room", "time_of_day": "indoor",
            "subjects": [
                {"hair": "light brown long", "clothing": "black top and pink gloves",
                 "posture": "leaning",
                 "action": "pressing her pink-gloved hand flat against the wall",
                 "emotion": "unknown", "eyes": "unknown"},
            ],
            "objects": ["phone", "red handprint"],
            "summary": "The woman presses her pink-gloved hand flat against the "
                       "wall next to the red handprint while the man stays still.",
        },
        {
            "setting": "same tiled room", "time_of_day": "indoor",
            "subjects": [
                {"hair": "dark short", "clothing": "blue shirt", "posture": "lying",
                 "action": "lying still on the tiles", "emotion": "calm",
                 "eyes": "open"},
            ],
            "objects": ["phone", "red handprint"],
            "summary": "The man lies still on the tiles with the phone beside him "
                       "and the red handprint unchanged on the wall.",
        },
    ],
    "event_arc": "A pink-gloved hand appears flat on the wall beside the handprint.",
    "static": False,
}

RECORD_761 = {
    "beats": [
        {
            "setting": "outdoors in daylight", "time_of_day": "day",
            "subjects": [
                {"hair": "dark", "clothing": "light blue shirt", "posture": "standing",
                 "action": "holding up a phone showing a photo", "emotion": "smiling",
                 "eyes": "open"},
            ],
            "objects": ["phone"],
            "summary": "In daylight a man in a light blue shirt holds up a phone "
                       "showing a photo of a woman eating a cookie.",
        },
        {
            "setting": "outdoors under string lights at night", "time_of_day": "night",
            "subjects": [
                {"hair": "light brown", "clothing": "pink shirt", "posture": "standing",
                 "action": "running past laughing", "emotion": "laughing",
                 "eyes": "open"},
                {"hair": "dark", "clothing": "light blue shirt", "posture": "standing",
                 "action": "standing with both hands near his mouth",
                 "emotion": "smiling", "eyes": "open"},
            ],
            "objects": ["string lights", "phone"],
            "summary": "At night under string lights the woman in a pink shirt "
                       "runs past laughing while the man stands with both hands "
                       "near his mouth.",
        },
        {
            "setting": "outdoors under string lights at night", "time_of_day": "night",
            "subjects": [
                {"hair": "dark", "clothing": "light blue shirt", "posture": "standing",
                 "action": "grinning with both hands over his mouth",
                 "emotion": "smiling", "eyes": "open"},
            ],
            "objects": ["string lights"],
            "summary": "The man stands grinning with both hands over his mouth "
                       "under the string lights.",
        },
    ],
    "event_arc": "The woman runs past laughing and the man reacts with his "
                 "hands over his mouth.",
    "static": False,
}

RECORD_721 = {
    "beats": [
        {
            "setting": "living room with a sofa and plain walls", "time_of_day": "indoor",
            "subjects": [
                {"hair": "dark", "clothing": "patterned robe", "posture": "sitting",
                 "action": "holding a small brown teapot", "emotion": "calm",
                 "eyes": "open"},
                {"hair": "dark long", "clothing": "pink floral robe",
                 "posture": "standing", "action": "standing beside him laughing",
                 "emotion": "laughing", "eyes": "open"},
            ],
            "objects": ["teapot", "kettle", "wall switch"],
            "summary": "A man in a patterned robe sits on the floor holding a "
                       "small brown teapot while a woman in a pink floral robe "
                       "stands beside him laughing.",
        },
        {
            "setting": "living room", "time_of_day": "indoor",
            "subjects": [
                {"hair": "dark", "clothing": "patterned robe", "posture": "sitting",
                 "action": "reaching up toward a wall switch", "emotion": "calm",
                 "eyes": "open"},
            ],
            "objects": ["teapot", "wall switch"],
            "summary": "He reaches up to press the wall switch while she crouches "
                       "beside him still laughing.",
        },
        {
            "setting": "living room", "time_of_day": "indoor",
            "subjects": [
                {"hair": "dark long", "clothing": "pink floral robe",
                 "posture": "crouching", "action": "laughing and reaching toward him",
                 "emotion": "laughing", "eyes": "open"},
            ],
            "objects": ["teapot", "wall switch"],
            "summary": "She laughs and reaches toward him as he holds his arm "
                       "toward the wall switch.",
        },
    ],
    "event_arc": "He reaches for the wall switch and she cracks up laughing.",
    "static": False,
}

RECORD_683 = {
    "beats": [
        {
            "setting": "indoors with a bright screen behind her", "time_of_day": "indoor",
            "subjects": [
                {"hair": "dark long", "clothing": "red top", "posture": "standing",
                 "action": "holding a red-wrapped candy stick near her face",
                 "emotion": "smiling", "eyes": "open"},
            ],
            "objects": ["candy stick", "blender", "glass"],
            "summary": "A woman in a red top holds a red-wrapped candy stick "
                       "near her face.",
        },
        {
            "setting": "kitchen counter indoors", "time_of_day": "indoor",
            "subjects": [
                {"hair": "dark long", "clothing": "red top", "posture": "standing",
                 "action": "pouring pink liquid from a blender into a glass",
                 "emotion": "smiling", "eyes": "open"},
            ],
            "objects": ["blender", "glass"],
            "summary": "She pours thick pink liquid from the blender into a "
                       "clear glass on the counter.",
        },
        {
            "setting": "indoors at a desk", "time_of_day": "indoor",
            "subjects": [
                {"hair": "dark short", "clothing": "dark shirt", "posture": "sitting",
                 "action": "wearing headphones and looking at a brown snack bag",
                 "emotion": "calm", "eyes": "open"},
            ],
            "objects": ["snack bag", "monitor", "headphones"],
            "summary": "A man wearing headphones looks at a brown snack bag "
                       "while a monitor glows behind him.",
        },
    ],
    "event_arc": "She pours the pink drink while he watches the snack bag.",
    "static": False,
}


# --------------------------------------------------------------------------- #
# defect 1 — invented narration (jobs 741, 761)
# --------------------------------------------------------------------------- #
def test_job741_identity_and_eyes_claims_rejected():
    commentary = (
        "A man in a blue shirt lies on the tiles, phone beside him. "
        "A black woman in pink gloves presses her face to the wall. "
        "He stays completely still with his eyes closed the whole time."
    )
    found = kinds(vq.check_consistency(commentary=commentary, record=RECORD_741))
    # The woman is light-skinned with light-brown hair; the record never
    # records race at all, so the identity claim is unverifiable by design.
    assert "unverifiable_identity" in found
    # His eyes are recorded open; the script says closed.
    assert "unverified_eyes" in found
    # The grounded claims in the same script are NOT flagged.
    assert "unseen_colour" not in found
    assert "unverified_garment_colour" not in found


def test_job761_inventions_rejected():
    title = "Nighttime Phone Panic Under String Lights"
    commentary = (
        "A man in a light blue shirt sits outdoors at night clutching his phone. "
        "The pink-haired woman on the screen holds a cookie and stares at him. "
        "He covers his mouth and nose with both hands in total panic."
    )
    found = kinds(vq.check_consistency(
        commentary=commentary, title=title, record=RECORD_761
    ))
    assert "unverified_posture" in found        # he stands; the script sits him
    assert "unverified_hair" in found           # pink SHIRT, brown hair
    assert "unverified_emotion" in found        # panic; both are laughing/smiling
    assert "time_of_day_contradiction" in found  # night claimed over the day beat / title


def test_job761_grounded_package_passes_every_gate():
    commentary = (
        "Watch his face when the phone photo appears in bright daylight. "
        "She laughs and runs right past him under the string lights. "
        "He just stands there grinning with both hands over his mouth."
    )
    title = "He Was Not Ready for That Photo Reveal"
    description = (
        "A daylight phone photo, a run past under the string lights, and one "
        "priceless reaction.\n\nDid you spot the phone?\n\n#Shorts #VyralX"
    )
    assert vq.check_consistency(
        commentary=commentary, title=title, description=description,
        record=RECORD_761,
    ) == []
    assert vq.check_structure(commentary=commentary, record=RECORD_761) == []
    assert vq.check_script_length(commentary=commentary, duration=21.0) == []


# --------------------------------------------------------------------------- #
# defect 3 — no hook, no payoff, repeated action, fake questions (721, 701)
# --------------------------------------------------------------------------- #
def test_job721_repetition_filler_and_title_rejected():
    title = "Teapot Switch Shock Caught on Camera"
    commentary = (
        "He sits on the floor holding a small teapot beside a woman in a pink robe. "
        "Then he reaches up to press a wall switch while she crouches right beside him. "
        "Finally he holds his arm toward the switch while she laughs and reaches for him. "
        "This poor ghost routine is legendary."
    )
    consistency = kinds(vq.check_consistency(title=title, record=RECORD_721))
    assert "unverified_emotion" in consistency  # "Shock": nobody is shocked
    structure = kinds(vq.check_structure(commentary=commentary, record=RECORD_721))
    assert "repeated_action" in structure       # the switch reach, twice
    assert "filler_closer" in structure         # "...is legendary"
    assert "payoff_ungrounded" in structure     # the closer is about nothing filmed


def test_hook_length_boundary_is_calibrated_at_18_words():
    # Exactly 18 grounded words pass; 23 fail. (Recalibrated from 14 after
    # two grounded self-test drafts died on this rule alone.)
    tail = (
        "She laughs and runs right past him under the string lights. "
        "He just stands there grinning with both hands over his mouth."
    )
    hook18 = (
        "Watch the man in the light blue shirt as the phone photo "
        "appears in bright daylight right now"
    )
    assert len(hook18.split()) == 18
    assert "hook_too_long" not in kinds(vq.check_structure(
        commentary=f"{hook18}. {tail}", record=RECORD_761))
    hook23 = (
        "Watch the man in the light blue shirt sitting outside in bright "
        "daylight holding his phone up high for everyone to see clearly"
    )
    assert len(hook23.split()) == 23
    assert "hook_too_long" in kinds(vq.check_structure(
        commentary=f"{hook23}. {tail}", record=RECORD_761))


def test_description_cta_without_question_rejected():
    description = "Two people stand in a room.\n\nDrop your answer below!"
    found = kinds(vq.check_consistency(description=description, record=RECORD_721))
    assert "cta_without_question" in found


def test_description_ungrounded_question_rejected():
    description = "Two people stand in a room.\n\nDid you see the elephant?"
    found = kinds(vq.check_consistency(description=description, record=RECORD_721))
    assert "question_ungrounded" in found


def test_grounded_question_uses_record_objects():
    question = vq.grounded_question(RECORD_721)
    assert question.startswith("Did you spot the ")
    assert question.endswith("?")
    assert vq.grounded_question({"beats": []}) == ""


def test_repair_description_question_swaps_in_the_grounded_question():
    description = (
        "He sits on the floor holding a small teapot beside a woman in a "
        "pink robe.\n\nDid you see the elephant?"
    )
    repaired = vq.repair_description_question(description, RECORD_721)
    assert "elephant" not in repaired
    assert "Did you spot the" in repaired
    # After repair the description passes the question checks...
    found = kinds(vq.check_consistency(description=repaired, record=RECORD_721))
    assert "question_ungrounded" not in found
    # ...and a grounded question already present is left exactly as written.
    good = "A man holds a teapot.\n\nDid you spot the teapot?"
    assert vq.repair_description_question(good, RECORD_721) == good


def test_repair_never_edits_factual_claims_into_compliance():
    description = "A woman in a green dress dances.\n\nDid you see the elephant?"
    repaired = vq.repair_description_question(description, RECORD_721)
    # The invented colour claim survives the repair untouched, so the gate
    # still rejects the package — repair is for questions, never for facts.
    assert "green dress" in repaired
    found = kinds(vq.check_consistency(description=repaired, record=RECORD_721))
    assert "unseen_colour" in found


# --------------------------------------------------------------------------- #
# defect 2 — cut-off endings (job 683)
# --------------------------------------------------------------------------- #
SCRIPT_683 = (
    "She grips a red wrapped candy stick crown with green leaves, flashing it "
    "near her face under the bright sky. She then tilts the blender, pouring "
    "a thick pink liquid into a clear glass on the counter. Meanwhile a man "
    "with headphones watches a brown snack bag while a monitor flashes behind "
    "him today. Now again, about"
)


def test_job683_unterminated_overlong_and_invented():
    length = kinds(vq.check_script_length(commentary=SCRIPT_683, duration=23.0))
    assert "unterminated_script" in length  # ends "Now again, about"
    assert "script_too_long" in length
    consistency = kinds(vq.check_consistency(commentary=SCRIPT_683, record=RECORD_683))
    assert "unseen_colour" in consistency   # "green leaves" were never filmed


def test_length_window_accepts_a_fitted_script():
    script = (
        "She lifts the small teapot from the tray and holds it toward the "
        "camera with a grin. He watches from the sofa and starts laughing at "
        "her serious face. Nobody expected the lid to pop."
    )
    assert vq.check_script_length(commentary=script, duration=20.0) == []
    assert vq.word_budget(20.0) == 46


def test_narration_fit_catches_truncated_final_sentence():
    script = "One beat lands. Two beats land. The final sentence lands whole."
    overrun = kinds(vq.evaluate_narration_fit(
        commentary=script, narration_seconds=21.5, duration=20.0,
        last_sentence_coverage=1.0,
    ))
    assert "narration_overruns_clip" in overrun
    truncated = kinds(vq.evaluate_narration_fit(
        commentary=script, narration_seconds=19.0, duration=20.0,
        last_sentence_coverage=0.0,
    ))
    assert "final_sentence_truncated" in truncated
    # Coverage unknown (no transcript) must not invent a failure.
    assert vq.evaluate_narration_fit(
        commentary=script, narration_seconds=19.0, duration=20.0,
        last_sentence_coverage=None,
    ) == []
    assert vq.last_sentence_coverage(script, {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11}) == 1.0
    assert vq.last_sentence_coverage(script, None) is None


# --------------------------------------------------------------------------- #
# defect 4 — phantom [music] captions, flat voice, no music bed
# --------------------------------------------------------------------------- #
def test_spoken_text_strips_bracket_tags():
    assert vq.sanitize_spoken_text("He laughs [music] loudly <break> now") == \
        "He laughs loudly now"
    cues = vr._sanitize_cues([{"start": 0.0, "end": 1.0, "text": "[music] hello"}])
    assert cues == [{"start": 0.0, "end": 1.0, "text": "hello"}]


def test_beat_prosody_varies_by_position():
    hook = vr._beat_prosody(0, 3)
    payoff = vr._beat_prosody(2, 3)
    build = vr._beat_prosody(1, 3)
    assert hook != payoff and build != payoff
    assert hook["rate"] == "+8%" and payoff["rate"] == "-3%"


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_music_bed_is_real_audio_of_the_right_length(tmp_path):
    bed = vr.build_music_bed(tmp_path / "bed.wav", 6.0)
    assert bed is not None and Path(bed).exists()
    with wave.open(str(bed)) as handle:
        seconds = handle.getnframes() / handle.getframerate()
    assert 5.4 <= seconds <= 6.6


# --------------------------------------------------------------------------- #
# defect 5 — dead source clips (job 701's static two-shot)
# --------------------------------------------------------------------------- #
def test_static_frames_fail_the_arc_gate():
    frames = [bytes([128] * 400) for _ in range(6)]
    arc = vq.frame_change_metrics(frames)
    ok, reason = vq.arc_gate(arc)
    assert not ok and reason == "static_scene"


def test_eventful_frames_pass_the_arc_gate():
    frames = [bytes([0] * 400), bytes([255] * 400)] * 3
    arc = vq.frame_change_metrics(frames)
    ok, _reason = vq.arc_gate(arc)
    assert ok
    # An unmeasurable clip is not condemned by the arc gate alone.
    assert vq.arc_gate(None) == (True, "arc_unmeasured")


# --------------------------------------------------------------------------- #
# vision record coercion (the record is the only source of truth)
# --------------------------------------------------------------------------- #
def test_record_pass_respects_provider_image_cap():
    # Proven on the production host (2026-11-17, staging self-test): the
    # vision provider rejects >3 images per request with HTTP 400 "Too many
    # images provided. This model supports up to 3 images" — a six-frame
    # record pass made EVERY candidate skip as vision_unavailable.
    from app.services.scene_analysis import _RECORD_POSITIONS
    assert sum(len(positions) for positions in _RECORD_POSITIONS) <= 3
    assert len(_RECORD_POSITIONS) == 3  # one frame per beat


def test_coerce_record_validates_and_pads():
    payload = {
        "beats": [
            {"setting": "room", "time_of_day": "day", "subjects": [], "objects": [],
             "summary": "One."},
            {"setting": "room", "time_of_day": "day", "subjects": [], "objects": [],
             "summary": "Two."},
        ],
        "event_arc": "Something changes.",
        "static": False,
    }
    record = _coerce_record(payload)
    assert record is not None and len(record["beats"]) == 3
    assert "1) One." in scene_text(record)
    assert _coerce_record("not a dict") is None
    assert _coerce_record({"beats": []}) is None
    assert _coerce_record({"event_arc": "x"}) is None


# --------------------------------------------------------------------------- #
# metadata: grounded fallback question, no orphan CTA, hashtag dedupe
# --------------------------------------------------------------------------- #
def _candidate(**overrides):
    base = dict(
        video_id="abc123XYZ", title="Teapot ghost clip", channel="Some Channel",
        duration=20.0, view_count=1000, like_count=10, upload_date="20251101",
        license="creative commons", category="VIRAL", hook="WAIT FOR IT",
        score=1.0, tags=[], description="", webpage_url="",
    )
    base.update(overrides)
    from app.services.viral_discovery import Candidate
    return Candidate(**base)


def _speech():
    return SimpleNamespace(has_speech=False, text="", speech_seconds=0.0)


def test_metadata_fallback_question_is_grounded_in_the_record():
    meta = vr.build_metadata(
        _candidate(), _speech(), "WAIT FOR IT", "VIRAL",
        {"commentary": "He sits holding a teapot.", "title": "Teapot Moment",
         "description": ""},
        set(), record=RECORD_721,
    )
    assert "Did you spot the" in meta["description"]
    assert meta["description"].index("?") < meta["description"].index("Drop your answer")


def test_metadata_no_question_no_cta_when_record_is_empty():
    meta = vr.build_metadata(
        _candidate(), _speech(), "WAIT FOR IT", "VIRAL",
        {"commentary": "Something happens on screen.", "title": "A Moment",
         "description": ""},
        set(), record={"beats": []},
    )
    assert "Drop your answer" not in meta["description"]


def test_metadata_dedupes_hashtags():
    meta = vr.build_metadata(
        _candidate(), _speech(), "WAIT FOR IT", "VIRAL",
        {"commentary": "He sits holding a teapot.", "title": "Teapot Moment",
         "description": "Fun clip #Shorts #Viral\n\nMore #Shorts fun"},
        set(), record=RECORD_721,
    )
    assert meta["description"].count("#Shorts") == 1
    assert meta["description"].count("#Viral") == 1


# --------------------------------------------------------------------------- #
# produce_viral_short: the fail-closed wiring itself
# --------------------------------------------------------------------------- #
class _FakeSession:
    def __init__(self):
        self.added: list = []
        self._next_id = 1

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = self._next_id
                self._next_id += 1

    def commit(self):
        pass


def _wire_common(monkeypatch, tmp_path):
    monkeypatch.setattr(vr, "download_audio_only",
                        lambda video_id, dest: tmp_path / "probe.webm")
    monkeypatch.setattr(vr, "detect_speech", lambda path: _speech())
    monkeypatch.setattr(vr, "download_source_video",
                        lambda video_id, dest: tmp_path / "source.mp4")
    monkeypatch.setattr(vr, "probe_media", lambda path: SimpleNamespace(
        duration=21.0, width=1080, height=1920, has_audio=True))
    monkeypatch.setattr(vr, "existing_upload_titles", lambda db: set())


def test_produce_skips_static_clip_before_vision(monkeypatch, tmp_path):
    _wire_common(monkeypatch, tmp_path)
    monkeypatch.setattr(vq, "measure_event_arc", lambda *a, **k: vq.EventArc(
        samples=10, mean_change=0.0005, max_change=0.001,
        static_ratio=1.0, peak_position=0.5, changes=(0.001,) * 9))
    vision_calls = []
    monkeypatch.setattr(vr, "analyze_scene",
                        lambda *a, **k: vision_calls.append(1) or RECORD_761)
    result = vr.produce_viral_short(_candidate(), _FakeSession(), publish=False)
    assert result["status"] == "SKIPPED" and result["reason"] == "static_scene"
    assert vision_calls == []  # rejected before any model spend


def test_produce_skips_when_vision_unavailable(monkeypatch, tmp_path):
    _wire_common(monkeypatch, tmp_path)
    monkeypatch.setattr(vq, "measure_event_arc", lambda *a, **k: None)
    monkeypatch.setattr(vr, "analyze_scene", lambda *a, **k: None)
    result = vr.produce_viral_short(_candidate(), _FakeSession(), publish=False)
    assert result["status"] == "SKIPPED"
    assert result["reason"] == "vision_unavailable"


def test_produce_skips_unverifiable_script_after_one_retry(monkeypatch, tmp_path):
    _wire_common(monkeypatch, tmp_path)
    monkeypatch.setattr(vq, "measure_event_arc", lambda *a, **k: None)
    monkeypatch.setattr(vr, "analyze_scene", lambda *a, **k: RECORD_761)
    calls = []

    def bad_editorial(*args, **kwargs):
        calls.append(kwargs.get("feedback"))
        return {
            "commentary": (
                "A man in a light blue shirt sits outdoors at night clutching "
                "his phone. The pink-haired woman on the screen holds a cookie "
                "and stares at him. He covers his mouth and nose with both "
                "hands in total panic."
            ),
            "title": "Nighttime Phone Panic Under String Lights",
            "description": "A man sits with his phone.",
            "hashtags": "",
        }

    monkeypatch.setattr(vr, "generate_editorial", bad_editorial)
    result = vr.produce_viral_short(_candidate(), _FakeSession(), publish=False)
    assert result["status"] == "SKIPPED"
    assert result["reason"] == "script_unverifiable"
    assert len(calls) == 3 and calls[1] and calls[2]  # retries carry feedback
    assert "unverified_hair" in result["violations"]


def test_produce_renders_grounded_package_with_music_bed(monkeypatch, tmp_path):
    _wire_common(monkeypatch, tmp_path)
    monkeypatch.setattr(vq, "measure_event_arc", lambda *a, **k: vq.EventArc(
        samples=10, mean_change=0.05, max_change=0.2,
        static_ratio=0.1, peak_position=0.8, changes=(0.05,) * 9))
    monkeypatch.setattr(vr, "analyze_scene", lambda *a, **k: RECORD_761)
    monkeypatch.setattr(vr, "generate_editorial", lambda *a, **k: {
        "commentary": (
            "Watch his face when the phone photo appears in bright daylight. "
            "She laughs and runs right past him under the string lights. "
            "He just stands there grinning with both hands over his mouth."
        ),
        "title": "He Was Not Ready for That Photo Reveal",
        "description": (
            "A daylight phone photo, a run past under the string lights, and "
            "one priceless reaction.\n\nDid you spot the phone?"
        ),
        "hashtags": "",
    })
    monkeypatch.setattr(vr, "build_scene_tracks", lambda *a, **k: {
        "total_seconds": 19.5, "narration_path": tmp_path / "narration.wav",
        "beats": [],
    })
    monkeypatch.setattr(vr, "_last_sentence_coverage", lambda *a, **k: 1.0)
    monkeypatch.setattr(vr, "build_commentary_cues", lambda tracks, script: [
        {"start": 0.0, "end": 2.0, "text": "Watch his face"}])
    monkeypatch.setattr(vr, "build_music_bed",
                        lambda path, seconds: Path(path))
    render_kwargs = {}
    monkeypatch.setattr(vr, "render_scene_timed",
                        lambda *a, **k: render_kwargs.update(k))
    result = vr.produce_viral_short(_candidate(), _FakeSession(), publish=False)
    assert result["status"] == "RENDERED"
    assert render_kwargs.get("music_bed_path") is not None


def test_produce_repairs_an_ungrounded_description_question(monkeypatch, tmp_path):
    # The staging self-test's real outcome (2026-11-17): the model's draft
    # was fully grounded and died only on the description's question. That
    # one defect is repaired deterministically; the video renders.
    _wire_common(monkeypatch, tmp_path)
    monkeypatch.setattr(vq, "measure_event_arc", lambda *a, **k: None)
    monkeypatch.setattr(vr, "analyze_scene", lambda *a, **k: RECORD_761)
    monkeypatch.setattr(vr, "generate_editorial", lambda *a, **k: {
        "commentary": (
            "Watch his face when the phone photo appears in bright daylight. "
            "She laughs and runs right past him under the string lights. "
            "He just stands there grinning with both hands over his mouth."
        ),
        "title": "He Was Not Ready for That Photo Reveal",
        "description": (
            "A daylight phone photo and one priceless reaction.\n\n"
            "Did you see the elephant?"
        ),
        "hashtags": "",
    })
    monkeypatch.setattr(vr, "build_scene_tracks", lambda *a, **k: {
        "total_seconds": 19.5, "narration_path": tmp_path / "narration.wav",
        "beats": [],
    })
    monkeypatch.setattr(vr, "_last_sentence_coverage", lambda *a, **k: 1.0)
    monkeypatch.setattr(vr, "build_commentary_cues", lambda tracks, script: [
        {"start": 0.0, "end": 2.0, "text": "Watch his face"}])
    monkeypatch.setattr(vr, "build_music_bed", lambda path, seconds: Path(path))
    monkeypatch.setattr(vr, "render_scene_timed", lambda *a, **k: None)
    session = _FakeSession()
    result = vr.produce_viral_short(_candidate(), session, publish=True)
    assert result["status"] == "QUEUED_FOR_PUBLISH"
    assert result["description_repaired"] is True
    publish_jobs = [o for o in session.added if type(o).__name__ == "PublishJob"]
    assert len(publish_jobs) == 1
    assert "elephant" not in publish_jobs[0].description
    assert "Did you spot the" in publish_jobs[0].description


# --------------------------------------------------------------------------- #
# hook-length convergence — a grounded draft must not die on hook length
# (first gated production render, 2026-11-17: hook_too_long on all 3 attempts)
# --------------------------------------------------------------------------- #
PRODUCTION_HOOK_DRAFT = (
    "A driver in a yellow shirt sits in the seat, his face frozen in a "
    "surprised expression as the world seems to pause. A woman in a pink "
    "dress stands beside the car, watching the driver with a surprised "
    "expression. The driver remains frozen in place, still staring ahead "
    "with his mouth slightly open in shock. The woman in pink continues to "
    "watch, her posture tense as she takes in the scene. The driver stays "
    "frozen in his seat as the moment stretches on."
)


def test_repair_hook_length_drops_trailing_clauses_to_the_cap():
    # The verbatim production draft whose 23-word hook sank a grounded
    # package: the repair keeps the first clause and drops the rest.
    repaired = vq.repair_hook_length(PRODUCTION_HOOK_DRAFT)
    sentences = vq.split_sentences(repaired)
    assert sentences[0] == "A driver in a yellow shirt sits in the seat."
    assert len(sentences[0].split()) <= 18
    # Only the first sentence changes; every later sentence is untouched.
    assert sentences[1:] == vq.split_sentences(PRODUCTION_HOOK_DRAFT)[1:]
    # The repair never invents: every repaired word was in the draft.
    assert {w.strip(",.;:!?") for w in repaired.split()} <= {
        w.strip(",.;:!?") for w in PRODUCTION_HOOK_DRAFT.split()}


def test_repair_hook_length_leaves_compliant_and_unclaused_hooks_alone():
    compliant = (
        "Watch his face when the phone photo appears in bright daylight. "
        "She laughs and runs right past him under the string lights. "
        "He just stands there grinning with both hands over his mouth."
    )
    assert vq.repair_hook_length(compliant) == compliant
    # A single-clause hook over the cap has no clause boundary to drop at:
    # the repair returns it unchanged and the gate still rejects it —
    # repair never truncates mid-clause into compliance.
    unclaused = (
        "Watch the man in the light blue shirt sitting outside in bright "
        "daylight holding his phone up high for everyone to see clearly. "
        "She laughs and runs right past him under the string lights. "
        "He just stands there grinning with both hands over his mouth."
    )
    assert vq.repair_hook_length(unclaused) == unclaused
    assert "hook_too_long" in kinds(
        vq.check_structure(commentary=unclaused, record=RECORD_761))


def test_repaired_long_hook_package_passes_every_gate():
    commentary = (
        "Watch his face when the phone photo appears in bright daylight, "
        "the exact moment the photo appears on his phone. "
        "She laughs and runs right past him under the string lights. "
        "He just stands there grinning with both hands over his mouth."
    )
    title = "He Was Not Ready for That Photo Reveal"
    description = (
        "A daylight phone photo, a run past under the string lights, and one "
        "priceless reaction.\n\nDid you spot the phone?\n\n#Shorts #VyralX"
    )
    # Before repair the ONLY defect, across every gate, is the hook length.
    before = (
        vq.check_consistency(commentary=commentary, title=title,
                             description=description, record=RECORD_761)
        + vq.check_structure(commentary=commentary, record=RECORD_761)
        + vq.check_script_length(commentary=commentary, duration=21.0)
    )
    assert kinds(before) == {"hook_too_long"}
    repaired = vq.repair_hook_length(commentary)
    assert repaired != commentary
    assert vq.split_sentences(repaired)[0] == (
        "Watch his face when the phone photo appears in bright daylight."
    )
    assert vq.check_consistency(
        commentary=repaired, title=title, description=description,
        record=RECORD_761) == []
    assert vq.check_structure(commentary=repaired, record=RECORD_761) == []
    assert vq.check_script_length(commentary=repaired, duration=21.0) == []


def test_produce_repairs_an_overlong_hook_and_renders(monkeypatch, tmp_path):
    # The production failure shape (2026-11-17): every model attempt returns
    # the same grounded package whose only defect is an over-cap hook. On
    # the old code this skipped as script_unverifiable after three attempts;
    # the deterministic hook repair must drive it to a render in-budget.
    _wire_common(monkeypatch, tmp_path)
    monkeypatch.setattr(vq, "measure_event_arc", lambda *a, **k: None)
    monkeypatch.setattr(vr, "analyze_scene", lambda *a, **k: RECORD_761)
    calls = []

    def long_hook_editorial(*args, **kwargs):
        calls.append(1)
        return {
            "commentary": (
                "Watch his face when the phone photo appears in bright "
                "daylight, the exact moment the photo appears on his phone. "
                "She laughs and runs right past him under the string lights. "
                "He just stands there grinning with both hands over his mouth."
            ),
            "title": "He Was Not Ready for That Photo Reveal",
            "description": (
                "A daylight phone photo, a run past under the string lights, "
                "and one priceless reaction.\n\nDid you spot the phone?"
            ),
            "hashtags": "",
        }

    monkeypatch.setattr(vr, "generate_editorial", long_hook_editorial)
    monkeypatch.setattr(vr, "build_scene_tracks", lambda *a, **k: {
        "total_seconds": 19.5, "narration_path": tmp_path / "narration.wav",
        "beats": [],
    })
    monkeypatch.setattr(vr, "_last_sentence_coverage", lambda *a, **k: 1.0)
    monkeypatch.setattr(vr, "build_commentary_cues", lambda tracks, script: [
        {"start": 0.0, "end": 2.0, "text": "Watch his face"}])
    monkeypatch.setattr(vr, "build_music_bed", lambda path, seconds: Path(path))
    monkeypatch.setattr(vr, "render_scene_timed", lambda *a, **k: None)
    session = _FakeSession()
    result = vr.produce_viral_short(_candidate(), session, publish=True)
    assert result["status"] == "QUEUED_FOR_PUBLISH"
    assert result["hook_repaired"] is True
    # Repaired on the first attempt — no extra model spend was needed.
    assert len(calls) == 1
    assert result["narration"].startswith(
        "Watch his face when the phone photo appears in bright daylight.")
    publish_jobs = [o for o in session.added if type(o).__name__ == "PublishJob"]
    assert len(publish_jobs) == 1


# --- TASK-VYR-025: the remix path honours the source-captioned gate --- #
# Same pre-render rejection as the framed path: a source that already
# carries a full burned-in caption track is skipped with
# source_captioned before any editorial or render work, because the
# remix's own caption track would double it (cycle 6, job 841).


def test_produce_skips_a_captioned_source_before_editorial(monkeypatch, tmp_path):
    _wire_common(monkeypatch, tmp_path)
    monkeypatch.setattr(vq, "measure_event_arc", lambda *a, **k: None)
    captioned = dict(RECORD_761)
    captioned["source_caption_track"] = True
    captioned["caption_beats"] = 3
    monkeypatch.setattr(vr, "analyze_scene", lambda *a, **k: captioned)
    editorial_calls = []
    monkeypatch.setattr(vr, "generate_editorial",
                        lambda *a, **k: editorial_calls.append(1) or {})
    result = vr.produce_viral_short(_candidate(), _FakeSession(), publish=False)
    assert result["status"] == "SKIPPED"
    assert result["reason"] == "source_captioned"
    assert result["visual_defects"] == ["source_captioned"]
    assert editorial_calls == []  # rejected before any editorial/render work
