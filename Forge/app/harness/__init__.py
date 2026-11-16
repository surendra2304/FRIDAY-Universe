"""Forge agent harness (TASK-IG2-FRG-05, ECC pattern adoption)."""

from app.harness.ecc_patterns import (
    PIPELINE_STAGES,
    HarnessRun,
    Hook,
    InstinctStore,
    ShieldFinding,
    scan_agent_config,
    stage_gate,
)

__all__ = [
    "PIPELINE_STAGES",
    "HarnessRun",
    "Hook",
    "InstinctStore",
    "ShieldFinding",
    "scan_agent_config",
    "stage_gate",
]
