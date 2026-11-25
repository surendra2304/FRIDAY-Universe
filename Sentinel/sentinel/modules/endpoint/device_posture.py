"""Owner device & account security posture checks (TASK-IG-SEN-02).

Two read-only evaluators, both reporting through the shared operations
AlertEngine as BaselineDeltas (no new alert path):

1. ``DevicePostureEvaluator`` — scores an Android posture report (the
   shape the FRIDAY phone bridge / companion can produce) against the
   phone-safety model from the owner's reference corpus:
   * DViOIKejfEK — phone/account security-awareness checks that flag
     risky settings and fraud exposure on the owner's devices.
   * DXeyj7HCg-M — "Phantom Droid" Android security lab: untrusted
     connections and dangerous permission grants are the risk.
   The evaluator is pure: it judges a report, it does not touch a device.
   Rules DP-012/DP-013 (TASK-SEN-030) judge the device's Private DNS
   setting and resolver hygiene.

2. ``CredentialPostureChecker`` — stat-only permission checks on the
   fleet's credential material (per-agent .env files must be 0600,
   credential directories 0700). This is the recurring, automated form
   of the one-off fixes in TASK-SEN-011 (VyralX credentials dir 775->700,
   .env 664->600). It reads metadata only — never file contents.
"""

from __future__ import annotations

import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

UTC = timezone.utc  # Python 3.10-compatible alias for the 3.11+ name

from pydantic import BaseModel, Field

from sentinel.core.models import SeverityLevel
from sentinel.modules.operations.baseline import BaselineDelta, ChangeType

#: Permission classes that hand an app effective control of the device.
CONTROL_PERMISSIONS = {"accessibility", "device_admin"}
#: Permission classes that enable fraud / surveillance when abused.
SENSITIVE_PERMISSIONS = {"overlay", "notification_access", "sms", "call_log"}

#: A security patch older than this many days is a finding.
PATCH_MAX_AGE_DAYS = 180

#: Android Private DNS modes the companion can report (TASK-SEN-030).
PRIVATE_DNS_MODES = {"off", "opportunistic", "strict"}


class PermissionGrant(BaseModel):
    app_package: str
    app_label: str = ""
    permission: str
    trusted: bool = False
    """True for owner-trusted apps (e.g. the FRIDAY companion itself,
    whose accessibility use is the product working as designed)."""


class DevicePostureReport(BaseModel):
    """Posture facts about one Android device, as reported by the
    phone bridge / companion. Every field is a claim by the reporter;
    the evaluator judges the claims, it cannot verify them."""

    device_id: str
    os_version: str = ""
    security_patch: str = ""  # ISO date, e.g. "2026-10-05"
    screen_lock: bool = True
    unknown_sources_allowed: bool = False
    developer_options_on: bool = False
    adb_enabled: bool = False
    play_protect_enabled: bool = True
    device_encrypted: bool = True
    permission_grants: list[PermissionGrant] = Field(default_factory=list)
    paired_bluetooth: list[str] = Field(default_factory=list)
    trusted_bluetooth: list[str] = Field(default_factory=list)
    private_dns_mode: str = ""
    """Android Private DNS setting: 'off', 'opportunistic' or 'strict';
    empty when the companion does not report it (TASK-SEN-030)."""
    private_dns_hostname: str = ""
    """Private DNS provider hostname, reported when mode is 'strict'."""
    dns_servers: list[str] = Field(default_factory=list)
    """DNS resolver addresses the device is using, as reported."""
    trusted_dns_servers: list[str] = Field(default_factory=list)
    """Owner-trusted DNS resolver addresses."""


class PostureFinding(BaseModel):
    rule_id: str
    title: str
    severity: SeverityLevel
    target_ref: str
    description: str
    remediation: str
    evidence: str = ""


class DevicePostureEvaluator:
    """Judges one DevicePostureReport against the phone-safety rules."""

    def evaluate(
        self, report: DevicePostureReport, now: datetime | None = None
    ) -> list[PostureFinding]:
        now = now or datetime.now(UTC)
        ref = f"device:{report.device_id}"
        findings: list[PostureFinding] = []

        def add(rule_id, title, severity, description, remediation, evidence=""):
            findings.append(
                PostureFinding(
                    rule_id=rule_id,
                    title=title,
                    severity=severity,
                    target_ref=ref,
                    description=description,
                    remediation=remediation,
                    evidence=evidence,
                )
            )

        if report.unknown_sources_allowed:
            add(
                "DP-001",
                "Installs from unknown sources allowed",
                SeverityLevel.CRITICAL,
                "The device allows installing apps from unknown sources. "
                "This is the primary delivery path for banking-fraud APKs: "
                "a single sideloaded app bypasses every store review.",
                "Disable 'install via unknown sources' for every app that "
                "has it, and remove any app not installed from the Play Store.",
                "unknown_sources_allowed=true",
            )
        if report.adb_enabled:
            add(
                "DP-002",
                "USB debugging (ADB) enabled",
                SeverityLevel.HIGH,
                "ADB is enabled. Anyone with brief physical or paired "
                "wireless access gets a shell on the device.",
                "Turn off USB debugging; revoke USB debugging authorisations.",
                "adb_enabled=true",
            )
        if not report.screen_lock:
            add(
                "DP-003",
                "No screen lock set",
                SeverityLevel.HIGH,
                "The device has no screen lock. Physical access is full "
                "access — messages, banking apps, and the FRIDAY phone "
                "bridge included.",
                "Set a PIN/pattern/biometric screen lock.",
                "screen_lock=false",
            )
        if not report.device_encrypted:
            add(
                "DP-004",
                "Device storage not encrypted",
                SeverityLevel.HIGH,
                "Device storage is unencrypted; a lost device yields its "
                "data to whoever finds it.",
                "Enable device encryption (default on modern Android).",
                "device_encrypted=false",
            )

        for grant in report.permission_grants:
            if grant.trusted:
                continue
            who = grant.app_label or grant.app_package
            if grant.permission in CONTROL_PERMISSIONS:
                add(
                    "DP-005",
                    f"Untrusted app holds {grant.permission}",
                    SeverityLevel.HIGH,
                    f"'{who}' ({grant.app_package}) holds the "
                    f"{grant.permission} permission without being marked "
                    "owner-trusted. Accessibility/device-admin in an "
                    "untrusted app means it can read the screen and act "
                    "on the owner's behalf — the Phantom Droid pattern.",
                    "Revoke the permission or uninstall the app; if the "
                    "app is genuinely needed, mark it trusted deliberately.",
                    f"grant {grant.app_package} {grant.permission}",
                )
            elif grant.permission in SENSITIVE_PERMISSIONS:
                add(
                    "DP-006",
                    f"Untrusted app holds {grant.permission}",
                    SeverityLevel.MEDIUM,
                    f"'{who}' ({grant.app_package}) holds the "
                    f"{grant.permission} permission without being marked "
                    "owner-trusted — a fraud and surveillance enabler "
                    "(overlay phishing, notification/OTP reading).",
                    "Revoke the permission unless the app demonstrably needs it.",
                    f"grant {grant.app_package} {grant.permission}",
                )

        if not report.play_protect_enabled:
            add(
                "DP-007",
                "Play Protect disabled",
                SeverityLevel.MEDIUM,
                "Google Play Protect is off, removing the on-device scan "
                "that catches known-bad apps.",
                "Re-enable Play Protect in Play Store settings.",
                "play_protect_enabled=false",
            )

        if report.security_patch:
            try:
                patch_date = datetime.strptime(
                    report.security_patch, "%Y-%m-%d"
                ).replace(tzinfo=UTC)
                age_days = (now - patch_date).days
                if age_days > PATCH_MAX_AGE_DAYS:
                    add(
                        "DP-008",
                        "Security patch is stale",
                        SeverityLevel.MEDIUM,
                        f"Security patch level {report.security_patch} is "
                        f"{age_days} days old (limit {PATCH_MAX_AGE_DAYS}). "
                        "Known, patched-elsewhere exploits remain open.",
                        "Apply the latest system update, or treat the "
                        "device as untrusted for sensitive accounts.",
                        f"security_patch={report.security_patch} age_days={age_days}",
                    )
            except ValueError:
                add(
                    "DP-009",
                    "Security patch level unparseable",
                    SeverityLevel.INFO,
                    f"Reported patch level {report.security_patch!r} is "
                    "not an ISO date, so its age cannot be judged.",
                    "Report the patch level as an ISO date (YYYY-MM-DD).",
                    f"security_patch={report.security_patch!r}",
                )
        else:
            add(
                "DP-009",
                "Security patch level not reported",
                SeverityLevel.INFO,
                "The posture report carries no security patch level, so "
                "patch currency cannot be judged.",
                "Include the patch level (ISO date) in the posture report.",
                "security_patch missing",
            )

        trusted_bt = set(report.trusted_bluetooth)
        for name in report.paired_bluetooth:
            if name not in trusted_bt:
                add(
                    "DP-010",
                    "Untrusted Bluetooth pairing present",
                    SeverityLevel.MEDIUM,
                    f"Device '{name}' is paired over Bluetooth but not in "
                    "the owner-trusted list. Stale or unknown pairings are "
                    "an untrusted connection into the phone.",
                    "Remove the pairing, or add the device to the trusted "
                    "list deliberately.",
                    f"paired_bluetooth contains {name!r}",
                )

        if report.developer_options_on and not report.adb_enabled:
            add(
                "DP-011",
                "Developer options enabled",
                SeverityLevel.LOW,
                "Developer options are on (ADB itself is off). A standing "
                "invitation to weaken other checks later.",
                "Turn developer options off when not actively developing.",
                "developer_options_on=true",
            )

        # TASK-SEN-030: Private DNS + resolver hygiene.
        if report.private_dns_mode == "off":
            add(
                "DP-012",
                "Private DNS off",
                SeverityLevel.HIGH,
                "Private DNS is off, so DNS queries leave the device in "
                "cleartext on any network it joins — the Phantom Droid "
                "untrusted-connection pattern: a hostile network sees and "
                "can redirect every lookup.",
                "Turn on Private DNS (Automatic, or a strict hostname).",
                "private_dns_mode=off",
            )
        elif report.private_dns_mode == "":
            add(
                "DP-012",
                "Private DNS setting not reported",
                SeverityLevel.INFO,
                "The posture report carries no Private DNS setting, so "
                "DNS privacy cannot be judged.",
                "Include private_dns_mode in the posture report.",
                "private_dns_mode missing",
            )
        elif report.private_dns_mode not in PRIVATE_DNS_MODES:
            add(
                "DP-012",
                "Private DNS mode unrecognised",
                SeverityLevel.INFO,
                f"Reported Private DNS mode {report.private_dns_mode!r} is "
                "not one of off / opportunistic / strict, so it cannot be judged.",
                "Report private_dns_mode as off, opportunistic or strict.",
                f"private_dns_mode={report.private_dns_mode!r}",
            )
        elif report.private_dns_mode == "strict" and not report.private_dns_hostname:
            add(
                "DP-012",
                "Private DNS strict but no hostname reported",
                SeverityLevel.INFO,
                "Private DNS is strict, but no provider hostname was "
                "reported, so the strict endpoint cannot be judged.",
                "Include private_dns_hostname in the posture report.",
                "private_dns_hostname missing",
            )

        trusted_dns = set(report.trusted_dns_servers)
        for server in report.dns_servers:
            if server not in trusted_dns:
                add(
                    "DP-013",
                    "Untrusted DNS resolver in use",
                    SeverityLevel.MEDIUM,
                    f"DNS resolver {server} is in use but not in the "
                    "owner-trusted list. An untrusted resolver sees every "
                    "lookup and can answer with attacker-chosen addresses.",
                    "Use only owner-trusted resolvers, or add the resolver "
                    "to the trusted list deliberately.",
                    f"dns_servers contains {server!r}",
                )

        return findings


class CredentialPostureChecker:
    """Stat-only permission checks for fleet credential material.

    Never opens the files — mode bits only. This is the recurring form
    of TASK-SEN-011's one-off permission fixes.
    """

    def __init__(self, stat_fn: Callable[[str], os.stat_result] = os.stat):
        self._stat = stat_fn

    def check(
        self,
        env_files: list[str | Path],
        credential_dirs: list[str | Path],
        target_ref: str = "fleet-credentials",
    ) -> tuple[list[PostureFinding], list[str]]:
        findings: list[PostureFinding] = []
        missing: list[str] = []

        for raw in env_files:
            path = str(raw)
            try:
                mode = stat.S_IMODE(self._stat(path).st_mode)
            except OSError:
                missing.append(path)
                continue
            if mode != 0o600:
                findings.append(
                    PostureFinding(
                        rule_id="CP-001",
                        title="Credential file permissions too open",
                        severity=SeverityLevel.HIGH,
                        target_ref=target_ref,
                        description=(
                            f"{path} has mode {mode:04o}; fleet credential "
                            "files (.env) must be 0600. Anything broader "
                            "lets other local users read live API keys — "
                            "the SEN-011 F-3 condition (VyralX .env at 664)."
                        ),
                        remediation=f"chmod 600 {path}",
                        evidence=f"mode={mode:04o}",
                    )
                )

        for raw in credential_dirs:
            path = str(raw)
            try:
                mode = stat.S_IMODE(self._stat(path).st_mode)
            except OSError:
                missing.append(path)
                continue
            if mode != 0o700:
                findings.append(
                    PostureFinding(
                        rule_id="CP-002",
                        title="Credential directory permissions too open",
                        severity=SeverityLevel.MEDIUM,
                        target_ref=target_ref,
                        description=(
                            f"{path} has mode {mode:04o}; directories "
                            "holding credential material must be 0700 — "
                            "the SEN-011 F-2 condition (VyralX credentials "
                            "dir at 775 with token files at 664)."
                        ),
                        remediation=f"chmod 700 {path}",
                        evidence=f"mode={mode:04o}",
                    )
                )

        return findings, missing


def emit_posture_alerts(findings: list[PostureFinding], engine: Any) -> list[Any]:
    """Feed posture findings into the shared operations AlertEngine
    (the SEN-006/SEN-008 dispatch channel) as BaselineDeltas."""
    alerts = []
    for idx, finding in enumerate(findings):
        delta = BaselineDelta(
            delta_id=f"igsen02-{finding.target_ref}-{finding.rule_id}-{idx}",
            target_ref=finding.target_ref,
            change_type=ChangeType.NEW_FINDING,
            severity=finding.severity,
            description=(
                f"[{finding.rule_id}] {finding.title} — {finding.description} "
                f"Remediation: {finding.remediation}"
            ),
            new_state={"evidence": finding.evidence},
        )
        alerts.append(engine.process_delta(delta))
    return alerts
