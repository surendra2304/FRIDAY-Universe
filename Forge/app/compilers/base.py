"""
Base compiler interface and execution harness.
"""

from __future__ import annotations

import abc
import os
import shutil
import subprocess
import time
from pathlib import Path

from app.compilers.models import (
    CompilationOptions,
    CompilationResult,
    CompilerDiagnostic,
    LanguageTarget,
)


class BaseCompiler(abc.ABC):
    """Abstract base class for all language-specific compilers and build runners."""

    def __init__(self, language: LanguageTarget) -> None:
        self.language = language

    @abc.abstractmethod
    def check_availability(self) -> bool:
        """Determines if the underlying compiler binary or runtime is available on the system."""
        pass

    @abc.abstractmethod
    def compile(
        self,
        source_files: list[Path],
        options: CompilationOptions | None = None,
    ) -> CompilationResult:
        """Compiles or syntax-checks the provided source files."""
        pass

    @abc.abstractmethod
    def parse_diagnostics(self, stdout: str, stderr: str) -> list[CompilerDiagnostic]:
        """Parses compiler output into structured CompilerDiagnostic instances."""
        pass

    def _execute_subprocess(
        self,
        command: list[str],
        cwd: Path | None,
        timeout_seconds: float,
    ) -> tuple[int, str, str, float]:
        """
        Executes a compiler command as an isolated child process with timeout protection.
        Returns (exit_code, stdout, stderr, duration_ms).
        """
        start_time = time.perf_counter()
        try:
            creationflags = (
                subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0  # type: ignore[attr-defined]
            )
            proc = subprocess.run(
                command,
                cwd=str(cwd) if cwd else None,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                creationflags=creationflags,
            )
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return proc.returncode, proc.stdout, proc.stderr, duration_ms

        except subprocess.TimeoutExpired as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            stdout = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout or b"").decode("utf-8", "ignore")
            stderr = exc.stderr if isinstance(exc.stderr, str) else (exc.stderr or b"").decode("utf-8", "ignore")
            return -1, stdout, stderr + f"\nProcess timed out after {timeout_seconds}s", duration_ms

        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return -1, "", str(exc), duration_ms

    @staticmethod
    def _find_binary(binary_name: str) -> str | None:
        """Finds executable binary in system PATH."""
        return shutil.which(binary_name)
