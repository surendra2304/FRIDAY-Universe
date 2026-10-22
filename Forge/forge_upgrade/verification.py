from __future__ import annotations

import ast
import os
from dataclasses import dataclass, replace
from pathlib import Path
from time import perf_counter

from .exec_runner import ExecResult, SandboxedCommandRunner
from .models import VerificationCheck, VerificationReport

_EXCLUDED_PARSE_DIRECTORIES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "venv",
}


@dataclass(frozen=True, slots=True)
class VerificationPolicy:
    mandatory_commands: tuple[str, ...] = ()
    optional_commands: tuple[str, ...] = ()
    require_clean_git: bool = False


class VerificationEngine:
    """Run static parsing and configured project checks, retaining actionable evidence."""

    def __init__(self, project_root: str, policy: VerificationPolicy):
        self.root = Path(project_root).resolve()
        self.policy = policy
        self.runner = SandboxedCommandRunner(str(self.root))

    def static_parse(self) -> VerificationCheck:
        failures: list[str] = []
        if not self.root.is_dir():
            failures.append(f"{self.root}:project_root_not_directory")
        else:
            def walk_error(exc: OSError) -> None:
                location = exc.filename or str(self.root)
                failures.append(f"{location}:walk_error:{type(exc).__name__}:{exc}")

            for directory, subdirectories, filenames in os.walk(
                self.root, onerror=walk_error, followlinks=False
            ):
                current = Path(directory)
                subdirectories[:] = sorted(
                    name
                    for name in subdirectories
                    if name not in _EXCLUDED_PARSE_DIRECTORIES
                    and not (current / name).is_symlink()
                )
                for filename in sorted(filenames):
                    if not filename.endswith(".py"):
                        continue

                    path = current / filename
                    try:
                        resolved_path = path.resolve(strict=True)
                        try:
                            resolved_path.relative_to(self.root)
                        except ValueError:
                            failures.append(f"{path}:path_escapes_project_root")
                            continue
                        source = resolved_path.read_text(encoding="utf-8")
                        ast.parse(source, filename=str(path))
                    except SyntaxError as exc:
                        failures.append(f"{path}:{exc.lineno}:{exc.msg}")
                    except (OSError, UnicodeError) as exc:
                        failures.append(f"{path}:read_error:{type(exc).__name__}:{exc}")

        passed = not failures
        return VerificationCheck(
            name="python_ast",
            command="internal:python_ast",
            passed=passed,
            exit_code=0 if passed else 1,
            stdout="\n".join(failures),
            stderr="",
        )

    async def _run_command(self, command: str, timeout_seconds: float) -> ExecResult:
        started = perf_counter()
        try:
            result = await self.runner.run(command, timeout_seconds=timeout_seconds)
        except OSError as exc:
            return ExecResult(
                command=command,
                exit_code=127,
                stdout="",
                stderr=f"failed to start command ({type(exc).__name__}): {exc}",
                timed_out=False,
                duration_ms=(perf_counter() - started) * 1000,
            )

        if result.timed_out:
            diagnostic = f"command timed out after {timeout_seconds:g} seconds"
            stderr = "\n".join(part for part in (result.stderr, diagnostic) if part)
            return replace(result, stderr=stderr)
        return result

    async def run(self, baseline: bool = False) -> VerificationReport:
        checks = [self.static_parse()]
        mandatory_commands = self.policy.mandatory_commands
        for command in mandatory_commands + self.policy.optional_commands:
            result = await self._run_command(command, timeout_seconds=300)
            checks.append(
                VerificationCheck(
                    name=command,
                    command=command,
                    passed=result.exit_code == 0 and not result.timed_out,
                    exit_code=result.exit_code,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    mandatory=command in mandatory_commands,
                    stdout_truncated=result.stdout_truncated,
                    stderr_truncated=result.stderr_truncated,
                )
            )

        if self.policy.require_clean_git:
            command = "git status --porcelain --untracked-files=all"
            result = await self._run_command(command, timeout_seconds=30)
            clean = result.exit_code == 0 and not result.timed_out and not result.stdout.strip()
            checks.append(
                VerificationCheck(
                    name="git_clean",
                    command=command,
                    passed=clean,
                    exit_code=result.exit_code,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    mandatory=True,
                    stdout_truncated=result.stdout_truncated,
                    stderr_truncated=result.stderr_truncated,
                )
            )

        return VerificationReport(task_id="", checks=tuple(checks), baseline=baseline)
