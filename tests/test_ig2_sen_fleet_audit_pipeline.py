"""
TASK-IG2-SEN-02 — Multi-role defensive audit pipeline tests.

PentAGI's role design (researcher → planner → executor → reflector →
report), defensive only, scoped to FRIDAY's own fleet. All probes are
faked: no test touches the network.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from Sentinel.app.services.fleet_audit_pipeline import (  # noqa: E402
    AuditTarget,
    FleetAuditPipeline,
    FleetHost,
    FleetService,
    OutOfScopeError,
    ProbeSet,
    default_fleet_inventory,
)


HEALTHY_TLS = {
    "not_after": "far future",
    "expires_at": datetime.now(timezone.utc) + timedelta(days=180),
    "subject": "()",
}


def make_probes(open_ports, health_status=200, headers=None, tls_info=HEALTHY_TLS):
    def tcp_open(address, port):
        return (address, port) in open_ports

    def http_get(url):
        if url.endswith("/health"):
            return health_status, {}
        return 200, headers if headers is not None else {
            "strict-transport-security": "max-age=31536000",
            "x-content-type-options": "nosniff",
            "x-frame-options": "DENY",
        }

    return ProbeSet(
        tcp_open=tcp_open,
        tls_info=lambda address, port: tls_info,
        http_get=http_get,
    )


SMALL_FLEET = [
    FleetHost("server-1", "10.0.0.121", (
        FleetService("FRIDAY", 10000),
        FleetService("Memora", 8002, scheme="https"),
    )),
]


def test_default_inventory_is_the_ten_agent_fleet():
    inventory = default_fleet_inventory()
    services = [s.name for host in inventory for s in host.services]
    assert len(services) == 10
    assert set(services) == {
        "FRIDAY", "Inference", "Memora", "Stratex", "Futuris", "IntelX",
        "Forge", "Sentinel", "Cortex", "VyralX",
    }


def test_clean_fleet_produces_no_findings():
    probes = make_probes({("10.0.0.121", 10000), ("10.0.0.121", 8002)})
    report = FleetAuditPipeline(SMALL_FLEET, probes).run()
    assert report.findings == []
    assert report.targets == 2
    assert "No verified findings" in report.to_markdown()


def test_down_service_and_unexpected_port_are_found():
    # FRIDAY port closed; Redis (6379) unexpectedly open on the host.
    probes = make_probes({("10.0.0.121", 8002), ("10.0.0.121", 6379)})
    report = FleetAuditPipeline(SMALL_FLEET, probes).run()
    ids = {f.finding_id for f in report.findings}
    assert "server-1/FRIDAY/port-reachable" in ids
    assert "server-1/FRIDAY/unexpected-ports" in ids
    assert all(f.verified for f in report.findings)


def test_unhealthy_service_and_missing_headers_are_found():
    probes = make_probes(
        {("10.0.0.121", 10000), ("10.0.0.121", 8002)},
        health_status=503, headers={},
    )
    report = FleetAuditPipeline(SMALL_FLEET, probes).run()
    ids = {f.finding_id for f in report.findings}
    assert "server-1/FRIDAY/health" in ids
    assert "server-1/FRIDAY/headers" in ids


def test_tls_expiry_within_window_is_a_finding():
    expires = datetime.now(timezone.utc) + timedelta(days=10)
    probes = make_probes(
        {("10.0.0.121", 10000), ("10.0.0.121", 8002)},
        tls_info={"not_after": "soon", "expires_at": expires, "subject": "()"},
    )
    report = FleetAuditPipeline(SMALL_FLEET, probes).run()
    tls = [f for f in report.findings if f.check_id == "tls"]
    assert tls and tls[0].severity == "MEDIUM"


def test_reflector_drops_findings_that_do_not_reproduce():
    seen: set[tuple[str, int]] = set()

    def flaky_tcp(address, port):
        # The service port appears closed on the executor pass and open on
        # the reflector's re-check; every other port is always closed.
        if (address, port) == ("10.0.0.121", 10000):
            if (address, port) in seen:
                return True
            seen.add((address, port))
            return False
        return False

    probes = ProbeSet(
        tcp_open=flaky_tcp,
        tls_info=lambda a, p: None,
        http_get=lambda url: (200, {
            "strict-transport-security": "x", "x-content-type-options": "x",
            "x-frame-options": "x",
        }),
    )
    fleet = [FleetHost("server-1", "10.0.0.121", (FleetService("FRIDAY", 10000),))]
    report = FleetAuditPipeline(fleet, probes).run()
    assert report.findings == []
    assert any(
        d["finding_id"] == "server-1/FRIDAY/port-reachable"
        for d in report.dropped
    )


def test_out_of_scope_target_is_refused_before_any_probe():
    probes = make_probes(set())
    pipeline = FleetAuditPipeline(SMALL_FLEET, probes)
    with pytest.raises(OutOfScopeError):
        pipeline.run(extra_targets=[AuditTarget(
            "evil", "203.0.113.99", "FRIDAY", 10000, "http",
        )])


def test_report_dict_summary_counts_severities():
    probes = make_probes({("10.0.0.121", 8002)})  # FRIDAY down
    report = FleetAuditPipeline(SMALL_FLEET, probes).run()
    data = report.as_dict()
    assert data["summary"]["HIGH"] >= 1
    assert data["targets"] == 2 and data["checks_run"] > 0
