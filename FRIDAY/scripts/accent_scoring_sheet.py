#!/usr/bin/env python3
"""
accent_scoring_sheet.py — E10: render the Indian-English accent-accuracy
scoring sheet for an owner voice session.

Reads FRIDAY/src/friday/voice/accent_phrase_corpus.json and prints (or writes)
a markdown scoring sheet: one row per phrase with what to say, what PASS looks
like, and empty pass/fail + notes cells. After the session, count PASSes:
accuracy >= 90% (17/18) = kit PASS.

Usage:
    python FRIDAY/scripts/accent_scoring_sheet.py            # print to stdout
    python FRIDAY/scripts/accent_scoring_sheet.py --out FILE # write markdown
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
CORPUS = REPO / "FRIDAY" / "src" / "friday" / "voice" / "accent_phrase_corpus.json"


def render_sheet(corpus: dict) -> str:
    lines = [
        "# E10 Accent-Accuracy Scoring Sheet — Indian-English / Telugu mix",
        "",
        f"Corpus v{corpus.get('version', '?')} ({len(corpus['phrases'])} phrases) · "
        "Owner speaks each phrase once during the voice session.",
        "",
        corpus.get("scoring_rule", ""),
        "",
        "| # | ID | Category | Say this | PASS looks like | OK? | Notes |",
        "|---|----|----------|----------|-----------------|-----|-------|",
    ]
    for i, p in enumerate(corpus["phrases"], 1):
        phrase = p["phrase"].replace("|", "/")
        criteria = p["pass_criteria"].replace("|", "/")
        lines.append(
            f"| {i} | {p['id']} | {p['category']} | {phrase} | {criteria} | | |"
        )
    n = len(corpus["phrases"])
    lines += [
        "",
        "## Result",
        "",
        f"- Passed: ____ / {n}",
        f"- Accuracy: ____ %  (PASS needs >= {int(0.9 * n + 0.999)}/{n})",
        "- Date / device / browser: ____________________",
        "- Verdict: [ ] KIT PASS   [ ] needs tuning (record failing IDs above)",
        "",
        "Post this sheet to issue #35 as TASK-E10 evidence.",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", help="write the sheet to this markdown file")
    args = parser.parse_args(argv)
    try:
        corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"cannot load corpus {CORPUS}: {exc}", file=sys.stderr)
        return 1
    sheet = render_sheet(corpus)
    if args.out:
        Path(args.out).write_text(sheet, encoding="utf-8")
        print(f"sheet written: {args.out}")
    else:
        print(sheet, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
