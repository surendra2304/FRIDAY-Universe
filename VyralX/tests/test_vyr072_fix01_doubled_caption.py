"""TASK-VYR-072-FIX-01 regression: doubled captions in a framed render's .ass.

The Nov 18 cycle-2 framed render ``framed--bh5VGbrbLI-5970f1`` (job 802)
carries doubled captions: its .ass has 20 speech events with overlapping
pairs (live-leg evidence, docs/collaboration/TASK-VYR-072-LIVE-LEG.md
section 4b) — ``ass_caption_track_count`` = 2,
``caption_track_gate`` = ``multiple_caption_tracks:2``.

Root cause (scoped from the code + git history): the render predates
TASK-VYR-022 (2026-11-19), which moved framing lines to the AntonFraming
top band. On Nov 18, ``_write_ass`` wrote EVERY cue in AntonBold — the
hook (0.0-3.34s) and payoff (25.34-29.23s) lines share the lower-third
zone with the source-speech cues and overlap them in time. The current
forward path (``framed_cues`` + AntonFraming + the duplicate drop)
already separates them for new renders; the remaining gap was the writer
itself — ``_write_ass`` had no overlap validation and would silently
emit a doubled .ass for any overlapping same-style input, while the
other .ass writer (``captions.write_ass``) raises on overlap.

These tests pin the fix (pure: no ffmpeg, no vision model, no network):
* ``_write_ass`` refuses a same-style overlap (the Q1 cue list) and
  stays permissive where the design allows overlap (framing vs speech,
  different bands; the 0.06s row-extension micro-overlap);
* ``repair_doubled_ass`` re-authors a doubled framed .ass to a single
  speech track through the production writer, and fails closed when it
  cannot;
* the forward path (``framed_cues`` + ``_write_ass``) produces a
  single-track .ass for a Q1-shaped input.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services import held_render_qa as hrq
from app.services import viral_framing as vf
from app.services import viral_remix as vr

# The Q1 overlap events, verbatim from the live-leg evidence (section 4b).
# The two middle events are representative tiling fill for the render's
# other speech cues — they are NOT the render's words, only its shape
# (the live leg lists 20 speech events; the 6 overlap events are the
# ones that matter for the doubling).
_Q1_HOOK = "WATCH WHAT HAPPENS WHEN HE POINTS AT THAT BUTTON."
_Q1_PAYOFF = "HE SMILES AS THE DOG STAYS STILL BESIDE THE TWO BUTTONS."
_Q1_ASS = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: AntonBold,Anton,120,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,1.2,0,1,13.0,0,2,50,50,400,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:01.00,AntonBold,,0,0,0,,CRAP, PRESS THE BLUE BUTTON.
Dialogue: 0,0:00:00.00,0:00:03.34,AntonBold,,0,0,0,,WATCH WHAT HAPPENS WHEN HE POINTS AT THAT BUTTON.
Dialogue: 0,0:00:01.00,0:00:02.00,AntonBold,,0,0,0,,OH NO!
Dialogue: 0,0:00:02.00,0:00:03.56,AntonBold,,0,0,0,,WHAT YOU GOT BEEF WITH
Dialogue: 0,0:00:05.00,0:00:07.00,AntonBold,,0,0,0,,THE DOG LOOKS AT THE BUTTON
Dialogue: 0,0:00:07.00,0:00:09.00,AntonBold,,0,0,0,,HE WAITS FOR THE SIGNAL
Dialogue: 0,0:00:25.28,0:00:27.28,AntonBold,,0,0,0,,OH NO!
Dialogue: 0,0:00:25.34,0:00:29.23,AntonBold,,0,0,0,,HE SMILES AS THE DOG STAYS STILL BESIDE THE TWO BUTTONS.
"""

# The same cue list the Nov 18 writer received: hook + payoff in the
# same style as the speech cues (no "framing" flag — pre-VYR-022).
_Q1_CUES = [
    {"start": 0.0, "end": 1.0, "text": "crap, press the blue button."},
    {"start": 0.0, "end": 3.34, "text": "watch what happens when he points at that button."},
    {"start": 1.0, "end": 2.0, "text": "oh no!"},
    {"start": 2.0, "end": 3.56, "text": "what you got beef with"},
    {"start": 5.0, "end": 7.0, "text": "the dog looks at the button"},
    {"start": 7.0, "end": 9.0, "text": "he waits for the signal"},
    {"start": 25.28, "end": 27.28, "text": "oh no!"},
    {"start": 25.34, "end": 29.23, "text": "he smiles as the dog stays still beside the two buttons."},
]


def _write_ass_text(tmp_path: Path, text: str, name: str = "render.ass") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_q1_doubled_ass_counts_two(tmp_path):
    """Reproduces Q1: the Nov 18 .ass counts two speech tracks."""
    events, malformed = hrq.parse_ass_dialogue(_write_ass_text(tmp_path, _Q1_ASS))
    assert malformed == 0
    assert len(events) == 8
    assert len(hrq.speech_events(events)) == 8  # no hook layer at all
    assert hrq.ass_caption_track_count(hrq.speech_events(events)) == 2


def test_write_ass_rejects_q1_same_style_overlap(tmp_path):
    """The writer fix: the Q1 cue list raises instead of writing a doubled .ass."""
    with pytest.raises(ValueError, match="must not overlap"):
        vr._write_ass(_Q1_CUES, tmp_path / "caps.ass")
    assert not (tmp_path / "caps.ass").exists()


def test_write_ass_allows_cross_style_overlap(tmp_path):
    """Framing vs speech may overlap in time — different bands by design (VYR-022)."""
    cues = [
        {"start": 1.0, "end": 3.0, "text": "the source speaks", "speech": True},
        {"start": 0.0, "end": 2.0, "text": "watch this moment", "framing": True},
    ]
    ass_path = vr._write_ass(cues, tmp_path / "caps.ass")
    text = ass_path.read_text(encoding="utf-8")
    assert "Style: AntonFraming" in text
    events, _ = hrq.parse_ass_dialogue(ass_path)
    assert hrq.ass_caption_track_count(hrq.speech_events(events)) == 1


def test_write_ass_allows_tiling_and_row_extension_micro_overlap(tmp_path):
    """Tiling cues write fine, and so does the 0.06s row-extension
    micro-overlap from _cues_from_words (fast speech) — the tolerance
    preserves that deliberate behaviour; only real doublings raise."""
    tiling = [
        {"start": 0.0, "end": 1.0, "text": "hello world"},
        {"start": 1.0, "end": 2.0, "text": "goodbye moon"},
        {"start": 2.0, "end": 3.0, "text": "stay tuned"},
    ]
    vr._write_ass(tiling, tmp_path / "tile.ass")
    micro = [
        {"start": 0.0, "end": 0.94, "text": "watch what happens"},
        {"start": 0.9, "end": 1.84, "text": "when he points"},
    ]
    vr._write_ass(micro, tmp_path / "micro.ass")
    # Just above the tolerance, a same-style overlap is a doubling.
    real_overlap = [
        {"start": 0.0, "end": 1.0, "text": "first line here"},
        {"start": 0.8, "end": 2.0, "text": "second line here"},
    ]
    with pytest.raises(ValueError, match="must not overlap"):
        vr._write_ass(real_overlap, tmp_path / "real.ass")


def test_write_ass_rejects_out_of_order_and_zero_length(tmp_path):
    """Same semantics as captions.write_ass: ordered, and spanning at
    least 1 centisecond after rounding."""
    out_of_order = [
        {"start": 2.0, "end": 3.0, "text": "second"},
        {"start": 0.0, "end": 1.0, "text": "first"},
    ]
    with pytest.raises(ValueError, match="must be ordered"):
        vr._write_ass(out_of_order, tmp_path / "ooo.ass")
    zero_length = [{"start": 1.0, "end": 1.004, "text": "a flash"}]
    with pytest.raises(ValueError, match="at least 1 centisecond"):
        vr._write_ass(zero_length, tmp_path / "zero.ass")


def test_repair_doubled_ass_restores_single_track(tmp_path):
    """The Q1 .ass repairs to a single speech track: framing lines move
    to the AntonFraming top band, speech is preserved, source untouched."""
    source = _write_ass_text(tmp_path, _Q1_ASS, "framed--bh5VGbrbLI-5970f1.ass")
    report = vf.repair_doubled_ass(
        source, tmp_path / "repaired.ass",
        hook_text="Watch what happens when he points at that button.",
        payoff_text="He smiles as the dog stays still beside the two buttons.",
    )
    assert report["events_in"] == 8
    assert report["events_out"] == 8
    assert report["ass_caption_tracks"] == 1
    assert len(report["framing_restyled"]) == 2
    assert report["dropped_duplicates"] == []
    assert report["framing_restyled"][0]["text"] == _Q1_HOOK
    assert report["framing_restyled"][1]["text"] == _Q1_PAYOFF
    # Source never overwritten.
    assert source.read_text(encoding="utf-8") == _Q1_ASS
    repaired, malformed = hrq.parse_ass_dialogue(tmp_path / "repaired.ass")
    assert malformed == 0
    assert len(repaired) == 8
    assert len(hrq.speech_events(repaired)) == 6
    assert len(repaired) - len(hrq.speech_events(repaired)) == 2
    assert hrq.ass_caption_track_count(hrq.speech_events(repaired)) == 1
    assert "Style: AntonFraming" in (tmp_path / "repaired.ass").read_text(encoding="utf-8")
    # The re-styled lines keep their words, now in the top band.
    framing_events = [e for e in repaired if e not in hrq.speech_events(repaired)]
    assert {e["text"] for e in framing_events} == {_Q1_HOOK, _Q1_PAYOFF}


def test_repair_drops_speech_duplicate_of_framing_line(tmp_path):
    """Job 801's shape: the source's final line is quoted inside the
    payoff, so it was captioned twice at once. The duplicate speech cue
    is dropped; the framing line carries the words."""
    ass = """[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:01.00,AntonBold,,0,0,0,,OPENING LINE HERE
Dialogue: 0,0:00:25.34,0:00:27.00,AntonBold,,0,0,0,,HE SMILES AS THE DOG STAYS STILL
Dialogue: 0,0:00:25.34,0:00:29.23,AntonBold,,0,0,0,,HE SMILES AS THE DOG STAYS STILL BESIDE THE TWO BUTTONS.
"""
    source = _write_ass_text(tmp_path, ass, "dup.ass")
    report = vf.repair_doubled_ass(
        source, tmp_path / "dup-repaired.ass",
        payoff_text="He smiles as the dog stays still beside the two buttons.",
    )
    assert report["events_in"] == 3
    assert report["events_out"] == 2
    assert report["ass_caption_tracks"] == 1
    assert len(report["dropped_duplicates"]) == 1
    assert report["dropped_duplicates"][0]["text"] == "HE SMILES AS THE DOG STAYS STILL"


def test_repair_fails_closed(tmp_path):
    """The repair never guesses: no framing text, no match, or a
    remaining speech-vs-speech overlap all raise instead of claiming
    a single track."""
    source = _write_ass_text(tmp_path, _Q1_ASS, "q1.ass")
    with pytest.raises(ValueError, match="needs the hook and/or payoff"):
        vf.repair_doubled_ass(source, tmp_path / "out.ass")
    with pytest.raises(ValueError, match="found no event matching"):
        vf.repair_doubled_ass(
            source, tmp_path / "out.ass",
            hook_text="A line that is not in the file at all.",
        )
    speech_overlap = """[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:03.34,AntonBold,,0,0,0,,WATCH WHAT HAPPENS WHEN HE POINTS AT THAT BUTTON.
Dialogue: 0,0:00:00.00,0:00:02.00,AntonBold,,0,0,0,,FIRST SPEECH LINE HERE
Dialogue: 0,0:00:01.00,0:00:03.00,AntonBold,,0,0,0,,SECOND SPEECH LINE HERE
"""
    overlap_source = _write_ass_text(tmp_path, speech_overlap, "overlap.ass")
    with pytest.raises(ValueError, match="must not overlap"):
        vf.repair_doubled_ass(
            overlap_source, tmp_path / "overlap-out.ass",
            hook_text="Watch what happens when he points at that button.",
        )
    assert not (tmp_path / "overlap-out.ass").exists()


def test_framed_cues_plus_write_ass_produces_single_track(tmp_path):
    """Forward path, pinned: a Q1-shaped framed edit built with the
    current code (framed_cues + _write_ass) is a single speech track —
    the hook/payoff sit in the top band, the speech tiles below."""
    speech = [
        {"start": 0.0, "end": 1.0, "text": "crap, press the blue button."},
        {"start": 1.0, "end": 2.0, "text": "oh no!"},
        {"start": 2.0, "end": 3.56, "text": "what you got beef with"},
        {"start": 5.0, "end": 7.0, "text": "the dog looks at the button"},
        {"start": 7.0, "end": 9.0, "text": "he waits for the signal"},
        {"start": 25.28, "end": 27.28, "text": "oh no!"},
    ]
    cues = vf.framed_cues(
        speech,
        excerpt_start=0.0, excerpt_seconds=29.23,
        hook="Watch what happens when he points at that button.", hook_seconds=3.34,
        payoff="He smiles as the dog stays still beside the two buttons.", payoff_seconds=3.89,
    )
    ass_path = vr._write_ass(cues, tmp_path / "forward.ass")
    events, malformed = hrq.parse_ass_dialogue(ass_path)
    assert malformed == 0
    assert hrq.ass_caption_track_count(hrq.speech_events(events)) == 1
    framing = [e for e in events if e not in hrq.speech_events(events)]
    assert len(framing) == 2
