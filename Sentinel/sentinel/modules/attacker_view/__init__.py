"""Attacker-view self-audit package (TASK-IG-SEN-01).

Defensive, read-only audits of the owner's own fleet and devices:
service exposure, auth posture, camera exposure, and Wi-Fi posture
(the last via the existing wireless config assessment adapter).
Findings are reported through the shared operations AlertEngine.
"""

from sentinel.modules.attacker_view.audit import (
    AttackerViewAudit,
    default_fleet_config,
)
from sentinel.modules.attacker_view.models import (
    AuditConfig,
    AuditFinding,
    AuditReport,
    CameraTarget,
    HttpTarget,
    ServiceTarget,
    WifiObservation,
)

__all__ = [
    "AttackerViewAudit",
    "AuditConfig",
    "AuditFinding",
    "AuditReport",
    "CameraTarget",
    "HttpTarget",
    "ServiceTarget",
    "WifiObservation",
    "default_fleet_config",
]
