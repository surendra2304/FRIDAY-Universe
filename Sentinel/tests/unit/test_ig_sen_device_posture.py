"""TASK-IG-SEN-02 — owner device & account posture check tests."""

import os
from datetime import datetime, timezone

from sentinel.core.models import SeverityLevel
from sentinel.modules.endpoint.device_posture import (
    CredentialPostureChecker,
    DevicePostureEvaluator,
    DevicePostureReport,
    PermissionGrant,
    emit_posture_alerts,
)
from sentinel.modules.operations.alerting import AlertEngine

UTC = timezone.utc
NOW = datetime(2026, 11, 15, tzinfo=UTC)


def clean_report(**overrides):
    base = dict(
        device_id="owner-pixel",
        os_version="14",
        security_patch="2026-10-05",
        screen_lock=True,
        unknown_sources_allowed=False,
        developer_options_on=False,
        adb_enabled=False,
        play_protect_enabled=True,
        device_encrypted=True,
        permission_grants=[
            PermissionGrant(
                app_package="org.friday.companion",
                app_label="FRIDAY Companion",
                permission="accessibility",
                trusted=True,
            )
        ],
        paired_bluetooth=["Car Audio"],
        trusted_bluetooth=["Car Audio"],
    )
    base.update(overrides)
    return DevicePostureReport(**base)


def rules(findings):
    return [f.rule_id for f in findings]


def test_clean_device_has_no_findings():
    findings = DevicePostureEvaluator().evaluate(clean_report(), now=NOW)
    assert findings == []


def test_fraud_surface_device_flags_expected_rules():
    report = clean_report(
        unknown_sources_allowed=True,
        adb_enabled=True,
        screen_lock=False,
        play_protect_enabled=False,
        permission_grants=[
            PermissionGrant(
                app_package="com.flashlight.free",
                app_label="Flashlight",
                permission="accessibility",
            ),
            PermissionGrant(
                app_package="com.flashlight.free",
                permission="overlay",
            ),
        ],
        paired_bluetooth=["Car Audio", "Unknown Speaker"],
        trusted_bluetooth=["Car Audio"],
        security_patch="2025-01-01",
    )
    findings = DevicePostureEvaluator().evaluate(report, now=NOW)
    got = rules(findings)
    assert "DP-001" in got  # unknown sources
    assert "DP-002" in got  # adb
    assert "DP-003" in got  # no screen lock
    assert "DP-005" in got  # untrusted accessibility
    assert "DP-006" in got  # untrusted overlay
    assert "DP-007" in got  # play protect off
    assert "DP-008" in got  # stale patch (683 days)
    assert "DP-010" in got  # untrusted bluetooth
    sev = {f.rule_id: f.severity for f in findings}
    assert sev["DP-001"] == SeverityLevel.CRITICAL
    assert sev["DP-005"] == SeverityLevel.HIGH


def test_trusted_companion_grants_are_not_flagged():
    report = clean_report(
        permission_grants=[
            PermissionGrant(
                app_package="org.friday.companion",
                permission="device_admin",
                trusted=True,
            ),
            PermissionGrant(
                app_package="org.friday.companion",
                permission="notification_access",
                trusted=True,
            ),
        ]
    )
    findings = DevicePostureEvaluator().evaluate(report, now=NOW)
    assert findings == []


def test_patch_reporting_edges():
    ev = DevicePostureEvaluator()
    missing = ev.evaluate(clean_report(security_patch=""), now=NOW)
    assert rules(missing) == ["DP-009"]
    assert missing[0].severity == SeverityLevel.INFO
    garbage = ev.evaluate(clean_report(security_patch="Oct 2026"), now=NOW)
    assert rules(garbage) == ["DP-009"]
    fresh = ev.evaluate(clean_report(security_patch="2026-11-01"), now=NOW)
    assert fresh == []


def test_developer_options_alone_is_low():
    findings = DevicePostureEvaluator().evaluate(
        clean_report(developer_options_on=True), now=NOW
    )
    assert rules(findings) == ["DP-011"]
    assert findings[0].severity == SeverityLevel.LOW


def test_credential_posture_modes(tmp_path):
    good = tmp_path / "good.env"
    good.write_text("X=1")
    os.chmod(good, 0o600)
    bad = tmp_path / "bad.env"
    bad.write_text("X=1")
    os.chmod(bad, 0o664)
    creds = tmp_path / "credentials"
    creds.mkdir()
    os.chmod(creds, 0o775)
    tight = tmp_path / "tight"
    tight.mkdir()
    os.chmod(tight, 0o700)

    findings, missing = CredentialPostureChecker().check(
        env_files=[good, bad, tmp_path / "absent.env"],
        credential_dirs=[creds, tight],
    )
    got = {f.rule_id for f in findings}
    assert got == {"CP-001", "CP-002"}
    assert missing == [str(tmp_path / "absent.env")]
    cp1 = next(f for f in findings if f.rule_id == "CP-001")
    assert "0664" in cp1.evidence


def test_emit_posture_alerts_dedupes():
    findings = DevicePostureEvaluator().evaluate(
        clean_report(unknown_sources_allowed=True), now=NOW
    )
    engine = AlertEngine()
    alerts = emit_posture_alerts(findings, engine)
    assert len(alerts) == 1
    assert alerts[0].severity == SeverityLevel.CRITICAL
    again = emit_posture_alerts(findings, engine)
    assert again[0].occurrence_count == 2
    assert len(engine.list_alerts()) == 1
