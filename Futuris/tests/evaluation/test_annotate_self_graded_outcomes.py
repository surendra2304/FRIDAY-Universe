"""TASK-FUT-011 — hermetic tests for the self-graded outcome marker script.

The script under test (Futuris/scripts/annotate_self_graded_outcomes.py) is
loaded by file path: its pure classification/marking logic must stay
importable without the futuris package or a database, because the script is
an operator tool, not application code. No test here touches a database.
"""

import importlib.util
from pathlib import Path

_SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "annotate_self_graded_outcomes.py"
)
_spec = importlib.util.spec_from_file_location("annotate_self_graded_outcomes", _SCRIPT)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

is_self_graded = _mod.is_self_graded
select_tainted = _mod.select_tainted
apply_marker = _mod.apply_marker
MARKER = _mod.MARKER


class TestSignature:
    def test_exact_write_path_signature_is_tainted(self):
        # Pre-fix write path: observed = round(prediction, 2) after substitution.
        assert is_self_graded(1234.57, 1234.5678, "backtest:v1.0") is True
        assert is_self_graded(4000.0, 4000.0, "backtest:v1.0") is True

    def test_genuine_observation_is_not_tainted(self):
        assert is_self_graded(1234.58, 1234.5678, "backtest:v1.0") is False
        assert is_self_graded(987.65, 1234.5678, "backtest:v1.0") is False

    def test_near_miss_is_not_tainted(self):
        # Within half a cent of the prediction but NOT the rounded value:
        # cannot have come from the write path — suspicion only, never marked.
        assert is_self_graded(1234.564, 1234.5678, "backtest:v1.0") is False

    def test_other_versions_never_tainted(self):
        assert is_self_graded(1234.57, 1234.5678, "manual:human:v1") is False
        assert is_self_graded(1234.57, 1234.5678, "friday_resolution:v1") is False

    def test_null_observed_never_tainted(self):
        assert is_self_graded(None, 1234.5678, "backtest:v1.0") is False


class TestSelectTainted:
    def test_selects_only_signature_rows(self):
        rows = [
            {"outcome_id": "a", "observed_value": 10.0, "prediction": 10.004,
             "resolution_rule_version": "backtest:v1.0"},
            {"outcome_id": "b", "observed_value": 11.5, "prediction": 10.004,
             "resolution_rule_version": "backtest:v1.0"},
            {"outcome_id": "c", "observed_value": 10.0, "prediction": 10.004,
             "resolution_rule_version": "manual:human:v1"},
            {"outcome_id": "d", "observed_value": None, "prediction": 10.004,
             "resolution_rule_version": "backtest:v1.0"},
        ]
        selected = select_tainted(rows)
        assert [r["outcome_id"] for r in selected] == ["a"]

    def test_empty_input(self):
        assert select_tainted([]) == []


class TestApplyMarker:
    def test_marks_empty_note(self):
        assert apply_marker(None) == MARKER
        assert apply_marker("") == MARKER

    def test_preserves_existing_note(self):
        existing = "observation window straddled a data gap"
        marked = apply_marker(existing)
        assert marked.startswith(existing)
        assert MARKER in marked

    def test_idempotent(self):
        once = apply_marker("note")
        assert apply_marker(once) == once
        assert apply_marker(MARKER) == MARKER
