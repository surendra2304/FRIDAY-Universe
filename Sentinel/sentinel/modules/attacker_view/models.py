"""Data models for the attacker-view self-audit (TASK-IG-SEN-01).

The audit looks at the owner's OWN fleet and devices the way an attacker
would — exposed services, unauthenticated endpoints, open cameras, weak
Wi-Fi configuration — but it is strictly defensive and read-only:

* Every probe target must be on the config's explicit ``allowed_hosts``
  allowlist. Anything else is refused and recorded, never probed.
* Probes are limited to TCP connect checks and unauthenticated HTTP GETs.
  No authentication attempts, no exploitation, no writes.

Sources (owner's Instagram reference corpus, 2026-11-15):
* DVYxqjPE5km — audit networks as an attacker sees them (exposed cameras
  and open services; "most exposed cameras are left open, not hacked").
* DXb4CpmDBcx — home-router WPS risk check.
* DWWlMNyCA2O — login-bypass / auth-misconfiguration checks on own surface.
"""

from __future__ import annotations

from datetime import datetime, timezone

UTC = timezone.utc  # Python 3.10-compatible alias for the 3.11+ name

from pydantic import BaseModel, Field

from sentinel.core.models import SeverityLevel


class ServiceTarget(BaseModel):
    """One TCP service on an owned host."""

    host: str
    port: int
    label: str = ""
    expect_public: bool = False
    """True only if this port is part of the documented public surface
    (SEN-016 end-state: 22/80/443). Anything else answering on a public
    host is an exposure finding."""


class HttpTarget(BaseModel):
    """One HTTP endpoint on an owned service."""

    url: str
    label: str = ""
    auth_required: bool = True
    """True when the endpoint must reject unauthenticated requests.
    An unauthenticated 200 on such an endpoint is an auth-misconfiguration
    (login-bypass surface) finding."""


class CameraTarget(BaseModel):
    """One owner-owned camera / IoT device to check for open access."""

    host: str
    port: int = 80
    snapshot_path: str = "/snapshot.jpg"
    label: str = ""


class WifiObservation(BaseModel):
    """One observed access point (from a scan or the owner's router UI)."""

    ssid: str
    security_mode: str = ""
    wps_enabled: bool = False
    management_on_wireless: bool = False


class AuditConfig(BaseModel):
    """Full audit configuration. ``allowed_hosts`` is the hard boundary:
    probes refuse any host not listed here."""

    allowed_hosts: list[str]
    target_ref: str = "fleet"
    services: list[ServiceTarget] = Field(default_factory=list)
    http_targets: list[HttpTarget] = Field(default_factory=list)
    cameras: list[CameraTarget] = Field(default_factory=list)
    wifi: list[WifiObservation] = Field(default_factory=list)


class AuditFinding(BaseModel):
    rule_id: str
    title: str
    severity: SeverityLevel
    target_ref: str
    description: str
    remediation: str
    evidence: str = ""


class AuditReport(BaseModel):
    target_ref: str
    findings: list[AuditFinding] = Field(default_factory=list)
    checks_run: list[str] = Field(default_factory=list)
    refused_targets: list[str] = Field(default_factory=list)
    unreachable_targets: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
