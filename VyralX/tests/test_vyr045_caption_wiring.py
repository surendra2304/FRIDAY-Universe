"""TASK-VYR-045 wiring: dense frame sampling + render-path gate.

The gate core (count_caption_tracks / caption_track_gate) is pinned in
test_vyr045_caption_dedup.py. This file pins the wiring around it:

* the sampler samples the render at least every 0.5s and turns the
  vision reply into detections (zones -> bands, 0.5s windows);
* the sampler fails closed (None) when a frame will not extract, a
  vision call fails, or the reply is unusable;
* check_render_caption_tracks passes a single-track render and
  rejects a doubled one;
* both produce paths run the gate after the render and before any
  persistence: a doubled render is SKIPPED with the exact reason and
  no publish job is created; a clean render proceeds.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

from app.models import PublishJob
from app.services import scene_analysis
from app.services import viral_framing
from app.services import viral_quality as vq
from app.services import viral_remix as vr


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _make_bed(tmp_path, name="bed.wav", frequency=440, seconds=1.0):
    bed = tmp_path / name
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostdin", "-y",
         "-f", "lavfi", "-i", f"sine=frequency={frequency}:duration={seconds}",
         "-c:a", "pcm_s16le", str(bed)],
        capture_output=True, check=True,
    )
    return bed


def _beat(index, start, end, audio, factor=1.0):
    return {
        "index": index,
        "start": start,
        "end": end,
        "segment_seconds": round(end - start, 3),
        "audio_seconds": audio,
        "target_seconds": audio,
        "timing": {
            "factor": factor,
            "trim_head_seconds": 0.0,
            "trim_tail_seconds": 0.0,
            "pad_seconds": 0.0,
        },
    }


def _clean_payload():
    return {
        "beats": [{
            "setting": "running track", "time_of_day": "day",
            "subjects": [], "objects": ["mascot costume"],
            "summary": "A mascot races a runner down the track.",
            "captions_present": False,
        } for _ in range(3)],
        "event_arc": "the race is run",
        "static": False,
    }


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
        # A real session flushes on commit, assigning ids; mirror that so
        # publish_job_id / project_id are visible in the result dict.
        self.flush()


def _candidate():
    return SimpleNamespace(
        video_id="Pfxp6mysc90",
        title="Can You Beat The Fastest Mascot?",
        channel="BoltMotivation",
        duration=21.0,
        category="SPORTS",
        hook="WAIT FOR IT",
        license="",
    )


def _render(tmp_path):
    """A render file that exists (the sampler refuses a missing file)."""
    path = tmp_path / "render.mp4"
    path.touch()
    return path


def _wire_common(monkeypatch, tmp_path):
    monkeypatch.setattr(vr, "download_audio_only",
                        lambda video_id, dest: tmp_path / "probe.webm")
    monkeypatch.setattr(vr, "detect_speech",
                        lambda path: SimpleNamespace(
                            has_speech=False, text="", speech_seconds=0.0))
    monkeypatch.setattr(vr, "download_source_video",
                        lambda video_id, dest: tmp_path / "source.mp4")
    monkeypatch.setattr(vr, "probe_media", lambda path: SimpleNamespace(
        duration=21.0, width=1080, height=1920, has_audio=True))
    monkeypatch.setattr(vr, "existing_upload_titles", lambda db: set())


def _fake_settings(tmp_path):
    return SimpleNamespace(
        prepare_directories=lambda: None,
        render_dir=tmp_path / "renders",
        media_dir=tmp_path / "media",
        ffmpeg_bin="ffmpeg",
        viral_quality_gates_enabled=True,
        viral_music_bed_enabled=True,
        viral_max_source_seconds=58.0,
        autonomous_publish_privacy="unlisted",
        crosspost_export_enabled=False,
    )


class _FakeVisionResponse:
    def __init__(self, text):
        self._text = text

    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": self._text}}]}


class _FakeExtract:
    """Stub frame extractor: records sample times, writes a dummy JPEG."""

    def __init__(self, fail_on=None):
        self.calls: list[float] = []
        self.fail_on = fail_on

    def __call__(self, source, seconds, dest):
        self.calls.append(round(float(seconds), 3))
        if self.fail_on is not None and len(self.calls) == self.fail_on:
            return False
        dest.write_bytes(b"fake-jpeg-bytes")
        return True


class _FakeVision:
    """Stub vision transport: records batch sizes/times, replies from captions_fn."""

    def __init__(self, captions_fn):
        self.calls: list[dict] = []
        self.captions_fn = captions_fn

    def __call__(self, body, *, context=None):
        content = body["messages"][0]["content"]
        images = [c for c in content if c.get("type") == "image_url"]
        times = []
        for part in content:
            if part.get("type") == "text" and part["text"].startswith("Frame "):
                times.append(float(part["text"].split("t=")[1].rstrip("s):")))
        self.calls.append({"images": len(images), "times": times, "context": context})
        frames = [
            {"frame": i, "captions": self.captions_fn(i, t)}
            for i, t in enumerate(times)
        ]
        return _FakeVisionResponse(json.dumps({"frames": frames}))


def _single_track_captions(i, t):
    return [{"text": "hello world", "zone": "bottom"}]


def _doubled_captions(i, t):
    return [
        {"text": "hello world", "zone": "bottom"},
        {"text": "source caption here", "zone": "middle"},
    ]


# --------------------------------------------------------------------------- #
# coerce: vision reply -> detections
# --------------------------------------------------------------------------- #
def test_coerce_maps_zones_to_bands_and_windows():
    payload = {"frames": [
        {"frame": 0, "captions": [
            {"text": "hello world", "zone": "bottom"},
            {"text": "source line", "zone": "middle"},
            {"text": "top hook", "zone": "top"},
        ]},
        {"frame": 1, "captions": [{"text": "goodbye moon", "zone": "bottom"}]},
    ]}
    dets = scene_analysis._coerce_caption_detections(payload, [0.25, 0.75])
    assert dets == [
        {"y": 0.85, "start": 0.0, "end": 0.5, "text": "hello world"},
        {"y": 0.50, "start": 0.0, "end": 0.5, "text": "source line"},
        {"y": 0.15, "start": 0.0, "end": 0.5, "text": "top hook"},
        {"y": 0.85, "start": 0.5, "end": 1.0, "text": "goodbye moon"},
    ]


def test_coerce_skips_malformed_lines():
    payload = {"frames": [
        {"frame": 0, "captions": [
            {"text": "hello", "zone": "bottom"},
            {"text": "   ", "zone": "bottom"},
            {"text": "nowhere", "zone": "sideways"},
            {"text": "no zone"},
            "not a dict",
        ]},
        {"frame": 99, "captions": [{"text": "out of range", "zone": "bottom"}]},
        "not a dict",
    ]}
    dets = scene_analysis._coerce_caption_detections(payload, [0.25])
    assert dets == [{"y": 0.85, "start": 0.0, "end": 0.5, "text": "hello"}]


def test_coerce_empty_reply_is_no_detections():
    assert scene_analysis._coerce_caption_detections({"frames": []}, [0.25]) == []
    assert scene_analysis._coerce_caption_detections({}, [0.25]) == []


# --------------------------------------------------------------------------- #
# prune: one visual line reported twice in a frame is one detection
# --------------------------------------------------------------------------- #
def test_prune_drops_substring_duplicate_in_same_frame():
    # Real render framed-bhw0Cxw9WGs, frame 0: the model read the bottom
    # caption twice — "TODAY" in the middle zone and the full line at
    # the bottom. That is one track, not two.
    dets = scene_analysis._prune_caption_detections([
        {"y": 0.50, "start": 0.0, "end": 0.5, "text": "TODAY"},
        {"y": 0.85, "start": 0.0, "end": 0.5,
         "text": "TODAY WE'RE GONNA FIND OUT"},
    ])
    assert dets == [
        {"y": 0.85, "start": 0.0, "end": 0.5,
         "text": "TODAY WE'RE GONNA FIND OUT"},
    ]


def test_prune_keeps_distinct_lines_same_frame():
    # A real doubled track shows different wording in the same frame.
    dets = scene_analysis._prune_caption_detections([
        {"y": 0.50, "start": 0.0, "end": 0.5, "text": "WATCH A CLASSIC"},
        {"y": 0.85, "start": 0.0, "end": 0.5,
         "text": "TODAY WE'RE GONNA FIND OUT"},
    ])
    assert len(dets) == 2


def test_prune_keeps_substring_in_different_frame():
    # Out-of-sync tracks differ in other frames; dedup is per-frame only.
    dets = scene_analysis._prune_caption_detections([
        {"y": 0.50, "start": 0.0, "end": 0.5, "text": "TODAY"},
        {"y": 0.85, "start": 0.5, "end": 1.0,
         "text": "TODAY WE'RE GONNA FIND OUT"},
    ])
    assert len(dets) == 2


def test_prune_drops_middle_subsequence_in_same_frame():
    # Live shape: "WE'RE GONNA FIND" sits in the middle of the bottom
    # line's words — a fragment read, not a second track.
    dets = scene_analysis._prune_caption_detections([
        {"y": 0.50, "start": 0.5, "end": 1.0, "text": "WE'RE GONNA FIND"},
        {"y": 0.85, "start": 0.5, "end": 1.0,
         "text": "TODAY WE'RE GONNA FIND OUT"},
    ])
    assert dets == [
        {"y": 0.85, "start": 0.5, "end": 1.0,
         "text": "TODAY WE'RE GONNA FIND OUT"},
    ]


def test_segments_merge_same_text_and_drop_short_ones():
    # Three frames of one line merge to a 1.5s segment; a lone
    # half-second line in another band is a stray read, not a track.
    dets = scene_analysis._segments_from_detections([
        {"y": 0.85, "start": 0.0, "end": 0.5, "text": "hello world"},
        {"y": 0.85, "start": 0.5, "end": 1.0, "text": "hello world"},
        {"y": 0.85, "start": 1.0, "end": 1.5, "text": "hello world"},
        {"y": 0.50, "start": 1.0, "end": 1.5, "text": "OUT WHAT HAPPENS"},
    ], 0.5)
    assert dets == [
        {"y": 0.85, "start": 0.0, "end": 1.5, "text": "hello world"},
    ]


# --------------------------------------------------------------------------- #
# sampler: density, batching, fail-closed
# --------------------------------------------------------------------------- #
def test_sampler_samples_every_half_second(tmp_path):
    extract = _FakeExtract()
    vision = _FakeVision(_single_track_captions)
    dets = scene_analysis.sample_render_caption_detections(
        _render(tmp_path), 2.0,
        extract_frame=extract, vision_request=vision, pace_seconds=0,
    )
    assert extract.calls == [0.25, 0.75, 1.25, 1.75]
    # Four frames of one unchanging line merge into one segment.
    assert dets == [
        {"y": 0.85, "start": 0.0, "end": 2.0, "text": "hello world"},
    ]


def test_sampler_batches_three_frames_per_request(tmp_path):
    extract = _FakeExtract()
    vision = _FakeVision(_single_track_captions)
    dets = scene_analysis.sample_render_caption_detections(
        _render(tmp_path), 20.0,
        extract_frame=extract, vision_request=vision, pace_seconds=0,
    )
    assert len(extract.calls) == 40
    assert [c["images"] for c in vision.calls] == [3] * 13 + [1]
    # 40 frames of one unchanging line merge into a single segment.
    assert dets == [
        {"y": 0.85, "start": 0.0, "end": 20.0, "text": "hello world"},
    ]
    assert all(c["context"] == "caption_detection" for c in vision.calls)


def test_sampler_returns_none_when_extraction_fails(tmp_path):
    extract = _FakeExtract(fail_on=2)
    vision = _FakeVision(_single_track_captions)
    assert scene_analysis.sample_render_caption_detections(
        _render(tmp_path), 2.0,
        extract_frame=extract, vision_request=vision, pace_seconds=0,
    ) is None


def test_sampler_returns_none_when_vision_fails(tmp_path):
    def _boom(body, *, context=None):
        raise RuntimeError("groq down")

    assert scene_analysis.sample_render_caption_detections(
        _render(tmp_path), 2.0,
        extract_frame=_FakeExtract(), vision_request=_boom, pace_seconds=0,
    ) is None


def test_sampler_returns_none_on_unusable_reply(tmp_path):
    def _garbage(body, *, context=None):
        return _FakeVisionResponse("not json at all {{")

    assert scene_analysis.sample_render_caption_detections(
        _render(tmp_path), 2.0,
        extract_frame=_FakeExtract(), vision_request=_garbage, pace_seconds=0,
    ) is None


def test_sampler_parses_fenced_reply(tmp_path):
    # The model wraps the JSON in a ```json fenced block; that must
    # parse, not fail closed as unmeasured.
    def _fenced(body, *, context=None):
        payload = {"frames": [
            {"frame": 0, "captions": [{"text": "hello world", "zone": "bottom"}]},
            {"frame": 1, "captions": [{"text": "hello world", "zone": "bottom"}]},
            {"frame": 2, "captions": [{"text": "hello world", "zone": "bottom"}]},
        ]}
        return _FakeVisionResponse("```json\n" + json.dumps(payload) + "\n```")

    # 1.5s -> 3 samples in a single batch, so the stub's 3-frame reply
    # maps exactly once; the three identical frames merge to one segment.
    dets = scene_analysis.sample_render_caption_detections(
        _render(tmp_path), 1.5,
        extract_frame=_FakeExtract(), vision_request=_fenced, pace_seconds=0,
    )
    assert dets == [
        {"y": 0.85, "start": 0.0, "end": 1.5, "text": "hello world"},
    ]


def test_sampler_repairs_dropped_final_brace(tmp_path):
    # Live reply from the real Nov 21 render: the model dropped the
    # outer object's closing "}" (reply ends "...]}]"). The sampler
    # repairs it instead of failing closed.
    def _truncated(body, *, context=None):
        payload = {"frames": [
            {"frame": 0, "captions": [{"text": "hello world", "zone": "bottom"}]},
            {"frame": 1, "captions": [{"text": "hello world", "zone": "bottom"}]},
            {"frame": 2, "captions": [{"text": "hello world", "zone": "bottom"}]},
        ]}
        text = json.dumps(payload)[:-1]  # drop the final "}"
        return _FakeVisionResponse(text)

    dets = scene_analysis.sample_render_caption_detections(
        _render(tmp_path), 1.5,
        extract_frame=_FakeExtract(), vision_request=_truncated, pace_seconds=0,
    )
    assert dets == [
        {"y": 0.85, "start": 0.0, "end": 1.5, "text": "hello world"},
    ]


def test_sampler_drops_single_frame_stray_reads(tmp_path):
    # Exact shape of the live reply from the real Nov 21 render:
    # the bottom line holds steady for 3 frames while the middle band
    # shows a fragment in one frame ("WE'RE GONNA FIND", a subsequence
    # of the bottom line — pruned) and a stray line in another
    # ("OUT WHAT HAPPENS" — kept by prune, dropped as a sub-second
    # segment). Only the real caption track survives.
    by_frame = {
        0: [{"text": "TODAY WE'RE GONNA FIND OUT", "zone": "bottom"}],
        1: [{"text": "WE'RE GONNA FIND", "zone": "middle"},
            {"text": "TODAY WE'RE GONNA FIND OUT", "zone": "bottom"}],
        2: [{"text": "OUT WHAT HAPPENS", "zone": "middle"},
            {"text": "TODAY WE'RE GONNA FIND OUT", "zone": "bottom"}],
    }
    vision = _FakeVision(lambda i, t: by_frame[i])
    dets = scene_analysis.sample_render_caption_detections(
        _render(tmp_path), 1.5,
        extract_frame=_FakeExtract(), vision_request=vision, pace_seconds=0,
    )
    assert dets == [
        {"y": 0.85, "start": 0.0, "end": 1.5,
         "text": "TODAY WE'RE GONNA FIND OUT"},
    ]


def test_sampler_missing_file_is_none(tmp_path):
    assert scene_analysis.sample_render_caption_detections(
        tmp_path / "no-such-render.mp4", 20.0,
        extract_frame=_FakeExtract(),
        vision_request=_FakeVision(_single_track_captions), pace_seconds=0,
    ) is None


# --------------------------------------------------------------------------- #
# check_render_caption_tracks: verdict helper
# --------------------------------------------------------------------------- #
def test_check_passes_single_track(tmp_path):
    ok, reason, dets = vr.check_render_caption_tracks(
        tmp_path / "render.mp4", 2.0,
        sampler=lambda *a, **k: [
            {"y": 0.85, "start": 0.0, "end": 1.0, "text": "hello"},
            {"y": 0.85, "start": 1.0, "end": 2.0, "text": "goodbye"},
        ],
    )
    assert (ok, reason) == (True, "single_caption_track")
    assert dets is not None and len(dets) == 2


def test_check_rejects_doubled_render(tmp_path):
    ok, reason, dets = vr.check_render_caption_tracks(
        tmp_path / "render.mp4", 2.0,
        sampler=lambda *a, **k: [
            {"y": 0.85, "start": 0.0, "end": 1.0, "text": "hello"},
            {"y": 0.50, "start": 0.0, "end": 1.0, "text": "source line"},
        ],
    )
    assert (ok, reason) == (False, "multiple_caption_tracks:2")


def test_check_unmeasured_is_fail_closed(tmp_path):
    ok, reason, dets = vr.check_render_caption_tracks(
        tmp_path / "render.mp4", 2.0, sampler=lambda *a, **k: None,
    )
    assert (ok, reason, dets) == (False, "caption_gate_unmeasured", None)


# --------------------------------------------------------------------------- #
# commentary path: gate runs after the render, before persistence
# --------------------------------------------------------------------------- #
def _drive_commentary(monkeypatch, tmp_path, *, gate):
    monkeypatch.setattr(vr, "get_settings", lambda: _fake_settings(tmp_path))
    _wire_common(monkeypatch, tmp_path)
    monkeypatch.setattr(vq, "measure_event_arc", lambda *a, **k: None)
    record = scene_analysis._coerce_record(_clean_payload())
    monkeypatch.setattr(vr, "analyze_scene", lambda *a, **k: record)
    monkeypatch.setattr(vr, "generate_editorial", lambda *a, **k: {
        "commentary": "A mascot races a runner down the track.",
        "title": "Mascot Race",
        "description": "A mascot races.",
        "hashtags": "",
    })
    monkeypatch.setattr(vq, "check_consistency", lambda **k: [])
    monkeypatch.setattr(vq, "check_structure", lambda **k: [])
    monkeypatch.setattr(vq, "check_script_length", lambda **k: [])
    monkeypatch.setattr(vr, "build_scene_tracks", lambda *a, **k: {
        "beats": [_beat(0, 0.0, 21.0, 21.0)],
        "narration_path": tmp_path / "narration.wav",
        "total_seconds": 21.0,
    })
    monkeypatch.setattr(vr, "_last_sentence_coverage", lambda *a, **k: 1.0)
    monkeypatch.setattr(vr, "build_commentary_cues", lambda *a, **k: [
        {"start": 0.0, "end": 2.0, "text": "HELLO WORLD"},
    ])
    monkeypatch.setattr(
        "app.services.viral_bgm.prepare_music_bed",
        lambda *a, **k: (_make_bed(tmp_path), "synth-bed"),
    )

    def _fake_render(*args, **kwargs):
        out = Path(args[1])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.touch()
        return out

    monkeypatch.setattr(vr, "render_scene_timed", _fake_render)
    monkeypatch.setattr(vr, "check_render_caption_tracks", gate)
    monkeypatch.setattr(vr, "build_metadata", lambda *a, **k: {
        "title": "T", "description": "D", "tags": [], "category_id": "",
    })
    session = _FakeSession()
    result = vr.produce_viral_short(
        _candidate(), session, publish=True, hold_for_review=True,
    )
    return result, session


def test_produce_rejects_doubled_render(monkeypatch, tmp_path):
    doubled = [
        {"y": 0.85, "start": 0.0, "end": 1.0, "text": "hello"},
        {"y": 0.50, "start": 0.0, "end": 1.0, "text": "source line"},
    ]
    result, session = _drive_commentary(
        monkeypatch, tmp_path,
        gate=lambda *a, **k: (False, "multiple_caption_tracks:2", doubled),
    )
    assert result["status"] == "SKIPPED"
    assert result["reason"] == "multiple_caption_tracks:2"
    assert result["caption_tracks"] == 2
    assert session.added == []  # nothing persisted, no publish job


def test_produce_passes_single_track_render(monkeypatch, tmp_path):
    single = [
        {"y": 0.85, "start": 0.0, "end": 1.0, "text": "hello"},
        {"y": 0.85, "start": 1.0, "end": 2.0, "text": "goodbye"},
    ]
    result, session = _drive_commentary(
        monkeypatch, tmp_path,
        gate=lambda *a, **k: (True, "single_caption_track", single),
    )
    assert result["status"] == "QUEUED_FOR_PUBLISH"
    assert result["publish_job_id"] is not None
    assert any(isinstance(o, PublishJob) for o in session.added)


# --------------------------------------------------------------------------- #
# framed path: same gate, same placement
# --------------------------------------------------------------------------- #
def _drive_framed(monkeypatch, tmp_path, *, gate):
    monkeypatch.setattr(
        viral_framing, "get_settings", lambda: _fake_settings(tmp_path))
    monkeypatch.setattr(vr, "download_audio_only",
                        lambda video_id, dest: tmp_path / "probe.webm")
    monkeypatch.setattr(vr, "detect_speech", lambda path: SimpleNamespace(
        has_speech=True,
        cues=[{"start": 0.0, "end": 1.0, "text": "go"}],
        text="go go go",
    ))
    monkeypatch.setattr(vr, "download_source_video",
                        lambda video_id, dest: tmp_path / "source.mp4")

    def _probe(path):
        name = str(path)
        duration = 2.0 if name.endswith((".mp3", ".wav")) else 30.0
        return SimpleNamespace(
            duration=duration, width=1080, height=1920, has_audio=True)

    monkeypatch.setattr(vr, "probe_media", _probe)
    monkeypatch.setattr(vr, "existing_upload_titles", lambda db: set())
    monkeypatch.setattr(viral_framing, "_cut_excerpt",
                        lambda *a, **k: tmp_path / "excerpt.mp4")
    monkeypatch.setattr(viral_framing, "measure_tail_trim",
                        lambda *a, **k: (None, ""))
    monkeypatch.setattr(vq, "measure_event_arc", lambda *a, **k: None)
    record = scene_analysis._coerce_record(_clean_payload())
    monkeypatch.setattr(viral_framing, "analyze_scene", lambda *a, **k: record)
    monkeypatch.setattr(viral_framing, "generate_framing", lambda *a, **k: {
        "hook": "WAIT FOR IT", "payoff": "HE DID IT",
        "title": "T", "description": "D",
    })
    monkeypatch.setattr(viral_framing, "framing_violations", lambda *a, **k: [])
    monkeypatch.setattr(vr, "synthesize_commentary",
                        lambda *a, **k: (tmp_path / "hook.mp3", []))
    monkeypatch.setattr(viral_framing, "framed_cues", lambda *a, **k: [
        {"start": 0.0, "end": 2.0, "text": "GO"},
    ])
    monkeypatch.setattr(
        "app.services.viral_bgm.prepare_music_bed",
        lambda *a, **k: (_make_bed(tmp_path), "synth-bed"),
    )

    def _fake_render(*args, **kwargs):
        out = Path(args[1])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.touch()
        return out

    monkeypatch.setattr(viral_framing, "render_framed", _fake_render)
    monkeypatch.setattr(vr, "check_render_caption_tracks", gate)
    monkeypatch.setattr(vr, "build_metadata", lambda *a, **k: {
        "title": "T", "description": "D", "tags": [], "category_id": "",
    })
    session = _FakeSession()
    candidate = _candidate()
    result = viral_framing.produce_framed_short(
        candidate, session, publish=True, hold_for_review=True,
    )
    return result, session


def test_framed_rejects_doubled_render(monkeypatch, tmp_path):
    doubled = [
        {"y": 0.85, "start": 0.0, "end": 1.0, "text": "hello"},
        {"y": 0.50, "start": 0.0, "end": 1.0, "text": "source line"},
    ]
    result, session = _drive_framed(
        monkeypatch, tmp_path,
        gate=lambda *a, **k: (False, "multiple_caption_tracks:2", doubled),
    )
    assert result["status"] == "SKIPPED"
    assert result["reason"] == "multiple_caption_tracks:2"
    assert result["caption_tracks"] == 2
    assert session.added == []  # nothing persisted, no publish job


def test_framed_passes_single_track_render(monkeypatch, tmp_path):
    single = [
        {"y": 0.85, "start": 0.0, "end": 1.0, "text": "hello"},
        {"y": 0.85, "start": 1.0, "end": 2.0, "text": "goodbye"},
    ]
    result, session = _drive_framed(
        monkeypatch, tmp_path,
        gate=lambda *a, **k: (True, "single_caption_track", single),
    )
    assert result["status"] == "QUEUED_FOR_PUBLISH"
    assert result["publish_job_id"] is not None
    assert any(isinstance(o, PublishJob) for o in session.added)
