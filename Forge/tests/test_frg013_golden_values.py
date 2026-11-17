"""TASK-FRG-013: golden-value verification (fabricated test constants).

Production evidence (frg-reprobe G1, the FORGE_REVIEW calibration
baseline, and the FRG-009 codegen-quality battery's G1 -- three
independent samples): the generated shortlink tests assert
``encode_id(123456789) == "8M0kX"`` and ``decode_id("8M0kX") ==
123456789``, a pair the test author invented from recall. The
implementation is arithmetically correct every time
(``decode_id("8M0kX") == 129651731``); the pytest stage failed anyway,
and the recovery classifier read the AssertionError as a LOGIC_BUG and
aimed every repair route at the correct code.

These tests pin the fix end to end:

* extraction finds golden pairs in parametrize tables, plain asserts
  and assertEqual calls, with the expected literal's exact file
  segment -- and ignores anything it cannot execute faithfully;
* the checker EXECUTES the pairs: the fabricated pair fails the check
  as a TEST defect carrying a correction record with the computed
  value, while a wrong implementation (all pairs off, or a partially
  wrong one without majority corroboration), an impl that raises, and
  a clean suite all pass this check untouched;
* the classifier routes the golden evidence to TEST_DEFECT (never
  LOGIC_BUG), and the recovery engine's deterministic route rewrites
  the fabricated literals to the computed values -- failing closed,
  file untouched, when a recorded segment no longer matches.

On pristine main every test here fails: app/verification/golden_values
and FailureClass.TEST_DEFECT do not exist.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from app.recovery.classifier import FailureClass, FailureClassifier
from app.recovery.engine import RecoveryEngine
from app.recovery.loop_guard import AntiLoopController
from app.recovery.repair import PatchApplicator
from app.verification.evidence import CheckCategory, VerificationEvidence
from app.verification.golden_values import (
    CHECK_NAME,
    GoldenValueChecker,
    apply_golden_corrections,
    classify_pairs,
    correction_records,
    extract_golden_pairs,
)

# ---------------------------------------------------------------------------
# The G1 shape, verbatim in structure: a correct base62 implementation
# (alphabet 0-9a-zA-Z per the goal) and tests carrying the fabricated
# pair in both directions among correct known values.
# ---------------------------------------------------------------------------

ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

CODES_PY = '''
ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


def encode_id(n: int) -> str:
    if n == 0:
        return ALPHABET[0]
    out = ""
    while n:
        n, r = divmod(n, 62)
        out = ALPHABET[r] + out
    return out


def decode_id(s: str) -> int:
    n = 0
    for ch in s:
        n = n * 62 + ALPHABET.index(ch)
    return n
'''

# Same shape, systematically wrong implementation (base 61 instead of
# base 62): most pairs mismatch and no function reaches a majority of
# matches, so nothing may be blamed on the tests.
CODES_WRONG_PY = '''
ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


def encode_id(n: int) -> str:
    if n == 0:
        return ALPHABET[0]
    out = ""
    while n:
        n, r = divmod(n, 61)
        out = ALPHABET[r] + out
    return out


def decode_id(s: str) -> int:
    n = 0
    for ch in s:
        n = n * 61 + ALPHABET.index(ch)
    return n
'''

CODES_RAISING_PY = '''
def encode_id(n: int) -> str:
    raise RuntimeError("boom")


def decode_id(s: str) -> int:
    raise RuntimeError("boom")
'''

TEST_SHORTLINK = '''import pytest

from shortlink.codes import decode_id, encode_id


@pytest.mark.parametrize("n,code", [(0, "0"), (61, "Z"), (62, "10"), (123456789, "8M0kX")])
def test_encode_id_known_values(n, code):
    assert encode_id(n) == code


@pytest.mark.parametrize("code,n", [("0", 0), ("Z", 61), ("10", 62), ("8M0kX", 123456789)])
def test_decode_id_known_values(code, n):
    assert decode_id(code) == n
'''

CALC_PY = '''
def double(n):
    return n * 2


def triple(n):
    return n * 3
'''

TEST_CALC = '''import unittest

from calc import double, triple


def test_double_values():
    assert double(2) == 4
    assert double(5) == 10
    assert double(7) == 15


class TestTriple(unittest.TestCase):
    def test_known(self):
        self.assertEqual(triple(2), 6)
        self.assertEqual(triple(4), 13)
'''


def _plant(root: Path, files: dict[str, str]) -> Path:
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return root


def _g1_project(root: Path, codes: str = CODES_PY) -> Path:
    return _plant(
        root,
        {
            "shortlink/__init__.py": "",
            "shortlink/codes.py": codes,
            "tests/test_shortlink.py": TEST_SHORTLINK,
        },
    )


# ---------------------------------------------------------------------------
# Fakes for the checker / recovery wiring (real fs semantics on tmp dirs)
# ---------------------------------------------------------------------------


class _FakeFS:
    def __init__(self, project: Path):
        self.project = project

    def create_file(self, task_id, relative_path, content, role="developer"):
        path = self.project / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return relative_path

    def delete_file(self, task_id, relative_path, role="developer"):
        path = self.project / relative_path
        if path.exists():
            path.unlink()
            return True
        return False

    def read_file(self, task_id, relative_path, role="developer"):
        return (self.project / relative_path).read_text(encoding="utf-8")


class _FakeTerminal:
    def __init__(self, project: Path):
        self.project = project

    async def run_command(self, task_id, command, role="tester", timeout_seconds=60, **kw):
        proc = subprocess.run(
            command,
            shell=True,
            cwd=self.project,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        return SimpleNamespace(
            command=command,
            exit_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )


class _FakeEngine:
    def __init__(self, project: Path):
        self.fs = _FakeFS(project)
        self.terminal = _FakeTerminal(project)
        self.wm = SimpleNamespace(
            get_workspace_paths=lambda task_id: SimpleNamespace(project=project)
        )


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


def test_extraction_finds_parametrize_pairs_with_segments(tmp_path):
    project = _g1_project(tmp_path)
    pairs, imports = extract_golden_pairs(project)
    assert len(pairs) == 8
    assert imports["tests/test_shortlink.py"]  # the file's imports ride along

    fabricated = [p for p in pairs if p.call_source == "encode_id(123456789)"]
    assert len(fabricated) == 1
    pair = fabricated[0]
    assert pair.function == "encode_id"
    assert pair.expected == "8M0kX"
    assert pair.expected_source == '"8M0kX"'
    # The recorded segment addresses the literal in the file exactly.
    lines = TEST_SHORTLINK.split("\n")
    segment = lines[pair.seg_lineno - 1][pair.seg_col:pair.seg_end_col]
    assert segment == '"8M0kX"'

    decode_pair = [p for p in pairs if p.call_source == "decode_id('8M0kX')"]
    assert len(decode_pair) == 1
    assert decode_pair[0].expected == 123456789


def test_extraction_direct_asserts_and_assert_equal(tmp_path):
    project = _plant(tmp_path, {"calc.py": CALC_PY, "tests/test_calc.py": TEST_CALC})
    pairs, _ = extract_golden_pairs(project)
    by_call = {p.call_source: p for p in pairs}
    assert by_call["double(2)"].expected == 4
    assert by_call["double(7)"].expected == 15
    assert by_call["triple(2)"].expected == 6
    assert by_call["triple(4)"].expected == 13


def test_extraction_ignores_what_it_cannot_execute(tmp_path):
    test_file = '''from calc import double


def test_variables(x=None):
    y = 4
    assert double(y) == 8
    assert double(2) == y


def test_expression_args():
    assert double(1 + 1) == 4
'''
    project = _plant(tmp_path, {"calc.py": CALC_PY, "tests/test_x.py": test_file})
    pairs, _ = extract_golden_pairs(project)
    assert pairs == []


def test_extraction_skips_non_literal_parametrize(tmp_path):
    test_file = '''import pytest

from calc import double

SOME = 4


@pytest.mark.parametrize("n,out", [(2, 4), (SOME, 8)])
def test_double(n, out):
    assert double(n) == out
'''
    project = _plant(tmp_path, {"calc.py": CALC_PY, "tests/test_x.py": test_file})
    pairs, _ = extract_golden_pairs(project)
    assert pairs == []


# ---------------------------------------------------------------------------
# Classification (pure): probe results fabricated by hand
# ---------------------------------------------------------------------------


def _probe_results(pairs, outcomes):
    """outcomes: list of (status, match, actual_repr) aligned with pairs."""
    results = []
    for idx, (status, match, actual_repr) in enumerate(outcomes):
        results.append(
            {
                "index": idx,
                "status": status,
                "match": match,
                "actual_repr": actual_repr,
                "error": None if status == "value" else "boom",
            }
        )
    return results


def test_classification_fabricated_pair_is_test_defect(tmp_path):
    project = _g1_project(tmp_path)
    pairs, _ = extract_golden_pairs(project)
    # encode pairs: 3 match, fabricated mismatches (actual "8m0Kx");
    # decode pairs: 3 match, fabricated mismatches (actual 129651731).
    outcomes = []
    for p in pairs:
        if p.call_source == "encode_id(123456789)":
            outcomes.append(("value", False, "'8m0Kx'"))
        elif p.call_source == "decode_id('8M0kX')":
            outcomes.append(("value", False, "129651731"))
        else:
            outcomes.append(("value", True, repr(p.expected)))
    report = classify_pairs(pairs, _probe_results(pairs, outcomes))
    defects = report.test_defects
    assert len(defects) == 2
    records = correction_records(report)
    by_call = {r["call"]: r for r in records}
    assert by_call["encode_id(123456789)"]["actual_repr"] == "'8m0Kx'"
    assert by_call["decode_id('8M0kX')"]["actual_repr"] == "129651731"


def test_classification_wrong_impl_is_never_a_test_defect(tmp_path):
    project = _g1_project(tmp_path)
    pairs, _ = extract_golden_pairs(project)
    # Every pair mismatches (a systematically wrong implementation):
    # no majority corroboration anywhere.
    outcomes = [("value", False, "'zzz'")] * len(pairs)
    report = classify_pairs(pairs, _probe_results(pairs, outcomes))
    assert report.test_defects == []
    assert report.counts["uncorroborated"] == len(pairs)


def test_classification_errors_are_never_test_defects(tmp_path):
    project = _g1_project(tmp_path)
    pairs, _ = extract_golden_pairs(project)
    outcomes = [("error", None, None)] * len(pairs)
    report = classify_pairs(pairs, _probe_results(pairs, outcomes))
    assert report.test_defects == []
    assert report.counts["error"] == len(pairs)


def test_classification_split_pairs_give_no_majority(tmp_path):
    project = _g1_project(tmp_path)
    pairs, _ = extract_golden_pairs(project)
    # 2 match / 2 mismatch per function: no strict majority, no blame.
    outcomes = []
    seen: dict[str, int] = {}
    for p in pairs:
        seen[p.function] = seen.get(p.function, 0) + 1
        if seen[p.function] <= 2:
            outcomes.append(("value", True, repr(p.expected)))
        else:
            outcomes.append(("value", False, "'nope'"))
    report = classify_pairs(pairs, _probe_results(pairs, outcomes))
    assert report.test_defects == []


# ---------------------------------------------------------------------------
# Segment splicing (pure)
# ---------------------------------------------------------------------------


def test_apply_golden_corrections_splices_computed_values(tmp_path):
    project = _g1_project(tmp_path)
    pairs, _ = extract_golden_pairs(project)
    outcomes = []
    for p in pairs:
        if p.call_source == "encode_id(123456789)":
            outcomes.append(("value", False, "'8m0Kx'"))
        elif p.call_source == "decode_id('8M0kX')":
            outcomes.append(("value", False, "129651731"))
        else:
            outcomes.append(("value", True, repr(p.expected)))
    records = correction_records(classify_pairs(pairs, _probe_results(pairs, outcomes)))
    corrected = apply_golden_corrections(TEST_SHORTLINK, records)
    assert corrected is not None
    assert '(123456789, \'8m0Kx\')' in corrected
    assert '("8M0kX", 129651731)' in corrected
    compile(corrected, "tests/test_shortlink.py", "exec")  # still valid Python


def test_apply_golden_corrections_fails_closed_on_stale_file():
    records = [
        {
            "kind": "golden_value_test_defect",
            "file": "tests/test_shortlink.py",
            "expected_source": '"8M0kX"',
            "actual_repr": "'8m0Kx'",
            "segment": {"lineno": 1, "col": 0, "end_lineno": 1, "end_col": 6},
        }
    ]
    # The file's bytes at the recorded segment are not what the battery
    # recorded: nothing may be written.
    assert apply_golden_corrections('x = "different"\n', records) is None


# ---------------------------------------------------------------------------
# The checker, end to end over real tmp projects
# ---------------------------------------------------------------------------


async def test_checker_fails_on_fabricated_pair_with_correction_records(tmp_path):
    project = _g1_project(tmp_path)
    evidence = await GoldenValueChecker().run_check("t1", _FakeEngine(project))
    assert evidence.passed is False
    assert evidence.check_name == CHECK_NAME
    assert evidence.category == CheckCategory.TEST
    records = [i for i in evidence.issues if i.get("kind") == "golden_value_test_defect"]
    assert len(records) == 2
    actuals = {r["call"]: r["actual_repr"] for r in records}
    assert actuals["decode_id('8M0kX')"] == "129651731"
    assert actuals["encode_id(123456789)"] == "'8m0Kx'"
    assert "TEST defect" in evidence.stderr
    # The probe file is gone: the settled tree is byte-identical.
    assert not (project / "_golden_probe_tmp.py").exists()


async def test_checker_passes_on_clean_suite(tmp_path):
    clean = TEST_SHORTLINK.replace('"8M0kX")', '"8m0Kx")').replace(
        '("8M0kX", 123456789)', '("8M0kX", 129651731)'
    )
    project = _plant(
        tmp_path,
        {
            "shortlink/__init__.py": "",
            "shortlink/codes.py": CODES_PY,
            "tests/test_shortlink.py": clean,
        },
    )
    evidence = await GoldenValueChecker().run_check("t2", _FakeEngine(project))
    assert evidence.passed is True
    assert evidence.issues == []


async def test_checker_passes_when_impl_is_wrong(tmp_path):
    # Base-61 impl: 3 of 4 encode pairs and 2 of 4 decode pairs
    # mismatch -- no majority corroboration anywhere, so the check
    # must not blame the tests; the pytest failure owns this one.
    project = _g1_project(tmp_path, codes=CODES_WRONG_PY)
    evidence = await GoldenValueChecker().run_check("t3", _FakeEngine(project))
    assert evidence.passed is True
    assert evidence.issues == []
    assert "uncorroborated=5" in evidence.stdout


async def test_checker_passes_when_impl_raises(tmp_path):
    project = _g1_project(tmp_path, codes=CODES_RAISING_PY)
    evidence = await GoldenValueChecker().run_check("t4", _FakeEngine(project))
    assert evidence.passed is True
    assert evidence.issues == []


async def test_checker_passes_when_no_golden_pairs(tmp_path):
    project = _plant(tmp_path, {"calc.py": CALC_PY, "tests/test_none.py": "def test_ok():\n    assert True\n"})
    evidence = await GoldenValueChecker().run_check("t5", _FakeEngine(project))
    assert evidence.passed is True
    assert "0 golden pairs" in evidence.stdout


# ---------------------------------------------------------------------------
# Classifier routing + the deterministic recovery route
# ---------------------------------------------------------------------------


def test_classifier_routes_golden_evidence_to_test_defect():
    evidence = VerificationEvidence(
        check_name=CHECK_NAME,
        category=CheckCategory.TEST,
        exit_code=1,
        passed=False,
        stderr="TEST defect(s) -- golden values invented from recall",
        issues=[
            {
                "kind": "golden_value_test_defect",
                "file": "tests/test_shortlink.py",
                "actual_repr": "129651731",
            }
        ],
    )
    diagnosis = FailureClassifier().classify(evidence)
    assert diagnosis.failure_class == FailureClass.TEST_DEFECT
    assert diagnosis.failing_file == "tests/test_shortlink.py"


def test_classifier_does_not_route_probe_no_report_to_test_defect():
    # F1: the checker's probe-did-not-report infrastructure failure
    # carries no golden_value_test_defect record (issues=[]) -- it is
    # not a test defect and must fall through to the standard
    # classification instead of being mislabelled TEST_DEFECT.
    evidence = VerificationEvidence(
        check_name=CHECK_NAME,
        category=CheckCategory.TEST,
        exit_code=1,
        passed=False,
        stderr="Golden value probe did not report results (terminal exit=1): ",
        issues=[],
    )
    diagnosis = FailureClassifier().classify(evidence)
    assert diagnosis.failure_class != FailureClass.TEST_DEFECT
    assert diagnosis.failure_class == FailureClass.UNKNOWN


def test_classifier_still_reads_pytest_failure_as_logic_bug():
    evidence = VerificationEvidence(
        check_name="Test Suite Runner",
        category=CheckCategory.TEST,
        exit_code=1,
        passed=False,
        stderr="AssertionError: assert 12 == 13",
        stdout="FAILED tests/test_calc.py::test_double_values",
    )
    diagnosis = FailureClassifier().classify(evidence)
    assert diagnosis.failure_class == FailureClass.LOGIC_BUG


class _FakeStore:
    def __init__(self):
        self.events = []

    async def record_event(self, task_id, event_type, payload):
        self.events.append((event_type, payload))


class _FakeVerifier:
    def __init__(self, all_passed=True):
        self._all_passed = all_passed

    async def verify_task(self, task_id):
        return SimpleNamespace(
            all_passed=self._all_passed, failure_reasons=[] if self._all_passed else ["still failing"]
        )


def _recovery_engine(project: Path, verifier=None) -> RecoveryEngine:
    engine = _FakeEngine(project)
    return RecoveryEngine(
        loop_guard=AntiLoopController(),
        applicator=PatchApplicator(engine=engine),
        verifier=verifier or _FakeVerifier(),
        store=_FakeStore(),
        exec_engine=engine,
    )


async def _golden_evidence(project: Path) -> VerificationEvidence:
    return await GoldenValueChecker().run_check("t6", _FakeEngine(project))


async def test_recovery_route_corrects_fabricated_literals(tmp_path):
    project = _g1_project(tmp_path)
    evidence = await _golden_evidence(project)
    recovery = _recovery_engine(project)
    recovered, message, patch = await recovery.attempt_recovery("t6", evidence)
    assert recovered is True
    assert patch is not None and patch.target_file == "tests/test_shortlink.py"
    corrected = (project / "tests/test_shortlink.py").read_text(encoding="utf-8")
    assert '("8M0kX", 129651731)' in corrected
    assert "123456789, '8m0Kx'" in corrected
    # And the corrected suite really passes under pytest.
    proc = subprocess.run(
        [sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider",
         "-c", "/dev/null", "--rootdir=.", "tests/test_shortlink.py"],
        cwd=project, capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


async def test_recovery_route_fails_closed_on_stale_segments(tmp_path):
    project = _g1_project(tmp_path)
    evidence = await _golden_evidence(project)
    # The file changed after the battery ran: recorded segments stale.
    target = project / "tests/test_shortlink.py"
    target.write_text(TEST_SHORTLINK.replace('"8M0kX"', '"ZZZZZ"'), encoding="utf-8")
    before = target.read_text(encoding="utf-8")
    recovery = _recovery_engine(project)
    recovered, message, patch = await recovery.attempt_recovery("t6", evidence)
    assert recovered is False
    assert patch is None
    assert "stale positions" in message
    assert target.read_text(encoding="utf-8") == before


async def test_recovery_route_without_records_does_nothing(tmp_path):
    project = _g1_project(tmp_path)
    evidence = VerificationEvidence(
        check_name=CHECK_NAME,
        category=CheckCategory.TEST,
        exit_code=1,
        passed=False,
        stderr="TEST defect(s)",
        issues=[{"kind": "golden_value_test_defect"}],
    )
    recovery = _recovery_engine(project)
    recovered, message, patch = await recovery.attempt_recovery("t6", evidence)
    assert recovered is False and patch is None
    assert (project / "tests/test_shortlink.py").read_text(encoding="utf-8") == TEST_SHORTLINK
