"""
Unit tests for the Polyglot Compiler and Build Matrix Subsystem.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from app.compilers.models import (
    CompilationStatus,
    DiagnosticSeverity,
    LanguageTarget,
)
from app.compilers.polyglot import (
    CppCompiler,
    GoCompiler,
    JavaCompiler,
    PolyglotCompilerMatrix,
    PythonCompiler,
    RustCompiler,
    TypeScriptCompiler,
)


def test_python_compiler_success() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        src = Path(tmp_dir) / "valid.py"
        src.write_text("def add(a: int, b: int) -> int:\n    return a + b\n", encoding="utf-8")

        compiler = PythonCompiler()
        assert compiler.check_availability() is True

        res = compiler.compile([src])
        assert res.is_success is True
        assert res.status == CompilationStatus.SUCCESS
        assert res.exit_code == 0
        assert len(res.diagnostics) == 0


def test_python_compiler_syntax_error() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        src = Path(tmp_dir) / "invalid.py"
        src.write_text("def broken(\n", encoding="utf-8")

        compiler = PythonCompiler()
        res = compiler.compile([src])
        assert res.is_success is False
        assert res.status == CompilationStatus.FAILURE
        assert res.exit_code == 1
        assert len(res.diagnostics) >= 1
        assert res.diagnostics[0].severity == DiagnosticSeverity.ERROR


def test_typescript_compiler_diagnostics_parser() -> None:
    compiler = TypeScriptCompiler()
    sample_stdout = "src/index.ts(14,5): error TS2322: Type 'string' is not assignable to type 'number'."
    diagnostics = compiler.parse_diagnostics(sample_stdout, "")
    assert len(diagnostics) == 1
    d = diagnostics[0]
    assert d.file_path == "src/index.ts"
    assert d.line == 14
    assert d.column == 5
    assert d.severity == DiagnosticSeverity.ERROR
    assert d.rule_code == "TS2322"
    assert "Type 'string' is not assignable" in d.message


def test_go_compiler_diagnostics_parser() -> None:
    compiler = GoCompiler()
    sample_stderr = "./server.go:22:9: undefined: HandlerFunc"
    diagnostics = compiler.parse_diagnostics("", sample_stderr)
    assert len(diagnostics) == 1
    d = diagnostics[0]
    assert d.file_path == "./server.go"
    assert d.line == 22
    assert d.column == 9
    assert "undefined: HandlerFunc" in d.message


def test_rust_compiler_diagnostics_parser() -> None:
    compiler = RustCompiler()
    sample_stderr = "src/lib.rs:18:5: error[E0308]: mismatched types"
    diagnostics = compiler.parse_diagnostics("", sample_stderr)
    assert len(diagnostics) == 1
    d = diagnostics[0]
    assert d.file_path == "src/lib.rs"
    assert d.line == 18
    assert d.column == 5
    assert d.rule_code == "E0308"
    assert "mismatched types" in d.message


def test_java_compiler_diagnostics_parser() -> None:
    compiler = JavaCompiler()
    sample_stderr = "App.java:12: error: cannot find symbol"
    diagnostics = compiler.parse_diagnostics("", sample_stderr)
    assert len(diagnostics) == 1
    d = diagnostics[0]
    assert d.file_path == "App.java"
    assert d.line == 12
    assert d.severity == DiagnosticSeverity.ERROR
    assert "cannot find symbol" in d.message


def test_cpp_compiler_diagnostics_parser() -> None:
    compiler = CppCompiler()
    sample_stderr = "main.cpp:8:12: error: use of undeclared identifier 'x'"
    diagnostics = compiler.parse_diagnostics("", sample_stderr)
    assert len(diagnostics) == 1
    d = diagnostics[0]
    assert d.file_path == "main.cpp"
    assert d.line == 8
    assert d.column == 12
    assert "use of undeclared identifier" in d.message


def test_polyglot_compiler_matrix_extension_detection() -> None:
    matrix = PolyglotCompilerMatrix()
    assert matrix.detect_target(Path("service.py")) == LanguageTarget.PYTHON
    assert matrix.detect_target(Path("app.tsx")) == LanguageTarget.TYPESCRIPT
    assert matrix.detect_target(Path("client.js")) == LanguageTarget.JAVASCRIPT
    assert matrix.detect_target(Path("main.go")) == LanguageTarget.GO
    assert matrix.detect_target(Path("lib.rs")) == LanguageTarget.RUST
    assert matrix.detect_target(Path("Main.java")) == LanguageTarget.JAVA
    assert matrix.detect_target(Path("engine.cpp")) == LanguageTarget.CPP
    assert matrix.detect_target(Path("header.h")) == LanguageTarget.C


def test_polyglot_compiler_matrix_workspace_compilation() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        p1 = tmp_path / "mod1.py"
        p1.write_text("x = 42\n", encoding="utf-8")
        p2 = tmp_path / "mod2.py"
        p2.write_text("y = 'hello'\n", encoding="utf-8")

        matrix = PolyglotCompilerMatrix()
        results = matrix.compile_matrix(tmp_path)
        assert LanguageTarget.PYTHON in results
        py_res = results[LanguageTarget.PYTHON]
        assert py_res.is_success is True
        assert py_res.status == CompilationStatus.SUCCESS
