"""TASK-IG2-FRG-03: open-code-review (ocr) as a PR-review supplement.

Pins the honesty properties: deterministic file selection, Delegation
Mode by default, honest UNAVAILABLE without the CLI, unparseable
output is a failed pass (never "no findings"), and — above all — the
OCR result can never change the existing review's gate verdict.
"""
from __future__ import annotations

import json

from forge_upgrade.ocr_review import (
    OcrFinding,
    OcrResult,
    build_ocr_command,
    parse_ocr_json,
    run_ocr_review,
    select_review_files,
    supplement_review,
)


def test_selection_skips_binaries_lockfiles_and_vendored() -> None:
    changed = [
        "Forge/app/main.py",
        "package-lock.json",
        "assets/logo.png",
        "node_modules/pkg/index.js",
        "Forge/ui/widget.generated.ts",
        "Stratex/app/engine.py",
    ]
    assert select_review_files(changed) == [
        "Forge/app/main.py",
        "Stratex/app/engine.py",
    ]


def test_command_defaults_to_delegation_mode() -> None:
    cmd = build_ocr_command(["a.py", "b.py"])
    assert cmd[0] == "ocr"
    assert "--delegate" in cmd
    assert "--format" in cmd and "json" in cmd
    assert "--delegate" not in build_ocr_command(["a.py"], delegation=False)


def test_parse_ocr_json_list_and_object_shapes() -> None:
    bare = json.dumps(
        [{"file": "a.py", "line": 7, "severity": "warning",
          "rule": "SQLI", "message": "string-built query"}]
    )
    findings = parse_ocr_json(bare)
    assert findings == [
        OcrFinding("a.py", 7, "warning", "SQLI", "string-built query")
    ]
    wrapped = json.dumps({"comments": [{"path": "b.py", "comment": "npe risk"}]})
    findings = parse_ocr_json(wrapped)
    assert findings[0].file == "b.py"
    assert findings[0].message == "npe risk"


def test_parse_ocr_json_garbage_raises() -> None:
    try:
        parse_ocr_json("not json at all")
    except ValueError:
        return
    raise AssertionError("unparseable output must raise, not pass silently")


def test_run_review_unavailable_without_cli(monkeypatch) -> None:
    monkeypatch.setattr("forge_upgrade.ocr_review.shutil.which", lambda _: None)
    result = run_ocr_review(["Forge/app/main.py"])
    assert result.status == "unavailable"
    assert result.findings == []


def test_run_review_no_reviewable_files_completes_empty() -> None:
    result = run_ocr_review(["logo.png", "package-lock.json"])
    # Either the CLI is absent (unavailable) or present with nothing to
    # review (completed, zero findings) — both are honest outcomes.
    assert result.status in {"unavailable", "completed"}
    assert result.findings == []


def test_supplement_never_changes_gate_verdict() -> None:
    scary = OcrResult(
        "completed",
        "ocr reviewed 1 files",
        findings=[OcrFinding("a.py", 1, "critical", "XSS", "unescaped output")],
    )
    for verdict in ("APPROVE", "REQUEST_CHANGES", "PASS", "FAIL"):
        combined = supplement_review(verdict, scary)
        assert combined.gate_verdict == verdict
        assert combined.gate_changed_by_ocr is False
        assert combined.ocr_findings == scary.findings


def test_supplement_when_ocr_unavailable_keeps_verdict_and_explains() -> None:
    combined = supplement_review("APPROVE", OcrResult("unavailable", "no cli"))
    assert combined.gate_verdict == "APPROVE"
    assert combined.ocr_status == "unavailable"
    assert "unavailable" in combined.note
