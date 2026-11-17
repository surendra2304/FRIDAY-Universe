"""
Golden-Value Verification for Project FORGE (TASK-FRG-013).

The defect this module exists to catch
--------------------------------------
Forge's generated tests carry "known values" the test author wrote from
recall instead of computing them. The measured signature (three
independent acceptance samples: frg-reprobe's G1, the FORGE_REVIEW
calibration baseline, and the FRG-009 codegen-quality battery's G1) is
one fabricated base62 pair -- the test asserts
``encode_id(123456789) == "8M0kX"`` / ``decode_id("8M0kX") == 123456789``
while the implementation, arithmetically correct every time, computes
``decode_id("8M0kX") == 129651731``. The build then fails its pytest
stage with the blame on the code, and the recovery classifier reads the
AssertionError as a LOGIC_BUG and aims every repair route at the
correct implementation.

Nothing in the pipeline ever executed a golden pair independently, so
nothing could tell a fabricated constant from a real logic bug. This
module is that check, in three parts:

1. EXTRACTION (pure AST, read-only): find golden assertions in the
   generated test files -- ``assert f(<literals>) == <literal>``,
   ``self.assertEqual(f(<literals>), <literal>)``, and
   ``@pytest.mark.parametrize`` known-value tables -- and record each
   pair with the exact file segment of its expected literal.
2. EXECUTION PROBE: a generated script, run through the same
   permission-checked terminal and interpreter the TestChecker uses,
   imports what the test file imports and evaluates each call for
   real. "Compute, don't recall" enforced by execution.
3. CLASSIFICATION (pure): a mismatch is a TEST defect (fabricated
   golden value) only when the implementation is *corroborated* --
   a strict majority of the executed pairs for the same called
   function verify exactly, so the impl demonstrably agrees with
   the test author's own other examples and the mismatching pair
   is a rare outlier, not a pattern -- and the actual value can be
   written back as a literal. The majority bar matters: a partially
   wrong impl (e.g. base62 with the letter ranges swapped) still
   matches its digit-only pairs, so a lone matching sibling proves
   nothing; and an encode/decode round-trip through the impl's own
   values proves nothing either -- a systematically wrong but
   bijective impl round-trips perfectly while violating the spec
   the sibling pairs pin down. An uncorroborated mismatch is
   reported but never acted on and never fails this check: the
   ordinary pytest failure already carries it as an impl-side
   signal, so a genuinely wrong implementation still fails as an
   implementation defect, exactly as before. This checker can only
   fail a battery when it holds positive evidence the TEST is wrong.

The correction half lives in the recovery engine: a TEST_DEFECT
diagnosis (app/recovery/classifier.py) routes to a deterministic
correction that replaces the fabricated literal with the value the
probe computed -- never a model-generated constant.
"""

from __future__ import annotations

import ast
import copy
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.verification.checkers import BaseChecker
from app.verification.evidence import CheckCategory, VerificationEvidence

logger = get_logger("verification.golden_values")

CHECK_NAME = "Golden Value Verification"
PROBE_FILENAME = "_golden_probe_tmp.py"
_PROBE_MARKER = "GOLDEN_PROBE_JSON:"
# Paranoia bounds: a generated suite larger than this is judged by the
# pytest stage alone; the probe stays a bounded, cheap sub-step.
MAX_PAIRS = 512
MAX_TEST_FILES = 64

_EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
}


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


@dataclass
class GoldenPair:
    """One golden assertion: a call and the literal it is claimed to equal."""

    file: str  # test file, project-relative posix path
    test_name: str
    function: str  # the called function's expression as written (e.g. "encode_id")
    call_source: str  # the call, parametrize values substituted, unparsed
    expected_source: str  # source segment of the expected literal
    expected: Any  # the expected literal's value
    seg_lineno: int
    seg_col: int
    seg_end_lineno: int
    seg_end_col: int
    # For single-positional-arg calls: the input literal, recorded for
    # reporting (classification deliberately does not use it -- see the
    # module docstring on why round-trips do not corroborate).
    input_value: Any = None


def _literal(node: ast.AST) -> tuple[bool, Any]:
    try:
        return True, ast.literal_eval(node)
    except Exception:
        return False, None


def _is_test_path(rel: Path) -> bool:
    parts = rel.parts
    if any(p in _EXCLUDED_DIRS for p in parts):
        return False
    name = rel.name
    if not name.endswith(".py") or name == PROBE_FILENAME:
        return False
    return (
        "tests" in parts[:-1]
        or "test" in parts[:-1]
        or name.startswith("test_")
        or name.endswith("_test.py")
    )


def _parametrize_rows(
    decorator_list: list[ast.expr],
) -> list[dict[str, ast.expr]] | None:
    """Row bindings {param: value-node} from a parametrize decorator.

    Returns None when no usable parametrize decorator exists (no
    decorator, non-literal rows, pytest.param(...) wrappers, ...):
    the function's pairs then come only from constant-only asserts.
    """
    for dec in decorator_list:
        if not isinstance(dec, ast.Call) or len(dec.args) < 2:
            continue
        func = dec.func
        is_parametrize = (
            isinstance(func, ast.Attribute) and func.attr == "parametrize"
        ) or (isinstance(func, ast.Name) and func.id == "parametrize")
        if not is_parametrize:
            continue
        names_node, values_node = dec.args[0], dec.args[1]
        names: list[str] | None = None
        if isinstance(names_node, ast.Constant) and isinstance(names_node.value, str):
            names = [n.strip() for n in names_node.value.split(",") if n.strip()]
        elif isinstance(names_node, (ast.List, ast.Tuple)):
            collected: list[str] = []
            for elt in names_node.elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    collected.append(elt.value)
                else:
                    collected = []
                    break
            names = collected or None
        if not names or not isinstance(values_node, (ast.List, ast.Tuple)):
            return None
        rows: list[dict[str, ast.expr]] = []
        for row in values_node.elts:
            if len(names) == 1:
                row_nodes = [row]
            elif isinstance(row, (ast.Tuple, ast.List)) and len(row.elts) == len(names):
                row_nodes = list(row.elts)
            else:
                return None
            binding: dict[str, ast.expr] = {}
            for nm, nd in zip(names, row_nodes):
                ok, _ = _literal(nd)
                if not ok:
                    return None
                binding[nm] = nd
            rows.append(binding)
        return rows or None
    return None


class _Substitute(ast.NodeTransformer):
    """Replace parametrize-bound Names with (copies of) their row values."""

    def __init__(self, binding: dict[str, ast.expr]):
        self.binding = binding

    def visit_Name(self, node: ast.Name) -> ast.AST:
        if node.id in self.binding:
            return copy.deepcopy(self.binding[node.id])
        return node


def _resolve_expected(
    node: ast.expr, binding: dict[str, ast.expr]
) -> ast.expr | None:
    """The AST node carrying the expected literal, or None.

    A Name bound by parametrize resolves to its row element node (whose
    position inside the decorator is the correction target); anything
    else must itself be a literal.
    """
    if isinstance(node, ast.Name) and node.id in binding:
        return binding[node.id]
    ok, _ = _literal(node)
    return node if ok else None


def _pair_from_sides(
    *,
    rel_file: str,
    test_name: str,
    source: str,
    call_node: ast.expr,
    expected_node: ast.expr,
    binding: dict[str, ast.expr],
) -> GoldenPair | None:
    """Build a GoldenPair from a (call, expected) side pair, or None."""
    if not isinstance(call_node, ast.Call):
        return None
    if not isinstance(call_node.func, (ast.Name, ast.Attribute)):
        return None
    # Every argument must be a literal or a parametrize-bound name:
    # anything else (variables, expressions, calls) is not a golden pair
    # this checker can execute faithfully.
    for arg in list(call_node.args) + [kw.value for kw in call_node.keywords]:
        if isinstance(arg, ast.Name) and arg.id in binding:
            continue
        ok, _ = _literal(arg)
        if not ok:
            return None
    expected_expr = _resolve_expected(expected_node, binding)
    if expected_expr is None:
        return None
    ok, expected_value = _literal(expected_expr)
    if not ok:
        return None
    expected_source = ast.get_source_segment(source, expected_expr)
    if expected_source is None:
        return None

    substituted = _Substitute(binding).visit(copy.deepcopy(call_node))
    call_source = ast.unparse(substituted)

    input_value: Any = None
    if len(call_node.args) == 1 and not call_node.keywords:
        arg = call_node.args[0]
        arg_expr = binding.get(arg.id) if isinstance(arg, ast.Name) else arg
        if arg_expr is not None:
            ok, value = _literal(arg_expr)
            if ok:
                input_value = value

    return GoldenPair(
        file=rel_file,
        test_name=test_name,
        function=ast.unparse(call_node.func),
        call_source=call_source,
        expected_source=expected_source,
        expected=expected_value,
        seg_lineno=expected_expr.lineno,
        seg_col=expected_expr.col_offset,
        seg_end_lineno=expected_expr.end_lineno or expected_expr.lineno,
        seg_end_col=expected_expr.end_col_offset or expected_expr.col_offset,
        input_value=input_value,
    )


def _pairs_from_statement(
    *,
    rel_file: str,
    test_name: str,
    source: str,
    stmt: ast.stmt,
    binding: dict[str, ast.expr],
) -> list[GoldenPair]:
    """Golden pairs from one top-level statement of a test function."""
    sides: list[tuple[ast.expr, ast.expr]] | None = None
    if isinstance(stmt, ast.Assert) and isinstance(stmt.test, ast.Compare):
        cmp = stmt.test
        if len(cmp.ops) == 1 and isinstance(cmp.ops[0], ast.Eq) and len(cmp.comparators) == 1:
            sides = [(cmp.left, cmp.comparators[0]), (cmp.comparators[0], cmp.left)]
    elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
        call = stmt.value
        func = call.func
        is_assert_equal = (
            isinstance(func, ast.Attribute) and func.attr == "assertEqual"
        ) or (isinstance(func, ast.Name) and func.id == "assertEqual")
        if is_assert_equal and len(call.args) == 2 and not call.keywords:
            sides = [(call.args[0], call.args[1]), (call.args[1], call.args[0])]
    if not sides:
        return []
    for call_side, expected_side in sides:
        pair = _pair_from_sides(
            rel_file=rel_file,
            test_name=test_name,
            source=source,
            call_node=call_side,
            expected_node=expected_side,
            binding=binding,
        )
        if pair is not None:
            return [pair]
    return []


def _pairs_from_function(
    rel_file: str, source: str, fn: ast.FunctionDef | ast.AsyncFunctionDef
) -> list[GoldenPair]:
    rows = _parametrize_rows(fn.decorator_list)
    bindings: list[dict[str, ast.expr]] = rows if rows is not None else [{}]
    pairs: list[GoldenPair] = []
    for binding in bindings:
        for stmt in fn.body:
            pairs.extend(
                _pairs_from_statement(
                    rel_file=rel_file,
                    test_name=fn.name,
                    source=source,
                    stmt=stmt,
                    binding=binding,
                )
            )
    return pairs


def extract_golden_pairs(
    project: Path,
) -> tuple[list[GoldenPair], dict[str, list[str]]]:
    """Extract golden pairs + per-file import statements from a project.

    Returns (pairs, imports) where imports maps each test file that
    produced pairs to its top-level import statement sources -- the
    probe executes exactly those imports, the same ones pytest would.
    """
    project = Path(project)
    pairs: list[GoldenPair] = []
    imports: dict[str, list[str]] = {}
    test_files: list[Path] = []
    for path in sorted(project.rglob("*.py")):
        if path.is_symlink():
            continue
        rel = path.relative_to(project)
        if _is_test_path(rel):
            test_files.append(path)
        if len(test_files) >= MAX_TEST_FILES:
            break
    for path in test_files:
        rel = path.relative_to(project).as_posix()
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (SyntaxError, UnicodeError, OSError):
            continue  # The build checker reports malformed source separately.
        file_pairs: list[GoldenPair] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
                node.name.startswith("test")
            ):
                file_pairs.extend(_pairs_from_function(rel, source, node))
        if file_pairs:
            pairs.extend(file_pairs)
            imports[rel] = [
                ast.get_source_segment(source, node) or ""
                for node in tree.body
                if isinstance(node, (ast.Import, ast.ImportFrom))
            ]
        if len(pairs) >= MAX_PAIRS:
            pairs = pairs[:MAX_PAIRS]
            break
    return pairs, imports


# ---------------------------------------------------------------------------
# Execution probe
# ---------------------------------------------------------------------------

_PROBE_BODY = '''
import ast as _ast
import json as _json
import sys as _sys

_sys.path.insert(0, ".")
_PAIRS = _json.loads(__PAIRS_JSON__)
_IMPORTS = _json.loads(__IMPORTS_JSON__)


def _main():
    namespaces = {}
    import_errors = {}
    for fname, stmts in _IMPORTS.items():
        ns = {"__name__": "__golden_probe__"}
        try:
            for stmt in stmts:
                exec(stmt, ns)
        except Exception as exc:  # an import the suite itself would hit
            import_errors[fname] = "%s: %s" % (type(exc).__name__, exc)
        namespaces[fname] = ns

    results = []
    evaluated = {}
    for idx, pair in enumerate(_PAIRS):
        entry = {
            "index": idx,
            "status": "error",
            "match": None,
            "actual_repr": None,
            "error": None,
        }
        fname = pair["file"]
        if fname in import_errors:
            entry["status"] = "import_error"
            entry["error"] = import_errors[fname]
            results.append(entry)
            evaluated[idx] = ("import_error", None)
            continue
        ns = namespaces.get(fname, {})
        try:
            expected = _ast.literal_eval(pair["expected_source"])
        except Exception as exc:
            entry["error"] = "expected literal unevaluable: %s" % exc
            results.append(entry)
            evaluated[idx] = ("error", None)
            continue
        try:
            actual = eval(pair["call_source"], ns)
        except Exception as exc:
            entry["error"] = "%s: %s" % (type(exc).__name__, exc)
            results.append(entry)
            evaluated[idx] = ("error", None)
            continue
        entry["status"] = "value"
        try:
            entry["actual_repr"] = repr(actual)
        except Exception:
            entry["actual_repr"] = None
        try:
            entry["match"] = bool(actual == expected)
        except Exception:
            entry["match"] = False
        results.append(entry)
        evaluated[idx] = ("value", actual)

    print(__MARKER__ + _json.dumps(results))


_main()
'''


def build_probe_source(
    pairs: list[GoldenPair], imports: dict[str, list[str]]
) -> str:
    """Render the probe script for a set of extracted pairs."""
    payload = [
        {
            "file": p.file,
            "call_source": p.call_source,
            "expected_source": p.expected_source,
        }
        for p in pairs
    ]
    return (
        _PROBE_BODY.replace("__PAIRS_JSON__", repr(json.dumps(payload)))
        .replace("__IMPORTS_JSON__", repr(json.dumps(imports)))
        .replace("__MARKER__", repr(_PROBE_MARKER))
    )


def parse_probe_output(stdout: str) -> list[dict[str, Any]] | None:
    """The probe's JSON result list, or None when the probe did not report."""
    for line in (stdout or "").splitlines():
        if line.startswith(_PROBE_MARKER):
            try:
                data = json.loads(line[len(_PROBE_MARKER):])
            except Exception:
                return None
            return data if isinstance(data, list) else None
    return None


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


@dataclass
class PairOutcome:
    pair: GoldenPair
    status: str  # match | mismatch | error | import_error
    actual_repr: str | None = None
    error: str | None = None
    classification: str | None = None  # test_defect | uncorroborated (mismatches only)

    @property
    def is_test_defect(self) -> bool:
        return self.classification == "test_defect"


@dataclass
class GoldenReport:
    outcomes: list[PairOutcome] = field(default_factory=list)

    @property
    def test_defects(self) -> list[PairOutcome]:
        return [o for o in self.outcomes if o.is_test_defect]

    @property
    def counts(self) -> dict[str, int]:
        counts = {"pairs": len(self.outcomes), "match": 0, "mismatch": 0,
                  "error": 0, "import_error": 0, "test_defect": 0,
                  "uncorroborated": 0}
        for o in self.outcomes:
            counts[o.status] = counts.get(o.status, 0) + 1
            if o.classification == "test_defect":
                counts["test_defect"] += 1
            elif o.classification == "uncorroborated":
                counts["uncorroborated"] += 1
        return counts


def _literal_safe(actual_repr: str | None) -> bool:
    """True when repr(actual) round-trips through literal_eval unchanged,
    so the computed value can be written back into the test as a literal."""
    if not actual_repr:
        return False
    try:
        value = ast.literal_eval(actual_repr)
    except Exception:
        return False
    try:
        return repr(value) == actual_repr
    except Exception:
        return False


def classify_pairs(
    pairs: list[GoldenPair], probe_results: list[dict[str, Any]]
) -> GoldenReport:
    """Classify executed pairs: which mismatches are fabricated goldens.

    The rule (see module docstring): a mismatch is a TEST defect only
    with majority corroboration -- a strict majority of the executed
    pairs for the same called function matched exactly -- AND the
    actual value is literal-safe to write back. Everything else
    mismatched is uncorroborated: reported, never corrected, never
    failed by this check.
    """
    by_index = {r.get("index"): r for r in probe_results if isinstance(r, dict)}
    outcomes: list[PairOutcome] = []
    for idx, pair in enumerate(pairs):
        result = by_index.get(idx) or {}
        status = result.get("status")
        if status == "value":
            status = "match" if result.get("match") else "mismatch"
        elif status not in ("error", "import_error"):
            status = "error"
        outcomes.append(
            PairOutcome(
                pair=pair,
                status=status,
                actual_repr=result.get("actual_repr"),
                error=result.get("error"),
            )
        )

    per_function: dict[str, dict[str, int]] = {}
    for outcome in outcomes:
        tally = per_function.setdefault(outcome.pair.function, {"match": 0, "mismatch": 0})
        if outcome.status in ("match", "mismatch"):
            tally[outcome.status] += 1
    for outcome in outcomes:
        if outcome.status != "mismatch":
            continue
        tally = per_function[outcome.pair.function]
        corroborated = tally["match"] > tally["mismatch"]
        if corroborated and _literal_safe(outcome.actual_repr):
            outcome.classification = "test_defect"
        else:
            outcome.classification = "uncorroborated"
    return GoldenReport(outcomes=outcomes)


def correction_records(report: GoldenReport) -> list[dict[str, Any]]:
    """Machine-readable correction records for TEST-defect mismatches.

    Consumed by the recovery engine's deterministic golden-correction
    route. One record per distinct expected-literal segment (a segment
    shared by two pairs is corrected once).
    """
    records: list[dict[str, Any]] = []
    seen: set[tuple[str, int, int]] = set()
    for outcome in report.test_defects:
        pair = outcome.pair
        key = (pair.file, pair.seg_lineno, pair.seg_col)
        if key in seen:
            continue
        seen.add(key)
        records.append(
            {
                "kind": "golden_value_test_defect",
                "file": pair.file,
                "test_name": pair.test_name,
                "function": pair.function,
                "call": pair.call_source,
                "expected_source": pair.expected_source,
                "actual_repr": outcome.actual_repr,
                "segment": {
                    "lineno": pair.seg_lineno,
                    "col": pair.seg_col,
                    "end_lineno": pair.seg_end_lineno,
                    "end_col": pair.seg_end_col,
                },
            }
        )
    return records


def apply_golden_corrections(
    content: str, records: list[dict[str, Any]]
) -> str | None:
    """Splice computed values over the records' expected-literal segments.

    Pure and fail-closed: returns the corrected file content, or None
    when any segment's current text differs from the expected source
    the battery recorded -- the file changed since verification, so the
    recorded positions cannot be trusted and nothing may be written.
    Replacements are applied back-to-front so earlier splices never
    shift later segments.
    """
    lines = content.split("\n")
    starts: list[int] = []
    pos = 0
    for line in lines:
        starts.append(pos)
        pos += len(line) + 1

    def char_index(lineno: int, byte_col: int) -> int:
        # AST col offsets are UTF-8 byte offsets into the line; token
        # boundaries are always character boundaries in valid source.
        line = lines[lineno - 1]
        return len(line.encode("utf-8")[:byte_col].decode("utf-8", errors="ignore"))

    spans: list[tuple[int, int, str]] = []
    for record in records:
        segment = record.get("segment") or {}
        try:
            start = starts[int(segment["lineno"]) - 1] + char_index(
                int(segment["lineno"]), int(segment["col"])
            )
            end = starts[int(segment["end_lineno"]) - 1] + char_index(
                int(segment["end_lineno"]), int(segment["end_col"])
            )
        except Exception:
            return None
        if content[start:end] != record.get("expected_source"):
            return None
        spans.append((start, end, str(record.get("actual_repr"))))
    corrected = content
    for start, end, replacement in sorted(spans, reverse=True):
        corrected = corrected[:start] + replacement + corrected[end:]
    return corrected


# ---------------------------------------------------------------------------
# The checker
# ---------------------------------------------------------------------------


class GoldenValueChecker(BaseChecker):
    """Executes generated tests' golden assertions against the impl.

    Fails ONLY on corroborated fabricated golden values (TEST defects);
    see the module docstring for the classification rule. Read-only
    with respect to the settled tree: its probe script is written into
    the project, run, and deleted before the checker returns, so the
    battery's source-integrity stage sees an unchanged tree.
    """

    __test__ = False

    def __init__(self):
        super().__init__(name=CHECK_NAME, category=CheckCategory.TEST)

    async def run_check(self, task_id: str, engine) -> VerificationEvidence:
        start_time = time.perf_counter()

        def evidence(**kwargs: Any) -> VerificationEvidence:
            kwargs.setdefault("check_name", self.name)
            kwargs.setdefault("category", self.category)
            kwargs.setdefault("duration_ms", round((time.perf_counter() - start_time) * 1000.0, 2))
            return VerificationEvidence(**kwargs)

        paths = engine.wm.get_workspace_paths(task_id)
        if not paths:
            return evidence(
                exit_code=1,
                passed=False,
                stderr="No workspace exists; no golden values were verified.",
            )

        pairs, imports = extract_golden_pairs(paths.project)
        if not pairs:
            return evidence(
                exit_code=0,
                passed=True,
                command="golden value extraction (AST)",
                stdout="0 golden pairs extracted from the generated tests; "
                "nothing for this check to execute.",
                artifacts_inspected=[],
            )

        probe_source = build_probe_source(pairs, imports)
        command = f'"{sys.executable}" -B {PROBE_FILENAME}'
        cmd_res = None
        try:
            engine.fs.create_file(
                task_id=task_id,
                relative_path=PROBE_FILENAME,
                content=probe_source,
                role="tester",
            )
            cmd_res = await engine.terminal.run_command(
                task_id, command, role="tester", timeout_seconds=120
            )
        finally:
            # The probe is this checker's own scratch: removing it keeps
            # the settled tree byte-identical for the source-integrity
            # stage. FS_DELETE is a developer-grant permission; the
            # cleanup is housekeeping over the checker's own file.
            try:
                engine.fs.delete_file(
                    task_id=task_id, relative_path=PROBE_FILENAME, role="developer"
                )
            except Exception as exc:
                logger.warning(
                    f"Golden probe cleanup failed for task '{task_id}': {exc}"
                )

        probe_results = parse_probe_output(cmd_res.stdout if cmd_res else "")
        if probe_results is None:
            return evidence(
                exit_code=1,
                passed=False,
                command=command,
                stderr=(
                    "Golden value probe did not report results "
                    f"(terminal exit={cmd_res.exit_code if cmd_res else 'n/a'}): "
                    f"{(cmd_res.stderr if cmd_res else '')[:300]}"
                ),
                artifacts_inspected=sorted({p.file for p in pairs}),
            )

        report = classify_pairs(pairs, probe_results)
        counts = report.counts
        records = correction_records(report)
        summary = (
            f"golden pairs={counts['pairs']} matched={counts['match']} "
            f"mismatched={counts['mismatch']} (test_defects={counts['test_defect']}, "
            f"uncorroborated={counts['uncorroborated']}) "
            f"errors={counts['error'] + counts['import_error']}"
        )
        if records:
            lines = [
                f"{r['file']}:{r['segment']['lineno']}: {r['call']} == "
                f"{r['expected_source']} is a fabricated golden value; "
                f"executing the implementation computes {r['actual_repr']}."
                for r in records
            ]
            return evidence(
                exit_code=1,
                passed=False,
                command=command,
                stdout=summary,
                stderr=(
                    "TEST defect(s) -- golden values invented from recall, "
                    "implementation corroborated:\n" + "\n".join(lines)
                ),
                issues=records,
                artifacts_inspected=sorted({p.file for p in pairs}),
            )
        return evidence(
            exit_code=0,
            passed=True,
            command=command,
            stdout=summary,
            artifacts_inspected=sorted({p.file for p in pairs}),
        )
