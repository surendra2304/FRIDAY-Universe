"""IG2 · B7-C1: MoneyPrinterTurbo producer lane for the viral autopilot.

The lane is an adapter: brief -> MPT CLI -> artefacts -> the TASK-VYR-014
quality gates. These tests pin the three properties the packet demands:

* the invocation is the free-only one (the brief's own script is always
  supplied so MPT's LLM is never invoked, the stock source is a free
  tier, no MPT music, stop at the render stage);
* preflight fails closed (cross-posting on, paid TTS, missing free
  stock keys, ungated mode, unprovisioned MPT home — all refuse);
* a package MPT "produced" goes through the real gates: invented copy
  is rejected with the native reason strings, grounded copy passes,
  and a pass is GATED_PASS — never a publish job.

On clean main every test here fails: app.services.mpt_lane does not
exist and Settings has no viral_producer_lane.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services import mpt_lane as ml
from app.services import viral_quality as vq
from app.services import viral_remix as vr


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #
RECORD = {
    "beats": [
        {
            "setting": "sunny garden with green grass",
            "time_of_day": "day",
            "subjects": [
                {"hair": "orange fur", "clothing": "", "posture": "sitting",
                 "action": "sitting on the grass beside a red ball",
                 "emotion": "calm", "eyes": "open"},
            ],
            "objects": ["red ball", "grass"],
            "summary": "An orange cat sits on the grass beside a red ball "
                       "in a sunny garden.",
        },
        {
            "setting": "same sunny garden",
            "time_of_day": "day",
            "subjects": [
                {"hair": "orange fur", "clothing": "", "posture": "standing",
                 "action": "chasing the red ball across the grass",
                 "emotion": "excited", "eyes": "open"},
            ],
            "objects": ["red ball", "grass"],
            "summary": "The cat stands up and chases the red ball across "
                       "the grass.",
        },
        {
            "setting": "same sunny garden",
            "time_of_day": "day",
            "subjects": [
                {"hair": "orange fur", "clothing": "", "posture": "lying",
                 "action": "lying on the grass holding the red ball",
                 "emotion": "calm", "eyes": "open"},
            ],
            "objects": ["red ball", "grass"],
            "summary": "The cat lies on the grass holding the red ball "
                       "between its paws.",
        },
    ],
    "event_arc": "The cat chases the red ball and catches it.",
    "static": False,
}

# Written from the record's own facts; ~40 words for a 20 s render.
GROUNDED_SCRIPT = (
    "An orange cat sits on the grass beside a red ball. "
    "The cat stands up and chases it across the sunny garden. "
    "It races over the lawn while the ball rolls ahead. "
    "The cat lies on the grass holding the red ball."
)

# The job-761 failure shape: invented hair, an unseen colour, a time of
# day the footage never shows.
INVENTED_SCRIPT = (
    "A pink-haired woman panics under the moonlight. "
    "She screams at the purple dinosaur crossing the road. "
    "Everyone runs away in terror from the monster. "
    "The nightmare ends when the dinosaur vanishes forever."
)

GOOD_CONFIG = """
[app]
pexels_api_keys = ["free-tier-key"]
pixabay_api_keys = ["free-tier-key"]
upload_post_enabled = false
upload_post_auto_upload = false
subtitle_provider = "edge"

[ui]
tts_server = "azure-tts-v1"
"""


def _mpt_home(tmp_path: Path, config: str = GOOD_CONFIG) -> Path:
    home = tmp_path / "mpt"
    home.mkdir(parents=True, exist_ok=True)
    (home / "cli.py").write_text("# fake MPT checkout\n", encoding="utf-8")
    (home / "config.toml").write_text(config, encoding="utf-8")
    return home


def _settings(tmp_path: Path, home: Path, **overrides):
    base = dict(
        viral_producer_lane="mpt",
        viral_mpt_lane_enabled=True,
        viral_quality_gates_enabled=True,
        viral_mpt_home=str(home),
        viral_mpt_video_source="pexels",
        viral_mpt_voice_name="",
        viral_mpt_python_cmd="",
        viral_mpt_timeout_seconds=60,
        viral_mpt_briefs_path="",
        ffmpeg_bin="ffmpeg",
        ffprobe_bin="ffprobe",
        render_dir=tmp_path / "renders",
        data_dir=tmp_path / "data",
        media_dir=tmp_path / "media",
        render_max_memory_mb=512,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _brief(**overrides) -> ml.MPTBrief:
    base = dict(topic="A cat chases a ball", script=GROUNDED_SCRIPT,
                title="Cat catches the ball", description="")
    base.update(overrides)
    return ml.MPTBrief(**base)


def _fake_runner(record: dict, *, peak_rss_mb: float = 128.0,
                 returncode: int = 0, reported_script: str | None = None):
    """Stand-in for the MPT CLI: materialises a task dir the way the
    real CLI does (storage/tasks/<task-id>/final-1.mp4 + subtitle.srt)
    and prints one JSON object."""
    def run(cmd, *, cwd, timeout):
        record["cmd"] = cmd
        record["cwd"] = cwd
        task_id = cmd[cmd.index("--task-id") + 1]
        task_dir = Path(cwd) / "storage" / "tasks" / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        video = task_dir / "final-1.mp4"
        video.write_bytes(b"\x00\x00\x00\x18ftypmp42-fake-render")
        (task_dir / "subtitle.srt").write_text(
            "1\n00:00:00,000 --> 00:00:03,000\nAn orange cat\n",
            encoding="utf-8")
        payload = {"task_id": task_id, "videos": [str(video)]}
        if reported_script is not None:
            payload["script"] = reported_script
        return ml.RunnerResult(returncode, json.dumps(payload), "",
                               peak_rss_mb)
    return run


def _wire_gates(monkeypatch, *, record=RECORD, arc=None):
    """Patch only the media plumbing; the gate functions stay real."""
    if arc is None:
        arc = vq.EventArc(samples=10, mean_change=0.2, max_change=0.5,
                          static_ratio=0.1, peak_position=0.8)
    monkeypatch.setattr(vq, "measure_event_arc", lambda *a, **k: arc)
    monkeypatch.setattr(ml, "analyze_scene", lambda *a, **k: record)
    monkeypatch.setattr(ml, "probe_media",
                        lambda path: SimpleNamespace(
                            duration=20.0, width=1080, height=1920,
                            has_audio=True))
    monkeypatch.setattr(vr, "_last_sentence_coverage",
                        lambda script, path: 1.0)
    real_run = ml.subprocess.run

    def fake_ffmpeg(cmd, **kwargs):
        if "-vn" in cmd:  # the narration-extraction call in the fit gate
            Path(cmd[-1]).write_bytes(b"RIFF-fake-wav")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        return real_run(cmd, **kwargs)

    monkeypatch.setattr(ml.subprocess, "run", fake_ffmpeg)


# --------------------------------------------------------------------------- #
# config: the lane exists, defaults to the native lane, validates
# --------------------------------------------------------------------------- #
def test_settings_default_to_native_lane():
    from app.config import Settings

    settings = Settings(_env_file=None)
    assert settings.viral_producer_lane == "viral_remix"
    assert settings.viral_mpt_lane_enabled is False
    assert settings.viral_mpt_home == ""


def test_settings_reject_unknown_producer_lane():
    from pydantic import ValidationError

    from app.config import Settings

    with pytest.raises(ValidationError):
        Settings(_env_file=None, viral_producer_lane="something-else")


# --------------------------------------------------------------------------- #
# preflight: fail closed on everything unsafe or unprovisioned
# --------------------------------------------------------------------------- #
def test_preflight_refuses_when_lane_not_selected(tmp_path):
    home = _mpt_home(tmp_path)
    settings = _settings(tmp_path, home, viral_producer_lane="viral_remix")
    result = ml.produce_mpt_short(_brief(), settings, runner=_fake_runner({}))
    assert result["status"] == "SKIPPED"
    assert result["reason"] == "lane_not_selected"


def test_preflight_refuses_when_gates_disabled(tmp_path):
    # The lane has no ungated path, even though the native lane's kill
    # switch would let IT run ungated.
    home = _mpt_home(tmp_path)
    settings = _settings(tmp_path, home, viral_quality_gates_enabled=False)
    result = ml.produce_mpt_short(_brief(), settings, runner=_fake_runner({}))
    assert result["reason"] == "quality_gates_disabled"


def test_preflight_refuses_scriptless_brief(tmp_path):
    # A scriptless brief would make MPT call an LLM — never allowed.
    home = _mpt_home(tmp_path)
    settings = _settings(tmp_path, home)
    result = ml.produce_mpt_short(_brief(script="  "), settings,
                                  runner=_fake_runner({}))
    assert result["reason"] == "brief_script_missing"


def test_preflight_refuses_paid_video_source(tmp_path):
    home = _mpt_home(tmp_path)
    settings = _settings(tmp_path, home)
    result = ml.produce_mpt_short(_brief(video_source="wavespeed"),
                                  settings, runner=_fake_runner({}))
    assert result["reason"] == "video_source_not_free"


def test_preflight_refuses_paid_voice_prefix(tmp_path):
    home = _mpt_home(tmp_path)
    settings = _settings(tmp_path, home)
    result = ml.produce_mpt_short(
        _brief(voice_name="elevenlabs:rachel"), settings,
        runner=_fake_runner({}))
    assert result["reason"] == "voice_provider_not_free"


def test_preflight_refuses_cross_posting_home(tmp_path):
    config = GOOD_CONFIG.replace("upload_post_enabled = false",
                                 "upload_post_enabled = true")
    home = _mpt_home(tmp_path, config)
    settings = _settings(tmp_path, home)
    result = ml.produce_mpt_short(_brief(), settings, runner=_fake_runner({}))
    assert result["reason"] == "mpt_cross_posting_enabled"


def test_preflight_refuses_paid_tts_server(tmp_path):
    config = GOOD_CONFIG.replace('tts_server = "azure-tts-v1"',
                                 'tts_server = "azure-tts-v2"')
    home = _mpt_home(tmp_path, config)
    settings = _settings(tmp_path, home)
    result = ml.produce_mpt_short(_brief(), settings, runner=_fake_runner({}))
    assert result["reason"] == "mpt_tts_not_free"


def test_preflight_refuses_whisper_subtitles(tmp_path):
    config = GOOD_CONFIG.replace('subtitle_provider = "edge"',
                                 'subtitle_provider = "whisper"')
    home = _mpt_home(tmp_path, config)
    settings = _settings(tmp_path, home)
    result = ml.produce_mpt_short(_brief(), settings, runner=_fake_runner({}))
    assert result["reason"] == "mpt_subtitle_provider_not_edge"


def test_preflight_refuses_missing_stock_keys(tmp_path):
    config = GOOD_CONFIG.replace('pexels_api_keys = ["free-tier-key"]',
                                 "pexels_api_keys = []")
    home = _mpt_home(tmp_path, config)
    settings = _settings(tmp_path, home)
    result = ml.produce_mpt_short(_brief(), settings, runner=_fake_runner({}))
    assert result["reason"] == "mpt_stock_keys_missing"


def test_preflight_refuses_unprovisioned_home(tmp_path):
    settings = _settings(tmp_path, tmp_path / "nowhere")
    result = ml.produce_mpt_short(_brief(), settings, runner=_fake_runner({}))
    assert result["reason"] == "mpt_not_provisioned"


# --------------------------------------------------------------------------- #
# invocation: brief -> the free-only CLI call -> artefact hand-off
# --------------------------------------------------------------------------- #
def test_invocation_is_the_free_only_cli_call(tmp_path, monkeypatch):
    home = _mpt_home(tmp_path)
    settings = _settings(tmp_path, home)
    _wire_gates(monkeypatch)
    record: dict = {}
    result = ml.produce_mpt_short(_brief(terms=["cat", "garden"]),
                                  settings, runner=_fake_runner(record))
    assert result["status"] == "GATED_PASS"
    cmd = record["cmd"]
    assert record["cwd"] == home
    assert cmd[cmd.index("--video-script") + 1] == GROUNDED_SCRIPT
    assert cmd[cmd.index("--video-source") + 1] == "pexels"
    assert cmd[cmd.index("--bgm-type") + 1] == "none"
    assert cmd[cmd.index("--stop-at") + 1] == "video"
    assert cmd[cmd.index("--video-terms") + 1] == "cat, garden"
    # The gated package lands in VyralX's own render dir, with captions.
    assert Path(result["video_path"]).is_file()
    assert Path(result["captions_path"]).is_file()
    # And it is NOT a publish job — the lane never queues an upload.
    assert result["publish_job_id"] is None


def test_cli_failure_is_a_skip_not_a_crash(tmp_path):
    home = _mpt_home(tmp_path)
    settings = _settings(tmp_path, home)
    result = ml.produce_mpt_short(
        _brief(), settings, runner=_fake_runner({}, returncode=1))
    assert result["status"] == "SKIPPED"
    assert result["reason"] == "mpt_failed"


def test_fleet_memory_budget_is_a_gate(tmp_path, monkeypatch):
    home = _mpt_home(tmp_path)
    settings = _settings(tmp_path, home)  # budget 512 MB
    _wire_gates(monkeypatch)
    result = ml.produce_mpt_short(
        _brief(), settings, runner=_fake_runner({}, peak_rss_mb=900.0))
    assert result["status"] == "SKIPPED"
    assert result["reason"] == "fleet_memory_exceeded"
    assert result["peak_rss_mb"] == 900.0


def test_rewritten_script_is_rejected(tmp_path, monkeypatch):
    # If MPT reports different words than the brief supplied, the gates
    # must not certify the brief's script — the package is unverifiable.
    home = _mpt_home(tmp_path)
    settings = _settings(tmp_path, home)
    _wire_gates(monkeypatch)
    result = ml.produce_mpt_short(
        _brief(), settings,
        runner=_fake_runner({}, reported_script=INVENTED_SCRIPT))
    assert result["status"] == "SKIPPED"
    assert result["reason"] == "script_unverifiable"
    assert result["violations"] == ["script_rewritten_by_lane"]


# --------------------------------------------------------------------------- #
# gate integration: the real gates judge MPT packages
# --------------------------------------------------------------------------- #
def test_invented_copy_is_rejected_by_the_gates(tmp_path, monkeypatch):
    home = _mpt_home(tmp_path)
    settings = _settings(tmp_path, home)
    _wire_gates(monkeypatch)
    result = ml.produce_mpt_short(_brief(script=INVENTED_SCRIPT),
                                  settings, runner=_fake_runner({}))
    assert result["status"] == "SKIPPED"
    assert result["reason"] == "script_unverifiable"
    assert result["violations"]  # named gate violations, not a bare no


def test_grounded_copy_passes_every_gate(tmp_path, monkeypatch):
    home = _mpt_home(tmp_path)
    settings = _settings(tmp_path, home)
    _wire_gates(monkeypatch)
    result = ml.produce_mpt_short(_brief(), settings,
                                  runner=_fake_runner({}))
    assert result["status"] == "GATED_PASS"
    assert result["quality_gate_attempts"] == 1


def test_static_render_is_rejected_at_the_arc_gate(tmp_path, monkeypatch):
    home = _mpt_home(tmp_path)
    settings = _settings(tmp_path, home)
    static_arc = vq.EventArc(samples=10, mean_change=0.0, max_change=0.0,
                             static_ratio=1.0, peak_position=0.5)
    _wire_gates(monkeypatch, arc=static_arc)
    result = ml.produce_mpt_short(_brief(), settings,
                                  runner=_fake_runner({}))
    assert result["status"] == "SKIPPED"
    assert result["reason"] == "static_scene"


def test_missing_vision_record_is_rejected(tmp_path, monkeypatch):
    home = _mpt_home(tmp_path)
    settings = _settings(tmp_path, home)
    _wire_gates(monkeypatch)
    monkeypatch.setattr(ml, "analyze_scene", lambda *a, **k: None)
    result = ml.produce_mpt_short(_brief(), settings,
                                  runner=_fake_runner({}))
    assert result["status"] == "SKIPPED"
    assert result["reason"] == "vision_unavailable"


def test_narration_fit_gate_rejects_a_short_narration(tmp_path, monkeypatch):
    # The measured narration inside the render covers 3 s of a 20 s
    # video — evaluate_narration_fit must reject it (job 683's class).
    home = _mpt_home(tmp_path)
    settings = _settings(tmp_path, home)
    _wire_gates(monkeypatch)
    monkeypatch.setattr(
        ml, "probe_media",
        lambda path: SimpleNamespace(
            duration=3.0 if str(path).endswith(".wav") else 20.0,
            width=1080, height=1920, has_audio=True))
    result = ml.produce_mpt_short(_brief(), settings,
                                  runner=_fake_runner({}))
    assert result["status"] == "SKIPPED"
    assert result["reason"] == "script_length_misfit"
    assert "narration_underruns_clip" in result["violations"]


# --------------------------------------------------------------------------- #
# driver entry: briefs file in, gated summary out; inactive means inactive
# --------------------------------------------------------------------------- #
def test_produce_from_briefs_stops_at_first_gated_pass(tmp_path, monkeypatch):
    home = _mpt_home(tmp_path)
    settings = _settings(tmp_path, home)
    briefs_path = tmp_path / "briefs.json"
    briefs_path.write_text(json.dumps([
        {"topic": "Invented", "script": INVENTED_SCRIPT, "title": "Nope"},
        {"topic": "A cat chases a ball", "script": GROUNDED_SCRIPT,
         "title": "Cat catches the ball"},
    ]), encoding="utf-8")
    settings.viral_mpt_briefs_path = str(briefs_path)
    _wire_gates(monkeypatch)
    summary = ml.produce_from_briefs(settings, runner=_fake_runner({}))
    assert summary["status"] == "GATED_PASS"
    assert len(summary["attempts"]) == 2
    assert summary["attempts"][0]["reason"] == "script_unverifiable"


def test_produce_from_briefs_inactive_lane_does_nothing(tmp_path):
    home = _mpt_home(tmp_path)
    settings = _settings(tmp_path, home, viral_mpt_lane_enabled=False)
    called: dict = {}
    summary = ml.produce_from_briefs(settings, runner=_fake_runner(called))
    assert summary == {"status": "LANE_INACTIVE", "attempts": []}
    assert "cmd" not in called


def test_produce_from_briefs_without_briefs_file(tmp_path):
    home = _mpt_home(tmp_path)
    settings = _settings(tmp_path, home)
    summary = ml.produce_from_briefs(settings, runner=_fake_runner({}))
    assert summary["status"] == "NO_BRIEFS"
