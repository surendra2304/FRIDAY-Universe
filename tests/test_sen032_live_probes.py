"""
TASK-SEN-032 — tests for the live-probe driver (Sentinel/scripts/sen032_live_probes.py).

No network, no live host: the pipeline runs on stub probes, the ELA
check on generated image bytes, the triage checks on literal inputs.
The live run on Server 1 is the same driver with real inputs.
"""
import importlib.util
import os
import random
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from Sentinel.app.services.audit_baseline import (  # noqa: E402
    BaselineMemorist,
    InMemoryBaselineStore,
)
from Sentinel.app.services.compromised_host_triage import (  # noqa: E402
    UnknownIndicatorError,
    evaluate as triage_evaluate,
)
from Sentinel.app.services.extortion_mail_triage import triage_email  # noqa: E402
from Sentinel.app.services.fleet_audit_pipeline import (  # noqa: E402
    FleetAuditPipeline,
    FleetService,
    OutOfScopeError,
    ProbeSet,
    default_fleet_inventory,
)
from Sentinel.app.services.media_ela import (  # noqa: E402
    ElaInputError,
    analyse_image_bytes,
)

_SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "Sentinel", "scripts",
    "sen032_live_probes.py",
)
_spec = importlib.util.spec_from_file_location("sen032_live_probes", _SCRIPT)
assert _spec is not None and _spec.loader is not None
probes_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(probes_mod)

HEALTHY_TLS = {
    "not_after": "far future",
    "expires_at": datetime.now(timezone.utc) + timedelta(days=180),
    "subject": "()",
}


def make_probes(open_ports, health_status=200, headers=None,
                tls_info=HEALTHY_TLS):
    def tcp_open(address, port):
        return (address, port) in open_ports

    def http_get(url):
        if url.endswith("/health"):
            return health_status, {}
        return 200, headers or {
            "strict-transport-security": "max-age=31536000",
            "x-content-type-options": "nosniff",
            "x-frame-options": "DENY",
        }

    def tls(address, port):
        return tls_info

    return ProbeSet(tcp_open=tcp_open, tls_info=tls, http_get=http_get)


def textured_jpeg_bytes(seed=7, size=(128, 128)):
    """Deterministic noisy JPEG: ELA has texture to measure."""
    from PIL import Image
    rng = random.Random(seed)
    pixels = [
        (rng.randrange(256), rng.randrange(256), rng.randrange(256))
        for _ in range(size[0] * size[1])
    ]
    image = Image.new("RGB", size)
    image.putdata(pixels)
    import io
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=85)
    return buffer.getvalue()


def png_bytes():
    from PIL import Image
    import io
    buffer = io.BytesIO()
    Image.new("RGB", (128, 128), color=(200, 30, 30)).save(buffer, "PNG")
    return buffer.getvalue()


# --- SEN-02 inventory -------------------------------------------------

def test_corrected_inventory_is_the_relayout_not_the_stale_default():
    inventory = probes_mod.corrected_inventory()
    assert [h.name for h in inventory] == ["server-1"]
    host = inventory[0]
    assert host.address == "10.0.0.121"
    assert [(s.name, s.port) for s in host.services] == [
        ("Memora", 8002), ("Forge", 8006),
        ("Sentinel", 8008), ("Cortex", 8009),
    ]
    # The shipped default still lists services that moved off these
    # hosts in the 2026-11-24 re-layout (FRIDAY 10000, Inference 8001,
    # Stratex 8003, Futuris 8004, IntelX 8005 on server-1; VyralX on
    # server-2) — the driver must not use it for findings.
    default_services = {
        s.name for h in default_fleet_inventory() for s in h.services
    }
    assert "FRIDAY" in default_services and "VyralX" in default_services
    assert {s.name for s in host.services} <= {"Memora", "Forge", "Sentinel", "Cortex"}


def test_pipeline_healthy_stub_probes_no_findings():
    inventory = probes_mod.corrected_inventory()
    open_ports = {
        (h.address, s.port) for h in inventory for s in h.services
    }
    pipeline = FleetAuditPipeline(
        inventory=inventory, probes=make_probes(open_ports),
    )
    report = pipeline.run()
    assert report.findings == []
    assert report.targets == 4
    assert report.checks_run > 0


def test_pipeline_closed_port_finding_is_reproduced_by_reflector():
    inventory = probes_mod.corrected_inventory()
    open_ports = {
        (h.address, s.port) for h in inventory for s in h.services
    } - {("10.0.0.121", 8002)}  # Memora down
    pipeline = FleetAuditPipeline(
        inventory=inventory, probes=make_probes(open_ports),
    )
    report = pipeline.run()
    ids = {f.finding_id for f in report.findings}
    assert "server-1/Memora/port-reachable" in ids
    assert all(f.verified for f in report.findings)


def test_pipeline_refuses_off_inventory_address():
    pipeline = FleetAuditPipeline(inventory=probes_mod.corrected_inventory())
    with pytest.raises(OutOfScopeError):
        pipeline.researcher.assert_in_scope("8.8.8.8")


# --- SEN-03 memorist --------------------------------------------------

def test_memorist_repeat_run_is_all_unchanged_no_alerts():
    findings = [
        {"finding_id": "server-1/Memora/health", "severity": "LOW",
         "title": "t", "detail": "d"},
        {"finding_id": "server-1/Forge/headers", "severity": "HIGH",
         "title": "t", "detail": "d"},
    ]
    memorist = BaselineMemorist(InMemoryBaselineStore())
    memorist.accept_baseline(findings)
    diff, alerts = memorist.record_run(findings)
    assert diff.unchanged_count == 2
    assert diff.new == [] and diff.fixed == [] and diff.regressions == []
    assert alerts == []


def test_memorist_severity_raise_is_a_regression_alert():
    findings = [{"finding_id": "server-1/Memora/health", "severity": "LOW",
                 "title": "t", "detail": "d"}]
    memorist = BaselineMemorist(InMemoryBaselineStore())
    memorist.accept_baseline(findings)
    raised = [{"finding_id": "server-1/Memora/health", "severity": "HIGH",
               "title": "t", "detail": "d"}]
    diff, alerts = memorist.record_run(raised)
    assert len(diff.regressions) == 1
    assert diff.regressions[0]["from_severity"] == "LOW"
    assert alerts and alerts[0]["kind"] == "regression"


# --- SEN-04 ELA ---------------------------------------------------------

def test_ela_textured_jpeg_returns_a_measured_verdict():
    result = analyse_image_bytes(textured_jpeg_bytes())
    assert result.verdict in {
        "CONSISTENT", "SUSPICIOUS_REGIONS", "WHOLE_IMAGE_HETEROGENEOUS",
    }
    assert result.blocks_total > 0
    assert result.format == "JPEG"


def test_ela_non_image_bytes_raise():
    with pytest.raises(ElaInputError):
        analyse_image_bytes(b"this is not an image at all")


def test_ela_png_is_inconclusive_by_design():
    result = analyse_image_bytes(png_bytes())
    assert result.verdict == "INCONCLUSIVE"


# --- SEN-05 triage ------------------------------------------------------

def test_triage_no_observations_is_no_signs():
    result = triage_evaluate([])
    assert result.verdict == "NO_SIGNS"
    assert result.score == 0


def test_triage_hard_sign_escalates():
    result = triage_evaluate(["files_encrypted"])
    assert result.verdict == "LIKELY_COMPROMISED"
    assert "files_encrypted" in result.hard_signs
    assert result.action_plan[0].startswith("Disconnect")


def test_triage_unknown_indicator_is_rejected():
    with pytest.raises(UnknownIndicatorError):
        triage_evaluate(["not_a_real_indicator"])


# --- SEN-06 extortion triage --------------------------------------------

def test_extortion_corpus_scenario_is_extortion_with_pixel():
    result = triage_email(**probes_mod.CORPUS_RANSOM_SCENARIO)
    assert result.category in {
        "FAKE_RANSOM_DEMAND", "RANSOMWARE_CLAIM", "SEXTORTION_SCAM",
    }
    assert result.tracking_pixel is True
    assert "tracking_pixel_present" in result.signals
    assert result.guidance  # do-not-pay guidance is always attached
    assert result.as_dict()["engages_sender"] is False


def test_extortion_benign_mail_is_not_extortion():
    result = triage_email(**probes_mod.BENIGN_NEWSLETTER)
    assert result.category == "NOT_EXTORTION"
    assert result.guidance == []


def test_extortion_pixel_alone_never_makes_a_verdict():
    result = triage_email(**probes_mod.PIXEL_ONLY_NEWSLETTER)
    assert result.category == "NOT_EXTORTION"
    assert result.tracking_pixel is True
