"""
Polyglot Compiler and Build Matrix implementations for Python, TypeScript, Go, Rust, Java, and C/C++.
"""

from __future__ import annotations

import logging
import py_compile
import re
import sys
import time
from pathlib import Path

from app.compilers.base import BaseCompiler
from app.compilers.models import (
    CompilationOptions,
    CompilationResult,
    CompilationStatus,
    CompilerDiagnostic,
    DiagnosticSeverity,
    LanguageTarget,
)

logger = logging.getLogger("forge.compilers.polyglot")


class PythonCompiler(BaseCompiler):
    """Python compiler using built-in py_compile and AST verification."""

    def __init__(self) -> None:
        super().__init__(LanguageTarget.PYTHON)

    def check_availability(self) -> bool:
        return True

    def compile(
        self,
        source_files: list[Path],
        options: CompilationOptions | None = None,
    ) -> CompilationResult:
        _opts = options or CompilationOptions()
        start_time = time.perf_counter()
        diagnostics: list[CompilerDiagnostic] = []
        errors_found = 0
        compiled_files: list[str] = []

        for src in source_files:
            file_path = str(src.resolve())
            compiled_files.append(file_path)
            try:
                # py_compile checks syntax and bytecode compilability
                py_compile.compile(file_path, doraise=True)
            except py_compile.PyCompileError as exc:
                errors_found += 1
                msg = str(exc)
                lineno = 1
                col_offset = 1
                snippet = ""

                # Extract line number if present
                match = re.search(r", line (\d+)", msg)
                if match:
                    lineno = int(match.group(1))

                try:
                    if src.is_file():
                        lines = src.read_text(encoding="utf-8", errors="ignore").splitlines()
                        if 1 <= lineno <= len(lines):
                            snippet = lines[lineno - 1]
                except Exception:
                    pass

                diagnostics.append(
                    CompilerDiagnostic(
                        file_path=file_path,
                        line=lineno,
                        column=col_offset,
                        severity=DiagnosticSeverity.ERROR,
                        message=msg.strip(),
                        code_snippet=snippet,
                        rule_code="PYTHON_SYNTAX_ERROR",
                    )
                )

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        status = (
            CompilationStatus.SUCCESS
            if errors_found == 0
            else CompilationStatus.FAILURE
        )
        exit_code = 0 if errors_found == 0 else 1

        return CompilationResult(
            target_language=self.language,
            status=status,
            exit_code=exit_code,
            stdout=f"Compiled {len(source_files) - errors_found}/{len(source_files)} Python files successfully.",
            stderr="\n".join(d.message for d in diagnostics),
            duration_ms=duration_ms,
            command_executed=[sys.executable, "-m", "py_compile"] + compiled_files,
            diagnostics=diagnostics,
        )

    def parse_diagnostics(self, stdout: str, stderr: str) -> list[CompilerDiagnostic]:
        diagnostics: list[CompilerDiagnostic] = []
        pattern = re.compile(r'File "(.*?)", line (\d+)(?:, in .*)?\n(?:\s*(.*?)\n)?(?:\s*\^)?\n([a-zA-Z0-9_]+Error: .*)')
        for match in pattern.finditer(stderr):
            fpath, line_str, snippet, msg = match.groups()
            diagnostics.append(
                CompilerDiagnostic(
                    file_path=fpath,
                    line=int(line_str),
                    column=1,
                    severity=DiagnosticSeverity.ERROR,
                    message=msg.strip(),
                    code_snippet=(snippet or "").strip(),
                )
            )
        return diagnostics


class TypeScriptCompiler(BaseCompiler):
    """TypeScript compiler runner using tsc or node --check fallback."""

    def __init__(self) -> None:
        super().__init__(LanguageTarget.TYPESCRIPT)

    def check_availability(self) -> bool:
        return self._find_binary("tsc") is not None or self._find_binary("node") is not None

    def compile(
        self,
        source_files: list[Path],
        options: CompilationOptions | None = None,
    ) -> CompilationResult:
        opts = options or CompilationOptions()
        tsc_bin = self._find_binary("tsc")
        node_bin = self._find_binary("node")

        if not tsc_bin and not node_bin:
            return CompilationResult(
                target_language=self.language,
                status=CompilationStatus.TOOL_NOT_FOUND,
                exit_code=-1,
                stdout="",
                stderr="Neither 'tsc' nor 'node' compiler found in PATH.",
                duration_ms=0.0,
            )

        cmd: list[str] = []
        if tsc_bin:
            cmd = [tsc_bin, "--noEmit"] + [str(p) for p in source_files]
            if opts.strict_mode:
                cmd.append("--strict")
            cmd.extend(opts.extra_flags)
        else:
            # Fallback to node syntax check on first file
            assert node_bin is not None
            cmd = [node_bin, "--check"] + [str(source_files[0])] if source_files else [node_bin, "--check"]

        exit_code, stdout, stderr, duration_ms = self._execute_subprocess(
            command=cmd,
            cwd=opts.working_dir,
            timeout_seconds=opts.timeout_seconds,
        )

        diagnostics = self.parse_diagnostics(stdout, stderr)
        status = (
            CompilationStatus.SUCCESS
            if exit_code == 0
            else (CompilationStatus.TIMEOUT if "timed out" in stderr else CompilationStatus.FAILURE)
        )

        return CompilationResult(
            target_language=self.language,
            status=status,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_ms=duration_ms,
            command_executed=cmd,
            diagnostics=diagnostics,
        )

    def parse_diagnostics(self, stdout: str, stderr: str) -> list[CompilerDiagnostic]:
        diagnostics: list[CompilerDiagnostic] = []
        # Example: src/index.ts(12,5): error TS2322: Type 'string' is not assignable to type 'number'.
        pattern = re.compile(
            r"^(.*?)\((\d+),(\d+)\):\s+(error|warning)\s+(TS\d+):\s+(.*)$",
            re.MULTILINE,
        )
        combined = f"{stdout}\n{stderr}"
        for match in pattern.finditer(combined):
            fpath, line, col, sev_str, code, msg = match.groups()
            severity = (
                DiagnosticSeverity.ERROR
                if sev_str.lower() == "error"
                else DiagnosticSeverity.WARNING
            )
            diagnostics.append(
                CompilerDiagnostic(
                    file_path=fpath.strip(),
                    line=int(line),
                    column=int(col),
                    severity=severity,
                    message=msg.strip(),
                    rule_code=code,
                )
            )
        return diagnostics


class GoCompiler(BaseCompiler):
    """Go compiler and vet verification runner."""

    def __init__(self) -> None:
        super().__init__(LanguageTarget.GO)

    def check_availability(self) -> bool:
        return self._find_binary("go") is not None

    def compile(
        self,
        source_files: list[Path],
        options: CompilationOptions | None = None,
    ) -> CompilationResult:
        opts = options or CompilationOptions()
        go_bin = self._find_binary("go")
        if not go_bin:
            return CompilationResult(
                target_language=self.language,
                status=CompilationStatus.TOOL_NOT_FOUND,
                exit_code=-1,
                stdout="",
                stderr="Go binary not found in PATH.",
                duration_ms=0.0,
            )

        cmd = [go_bin, "vet"] + ([str(p) for p in source_files] if source_files else ["./..."])
        cmd.extend(opts.extra_flags)

        exit_code, stdout, stderr, duration_ms = self._execute_subprocess(
            command=cmd,
            cwd=opts.working_dir,
            timeout_seconds=opts.timeout_seconds,
        )

        diagnostics = self.parse_diagnostics(stdout, stderr)
        status = (
            CompilationStatus.SUCCESS
            if exit_code == 0
            else (CompilationStatus.TIMEOUT if "timed out" in stderr else CompilationStatus.FAILURE)
        )

        return CompilationResult(
            target_language=self.language,
            status=status,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_ms=duration_ms,
            command_executed=cmd,
            diagnostics=diagnostics,
        )

    def parse_diagnostics(self, stdout: str, stderr: str) -> list[CompilerDiagnostic]:
        diagnostics: list[CompilerDiagnostic] = []
        # Example: ./main.go:10:2: undeclared name: foo
        pattern = re.compile(r"^(.*?):(\d+):(\d+):\s+(.*)$", re.MULTILINE)
        combined = f"{stdout}\n{stderr}"
        for match in pattern.finditer(combined):
            fpath, line, col, msg = match.groups()
            diagnostics.append(
                CompilerDiagnostic(
                    file_path=fpath.strip(),
                    line=int(line),
                    column=int(col),
                    severity=DiagnosticSeverity.ERROR,
                    message=msg.strip(),
                )
            )
        return diagnostics


class RustCompiler(BaseCompiler):
    """Rust compiler (cargo / rustc) verification runner."""

    def __init__(self) -> None:
        super().__init__(LanguageTarget.RUST)

    def check_availability(self) -> bool:
        return self._find_binary("cargo") is not None or self._find_binary("rustc") is not None

    def compile(
        self,
        source_files: list[Path],
        options: CompilationOptions | None = None,
    ) -> CompilationResult:
        opts = options or CompilationOptions()
        cargo_bin = self._find_binary("cargo")
        rustc_bin = self._find_binary("rustc")

        if not cargo_bin and not rustc_bin:
            return CompilationResult(
                target_language=self.language,
                status=CompilationStatus.TOOL_NOT_FOUND,
                exit_code=-1,
                stdout="",
                stderr="Neither 'cargo' nor 'rustc' found in PATH.",
                duration_ms=0.0,
            )

        cmd: list[str] = []
        if cargo_bin and (opts.working_dir and (opts.working_dir / "Cargo.toml").is_file()):
            cmd = [cargo_bin, "check", "--message-format=short"]
        elif rustc_bin and source_files:
            cmd = [rustc_bin, "--emit=metadata", str(source_files[0])]
        elif cargo_bin:
            cmd = [cargo_bin, "check", "--message-format=short"]
        else:
            assert rustc_bin is not None
            cmd = [rustc_bin, "--help"]

        cmd.extend(opts.extra_flags)

        exit_code, stdout, stderr, duration_ms = self._execute_subprocess(
            command=cmd,
            cwd=opts.working_dir,
            timeout_seconds=opts.timeout_seconds,
        )

        diagnostics = self.parse_diagnostics(stdout, stderr)
        status = (
            CompilationStatus.SUCCESS
            if exit_code == 0
            else (CompilationStatus.TIMEOUT if "timed out" in stderr else CompilationStatus.FAILURE)
        )

        return CompilationResult(
            target_language=self.language,
            status=status,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_ms=duration_ms,
            command_executed=cmd,
            diagnostics=diagnostics,
        )

    def parse_diagnostics(self, stdout: str, stderr: str) -> list[CompilerDiagnostic]:
        diagnostics: list[CompilerDiagnostic] = []
        # Example: src/main.rs:4:5: error[E0425]: cannot find value `x` in this scope
        pattern = re.compile(
            r"^(.*?):(\d+):(\d+):\s+(error|warning)(?:\[([a-zA-Z0-9]+)\])?:\s+(.*)$",
            re.MULTILINE,
        )
        combined = f"{stdout}\n{stderr}"
        for match in pattern.finditer(combined):
            fpath, line, col, sev_str, code, msg = match.groups()
            severity = (
                DiagnosticSeverity.ERROR
                if sev_str.lower() == "error"
                else DiagnosticSeverity.WARNING
            )
            diagnostics.append(
                CompilerDiagnostic(
                    file_path=fpath.strip(),
                    line=int(line),
                    column=int(col),
                    severity=severity,
                    message=msg.strip(),
                    rule_code=code,
                )
            )
        return diagnostics


class JavaCompiler(BaseCompiler):
    """Java compiler (javac) verification runner."""

    def __init__(self) -> None:
        super().__init__(LanguageTarget.JAVA)

    def check_availability(self) -> bool:
        return self._find_binary("javac") is not None

    def compile(
        self,
        source_files: list[Path],
        options: CompilationOptions | None = None,
    ) -> CompilationResult:
        opts = options or CompilationOptions()
        javac_bin = self._find_binary("javac")
        if not javac_bin:
            return CompilationResult(
                target_language=self.language,
                status=CompilationStatus.TOOL_NOT_FOUND,
                exit_code=-1,
                stdout="",
                stderr="javac compiler not found in PATH.",
                duration_ms=0.0,
            )

        cmd = [javac_bin, "-Xlint"] + [str(p) for p in source_files]
        cmd.extend(opts.extra_flags)

        exit_code, stdout, stderr, duration_ms = self._execute_subprocess(
            command=cmd,
            cwd=opts.working_dir,
            timeout_seconds=opts.timeout_seconds,
        )

        diagnostics = self.parse_diagnostics(stdout, stderr)
        status = (
            CompilationStatus.SUCCESS
            if exit_code == 0
            else (CompilationStatus.TIMEOUT if "timed out" in stderr else CompilationStatus.FAILURE)
        )

        return CompilationResult(
            target_language=self.language,
            status=status,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_ms=duration_ms,
            command_executed=cmd,
            diagnostics=diagnostics,
        )

    def parse_diagnostics(self, stdout: str, stderr: str) -> list[CompilerDiagnostic]:
        diagnostics: list[CompilerDiagnostic] = []
        # Example: Main.java:5: error: cannot find symbol
        pattern = re.compile(
            r"^(.*?):(\d+):\s+(error|warning):\s+(.*)$",
            re.MULTILINE,
        )
        combined = f"{stdout}\n{stderr}"
        for match in pattern.finditer(combined):
            fpath, line, sev_str, msg = match.groups()
            severity = (
                DiagnosticSeverity.ERROR
                if sev_str.lower() == "error"
                else DiagnosticSeverity.WARNING
            )
            diagnostics.append(
                CompilerDiagnostic(
                    file_path=fpath.strip(),
                    line=int(line),
                    column=1,
                    severity=severity,
                    message=msg.strip(),
                )
            )
        return diagnostics


class CppCompiler(BaseCompiler):
    """C/C++ compiler (g++, clang++, or gcc) runner."""

    def __init__(self, language: LanguageTarget = LanguageTarget.CPP) -> None:
        super().__init__(language)

    def check_availability(self) -> bool:
        return (
            self._find_binary("g++") is not None
            or self._find_binary("clang++") is not None
            or self._find_binary("gcc") is not None
        )

    def compile(
        self,
        source_files: list[Path],
        options: CompilationOptions | None = None,
    ) -> CompilationResult:
        opts = options or CompilationOptions()
        binary = (
            self._find_binary("g++")
            or self._find_binary("clang++")
            or self._find_binary("gcc")
        )

        if not binary:
            return CompilationResult(
                target_language=self.language,
                status=CompilationStatus.TOOL_NOT_FOUND,
                exit_code=-1,
                stdout="",
                stderr="C/C++ compiler (g++, clang++, or gcc) not found in PATH.",
                duration_ms=0.0,
            )

        cmd = [binary, "-fsyntax-only", "-Wall"] + [str(p) for p in source_files]
        cmd.extend(opts.extra_flags)

        exit_code, stdout, stderr, duration_ms = self._execute_subprocess(
            command=cmd,
            cwd=opts.working_dir,
            timeout_seconds=opts.timeout_seconds,
        )

        diagnostics = self.parse_diagnostics(stdout, stderr)
        status = (
            CompilationStatus.SUCCESS
            if exit_code == 0
            else (CompilationStatus.TIMEOUT if "timed out" in stderr else CompilationStatus.FAILURE)
        )

        return CompilationResult(
            target_language=self.language,
            status=status,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_ms=duration_ms,
            command_executed=cmd,
            diagnostics=diagnostics,
        )

    def parse_diagnostics(self, stdout: str, stderr: str) -> list[CompilerDiagnostic]:
        diagnostics: list[CompilerDiagnostic] = []
        # Example: main.cpp:10:5: error: 'foo' was not declared in this scope
        pattern = re.compile(
            r"^(.*?):(\d+):(\d+):\s+(error|warning):\s+(.*)$",
            re.MULTILINE,
        )
        combined = f"{stdout}\n{stderr}"
        for match in pattern.finditer(combined):
            fpath, line, col, sev_str, msg = match.groups()
            severity = (
                DiagnosticSeverity.ERROR
                if sev_str.lower() == "error"
                else DiagnosticSeverity.WARNING
            )
            diagnostics.append(
                CompilerDiagnostic(
                    file_path=fpath.strip(),
                    line=int(line),
                    column=int(col),
                    severity=severity,
                    message=msg.strip(),
                )
            )
        return diagnostics


class PolyglotCompilerMatrix:
    """
    Central build matrix coordinator across all supported languages.
    """

    EXTENSION_MAP: dict[str, LanguageTarget] = {
        ".py": LanguageTarget.PYTHON,
        ".ts": LanguageTarget.TYPESCRIPT,
        ".tsx": LanguageTarget.TYPESCRIPT,
        ".js": LanguageTarget.JAVASCRIPT,
        ".jsx": LanguageTarget.JAVASCRIPT,
        ".go": LanguageTarget.GO,
        ".rs": LanguageTarget.RUST,
        ".java": LanguageTarget.JAVA,
        ".cpp": LanguageTarget.CPP,
        ".cc": LanguageTarget.CPP,
        ".cxx": LanguageTarget.CPP,
        ".hpp": LanguageTarget.CPP,
        ".h": LanguageTarget.C,
        ".c": LanguageTarget.C,
    }

    def __init__(self) -> None:
        self.compilers: dict[LanguageTarget, BaseCompiler] = {
            LanguageTarget.PYTHON: PythonCompiler(),
            LanguageTarget.TYPESCRIPT: TypeScriptCompiler(),
            LanguageTarget.JAVASCRIPT: TypeScriptCompiler(),
            LanguageTarget.GO: GoCompiler(),
            LanguageTarget.RUST: RustCompiler(),
            LanguageTarget.JAVA: JavaCompiler(),
            LanguageTarget.CPP: CppCompiler(LanguageTarget.CPP),
            LanguageTarget.C: CppCompiler(LanguageTarget.C),
        }

    def get_compiler(self, language: LanguageTarget) -> BaseCompiler:
        """Retrieves compiler instance for given language target."""
        if language not in self.compilers:
            raise ValueError(f"Unsupported language target: {language}")
        return self.compilers[language]

    def detect_target(self, path: Path) -> LanguageTarget | None:
        """Detects language target from file extension."""
        suffix = path.suffix.lower()
        return self.EXTENSION_MAP.get(suffix)

    def compile(
        self,
        files_or_dir: Path | list[Path],
        target: LanguageTarget | None = None,
        options: CompilationOptions | None = None,
    ) -> CompilationResult:
        """
        Compiles the provided files or directory with automatic or explicit language targeting.
        """
        paths: list[Path] = []
        if isinstance(files_or_dir, Path):
            if files_or_dir.is_dir():
                paths = [p for p in files_or_dir.rglob("*") if p.is_file()]
            else:
                paths = [files_or_dir]
        else:
            paths = list(files_or_dir)

        if not paths:
            return CompilationResult(
                target_language=target or LanguageTarget.PYTHON,
                status=CompilationStatus.SKIPPED,
                exit_code=0,
                stdout="No files to compile.",
                stderr="",
                duration_ms=0.0,
            )

        # Infer target if not provided
        resolved_target = target
        if resolved_target is None:
            resolved_target = self.detect_target(paths[0]) or LanguageTarget.PYTHON

        compiler = self.get_compiler(resolved_target)
        return compiler.compile(paths, options=options)

    def compile_matrix(
        self,
        workspace: Path,
        options: CompilationOptions | None = None,
    ) -> dict[LanguageTarget, CompilationResult]:
        """
        Discovers all files in workspace grouped by language and runs compilation matrix.
        """
        results: dict[LanguageTarget, CompilationResult] = {}
        grouped_files: dict[LanguageTarget, list[Path]] = {}

        for p in workspace.rglob("*"):
            if p.is_file():
                # Avoid node_modules, .venv, etc.
                parts = set(p.parts)
                if parts.intersection({".venv", "venv", "__pycache__", "node_modules", "target", ".git"}):
                    continue
                lang = self.detect_target(p)
                if lang:
                    grouped_files.setdefault(lang, []).append(p)

        for lang, files in grouped_files.items():
            compiler = self.get_compiler(lang)
            results[lang] = compiler.compile(files, options=options)

        return results
