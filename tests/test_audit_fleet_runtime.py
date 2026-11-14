"""Hermetic runtime-audit regressions; no fleet connections or credentials."""
import importlib.util
import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "audit_fleet_runtime.py"
spec = importlib.util.spec_from_file_location("runtime_audit", SOURCE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
A, B = "a" * 40, "b" * 40


@pytest.mark.parametrize("code,body,ok", [
    (200, {"status": "ok"}, True), (200, {"status": "healthy"}, True),
    (200, {"status": "degraded"}, False), (200, {"status": "ok", "healthy": False}, False),
    (200, {"status": "ok", "ready": False}, False), (200, {"status": "not_initialized"}, False),
    (200, "<html>login</html>", False), (200, {}, False), (200, None, False),
    (503, {"status": "ok"}, False), (None, None, False),
])
def test_health_truth(code, body, ok):
    r = m.classify_health(code, body)
    assert r["health_ok"] is ok
    assert r["functional_verified"] is False


def test_exact_ten_agents():
    names = [n for group in m.PLACEMENT.values() for n in group]
    assert len(names) == len(set(names)) == 10
    assert "VyralX" in names


def test_git_counts_no_content_or_filenames(monkeypatch, tmp_path):
    answers = iter([A, A, " M secret-password-file\0?? token.env\0R  renamed\0old\0"])
    seen = []
    def run(args, cwd):
        seen.append(args)
        return next(answers)
    monkeypatch.setattr(m, "command", run)
    r = m.git_snapshot(tmp_path, B)
    assert r["tracked_changes"] == 2
    assert r["untracked_entries"] == 1
    assert r["protected_local_work"] is True
    assert r["matches_expected"] is False
    assert r["matches_cached_origin_main"] is True
    assert r["cached_ref_is_remote_verification"] is False
    assert "secret-password" not in json.dumps(r)
    assert "token.env" not in json.dumps(r)
    assert all(cmd[1] == "--no-optional-locks" for cmd in seen)
    assert all(cmd[2] in ("rev-parse", "status") for cmd in seen)


def test_real_temp_repo_does_not_change_work(monkeypatch, tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                    "commit", "--allow-empty", "-qm", "fixture"], check=True)
    (tmp_path / "private.env").write_text("do-not-read-me")
    before = subprocess.check_output(["git", "-C", str(tmp_path), "status", "--porcelain"])
    r = m.git_snapshot(tmp_path, None)
    after = subprocess.check_output(["git", "-C", str(tmp_path), "status", "--porcelain"])
    assert before == after
    assert r["untracked_entries"] == 1
    assert r["matches_expected"] is None
    assert "do-not-read-me" not in json.dumps(r)


def test_unknown_git_not_clean(monkeypatch, tmp_path):
    monkeypatch.setattr(m, "command", lambda *a: None)
    r = m.git_snapshot(tmp_path, A)
    assert r["protected_local_work"] is None
    assert r["matches_expected"] is None
    assert r["worktree_observed"] is False


def test_unit_filters_unrequested_fields(monkeypatch, tmp_path):
    monkeypatch.setattr(m, "command", lambda *a: "LoadState=loaded\nActiveState=active\nNRestarts=3\nEnvironment=secret")
    r = m.service_snapshot("FRIDAY", tmp_path)
    assert r["active"] is True
    assert "secret" not in json.dumps(r)


@pytest.mark.parametrize("failure", [FileNotFoundError("secret"), subprocess.TimeoutExpired("secret", 10)])
def test_command_redacts_errors(monkeypatch, tmp_path, failure):
    def run(*a, **kw):
        raise failure
    monkeypatch.setattr(m.subprocess, "run", run)
    assert m.command(["git"], tmp_path) is None


def test_http_bounded_and_does_not_print_payload(monkeypatch):
    response = MagicMock()
    response.__enter__.return_value = response
    response.status = 200
    response.read.return_value = b'{"status":"healthy","token":"secret"}'
    opener = MagicMock()
    opener.open.return_value = response
    monkeypatch.setattr(m.urllib.request, "build_opener", lambda *a: opener)
    r = m.health_snapshot(8001)
    assert r["health_ok"] is True
    response.read.assert_called_once_with(65537)
    opener.open.assert_called_once_with("http://127.0.0.1:8001/health", timeout=5)
    assert "secret" not in json.dumps(r)


def test_http_oversize_not_healthy(monkeypatch):
    response = MagicMock()
    response.__enter__.return_value = response
    response.status = 200
    response.read.return_value = b"x" * 65537
    opener = MagicMock()
    opener.open.return_value = response
    monkeypatch.setattr(m.urllib.request, "build_opener", lambda *a: opener)
    r = m.health_snapshot(8001)
    assert r["health_ok"] is False
    assert r["error"] == "response_too_large"


def test_redirect_refused():
    assert m.NoRedirect().redirect_request(None, None, 302, "", {}, "https://outside.invalid") is None


@pytest.mark.parametrize("runtime,revision,exitcode", [(True, True, 0), (True, False, 1), (False, True, 1), (False, False, 1)])
def test_exit_requires_runtime_and_fresh_revision(monkeypatch, capsys, runtime, revision, exitcode):
    monkeypatch.setattr(m, "audit", lambda *a: {"runtime_ok": runtime, "checkout_revision_verified": revision})
    assert m.main(["--server", "1", "--expected-revision", A]) == exitcode
    json.loads(capsys.readouterr().out)


@pytest.mark.parametrize("value", ["main", "--help", "a" * 7, "A" * 40, "https://secret@host"])
def test_expected_revision_is_only_sha(value):
    with pytest.raises(m.argparse.ArgumentTypeError):
        m.full_sha(value)
