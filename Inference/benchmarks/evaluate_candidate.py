#!/usr/bin/env python3
"""TASK-IG-INF-03 — CLI for the candidate evaluation pipeline.

    python benchmarks/evaluate_candidate.py --spec benchmarks/candidates/minimax.json
    python benchmarks/evaluate_candidate.py --spec benchmarks/candidates/bytez.json --out report.json --markdown report.md

Exit codes: 0 = ADMIT, 1 = REJECT, 2 = BLOCKED (no credentials /
no route). The JSON report is the machine-readable evidence; the
markdown rendering is the human side-by-side. See candidate_eval.py
for the discipline this implements (INF-005: a model enters the
catalogue only after a benchmark shows it actually SERVES).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from candidate_eval import CandidateSpec, evaluate_candidate, render_markdown  # noqa: E402

_EXIT = {"ADMIT": 0, "REJECT": 1, "BLOCKED_NO_CREDENTIALS": 2, "BLOCKED_NO_ROUTE": 2}


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate a candidate model for catalogue admission.")
    parser.add_argument("--spec", required=True, help="candidate spec JSON (see benchmarks/candidates/)")
    parser.add_argument("--out", help="write the JSON report here")
    parser.add_argument("--markdown", help="write the markdown report here")
    parser.add_argument("--probes", type=int, default=3, help="serve-check probes (default 3)")
    parser.add_argument("--base-url", help="override the spec's base_url")
    parser.add_argument("--model-id", help="override the spec's model_id")
    parser.add_argument("--api-key-env", help="override the spec's api_key_env")
    args = parser.parse_args()

    spec = CandidateSpec.load(args.spec)
    if args.base_url:
        spec.base_url = args.base_url
    if args.model_id:
        spec.model_id = args.model_id
    if args.api_key_env:
        spec.api_key_env = args.api_key_env

    report = asyncio.run(evaluate_candidate(spec, probes=args.probes))
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    if args.markdown:
        Path(args.markdown).write_text(render_markdown(report), encoding="utf-8")
    print(render_markdown(report))
    print(f"VERDICT: {report['verdict']}" + (f" ({report['reason']})" if report.get("reason") else ""))
    return _EXIT.get(report["verdict"], 1)


if __name__ == "__main__":
    raise SystemExit(main())
