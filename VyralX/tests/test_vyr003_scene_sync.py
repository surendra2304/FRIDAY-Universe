"""TASK-VYR-003: scene-timed assembly + audio-derived captions for viral shorts.

The defects these tests pin, measured on the production render
viral-Bqf5iKfRPnc-1c9a14 (2026-11-13) before the fix:

* the single-block narration ran 28.44s over a 38.64s clip — the payoff
  sentence was spoken at 19.5-28.4s while its frame sits at ~32.8s, and the
  last 10.2s of the video had no commentary at all;
* edge-tts on the production host emits ZERO WordBoundary events, so the
  word-timed caption path never ran and captions were sentence-proportional
  estimates — late by +0.73s on average, up to +1.5s, against a Whisper
  transcript of the render's own audio.

On clean main every test here fails: the scene-timing API does not exist and
``produce_viral_short`` still renders through the single-block path.
"""
from __future__ import annotations

import pytest

from app.services import viral_remix as vr


SCRIPT = (
    "In a flash of pink the dancer strikes a pose against the black backdrop. "
    "She steps forward in a bright sari and plants her hands on her hips. "
    "Then she lifts both arms wide and the stage bursts into fireworks."
)


# --------------------------------------------------------------------------- #
# sentence splitting + beat planning
# --------------------------------------------------------------------------- #
def test_split_sentences_keeps_punctuation_and_order():
    assert vr.split_sentences(SCRIPT) == [
        "In a flash of pink the dancer strikes a pose against the black backdrop.",
        "She steps forward in a bright sari and plants her hands on her hips.",
        "Then she lifts both arms wide and the stage bursts into fireworks.",
    ]
    assert vr.split_sentences("") == []
    assert vr.split_sentences("No terminator here") == ["No terminator here"]


def test_plan_beats_boundaries_midway_between_anchors():
    beats = vr.plan_beats(vr.split_sentences(SCRIPT), 40.0)
    assert [(b["start"], b["end"]) for b in beats] == [
        (0.0, 13.0), (13.0, 27.0), (27.0, 40.0),
    ]
    # the frame each sentence describes sits inside its own segment
    for beat in beats:
        assert beat["start"] <= beat["anchor"] <= beat["end"]
    assert [b["text"] for b in beats] == vr.split_sentences(SCRIPT)


def test_plan_beats_distributes_sentences_contiguously():
    sentences = [f"Sentence {i}." for i in range(7)]
    beats = vr.plan_beats(sentences, 30.0)
    assigned = [s for beat in beats for s in beat["sentences"]]
    assert assigned == sentences  # nothing dropped, nothing reordered
    counts = [len(beat["sentences"]) for beat in beats]
    assert max(counts) - min(counts) <= 1


def test_plan_beats_fewer_sentences_than_beats():
    beats = vr.plan_beats(["Only one beat is narrated."], 30.0)
    assert beats[0]["text"] == "Only one beat is narrated."
    assert beats[1]["text"] == "" and beats[2]["text"] == ""


# --------------------------------------------------------------------------- #
# segment retiming
# --------------------------------------------------------------------------- #
def test_segment_timing_exact_fit():
    timing = vr.segment_timing(10.0, 10.0)
    assert timing == {
        "factor": 1.0, "pad_seconds": 0.0,
        "trim_head_seconds": 0.0, "trim_tail_seconds": 0.0,
    }


def test_segment_timing_slowdown_within_clamp():
    timing = vr.segment_timing(10.0, 15.0)
    assert timing["factor"] == pytest.approx(1.5)
    assert timing["pad_seconds"] == 0.0 and timing["trim_tail_seconds"] == 0.0


def test_segment_timing_freeze_pads_beyond_max_slowdown():
    # audio is 2.5x the segment: slow to the 2.0x clamp, freeze the rest
    timing = vr.segment_timing(10.0, 25.0)
    assert timing["factor"] == 2.0
    assert timing["pad_seconds"] == pytest.approx(5.0)


def test_segment_timing_trims_tail_beyond_max_speedup():
    timing = vr.segment_timing(10.0, 4.0)
    assert timing["factor"] == 0.5
    assert timing["trim_tail_seconds"] == pytest.approx(1.0)
    assert timing["trim_head_seconds"] == 0.0


def test_segment_timing_last_segment_trims_head_to_protect_the_payoff():
    timing = vr.segment_timing(10.0, 4.0, is_last=True)
    assert timing["trim_head_seconds"] == pytest.approx(1.0)
    assert timing["trim_tail_seconds"] == 0.0


def test_segment_timing_always_lands_on_the_audio_length():
    for segment, audio in [(12.56, 9.31), (13.5, 13.5), (12.56, 28.4), (3.0, 1.2), (20.0, 3.0)]:
        timing = vr.segment_timing(segment, audio, is_last=True)
        landed = (
            segment * timing["factor"]
            + timing["pad_seconds"]
            - timing["trim_head_seconds"]
            - timing["trim_tail_seconds"]
        )
        assert landed == pytest.approx(audio, abs=0.01)


# --------------------------------------------------------------------------- #
# caption alignment from the actual audio
# --------------------------------------------------------------------------- #
def _skewed_transcriber(_path):
    """Fake Whisper: real speech is not metronomic — early words are slow."""
    words = SCRIPT.split()
    heard = []
    cursor = 0.0
    for index, word in enumerate(words):
        length = 0.9 if index < 6 else 0.18  # first words take 5x longer
        heard.append({"text": word, "start": cursor, "end": cursor + length})
        cursor += length + 0.04
    return heard


def test_align_script_words_carries_real_audio_times():
    aligned = vr.align_script_words("ignored.wav", SCRIPT, _transcribe=_skewed_transcriber)
    assert aligned is not None
    heard = _skewed_transcriber("ignored.wav")
    assert aligned[0]["start"] == pytest.approx(heard[0]["start"])
    assert aligned[5]["start"] == pytest.approx(heard[5]["start"])
    assert aligned[-1]["end"] == pytest.approx(heard[-1]["end"])
    starts = [word["start"] for word in aligned]
    assert starts == sorted(starts)


def test_aligned_cues_beat_the_old_proportional_estimate():
    aligned = vr.align_script_words("ignored.wav", SCRIPT, _transcribe=_skewed_transcriber)
    cues = vr._cues_from_words(aligned)
    heard = _skewed_transcriber("ignored.wav")
    # the first cue starts when the first word is actually spoken
    assert cues[0]["start"] == pytest.approx(heard[0]["start"], abs=0.05)
    # the old sentence-proportional spread (word-count share of the sentence)
    # puts word 6 of sentence 1 at 6/13 of the sentence's span — more than a
    # second away from when it is really spoken in this fixture.
    sentence_words = SCRIPT.split(".")[0].split()
    sentence_span = heard[len(sentence_words) - 1]["end"]
    proportional_start = sentence_span * 6 / len(sentence_words)
    real_start = heard[6]["start"]
    assert abs(proportional_start - real_start) > 0.25
    aligned_start = aligned[6]["start"]
    assert abs(aligned_start - real_start) < 0.05


def test_align_script_words_rejects_an_unrelated_transcript():
    def unrelated(_path):
        return [
            {"text": word, "start": float(i), "end": float(i) + 0.5}
            for i, word in enumerate(["completely", "different", "words", "here"])
        ]

    assert vr.align_script_words("x.wav", SCRIPT, _transcribe=unrelated) is None


def test_align_script_words_interpolates_unmatched_words():
    def partial(_path):
        words = SCRIPT.split()
        # Whisper misses every fifth word; alignment must still place them
        return [
            {"text": word, "start": i * 0.4, "end": i * 0.4 + 0.3}
            for i, word in enumerate(words) if i % 5 != 4
        ]

    aligned = vr.align_script_words("x.wav", SCRIPT, _transcribe=partial)
    assert aligned is not None and len(aligned) == len(SCRIPT.split())
    starts = [word["start"] for word in aligned]
    assert starts == sorted(starts)


def test_align_script_words_survives_transcriber_failure():
    def boom(_path):
        raise RuntimeError("whisper unavailable")

    assert vr.align_script_words("x.wav", SCRIPT, _transcribe=boom) is None


# --------------------------------------------------------------------------- #
# cue fallbacks stay inside their beat windows
# --------------------------------------------------------------------------- #
def _fake_tracks():
    beats = []
    cursor = 0.0
    for index, text in enumerate(vr.split_sentences(SCRIPT)):
        beats.append({
            "index": index, "text": text, "track_start": cursor,
            "target_seconds": 8.0, "word_words": None,
        })
        cursor += 8.0
    return {"beats": beats, "narration_path": "unused.wav", "total_seconds": cursor}


def test_beat_proportional_cues_confined_to_their_window():
    cues = vr._beat_proportional_cues("One two three four. Five six.", 20.0, 6.0)
    assert cues
    assert all(20.0 <= cue["start"] and cue["end"] <= 26.05 for cue in cues)


def test_build_commentary_cues_falls_back_per_beat(monkeypatch):
    monkeypatch.setattr(vr, "align_script_words", lambda *a, **k: None)
    cues = vr.build_commentary_cues(_fake_tracks(), SCRIPT)
    assert cues
    for cue in cues:
        beat_index = int(cue["start"] // 8.0)
        assert beat_index * 8.0 <= cue["start"] < (beat_index + 1) * 8.0 + 0.05


def test_build_commentary_cues_prefers_alignment(monkeypatch):
    words = [
        {"text": word, "start": i * 0.5, "end": i * 0.5 + 0.4}
        for i, word in enumerate(SCRIPT.split())
    ]
    monkeypatch.setattr(vr, "align_script_words", lambda *a, **k: words)
    cues = vr.build_commentary_cues(_fake_tracks(), SCRIPT)
    assert cues[0]["start"] == pytest.approx(0.0, abs=0.05)
    assert "flash" in cues[0]["text"].lower()


# --------------------------------------------------------------------------- #
# the pipeline wiring itself
# --------------------------------------------------------------------------- #
def test_produce_viral_short_uses_scene_timed_path():
    import inspect

    source = inspect.getsource(vr.produce_viral_short)
    assert "build_scene_tracks" in source
    assert "render_scene_timed" in source
    assert "_fallback_beats" not in source
    assert not hasattr(vr, "_fallback_beats")  # fictional captions are gone
