#!/usr/bin/env python3
"""Score the TASK-VYR-007 sample scripts and print a markdown results table.

Run from the VyralX project root:

    python3 scripts/run_script_quality_samples.py

Standard library only (the scorer is dependency-free by design).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from app.services.script_quality import score_script  # noqa: E402
from script_quality_samples import GOOD_HISTORY_STORY, SAMPLES  # noqa: E402


def main() -> int:
    history_result = score_script(
        GOOD_HISTORY_STORY, lane=GOOD_HISTORY_STORY["lane"],
        fmt=GOOD_HISTORY_STORY["format"], hook_formula=GOOD_HISTORY_STORY["hook_formula"],
    )
    history_result = {**history_result, "script": "\n".join(GOOD_HISTORY_STORY["beats"])}
    print("| Sample | Lane / format | Score | Grade | Verdict | Gates | Weakest dimensions |")
    print("|---|---|---|---|---|---|---|")
    for sample in SAMPLES:
        recent = [history_result] if sample["id"] == "flawed_history_repeat" else None
        r = score_script(sample, lane=sample["lane"], fmt=sample["format"],
                         hook_formula=sample["hook_formula"], recent=recent)
        weakest = sorted(r["dimensions"].items(),
                         key=lambda kv: kv[1]["score"] / max(1, kv[1]["max"]))[:2]
        weak = ", ".join(f"{k} {v['score']}/{v['max']}" for k, v in weakest)
        gates = "; ".join(r["gates_failed"]) or "-"
        print(f"| {sample['id']} | {sample['lane']} / {sample['format']} | {r['score']} "
              f"| {r['grade']} | {r['verdict']} | {gates} | {weak} |")
        print(f"<!-- metrics: {r['metrics']} -->")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
