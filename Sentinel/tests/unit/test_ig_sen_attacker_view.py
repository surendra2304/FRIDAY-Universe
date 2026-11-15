"""TASK-IG-SEN-01 — attacker-view self-audit tests.

All probes are fakes: no test touches a real network. The Wi-Fi check
runs the real WirelessConfigAssessmentAdapter (pure config evaluation).
"""

import pytest

from sentinel.core.models import SeverityLevel
from sentinel.modules.attacker_view import (
    AttackerViewAudit,
    AuditConfig,
    CameraTarget,
    HttpTarget,
    ServiceTarget,
    WifiObservation,
    default_fleet_config,
)
from sentinel.modules.attacker_view.probes import HttpResponse
from sentinel.modules.operations.alerting import AlertEngine

PUB = "203.0.113.10"  # TEST-NET-3, documentation range — never a real host


class FakeTcp:
    def __init__(self, open_ports):
        self.open_ports = open_ports
        self.calls = []

    def __call__(self, host, port):
        self.calls.append((host, port))
        return (host, port) in self.open_ports


class FakeHttp:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def __call__(self, url):
        self.calls.append(url)
        return self.responses.get(url)


def make_audit(tcp=None, http=None):
    return AttackerViewAudit(
        tcp_probe=tcp or FakeTcp(set()),
        http_probe=http or FakeHttp({}),
    )


@pytest.mark.asyncio
async def test_non_public_port_open_on_public_host_is_high_finding():
    tcp = FakeTcp({(PUB, 10000)})
    audit = make_audit(tcp=tcp)
    config = AuditConfig(
        allowed_hosts=[PUB],
        services=[
            ServiceTarget(host=PUB, port=443, label="HTTPS", expect_public=True),
            ServiceTarget(host=PUB, port=10000, label="FRIDAY", expect_public=False),
        ],
    )
    report = await audit.run(config)
    exp = [f for f in report.findings if f.rule_id == "AV-EXP-001"]
    assert len(exp) == 1
    assert exp[0].severity == SeverityLevel.HIGH
    assert exp[0].target_ref == f"{PUB}:10000"


@pytest.mark.asyncio
async def test_public_surface_open_is_clean_and_closed_public_is_info():
    audit = make_audit(tcp=FakeTcp({(PUB, 443)}))
    config = AuditConfig(
        allowed_hosts=[PUB],
        services=[
            ServiceTarget(host=PUB, port=443, label="HTTPS", expect_public=True),
            ServiceTarget(host=PUB, port=80, label="HTTP", expect_public=True),
        ],
    )
    report = await audit.run(config)
    assert [f.rule_id for f in report.findings] == ["AV-EXP-002"]
    assert report.findings[0].severity == SeverityLevel.INFO
    assert report.unreachable_targets == [f"{PUB}:80"]


@pytest.mark.asyncio
async def test_targets_off_allowlist_are_refused_and_never_probed():
    tcp = FakeTcp(set())
    http = FakeHttp({})
    audit = make_audit(tcp=tcp, http=http)
    config = AuditConfig(
        allowed_hosts=[PUB],
        services=[ServiceTarget(host="198.51.100.99", port=22)],
        http_targets=[HttpTarget(url="http://198.51.100.99/admin")],
        cameras=[CameraTarget(host="198.51.100.99")],
    )
    report = await audit.run(config)
    assert len(report.refused_targets) == 3
    assert tcp.calls == []
    assert http.calls == []
    assert report.findings == []


@pytest.mark.asyncio
async def test_auth_required_endpoint_answering_200_is_finding():
    url = f"http://{PUB}:8008/api/v1/sentinel/status"
    http = FakeHttp({url: HttpResponse(status=200, body="{}")})
    audit = make_audit(http=http)
    config = AuditConfig(
        allowed_hosts=[PUB],
        http_targets=[HttpTarget(url=url, label="Sentinel status", auth_required=True)],
    )
    report = await audit.run(config)
    assert [f.rule_id for f in report.findings] == ["AV-AUTH-001"]
    assert report.findings[0].severity == SeverityLevel.HIGH


@pytest.mark.asyncio
async def test_auth_posture_401_and_public_endpoint_are_clean():
    protected = f"http://{PUB}:8008/api/v1/sentinel/status"
    public = f"http://{PUB}:8008/health"
    http = FakeHttp(
        {
            protected: HttpResponse(status=401),
            public: HttpResponse(status=200, body="ok"),
        }
    )
    audit = make_audit(http=http)
    config = AuditConfig(
        allowed_hosts=[PUB],
        http_targets=[
            HttpTarget(url=protected, auth_required=True),
            HttpTarget(url=public, auth_required=False),
        ],
    )
    report = await audit.run(config)
    assert report.findings == []


@pytest.mark.asyncio
async def test_open_camera_snapshot_is_critical():
    url = f"http://{PUB}:80/snapshot.jpg"
    http = FakeHttp(
        {url: HttpResponse(status=200, headers={"Content-Type": "image/jpeg"}, body="...")}
    )
    audit = make_audit(http=http)
    config = AuditConfig(
        allowed_hosts=[PUB],
        cameras=[CameraTarget(host=PUB, label="Front door cam")],
    )
    report = await audit.run(config)
    assert [f.rule_id for f in report.findings] == ["AV-CAM-001"]
    assert report.findings[0].severity == SeverityLevel.CRITICAL


@pytest.mark.asyncio
async def test_camera_behind_auth_is_clean_and_open_ui_is_medium():
    protected = f"http://{PUB}:8080/snapshot.jpg"
    open_ui = f"http://{PUB}:8081/snapshot.jpg"
    http = FakeHttp(
        {
            protected: HttpResponse(status=401),
            open_ui: HttpResponse(status=200, headers={"Content-Type": "text/html"}, body="<html>"),
        }
    )
    audit = make_audit(http=http)
    config = AuditConfig(
        allowed_hosts=[PUB],
        cameras=[
            CameraTarget(host=PUB, port=8080),
            CameraTarget(host=PUB, port=8081),
        ],
    )
    report = await audit.run(config)
    assert [f.rule_id for f in report.findings] == ["AV-CAM-002"]
    assert report.findings[0].severity == SeverityLevel.MEDIUM


@pytest.mark.asyncio
async def test_wifi_wps_and_wep_flagged_via_existing_adapter():
    audit = make_audit()
    config = AuditConfig(
        allowed_hosts=[PUB],
        wifi=[
            WifiObservation(ssid="HomeNet", security_mode="WPA2", wps_enabled=True),
            WifiObservation(ssid="OldNet", security_mode="WEP"),
            WifiObservation(ssid="GoodNet", security_mode="WPA3", wps_enabled=False),
        ],
    )
    report = await audit.run(config)
    by_ssid = {}
    for f in report.findings:
        by_ssid.setdefault(f.target_ref, []).append(f.rule_id)
    assert by_ssid["wifi:HomeNet"] == ["WIFI-002"]
    assert by_ssid["wifi:OldNet"] == ["WIFI-001"]
    assert "wifi:GoodNet" not in by_ssid
    wps = next(f for f in report.findings if f.rule_id == "WIFI-002")
    assert wps.severity == SeverityLevel.HIGH


@pytest.mark.asyncio
async def test_findings_emit_into_alert_engine_with_dedupe():
    audit = make_audit(tcp=FakeTcp({(PUB, 8008)}))
    config = AuditConfig(
        allowed_hosts=[PUB],
        target_ref="fleet-public-surface",
        services=[ServiceTarget(host=PUB, port=8008, label="Sentinel")],
    )
    report = await audit.run(config)
    engine = AlertEngine()
    alerts = AttackerViewAudit.emit_alerts(report, engine)
    assert len(alerts) == 1
    assert alerts[0].severity == SeverityLevel.HIGH
    assert alerts[0].occurrence_count == 1
    again = AttackerViewAudit.emit_alerts(report, engine)
    assert again[0].occurrence_count == 2  # dedupe, not a second alert
    assert len(engine.list_alerts()) == 1


def test_default_fleet_config_surface():
    cfg = default_fleet_config("140.0.0.1", "140.0.0.2")
    assert cfg.allowed_hosts == ["140.0.0.1", "140.0.0.2"]
    public = {(s.host, s.port) for s in cfg.services if s.expect_public}
    private = {(s.host, s.port) for s in cfg.services if not s.expect_public}
    for host in ("140.0.0.1", "140.0.0.2"):
        assert (host, 22) in public and (host, 443) in public
        assert (host, 10000) in private and (host, 8008) in private
