"""
Unit tests for the Automated Refactoring Engine and AST Transformers.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from app.refactoring.analyzer import ASTCodeAnalyzer
from app.refactoring.engine import RefactoringEngine
from app.refactoring.models import (
    IssueSeverity,
    RefactoringRuleType,
)
from app.refactoring.transformer import (
    ASTCodeTransformer,
)


def test_complexity_visitor_basic() -> None:
    code = """
def sample_func(x, y):
    if x > 0:
        for i in range(x):
            if i % 2 == 0:
                print(i)
    return y
"""
    issues, metrics = ASTCodeAnalyzer.analyze_source(code, "test.py")
    assert "sample_func" in metrics
    m = metrics["sample_func"]
    assert m.cyclomatic_complexity >= 3
    assert m.max_nesting_depth >= 3
    assert m.num_returns == 1
    assert m.num_arguments == 2


def test_analyzer_detects_mutable_defaults() -> None:
    code = """
def bad_func(a, b=[], c={}):
    b.append(a)
    return b
"""
    issues, _ = ASTCodeAnalyzer.analyze_source(code, "bad.py")
    mutable_issues = [
        i for i in issues if i.rule_type == RefactoringRuleType.MUTABLE_DEFAULT_FIX
    ]
    assert len(mutable_issues) == 2
    assert mutable_issues[0].severity == IssueSeverity.WARNING


def test_analyzer_detects_bare_except() -> None:
    code = """
def risky():
    try:
        1 / 0
    except:
        pass
"""
    issues, _ = ASTCodeAnalyzer.analyze_source(code, "risky.py")
    bare_issues = [
        i for i in issues if i.rule_type == RefactoringRuleType.BARE_EXCEPT_FIX
    ]
    assert len(bare_issues) == 1
    assert bare_issues[0].suggested_fix == "except Exception:"


def test_analyzer_detects_legacy_typing() -> None:
    code = """
from typing import List, Dict, Any

def process(items: List[Dict[str, Any]]) -> None:
    pass
"""
    issues, _ = ASTCodeAnalyzer.analyze_source(code, "typing_legacy.py")
    typing_issues = [
        i for i in issues if i.rule_type == RefactoringRuleType.TYPE_ANNOTATION_UPGRADE
    ]
    assert len(typing_issues) >= 2


def test_transformer_mutable_default_fix() -> None:
    code = """def append_item(val, container=[]):
    container.append(val)
    return container"""
    changes = ASTCodeTransformer.apply_transformations(
        code,
        rules=[RefactoringRuleType.MUTABLE_DEFAULT_FIX],
    )
    assert len(changes) == 1
    refactored = changes[0].refactored_code
    assert "container=None" in refactored
    assert "if container is None:" in refactored
    assert "container = []" in refactored


def test_transformer_bare_except_fix() -> None:
    code = """try:
    do_something()
except:
    recover()"""
    changes = ASTCodeTransformer.apply_transformations(
        code,
        rules=[RefactoringRuleType.BARE_EXCEPT_FIX],
    )
    assert len(changes) == 1
    refactored = changes[0].refactored_code
    assert "except Exception:" in refactored


def test_transformer_dead_code_elimination() -> None:
    code = """def calc(a, b):
    return a + b
    print("unreachable")
    x = 10"""
    changes = ASTCodeTransformer.apply_transformations(
        code,
        rules=[RefactoringRuleType.DEAD_CODE_ELIMINATION],
    )
    assert len(changes) == 1
    refactored = changes[0].refactored_code
    assert 'print("unreachable")' not in refactored
    assert "x = 10" not in refactored


def test_transformer_legacy_typing_upgrade() -> None:
    code = """from typing import List
def process(names: List[str]) -> None:
    pass"""
    changes = ASTCodeTransformer.apply_transformations(
        code,
        rules=[RefactoringRuleType.TYPE_ANNOTATION_UPGRADE],
    )
    assert len(changes) == 1
    refactored = changes[0].refactored_code
    assert "list[str]" in refactored


def test_refactoring_engine_file_dry_run() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir) / "test_script.py"
        content = """def fn(items=[]):
    return len(items)
"""
        tmp_path.write_text(content, encoding="utf-8")

        engine = RefactoringEngine()
        success, changes, err = engine.refactor_file(tmp_path, dry_run=True)
        assert success is True
        assert len(changes) >= 1
        assert err is None
        # File on disk should remain unmodified in dry_run mode
        assert tmp_path.read_text(encoding="utf-8") == content

        # Now apply in-place
        success, changes, err = engine.refactor_file(tmp_path, dry_run=False)
        assert success is True
        assert tmp_path.read_text(encoding="utf-8") != content
        assert "items=None" in tmp_path.read_text(encoding="utf-8")


def test_refactoring_engine_project_scan() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        sub1 = tmp_path / "pkg"
        sub1.mkdir()
        f1 = sub1 / "mod1.py"
        f1.write_text("def fn(x=[]):\n    pass\n", encoding="utf-8")

        # Excluded folder
        ignored = tmp_path / ".venv" / "lib"
        ignored.mkdir(parents=True)
        f_ignored = ignored / "bad.py"
        f_ignored.write_text("def ignored(x=[]):\n    pass\n", encoding="utf-8")

        engine = RefactoringEngine()
        report = engine.refactor_project(tmp_path, dry_run=False)

        assert report.success is True
        assert report.total_files_analyzed == 1
        assert len(report.changes_applied) == 1
        assert "items" not in f1.read_text(encoding="utf-8")
        assert "x=None" in f1.read_text(encoding="utf-8")
