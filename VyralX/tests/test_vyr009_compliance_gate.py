"""TASK-VYR-009: the automated compliance gate.

The behaviour these tests pin (owner direction 2026-11-15 + REMIX_POLICY
§5): the per-video compliance checklist is an automated GATE, not an
advisory list stored on the review entry —

* provenance record present and complete, licence reuse-allowed;
* original commentary is the main content (original script, no source
  narration, narration covering the majority of the render);
* sync MEASURED and inside the TASK-VYR-003 thresholds — unmeasured sync
  fails, because "sync by construction" is how the broken era shipped;
* possibly-claimed material stays under 60 seconds;
* no excluded categories (anime/gameplay/sports/Bollywood/movie
  compilations, re-uploads) and no financial advice in the script;
* attribution present, English, declared format recorded.

Headline proof: the gate ACCEPTS the TASK-VYR-003 proof render (the one
objectively measured, well-made short this project has) and REJECTS a
deliberately non-compliant sample on seven independent checks. And the
wiring: produce_remix_short queues a failing render as blocked_compliance
and creates NO publish job for it.

On clean main every test here fails: app.services.compliance_gate does
not exist and produce_remix_short has no gate.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from app.services import compliance_gate as cg
from app.services import remix_flow as rf


# --------------------------------------------------------------------------- #
# The gate's lane/licence sets must never drift from the VYR-004 flow's.
# --------------------------------------------------------------------------- #
def test_gate_sets_mirror_remix_flow():
    assert cg.ALLOWED_LICENSE_CLASSES == rf.ALLOWED_LICENSE_CLASSES
    assert cg.EXCLUDED_LANES == rf.EXCLUDED_LANES
    assert cg.CONTENT_LANES == rf.CONTENT_LANES


# --------------------------------------------------------------------------- #
# A passing baseline candidate (NASA public-domain space short).
# --------------------------------------------------------------------------- #
def _passing_input(**overrides):
    base = dict(
        provenance={
            "record_id": "nasa123",
            "platform": "nasa",
            "title": "Earth from orbit",
            "author": "NASA",
            "source_page_url": "https://images.nasa.gov/details/ABC",
            "media_url": "https://images-assets.nasa.gov/video/ABC/ABC~small.mp4",
            "license_name": "NASA (U.S. Government work)",
            "license_url": "https://www.nasa.gov/nasa-brand-center/images-and-media/",
            "retrieved_at": "2026-11-15T00:00:00+00:00",
            "license_class": "public_domain",
            "allowed": True,
            "decision_reason": "U.S. Government work (NASA) is public domain",
        },
        lane="space_science",
        format_name="one_fact_escalation",
        script="The Sun is a star. It fuses hydrogen into light. Its flares can reach Earth.",
        source_has_speech=False,
        attribution_included=True,
        language="en",
        sync=cg.SyncMeasurements(
            beat_deviations_seconds=[0.0, 0.12, 0.03],
            caption_offset_max_abs_seconds=0.31,
            caption_match_rate=0.93,
            narration_seconds=31.0,
            render_seconds=31.0,
        ),
    )
    base.update(overrides)
    return cg.GateInput(**base)


def _failed_names(verdict):
    return set(verdict.blocking_failures)


def test_passing_candidate_is_accepted():
    verdict = cg.evaluate_compliance_gate(_passing_input())
    assert verdict.passed
    assert verdict.blocking_failures == []
    cg.assert_ready_to_upload(verdict)  # must not raise


# --------------------------------------------------------------------------- #
# One failure at a time
# --------------------------------------------------------------------------- #
def test_missing_or_incomplete_provenance_fails():
    assert "provenance_record" in _failed_names(
        cg.evaluate_compliance_gate(_passing_input(provenance=None))
    )
    incomplete = _passing_input()
    incomplete.provenance = {**incomplete.provenance, "author": ""}
    assert "provenance_record" in _failed_names(cg.evaluate_compliance_gate(incomplete))
    nc = _passing_input()
    nc.provenance = {**nc.provenance, "license_class": "cc_noncommercial", "allowed": False}
    assert "provenance_record" in _failed_names(cg.evaluate_compliance_gate(nc))


def test_unmeasured_sync_fails_closed():
    verdict = cg.evaluate_compliance_gate(_passing_input(sync=None))
    assert "sync_measurements" in _failed_names(verdict)
    partial = _passing_input(
        sync=cg.SyncMeasurements(
            beat_deviations_seconds=[0.0],
            caption_offset_max_abs_seconds=None,  # offsets never measured
            caption_match_rate=0.95,
            narration_seconds=31.0,
            render_seconds=31.0,
        )
    )
    assert "sync_measurements" in _failed_names(cg.evaluate_compliance_gate(partial))


def test_out_of_threshold_sync_fails():
    bad_beats = _passing_input(
        sync=cg.SyncMeasurements(
            beat_deviations_seconds=[0.0, 1.9],
            caption_offset_max_abs_seconds=0.2,
            caption_match_rate=0.95,
            narration_seconds=31.0,
            render_seconds=31.0,
        )
    )
    assert "sync_measurements" in _failed_names(cg.evaluate_compliance_gate(bad_beats))
    bad_captions = _passing_input(
        sync=cg.SyncMeasurements(
            beat_deviations_seconds=[0.0],
            caption_offset_max_abs_seconds=1.5,  # the pre-fix era's max
            caption_match_rate=0.91,
            narration_seconds=31.0,
            render_seconds=31.0,
        )
    )
    assert "sync_measurements" in _failed_names(cg.evaluate_compliance_gate(bad_captions))


def test_commentary_must_be_the_main_content():
    narrated_source = _passing_input(source_has_speech=True)
    assert "commentary_main_content" in _failed_names(
        cg.evaluate_compliance_gate(narrated_source)
    )
    thin_commentary = _passing_input(
        sync=cg.SyncMeasurements(
            beat_deviations_seconds=[0.0],
            caption_offset_max_abs_seconds=0.2,
            caption_match_rate=0.95,
            narration_seconds=10.0,  # 10s of talk over a 40s clip
            render_seconds=40.0,
        )
    )
    assert "commentary_main_content" in _failed_names(
        cg.evaluate_compliance_gate(thin_commentary)
    )
    no_script = _passing_input(script="  ")
    assert "commentary_main_content" in _failed_names(cg.evaluate_compliance_gate(no_script))


def test_claimed_short_over_60s_fails_but_owner_material_is_exempt():
    long_borrowed = _passing_input(
        sync=cg.SyncMeasurements(
            beat_deviations_seconds=[0.0],
            caption_offset_max_abs_seconds=0.2,
            caption_match_rate=0.95,
            narration_seconds=70.0,
            render_seconds=75.0,
        )
    )
    assert "claimed_short_duration" in _failed_names(
        cg.evaluate_compliance_gate(long_borrowed)
    )
    owner = _passing_input(
        sync=cg.SyncMeasurements(
            beat_deviations_seconds=[0.0],
            caption_offset_max_abs_seconds=0.2,
            caption_match_rate=0.95,
            narration_seconds=70.0,
            render_seconds=75.0,
        )
    )
    owner.provenance = {**owner.provenance, "license_class": "owner", "platform": "owner_upload"}
    verdict = cg.evaluate_compliance_gate(owner)
    assert "claimed_short_duration" not in _failed_names(verdict)


def test_excluded_categories_fail():
    for lane in ("anime_compilation", "gameplay_reupload", "sports_compilation",
                 "bollywood_compilation", "movie_compilation"):
        verdict = cg.evaluate_compliance_gate(_passing_input(lane=lane))
        assert "excluded_categories" in _failed_names(verdict), lane
    sneaky = _passing_input(lane="history_facts", format_name="anime_compilation_montage")
    assert "excluded_categories" in _failed_names(cg.evaluate_compliance_gate(sneaky))


def test_finance_advice_in_script_fails_even_in_a_story_lane():
    advice = _passing_input(
        lane="money_story",
        script="Buy now — you should buy this coin today. Guaranteed returns, "
               "double your money with 10x leverage.",
    )
    verdict = cg.evaluate_compliance_gate(advice)
    assert "finance_advice" in _failed_names(verdict)
    story = _passing_input(
        lane="money_story",
        script="He built an empire, then lost it all in one winter. "
               "This is the story of how it happened.",
    )
    assert "finance_advice" not in _failed_names(cg.evaluate_compliance_gate(story))
    lane = _passing_input(lane="finance_advice")
    assert "finance_advice" in _failed_names(cg.evaluate_compliance_gate(lane))


def test_attribution_language_and_format_are_required():
    verdict = cg.evaluate_compliance_gate(
        _passing_input(attribution_included=False, language="hi", format_name="")
    )
    assert {"attribution_present", "language_targeting", "declared_format"} <= _failed_names(verdict)


# --------------------------------------------------------------------------- #
# Measurement helpers (the TASK-VYR-003 recipe)
# --------------------------------------------------------------------------- #
def test_beat_deviations_from_tracks_matches_vyr003_proof_recipe():
    # The proof render's real beats (measure_new_beats.json): segments
    # retimed by segment_timing land exactly on the measured beat audio.
    tracks = {
        "beats": [
            {"segment_seconds": 12.558, "audio_seconds": 11.98,
             "timing": {"factor": 0.954, "pad_seconds": 0.0, "trim_head_seconds": 0.0, "trim_tail_seconds": 0.0}},
            {"segment_seconds": 13.524, "audio_seconds": 10.01,
             "timing": {"factor": 0.7402, "pad_seconds": 0.0, "trim_head_seconds": 0.0, "trim_tail_seconds": 0.0}},
            {"segment_seconds": 12.558, "audio_seconds": 9.0,
             "timing": {"factor": 0.7167, "pad_seconds": 0.0, "trim_head_seconds": 0.0, "trim_tail_seconds": 0.0}},
        ]
    }
    assert cg.beat_deviations_from_tracks(tracks) == [0.0, 0.0, 0.0]
    assert cg.beat_deviations_from_tracks({"beats": []}) is None
    assert cg.beat_deviations_from_tracks(None) is None


def test_caption_sync_metrics_aligned_and_shifted():
    cues = [
        {"start": 0.0, "end": 1.0, "text": "THE SUN IS"},
        {"start": 1.0, "end": 2.0, "text": "A STAR"},
    ]
    heard = [
        {"text": "the", "start": 0.0}, {"text": "sun", "start": 0.33},
        {"text": "is", "start": 0.66}, {"text": "a", "start": 1.0},
        {"text": "star", "start": 1.5},
    ]
    rate, offset = cg.caption_sync_metrics(cues, heard)
    assert rate == 1.0 and offset == pytest.approx(0.0, abs=0.01)
    shifted = [{**w, "start": w["start"] + 2.0} for w in heard]
    rate, offset = cg.caption_sync_metrics(cues, shifted)
    assert rate == 1.0 and offset == pytest.approx(2.0, abs=0.01)
    assert cg.caption_sync_metrics(cues, []) == (None, None)
    assert cg.caption_sync_metrics([], heard) == (None, None)


# --------------------------------------------------------------------------- #
# HEADLINE PROOF — the two samples.
#
# ACCEPT sample basis (every value traceable, nothing invented):
# * sync/durations: the TASK-VYR-003 crew's own measurement JSONs of the
#   proof render (~/workspace/vyr-003/measure_new_beats.json and
#   measure_new_render.json; board evidence for TASK-VYR-003, PR #276):
#   per-beat |segment − voiceover| 0.00s x3; render 30.99s == narration
#   30.99s; captions 83/90 words matched, offset mean −0.025s, max 0.413s.
# * script: the render's actual 90 words, reconstructed from its burned
#   .ass cue stream exactly as the VYR-003 crew reconstructed them.
# * provenance: the render predates the TASK-VYR-004 provenance registry.
#   Its source is the channel's own media-library clip Bqf5iKfRPnc.mp4,
#   documented end-to-end in TASK-VYR-003's production proof; it is
#   recorded here as owner-held library material and NO external licence
#   is claimed for it (none was ever recorded — if the clip were
#   re-sourced through discovery today it would first need a
#   licence-verified record). possibly_claimed is therefore set True
#   explicitly; at 30.99s the render satisfies the <60s rule regardless.
# * attribution: the flow's metadata builder emits the attribution block
#   for every candidate (build_remix_metadata); the proof render itself
#   was never packaged for upload (no publish job, per TASK-VYR-003).
# --------------------------------------------------------------------------- #
VYR003_PROOF_SAMPLE = {
    "provenance": {
        "record_id": "vyr003-proof",
        "platform": "vyralx_media_library",
        "title": "Bqf5iKfRPnc source clip — VyralX media library (viral_sources)",
        "author": "VyralX channel media library",
        "source_page_url": "media/viral_sources/Bqf5iKfRPnc.mp4 (Server 2 VyralX media store)",
        "media_url": "media/viral_sources/Bqf5iKfRPnc.mp4",
        "license_name": "Channel library material (owner-held production asset)",
        "license_url": "",
        "retrieved_at": "2026-11-13 (in the media library by the 2026-11-13 production render)",
        "license_class": "owner",
        "allowed": True,
        "decision_reason": "Proof render predates the TASK-VYR-004 provenance registry; "
                           "source is the channel's own media-library file, documented "
                           "in TASK-VYR-003's production proof. No external licence claimed.",
    },
    "lane": "",
    "format_name": "pipeline_proof",
    "script": (
        "IN A FLASH OF PINK AND A MOTION‑BLURRED FIGURE STRIKES A POSE AGAINST A BLACK "
        "BACKDROP, ITS SILHOUETTE PULSING WITH MYSTERIOUS ENERGY AS THE CAMERA WHIRLS, "
        "CAPTURING EVERY FLEETING RIPPLE.. OF COLOR. SHE STEPS FORWARD IN A BRIGHT PINK "
        "SARI CROWNED BY A WHITE FLORAL HEADPIECE, PLANTS HER HANDS ON HER HIPS AND "
        "FLASHES A TONGUE‑STICKING PLAYFUL FACE THAT CATCHES.. EVERY EYE. THEN SHE "
        "LIFTS BOTH ARMS TO SHOULDER HEIGHT, GRINS WIDE WITH HER MOUTH OPEN, TURNING "
        "THE DARK STAGE INTO A SUDDEN BURST OF JOYFUL FIREWORKS, PURE PINK POWER..."
    ),
    "source_has_speech": False,
    "attribution_included": True,
    "language": "en",
    "possibly_claimed": True,
    "sync": {
        "beat_deviations_seconds": [0.0, 0.0, 0.0],
        "caption_offset_max_abs_seconds": 0.413,
        "caption_match_rate": 83 / 90,
        "narration_seconds": 30.99,
        "render_seconds": 30.99,
    },
}

# REJECT sample: deliberately non-compliant on seven independent checks —
# no provenance record at all, an excluded category, a script that is
# prescriptive financial advice, narration in the source under the
# "commentary", broken-era sync numbers, a 75s runtime with claimed
# material, and no attribution.
NONCOMPLIANT_SAMPLE = {
    "provenance": None,
    "lane": "anime_compilation",
    "format_name": "compilation",
    "category": "anime",
    "script": (
        "Buy now — you should buy this coin today. Guaranteed returns, double "
        "your money in a week. Use 10x leverage and set a stop loss — this "
        "will make you rich, get rich quick."
    ),
    "source_has_speech": True,
    "attribution_included": False,
    "language": "en",
    "sync": {
        "beat_deviations_seconds": [3.42, 3.51, 3.38],
        "caption_offset_max_abs_seconds": 1.5,
        "caption_match_rate": 0.91,
        "narration_seconds": 28.44,
        "render_seconds": 75.0,
    },
}


def test_gate_accepts_the_vyr003_proof_render():
    verdict = cg.evaluate_compliance_gate(cg.GateInput.from_dict(VYR003_PROOF_SAMPLE))
    assert verdict.passed, verdict.to_dict()
    assert verdict.blocking_failures == []
    cg.assert_ready_to_upload(verdict)


def test_gate_rejects_the_deliberately_noncompliant_sample():
    verdict = cg.evaluate_compliance_gate(cg.GateInput.from_dict(NONCOMPLIANT_SAMPLE))
    assert not verdict.passed
    assert {
        "provenance_record",
        "commentary_main_content",
        "sync_measurements",
        "claimed_short_duration",
        "excluded_categories",
        "finance_advice",
        "attribution_present",
    } <= _failed_names(verdict)
    with pytest.raises(cg.ComplianceGateError):
        cg.assert_ready_to_upload(verdict)


# --------------------------------------------------------------------------- #
# Wiring: produce_remix_short enforces the gate.
# The heavy pipeline stages (download / TTS / render / Whisper) are stubbed
# at the module boundary; everything the gate consumes is the same shape
# the real stages produce.
# --------------------------------------------------------------------------- #
_WIRING_SCRIPT = "The Sun is a star. It fuses hydrogen into light. Its flares can reach Earth."
_WIRING_STATE: dict = {"heard_shift": 0.0, "cues": []}


def _fake_tracks():
    beats = []
    cursor = 0.0
    sentences = [
        "The Sun is a star.",
        "It fuses hydrogen into light.",
        "Its flares can reach Earth.",
    ]
    for index, (segment, audio, factor) in enumerate(
        [(12.558, 11.98, 0.954), (13.524, 10.01, 0.7402), (12.558, 9.0, 0.7167)]
    ):
        beats.append({
            "index": index,
            "text": sentences[index],
            "segment_seconds": segment,
            "audio_seconds": audio,
            "target_seconds": audio,
            "timing": {"factor": factor, "pad_seconds": 0.0,
                       "trim_head_seconds": 0.0, "trim_tail_seconds": 0.0},
            "track_start": round(cursor, 3),
        })
        cursor += audio
    return {"beats": beats, "narration_path": Path("narration.wav"), "total_seconds": 30.99}


def _fake_cues(tracks, script):
    cues = [
        {"start": b["track_start"], "end": b["track_start"] + b["audio_seconds"], "text": b["text"]}
        for b in tracks["beats"]
    ]
    _WIRING_STATE["cues"] = cues
    return cues


def _fake_heard(_path):
    heard = []
    for cue in _WIRING_STATE["cues"]:
        words = cue["text"].split()
        span = cue["end"] - cue["start"]
        for i, word in enumerate(words):
            heard.append({
                "text": word,
                "start": cue["start"] + span * (i / len(words)) + _WIRING_STATE["heard_shift"],
            })
    return heard


def _install_pipeline_stubs(monkeypatch, tmp_path):
    vr = types.ModuleType("app.services.viral_remix")
    vr.VOICE_BY_CATEGORY = {}
    vr.DEFAULT_VOICE = "en-US-TestNeural"
    vr.build_scene_tracks = lambda *a, **k: _fake_tracks()
    vr.build_commentary_cues = _fake_cues
    vr.render_scene_timed = lambda *a, **k: None
    vr._decode_to_wav = lambda *a, **k: Path("probe.wav")
    vr._whisper_words = _fake_heard
    monkeypatch.setitem(sys.modules, "app.services.viral_remix", vr)

    sa = types.ModuleType("app.services.source_analysis")

    class _Probe:
        def __init__(self, duration, has_audio=False):
            self.duration = duration
            self.has_audio = has_audio
            self.width = 1080
            self.height = 1920

    sa.probe_media = lambda p: _Probe(38.64) if Path(p).name == "source.mp4" else _Probe(30.99)
    sa.detect_speech = lambda p: types.SimpleNamespace(has_speech=False, speech_seconds=0.0)
    monkeypatch.setitem(sys.modules, "app.services.source_analysis", sa)

    settings = types.SimpleNamespace(
        data_dir=tmp_path,
        render_dir=tmp_path / "renders",
        media_dir=tmp_path / "media",
        prepare_directories=lambda: None,
    )
    monkeypatch.setattr(rf, "get_settings", lambda: settings)
    monkeypatch.setattr(
        rf, "download_media", lambda record, dest_dir: Path(dest_dir) / "source.mp4"
    )
    return settings


def _nasa_record():
    return rf.ProvenanceRecord(
        platform="nasa",
        title="Earth from orbit",
        author="NASA",
        source_page_url="https://images.nasa.gov/details/ABC",
        media_url="https://images-assets.nasa.gov/video/ABC/ABC~small.mp4",
        license_name="NASA (U.S. Government work)",
        license_url="https://www.nasa.gov/nasa-brand-center/images-and-media/",
        retrieved_at="2026-11-15T00:00:00+00:00",
        license_class="public_domain",
        allowed=True,
        decision_reason="U.S. Government work (NASA) is public domain",
    )


def test_produce_passes_gate_and_creates_publish_job(tmp_path, monkeypatch):
    _install_pipeline_stubs(monkeypatch, tmp_path)
    _WIRING_STATE["heard_shift"] = 0.0
    published = []
    monkeypatch.setattr(
        rf, "_persist_review_job", lambda *a, **k: published.append(a) or 999
    )
    queue = tmp_path / "queue.jsonl"
    result = rf.produce_remix_short(
        _nasa_record(), _WIRING_SCRIPT, title="The Sun",
        lane="space_science", db=object(), queue_path=queue,
    )
    assert result["status"] == "PENDING_REVIEW"
    assert result["compliance_gate"]["passed"] is True
    assert result["publish_job_id"] == 999 and len(published) == 1
    entry = rf.list_review_queue(queue)[0]
    assert entry["status"] != "blocked_compliance"
    assert entry["compliance_gate"]["passed"] is True


def test_produce_blocks_out_of_sync_render_and_creates_no_publish_job(tmp_path, monkeypatch):
    _install_pipeline_stubs(monkeypatch, tmp_path)
    _WIRING_STATE["heard_shift"] = 2.0  # captions land 2s after the audio
    published = []
    monkeypatch.setattr(
        rf, "_persist_review_job", lambda *a, **k: published.append(a) or 999
    )
    queue = tmp_path / "queue.jsonl"
    result = rf.produce_remix_short(
        _nasa_record(), _WIRING_SCRIPT, title="The Sun",
        lane="space_science", db=object(), queue_path=queue,
    )
    assert result["status"] == "BLOCKED_COMPLIANCE"
    assert result["compliance_gate"]["passed"] is False
    assert "sync_measurements" in result["compliance_gate"]["blocking_failures"]
    assert "publish_job_id" not in result and published == []
    entry = rf.list_review_queue(queue)[0]
    assert entry["status"] == "blocked_compliance"
