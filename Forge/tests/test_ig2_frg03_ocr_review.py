"""TASK-IG2-FRG-03: open-code-review (ocr) as a PR-review supplement.

Pins the honesty properties: deterministic file selection, Delegation
Mode by default, honest UNAVAILABLE without the CLI, unparseable
output is a failed pass (never "no findings"), and — above all — the
OCR result can never change the existing review's gate verdict.

TASK-FRG-028: the command shape is pinned to the real CLI (ocr
v1.14.3, verified live 2026-11-25). Delegation is a subcommand
(``ocr delegate preview`` / ``ocr delegate rule``), NOT a ``--delegate``
flag; ``ocr review`` takes ``--from`` (not ``--base``) and no ``--file``
flag, and needs a configured provider, so it is opt-in only.
"""
from __future__ import annotations

import json

from forge_upgrade.ocr_review import (
    OcrFinding,
    OcrResult,
    build_delegate_preview_command,
    build_delegate_rule_command,
    build_ocr_review_command,
    parse_ocr_json,
    run_ocr_review,
    select_review_files,
    supplement_review,
)


class _Proc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _fake_runner_factory(seen, proc):
    def runner(cmd, **kwargs):
        seen.append(list(cmd))
        return proc
    return runner


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


def test_delegate_rule_command_is_the_default_pass() -> None:
    cmd = build_delegate_rule_command(["a.py", "b.py"])
    assert cmd[:3] == ["ocr", "delegate", "rule"]
    assert cmd[3:] == ["a.py", "b.py"]
    # No LLM flags anywhere: delegation needs no provider.
    assert "--delegate" not in cmd
    assert "--format" not in cmd


def test_delegate_preview_command_uses_from_not_base() -> None:
    assert build_delegate_preview_command() == ["ocr", "delegate", "preview"]
    assert build_delegate_preview_command("main") == [
        "ocr", "delegate", "preview", "--from", "main",
    ]


def test_review_command_uses_from_and_no_delegate_flag() -> None:
    cmd = build_ocr_review_command("main")
    assert cmd == ["ocr", "review", "--from", "main", "--format", "json"]
    assert "--base" not in cmd
    assert "--delegate" not in cmd
    assert "--file" not in cmd


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


def test_run_review_default_is_delegate_rule_not_llm_review(monkeypatch) -> None:
    monkeypatch.setattr(
        "forge_upgrade.ocr_review.shutil.which", lambda _: "/usr/bin/ocr"
    )
    seen: list[list[str]] = []
    proc = _Proc(0, "### Rule Group 1: system / **/*.py\n\nApplies to:\n- a.py\n")
    result = run_ocr_review(
        ["a.py"], runner=_fake_runner_factory(seen, proc)
    )
    assert result.status == "completed"
    assert result.findings == []  # rules, not findings — no LLM ran
    assert "1 rule groups" in result.detail
    assert seen == [["ocr", "delegate", "rule", "a.py"]]
    assert "review" not in seen[0]


def test_run_review_delegate_failure_is_failed(monkeypatch) -> None:
    monkeypatch.setattr(
        "forge_upgrade.ocr_review.shutil.which", lambda _: "/usr/bin/ocr"
    )
    proc = _Proc(1, "", "delegate: no git repository")
    result = run_ocr_review(
        ["a.py"], runner=_fake_runner_factory([], proc)
    )
    assert result.status == "failed"
    assert "no git repository" in result.detail


def test_run_review_provider_path_parses_findings(monkeypatch) -> None:
    monkeypatch.setattr(
        "forge_upgrade.ocr_review.shutil.which", lambda _: "/usr/bin/ocr"
    )
    seen: list[list[str]] = []
    payload = json.dumps(
        [{"file": "a.py", "line": 3, "severity": "warning",
          "rule": "SQLI", "message": "string-built query"}]
    )
    result = run_ocr_review(
        ["a.py"],
        provider_review=True,
        runner=_fake_runner_factory(seen, _Proc(0, payload)),
    )
    assert result.status == "completed"
    assert result.findings == [
        OcrFinding("a.py", 3, "warning", "SQLI", "string-built query")
    ]
    assert seen == [["ocr", "review", "--from", "main", "--format", "json"]]


def test_run_review_provider_path_unparseable_is_failed(monkeypatch) -> None:
    monkeypatch.setattr(
        "forge_upgrade.ocr_review.shutil.which", lambda _: "/usr/bin/ocr"
    )
    result = run_ocr_review(
        ["a.py"],
        provider_review=True,
        runner=_fake_runner_factory([], _Proc(0, "not json")),
    )
    assert result.status == "failed"
    assert "unparseable" in result.detail


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
