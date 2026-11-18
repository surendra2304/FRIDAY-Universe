"""Stratex self-experimentation (TASK-STR-EXP-001).

Self-Upgrade Programme, Stratex slice 1 — design:
Stratex/docs/SELF_EXPERIMENTS_DESIGN.md and the shared mechanism in
~/workspace/self-upgrade/DESIGN.md. The loop proposes experiments from
a closed catalogue, pre-declares each in its ledger before running it,
judges under the frozen bars, admits second-tier passers to the
FORWARD_TEST lane, and banks Memora lessons for every outcome.

The loop is DEFAULT OFF (STRATEX_SELF_EXPERIMENTS must be exactly
"on") and is deliberately NOT wired into the daemon in this slice;
activation is a separate coordinator step.
"""

__all__ = ["bounds", "catalogue", "counter", "judge", "ledger", "loop",
           "runner", "store"]
