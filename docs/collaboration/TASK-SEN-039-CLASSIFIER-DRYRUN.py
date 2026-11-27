#!/usr/bin/env python3
"""TASK-SEN-039 checkpoint 2: classifier dry-run for the run-5 legs.

Runs the repo's own approval classifier (Sentinel/sentinel/gatekeeper/
approval_policy.py, stdlib-only per its module docstring) against the exact
planned run-5 actions, plus the run-3 legs as controls. No live effect: no
network, no ledger write, no Telegram, no server call. Run from the repo
root: python3 docs/collaboration/TASK-SEN-039-CLASSIFIER-DRYRUN.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "Sentinel"))

from sentinel.gatekeeper.approval_policy import classify_approval  # noqa: E402

CASES = [
    ("RUN5-LEG1", "MUSE_19", "check sentinel approval queue status", "LOW",
     {"purpose": "TASK-SEN-039 leg 1 proof", "task": "TASK-SEN-039"}),
    ("RUN5-LEG2", "MUSE_19", "rotate sentinel API key in production", "HIGH",
     {"purpose": "TASK-SEN-039 leg 2 proof, prompt only", "task": "TASK-SEN-039"}),
    ("CONTROL-RUN3-LEG1", "MUSE_4", "check sentinel health status", "LOW",
     {"purpose": "TASK-SEN-037 leg 1 proof", "task": "TASK-SEN-037"}),
    ("CONTROL-RUN3-LEG2", "MUSE_4", "deploy sentinel configuration change to production", "HIGH",
     {"purpose": "TASK-SEN-037 leg 2 proof, prompt only", "task": "TASK-SEN-037"}),
]

EXPECTED = {
    "RUN5-LEG1": ("AUTO_APPROVE", "read_only"),
    "RUN5-LEG2": ("OWNER_PROMPT", "credential_change"),
    "CONTROL-RUN3-LEG1": ("AUTO_APPROVE", "read_only"),
    "CONTROL-RUN3-LEG2": ("OWNER_PROMPT", "caller_risk_not_low"),
}


def main() -> int:
    failures = 0
    for name, agent, action, risk, details in CASES:
        result = classify_approval(agent_name=agent, action=action,
                                   risk_level=risk, details=details)
        want_tier, want_category = EXPECTED[name]
        ok = str(result.tier) == want_tier and result.category == want_category
        failures += 0 if ok else 1
        print(f"{name}: tier={result.tier} category={result.category} "
              f"hard_bound={result.hard_bound} {'OK' if ok else 'MISMATCH'}")
        print(f"   reason={result.reason!r}")
    print(f"{len(CASES) - failures}/{len(CASES)} classifications as expected")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
