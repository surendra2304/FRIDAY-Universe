"""TASK-VYR-045 regression: caption-duplication defect (renders 823/841/861 class).

Renders 823/841/861 shipped with captions doubled/stacked — three layers,
two speech tracks ~1s out of sync — because the only guard was the
pre-render vision gate (TASK-VYR-032, any-beat). VYR-045 adds the
post-render machine gate: sample the RENDERED output, count the caption
tracks, reject when there is more than one.

These tests pin the gate core (pure: no ffmpeg, no vision model). The
frame-sampling + render-path wiring is the follow-up commit.
"""
from __future__ import annotations

from app.services import viral_quality as vq


def _det(y, start, end, text):
    return {"y": y, "start": start, "end": end, "text": text}


def test_single_lower_third_track_passes():
    dets = [_det(0.85, 0.0, 1.0, "hello world"),
            _det(0.86, 1.0, 2.0, "goodbye moon"),
            _det(0.84, 2.0, 3.0, "stay tuned")]
    assert vq.count_caption_tracks(dets) == 1
    assert vq.caption_track_gate(dets) == (True, "single_caption_track")


def test_source_captions_in_second_band_rejected():
    # Our ASS track (lower third) + the source footage own captions (mid-frame).
    dets = [_det(0.85, 0.0, 1.0, "hello world"),
            _det(0.50, 0.0, 1.0, "source caption here"),
            _det(0.85, 1.0, 2.0, "goodbye moon"),
            _det(0.50, 1.0, 2.0, "source caption two")]
    assert vq.count_caption_tracks(dets) == 2
    ok, reason = vq.caption_track_gate(dets)
    assert ok is False
    assert reason == "multiple_caption_tracks:2"


def test_three_layers_rejected():
    # Render 861: three layers stacked.
    dets = [_det(0.85, 0.0, 1.0, "hook line"),
            _det(0.50, 0.0, 1.0, "source line"),
            _det(0.15, 0.0, 1.0, "top hook")]
    assert vq.count_caption_tracks(dets) == 3
    assert vq.caption_track_gate(dets) == (False, "multiple_caption_tracks:3")


def test_out_of_sync_second_track_same_band_rejected():
    # Two speech tracks ~1s out of sync in the same band: overlapping
    # windows carrying different words.
    dets = [_det(0.85, 0.0, 2.0, "hello world"),
            _det(0.85, 1.0, 3.0, "goodbye moon")]
    assert vq.count_caption_tracks(dets) == 2
    assert vq.caption_track_gate(dets) == (False, "multiple_caption_tracks:2")


def test_same_words_redetected_counts_once():
    # Same words sampled twice (overlapping windows, identical text) are
    # one track re-detected, not a duplicate.
    dets = [_det(0.85, 0.0, 2.0, "hello world"),
            _det(0.85, 0.5, 2.0, "hello world")]
    assert vq.count_caption_tracks(dets) == 1
    assert vq.caption_track_gate(dets) == (True, "single_caption_track")


def test_no_captions_visible_rejected():
    assert vq.count_caption_tracks([]) == 0
    assert vq.caption_track_gate([]) == (False, "no_caption_track_visible")


def test_band_edge_jitter_counts_once():
    # Centre-y jitter across samples of the same lower-third track.
    dets = [_det(0.82, 0.0, 1.0, "one"),
            _det(0.85, 1.0, 2.0, "two"),
            _det(0.88, 2.0, 3.0, "three")]
    assert vq.count_caption_tracks(dets) == 1


def test_empty_text_detections_ignored():
    dets = [_det(0.85, 0.0, 1.0, "hello"),
            _det(0.50, 0.0, 1.0, "   ")]
    assert vq.count_caption_tracks(dets) == 1
