"""TASK-IG2-VYR-07: OpenVoice assessment + gate + offline job design.

Pins the honest verdict: fleet-shaped inputs are INFEASIBLE with named
reasons; a well-equipped offline host is feasible; jobs never download
weights or run in-service; reference clips and V2 languages validated;
ingest only accepts finished MP3s from OpenVoice jobs.
On clean main this fails: app.services.openvoice_gate does not exist.
"""
from __future__ import annotations

import pytest

from app.services import openvoice_gate as ov

FLEET = dict(free_ram_mb=116, torch_available=False, checkpoint_present=False)
OWNER_HW = dict(free_ram_mb=8192, torch_available=True, checkpoint_present=True,
                checkpoint_mb=450.0, host_role="owner_machine")


def test_fleet_is_infeasible_with_reasons():
    a = ov.assess_environment(**FLEET)
    assert a["feasible"] is False and len(a["reasons"]) >= 3
    assert "Gemini Live" in a["live_voice_unaffected"]


def test_owner_hardware_feasible():
    a = ov.assess_environment(**OWNER_HW)
    assert a["feasible"] is True and a["reasons"] == []


def test_job_validation_and_shape():
    a = ov.assess_environment(**OWNER_HW)
    job = ov.build_narration_job(
        text="The crater formed in seconds.",
        reference_clip={"path": "ref.wav", "duration_seconds": 12.0},
        language="en", style={"emotion": "awe", "bogus": 1}, assessment=a)
    assert job["style"] == {"emotion": "awe"}  # unknown controls dropped
    assert job["downloads_weights"] is False and job["runs_in_service"] is False
    assert job["status"] == "pending_review" and job["privacy"] == "unlisted"
    with pytest.raises(ValueError):
        ov.build_narration_job(text="x", language="de", assessment=a,
                               reference_clip={"path": "r.wav", "duration_seconds": 10})
    with pytest.raises(ValueError):
        ov.build_narration_job(text="x", assessment=a,
                               reference_clip={"path": "r.wav", "duration_seconds": 1})


def test_ingest_requires_finished_mp3():
    a = ov.assess_environment(**OWNER_HW)
    job = ov.build_narration_job(
        text="Hello.", reference_clip={"path": "ref.wav", "duration_seconds": 5},
        assessment=a)
    plan = ov.ingest_narration(job, {"path": "narr.mp3", "bytes": 12345,
                                     "duration_seconds": 4.2})
    assert plan["status"] == "pending_review" and plan["publish"] is False
    with pytest.raises(ValueError):
        ov.ingest_narration(job, {"path": "narr.wav", "bytes": 10})
