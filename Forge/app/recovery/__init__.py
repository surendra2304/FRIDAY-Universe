"""
Recovery and Self-Healing subsystem for Project FORGE.
"""

from app.recovery.classifier import (
    FailureClass,
    FailureClassifier,
    FailureDiagnosis,
    failure_classifier,
)
from app.recovery.engine import RecoveryEngine, recovery_engine
from app.recovery.loop_guard import AntiLoopController, anti_loop_controller
from app.recovery.repair import PatchApplicator, RepairPatch, patch_applicator

__all__ = [
    "AntiLoopController",
    "FailureClass",
    "FailureClassifier",
    "FailureDiagnosis",
    "PatchApplicator",
    "RecoveryEngine",
    "RepairPatch",
    "anti_loop_controller",
    "failure_classifier",
    "patch_applicator",
    "recovery_engine",
]
