"""
IntelX/routers/dark_web_monitor.py — IntelX Dark Web Monitor.

Monitors dark web for data leaks, breached credentials, leaked API keys,
and sensitive information exposure. Provides alerting, breach correlation,
and remediation tracking.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field

from fastapi import APIRouter, HTTPException

router = APIRouter()


@dataclass
class LeakRecord:
    """A data leak record."""
    leak_id: str
    source: str  # e.g., "darkweb_forum", "pastebin", "marketplace"
    source_url: str = ""
    breach_type: str = ""  # credentials, api_key, personal_data, financial
    description: str = ""
    affected_entities: list[str] = field(default_factory=list)
    leaked_at: float = 0.0
    discovered_at: float = 0.0
    severity: str = "high"  # low, medium, high, critical
    credential_count: int = 0
    verified: bool = False


@dataclass
class BreachAlert:
    """A breach alert."""
    alert_id: str
    leak_id: str
    affected_domain: str = ""
    affected_emails: list[str] = field(default_factory=list)
    alert_type: str = ""  # new_breach, updated_breach, credential_exposure
    severity: str = "high"
    message: str = ""
    action_required: bool = True
    created_at: float = 0.0


@dataclass
class CredentialExposure:
    """Credential exposure record."""
    exposure_id: str
    username: str = ""
    email: str = ""
    password_hash: str = ""  # hash of the password, not the password itself
    origin: str = ""
    leak_count: int = 0
    first_seen: float = 0.0
    last_seen: float = 0.0
    remediated: bool = False


@dataclass
class MonitoringConfig:
    """Dark web monitoring configuration."""
    config_id: str
    domains: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    email_alerts: bool = True
    api_key_alerts: bool = True
    auto_verify: bool = True
    scan_interval_hours: int = 6
    created_at: float = 0.0


@dataclass
class ScanResult:
    """Result of a dark web scan."""
    scan_id: str
    started_at: float = 0.0
    completed_at: float = 0.0
    sources_scanned: list[str] = field(default_factory=list)
    leaks_found: int = 0
    new_leaks: int = 0
    credentials_found: int = 0
    api_keys_found: int = 0
    scan_duration_ms: float = 0.0


@dataclass
class RemediationTracker:
    """Remediation tracking for a leak."""
    tracker_id: str
    leak_id: str
    affected_entities: list[str] = field(default_factory=list)
    remediation_steps: list[str] = field(default_factory=list)
    status: str = "pending"  # pending, in_progress, completed
    notified_entities: int = 0
    completed_at: float = 0.0


class DarkWebMonitor:
    """Dark web monitoring engine."""

    def __init__(self):
        self._leaks: dict[str, LeakRecord] = {}
        self._alerts: list[BreachAlert] = []
        self._exposures: dict[str, CredentialExposure] = {}
        self._configs: dict[str, MonitoringConfig] = {}
        self._scans: list[ScanResult] = []
        self._remediations: dict[str, RemediationTracker] = {}

    def add_leak(
        self,
        source: str,
        description: str,
        breach_type: str = "credentials",
        affected_entities: list[str] | None = None,
        severity: str = "high",
        credential_count: int = 0,
        verified: bool = False,
        source_url: str = "",
    ) -> LeakRecord:
        """Add an operator-submitted leak record.

        TASK-REL-017: records enter this store only when an operator submits
        them via the API. Nothing here may invent provenance: the source URL
        is whatever the submitter provided (empty when unknown), ``leaked_at``
        stays 0.0 (unknown) unless the submitter supplies one, and a record
        is ``verified`` only when the submitter explicitly asserts it.
        Previously this fabricated an ``*.example.com`` source URL, backdated
        ``leaked_at`` by a day, and stamped every record ``verified=True``.
        """
        leak = LeakRecord(
            leak_id=hashlib.md5(
                f"leak:{source}:{description[:30]}:{time.time()}".encode()
            ).hexdigest()[:12],
            source=source,
            source_url=source_url,
            breach_type=breach_type,
            description=description,
            affected_entities=affected_entities or [],
            leaked_at=0.0,
            discovered_at=time.time(),
            severity=severity,
            credential_count=credential_count,
            verified=verified,
        )
        self._leaks[leak.leak_id] = leak

        # Create alert
        if leak.affected_entities:
            alert = BreachAlert(
                alert_id=hashlib.md5(
                    f"alert:{leak.leak_id}:{time.time()}".encode()
                ).hexdigest()[:12],
                leak_id=leak.leak_id,
                affected_domain=leak.affected_entities[0] if leak.affected_entities else "",
                affected_emails=leak.affected_entities[:10],
                alert_type="new_breach",
                severity=leak.severity,
                message=f"New leak record submitted from {source}: {description[:100]}",
                action_required=True,
                created_at=time.time(),
            )
            self._alerts.append(alert)

        return leak

    def track_credential(
        self,
        username: str,
        email: str = "",
        origin: str = "",
    ) -> CredentialExposure:
        """Track a credential exposure."""
        exposure = CredentialExposure(
            exposure_id=hashlib.md5(
                f"exposure:{username}:{email}:{time.time()}".encode()
            ).hexdigest()[:12],
            username=username,
            email=email,
            # TASK-REL-017: unknown — never fabricate a password hash.
            password_hash="",
            origin=origin,
            leak_count=1,
            first_seen=time.time(),
            last_seen=time.time(),
            remediated=False,
        )

        existing = self._find_exposure(username, email)
        if existing:
            existing.leak_count += 1
            existing.last_seen = time.time()
            return existing

        self._exposures[exposure.exposure_id] = exposure
        return exposure

    def _find_exposure(self, username: str, email: str) -> CredentialExposure | None:
        """Find an existing exposure record."""
        for exp in self._exposures.values():
            if exp.username == username and exp.email == email:
                return exp
        return None

    def create_config(
        self,
        domains: list[str] | None = None,
        keywords: list[str] | None = None,
        scan_interval: int = 6,
    ) -> MonitoringConfig:
        """Create a monitoring configuration."""
        config = MonitoringConfig(
            config_id=hashlib.md5(
                f"config:{time.time()}".encode()
            ).hexdigest()[:12],
            domains=domains or ["example.com", "company.com"],
            keywords=keywords or ["password", "api_key", "secret", "token"],
            email_alerts=True,
            api_key_alerts=True,
            auto_verify=True,
            scan_interval_hours=scan_interval,
            created_at=time.time(),
        )
        self._configs[config.config_id] = config
        return config

    def run_scan(self) -> ScanResult:
        """Record a dark web scan attempt.

        TASK-REL-017: no dark-web data source is connected to IntelX — no
        Tor crawler, no leak-feed API, no marketplace monitor. A scan
        therefore checks zero sources and finds nothing. The previous
        implementation invented leak records with a coin flip
        (``random.random() > 0.5``) and presented them as findings; that
        fabrication is removed. This result is honest bookkeeping: a scan
        was requested, no source exists to scan.
        """
        start = time.time()

        result = ScanResult(
            scan_id=hashlib.md5(
                f"scan:{time.time()}".encode()
            ).hexdigest()[:12],
            started_at=start,
            sources_scanned=[],
        )

        result.new_leaks = 0
        result.completed_at = time.time()
        result.scan_duration_ms = (time.time() - start) * 1000

        self._scans.append(result)
        return result

    def start_remediation(self, leak_id: str, steps: list[str] | None = None) -> RemediationTracker:
        """Start remediation for a leak."""
        leak = self._leaks.get(leak_id)
        if not leak:
            raise HTTPException(404, f"Leak {leak_id} not found")

        tracker = RemediationTracker(
            tracker_id=hashlib.md5(
                f"remediation:{leak_id}:{time.time()}".encode()
            ).hexdigest()[:12],
            leak_id=leak_id,
            affected_entities=leak.affected_entities,
            remediation_steps=steps or [
                "Notify affected entities",
                "Force password resets",
                "Revoke exposed API keys",
                "Monitor for credential stuffing",
                "Update security posture",
            ],
            status="in_progress",
            notified_entities=len(leak.affected_entities),
        )

        self._remediations[tracker.tracker_id] = tracker
        return tracker

    def get_report(self) -> dict:
        """Get dark web monitoring report."""
        total_credentials = sum(e.leak_count for e in self._exposures.values())
        total_remediations = len(self._remediations)
        completed_remediations = sum(1 for r in self._remediations.values() if r.status == "completed")

        return {
            "data_source": "operator_submitted_records_only",
            "live_feed_connected": False,
            "total_leaks": len(self._leaks),
            "total_alerts": len(self._alerts),
            "total_credential_exposures": len(self._exposures),
            "total_credentials_tracked": total_credentials,
            "total_scans": len(self._scans),
            "total_remediations": total_remediations,
            "completed_remediations": completed_remediations,
            "critical_leaks": sum(1 for l in self._leaks.values() if l.severity == "critical"),
            "unremediated_credentials": sum(1 for e in self._exposures.values() if not e.remediated),
            "recent_alerts": [
                {
                    "type": a.alert_type,
                    "severity": a.severity,
                    "message": a.message[:100],
                    "action_required": a.action_required,
                }
                for a in self._alerts[-10:]
            ],
            "recent_scans": [
                {
                    "leaks_found": s.leaks_found,
                    "new_leaks": s.new_leaks,
                    "credentials": s.credentials_found,
                    "duration_ms": s.scan_duration_ms,
                }
                for s in self._scans[-5:]
            ],
        }


# Module-level singleton
dark_web_monitor = DarkWebMonitor()


# ── API Routes ──────────────────────────────────────────────────────────────


@router.post("/api/v1/intelex/darkweb/leaks")
async def add_leak(payload: dict):
    """Add an operator-submitted leak record."""
    leak = dark_web_monitor.add_leak(
        source=payload["source"],
        description=payload["description"],
        breach_type=payload.get("breach_type", "credentials"),
        affected_entities=payload.get("affected_entities", []),
        severity=payload.get("severity", "high"),
        credential_count=payload.get("credential_count", 0),
        verified=bool(payload.get("verified", False)),
        source_url=payload.get("source_url", ""),
    )
    return {
        "leak_id": leak.leak_id,
        "source": leak.source,
        "severity": leak.severity,
        "verified": leak.verified,
        "data_source": "operator_submitted",
    }


@router.post("/api/v1/intelex/darkweb/scan")
async def run_scan():
    """Run a dark web scan.

    TASK-REL-017: no dark-web data source is connected, so the scan checks
    no sources and finds nothing — the payload says so explicitly instead
    of returning invented leaks.
    """
    result = dark_web_monitor.run_scan()
    return {
        "status": "no_real_data_source",
        "data_source": "none_connected",
        "detail": (
            "No dark-web data source is connected to IntelX (no Tor crawler "
            "or leak-feed API), so this scan checked no sources. Records in "
            "this API are limited to operator-submitted leak reports."
        ),
        "scan_id": result.scan_id,
        "sources_scanned": result.sources_scanned,
        "leaks_found": result.leaks_found,
        "new_leaks": result.new_leaks,
        "credentials_found": result.credentials_found,
        "api_keys_found": result.api_keys_found,
        "duration_ms": result.scan_duration_ms,
    }


@router.post("/api/v1/intelex/darkweb/remediation")
async def start_remediation(payload: dict):
    """Start remediation for a leak."""
    tracker = dark_web_monitor.start_remediation(
        leak_id=payload["leak_id"],
        steps=payload.get("steps", []),
    )
    return {
        "tracker_id": tracker.tracker_id,
        "leak_id": tracker.leak_id,
        "status": tracker.status,
        "steps": tracker.remediation_steps,
    }


@router.get("/api/v1/intelex/darkweb/report")
async def get_report():
    """Get dark web monitoring report."""
    return dark_web_monitor.get_report()
