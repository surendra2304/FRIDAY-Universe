from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from forge_upgrade.exec_runner import ExecResult
from forge_upgrade.verification import VerificationEngine, VerificationPolicy


def result(
    command: str,
    *,
    exit_code: int = 0,
    stdout: str = "",
    stderr: str = "",
    timed_out: bool = False,
    stdout_truncated: bool = False,
    stderr_truncated: bool = False,
) -> ExecResult:
    return ExecResult(
        command,
        exit_code,
        stdout,
        stderr,
        timed_out,
        1.0,
        stdout_truncated,
        stderr_truncated,
    )


def test_static_parse_reports_syntax_errors_in_project_source(tmp_path: Path) -> None:
    source = tmp_path / "src" / "broken.py"
    source.parent.mkdir()
    source.write_text("def broken(:\n", encoding="utf-8")
    engine = VerificationEngine(str(tmp_path), VerificationPolicy())

    check = engine.static_parse()

    assert not check.passed
    assert check.exit_code == 1
    assert f"{source}:1:" in check.stdout


def test_static_parse_reports_non_utf8_source(tmp_path: Path) -> None:
    source = tmp_path / "src" / "invalid_encoding.py"
    source.parent.mkdir()
    source.write_bytes(b"print('valid')\n\xff")
    engine = VerificationEngine(str(tmp_path), VerificationPolicy())

    check = engine.static_parse()

    assert not check.passed
    assert check.exit_code == 1
    assert f"{source}:read_error:UnicodeDecodeError:" in check.stdout
    assert "utf-8" in check.stdout


def test_static_parse_reports_source_read_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "src" / "unreadable.py"
    source.parent.mkdir()
    source.write_text("print('valid')\n", encoding="utf-8")
    original_read_text = Path.read_text

    def fail_for_source(path: Path, *args, **kwargs) -> str:
        if path == source:
            raise PermissionError("read denied")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fail_for_source)
    engine = VerificationEngine(str(tmp_path), VerificationPolicy())

    check = engine.static_parse()

    assert not check.passed
    assert check.exit_code == 1
    assert f"{source}:read_error:PermissionError:read denied" in check.stdout


@pytest.mark.parametrize(
    "excluded_directory",
    [".venv", ".git", "node_modules", "__pycache__", "build", "dist", ".pytest_cache"],
)
def test_static_parse_skips_excluded_directories(
    tmp_path: Path, excluded_directory: str
) -> None:
    dependency_source = tmp_path / excluded_directory / "broken.py"
    dependency_source.parent.mkdir()
    dependency_source.write_text("def broken(:\n", encoding="utf-8")
    engine = VerificationEngine(str(tmp_path), VerificationPolicy())

    check = engine.static_parse()

    assert check.passed
    assert check.exit_code == 0
    assert str(dependency_source) not in check.stdout


def test_static_parse_rejects_source_symlinks_that_escape_project_root(tmp_path: Path) -> None:
    source = tmp_path / "source.py"
    outside = tmp_path.parent / f"{tmp_path.name}_outside.py"
    outside.write_text("print('outside')\n", encoding="utf-8")
    try:
        source.symlink_to(outside)
    except (NotImplementedError, OSError) as exc:
        outside.unlink(missing_ok=True)
        pytest.skip(f"file symlinks are unavailable: {exc}")

    try:
        check = VerificationEngine(str(tmp_path), VerificationPolicy()).static_parse()
        assert not check.passed
        assert f"{source}:path_escapes_project_root" in check.stdout
    finally:
        outside.unlink(missing_ok=True)


def test_static_parse_fails_when_project_root_is_missing(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    check = VerificationEngine(str(missing), VerificationPolicy()).static_parse()

    assert not check.passed
    assert check.exit_code == 1
    assert f"{missing.resolve()}:project_root_not_directory" in check.stdout


@pytest.mark.asyncio
async def test_clean_git_policy_adds_mandatory_cleanliness_check(tmp_path: Path) -> None:
    engine = VerificationEngine(str(tmp_path), VerificationPolicy(require_clean_git=True))
    engine.runner.run = AsyncMock(  # type: ignore[method-assign]
        return_value=result("git status --porcelain --untracked-files=all")
    )

    report = await engine.run()

    git_check = next(check for check in report.checks if check.name == "git_clean")
    assert git_check.passed
    assert git_check.mandatory
    assert report.passed
    engine.runner.run.assert_awaited_once_with(
        "git status --porcelain --untracked-files=all", timeout_seconds=30
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("runner_result", "expected_exit_code"),
    [
        (result("git status", stdout=" M source.py\n"), 0),
        (result("git status", exit_code=128, stderr="not a git repository"), 128),
        (result("git status", exit_code=-9, timed_out=True), -9),
    ],
)
async def test_clean_git_policy_fails_for_dirty_or_unavailable_repository(
    tmp_path: Path, runner_result: ExecResult, expected_exit_code: int
) -> None:
    engine = VerificationEngine(str(tmp_path), VerificationPolicy(require_clean_git=True))
    engine.runner.run = AsyncMock(return_value=runner_result)  # type: ignore[method-assign]

    report = await engine.run()

    git_check = next(check for check in report.checks if check.name == "git_clean")
    assert not git_check.passed
    assert git_check.mandatory
    assert git_check.exit_code == expected_exit_code
    assert not report.passed


@pytest.mark.asyncio
async def test_git_status_is_not_run_when_policy_does_not_require_clean_tree(
    tmp_path: Path,
) -> None:
    engine = VerificationEngine(str(tmp_path), VerificationPolicy())
    engine.runner.run = AsyncMock()  # type: ignore[method-assign]

    report = await engine.run()

    assert all(check.name != "git_clean" for check in report.checks)
    engine.runner.run.assert_not_awaited()


@pytest.mark.asyncio
async def test_command_failure_preserves_output_and_fails_mandatory_check(
    tmp_path: Path,
) -> None:
    engine = VerificationEngine(
        str(tmp_path), VerificationPolicy(mandatory_commands=("pytest -q",))
    )
    engine.runner.run = AsyncMock(  # type: ignore[method-assign]
        return_value=result(
            "pytest -q", exit_code=1, stdout="2 failed", stderr="assertion failed"
        )
    )

    report = await engine.run()

    check = next(check for check in report.checks if check.name == "pytest -q")
    assert not check.passed
    assert check.mandatory
    assert check.exit_code == 1
    assert check.stdout == "2 failed"
    assert check.stderr == "assertion failed"
    assert report.mandatory_failures == ("pytest -q",)


@pytest.mark.asyncio
async def test_timed_out_command_includes_timeout_diagnostic_and_preserves_truncation(
    tmp_path: Path,
) -> None:
    engine = VerificationEngine(
        str(tmp_path), VerificationPolicy(mandatory_commands=("slow-check",))
    )
    engine.runner.run = AsyncMock(  # type: ignore[method-assign]
        return_value=result(
            "slow-check",
            exit_code=-9,
            stderr="partial diagnostic",
            timed_out=True,
            stdout_truncated=True,
            stderr_truncated=True,
        )
    )

    report = await engine.run()

    check = next(check for check in report.checks if check.name == "slow-check")
    assert not check.passed
    assert check.exit_code == -9
    assert check.stderr == "partial diagnostic\ncommand timed out after 300 seconds"
    assert check.stdout_truncated
    assert check.stderr_truncated
    assert report.mandatory_failures == ("slow-check",)


@pytest.mark.asyncio
async def test_runner_oserror_is_reported_and_does_not_abort_later_checks(
    tmp_path: Path,
) -> None:
    engine = VerificationEngine(
        str(tmp_path),
        VerificationPolicy(
            mandatory_commands=("required-check",),
            optional_commands=("optional-check", "later-optional-check"),
        ),
    )
    engine.runner.run = AsyncMock(  # type: ignore[method-assign]
        side_effect=[
            result("required-check"),
            OSError("runner unavailable"),
            result("later-optional-check"),
        ]
    )

    report = await engine.run()

    failed_optional = next(check for check in report.checks if check.name == "optional-check")
    required = next(check for check in report.checks if check.name == "required-check")
    later = next(check for check in report.checks if check.name == "later-optional-check")
    assert not failed_optional.passed
    assert not failed_optional.mandatory
    assert failed_optional.exit_code == 127
    assert failed_optional.stderr == "failed to start command (OSError): runner unavailable"
    assert required.passed
    assert required.mandatory
    assert later.passed
    assert report.passed
    assert engine.runner.run.await_count == 3
