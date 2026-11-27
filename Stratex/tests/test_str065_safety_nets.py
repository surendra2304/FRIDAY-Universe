"""
tests/test_str065_safety_nets.py — TASK-STR-065: Safety Nets stop-out rule
in the advisory/risk gate (source item S-05).

The rule's two triggers are onset / sign-change signals in AdvisoryGate.validate():
1. the session flips from profit to loss (prev >= 0, now < 0);
2. capital drawdown starts (prev == 0, now > 0).
Either trigger REJECTs the whole decision, in shadow mode as well as live.
None inputs skip that trigger, matching the telemetry / trade-count / drawdown
None-skip pattern. The bounded-recommendation path is NOT-APPLICABLE (it
receives no session telemetry); the triggers live in validate() only.
"""

import datetime
from unittest.mock import MagicMock, patch

from advisory_gate import AdvisoryGate


def _valid_decision(decision_id="DEC_STR065"):
    """A decision that passes every other gate check (APPLY in live mode)."""
    return {
        "decision_id": decision_id,
        "status": "APPROVED",
        "confidence": 0.85,
        "parameter_changes": [
            {"parameter": "adx_threshold", "current_value": 25.0, "new_value": 26.0, "strategy": "adx_ema"}
        ],
    }


def _params():
    return {"adx_threshold": 25.0}


def test_str065_session_flip_profit_to_loss_rejects():
    """1. Session flip profit -> loss => REJECT."""
    gate = AdvisoryGate()
    res = gate.validate(
        _valid_decision("DEC_STR065_01"), _params(), shadow_mode=False,
        session_pnl_pct_prev=2.5, session_pnl_pct_now=-1.0,
    )
    assert res.verdict == "REJECT"
    assert len(res.applied_changes) == 0
    assert len(res.rejected_changes) == 1
    assert "STR-065" in res.rejected_changes[0]["reason"]
    assert "flipped from profit to loss" in res.rationale


def test_str065_session_stays_profitable_no_trigger():
    """2. Session stays profitable => no flip trigger, decision applies."""
    gate = AdvisoryGate()
    res = gate.validate(
        _valid_decision("DEC_STR065_02"), _params(), shadow_mode=False,
        session_pnl_pct_prev=2.5, session_pnl_pct_now=1.0,
    )
    assert res.verdict == "APPLY"
    assert len(res.applied_changes) == 1


def test_str065_session_stays_in_loss_no_trigger():
    """3. Session stays in loss (prev < 0, now < 0) => no flip trigger (not an onset)."""
    gate = AdvisoryGate()
    res = gate.validate(
        _valid_decision("DEC_STR065_03"), _params(), shadow_mode=False,
        session_pnl_pct_prev=-1.0, session_pnl_pct_now=-2.0,
    )
    assert res.verdict == "APPLY"
    assert len(res.applied_changes) == 1


def test_str065_drawdown_onset_rejects():
    """4. Drawdown onset (0 -> >0) => REJECT."""
    gate = AdvisoryGate()
    res = gate.validate(
        _valid_decision("DEC_STR065_04"), _params(), shadow_mode=False,
        drawdown_pct_prev=0.0, drawdown_pct_now=1.5,
    )
    assert res.verdict == "REJECT"
    assert len(res.applied_changes) == 0
    assert "STR-065" in res.rejected_changes[0]["reason"]
    assert "drawdown started" in res.rationale


def test_str065_drawdown_ongoing_no_trigger():
    """5. Drawdown ongoing (prev > 0) => no onset trigger, decision applies."""
    gate = AdvisoryGate()
    res = gate.validate(
        _valid_decision("DEC_STR065_05"), _params(), shadow_mode=False,
        drawdown_pct_prev=1.5, drawdown_pct_now=2.0,
    )
    assert res.verdict == "APPLY"
    assert len(res.applied_changes) == 1


def test_str065_drawdown_recovered_to_zero_no_trigger():
    """6. Drawdown recovered to 0 => no trigger, decision applies."""
    gate = AdvisoryGate()
    res = gate.validate(
        _valid_decision("DEC_STR065_06"), _params(), shadow_mode=False,
        drawdown_pct_prev=1.5, drawdown_pct_now=0.0,
    )
    assert res.verdict == "APPLY"
    assert len(res.applied_changes) == 1


def test_str065_both_triggers_reject_with_both_reasons():
    """7. Both triggers together => REJECT, both reasons cited."""
    gate = AdvisoryGate()
    res = gate.validate(
        _valid_decision("DEC_STR065_07"), _params(), shadow_mode=False,
        session_pnl_pct_prev=1.0, session_pnl_pct_now=-0.5,
        drawdown_pct_prev=0.0, drawdown_pct_now=2.0,
    )
    assert res.verdict == "REJECT"
    assert "flipped from profit to loss" in res.rationale
    assert "drawdown started" in res.rationale
    assert "flipped from profit to loss" in res.rejected_changes[0]["reason"]
    assert "drawdown started" in res.rejected_changes[0]["reason"]


def test_str065_none_inputs_skip_checks():
    """8. None inputs => checks skipped, decision applies."""
    gate = AdvisoryGate()
    res = gate.validate(_valid_decision("DEC_STR065_08"), _params(), shadow_mode=False)
    assert res.verdict == "APPLY"
    assert len(res.applied_changes) == 1


def test_str065_session_boundary_prev_exactly_zero_fires():
    """9. Boundary: prev session PnL exactly 0.0, now < 0 => flip fires."""
    gate = AdvisoryGate()
    res = gate.validate(
        _valid_decision("DEC_STR065_09"), _params(), shadow_mode=False,
        session_pnl_pct_prev=0.0, session_pnl_pct_now=-0.5,
    )
    assert res.verdict == "REJECT"


def test_str065_trigger_rejects_in_shadow_mode():
    """10. Trigger active in shadow mode => still REJECT (safety beats shadow)."""
    gate = AdvisoryGate()
    res = gate.validate(
        _valid_decision("DEC_STR065_10"), _params(), shadow_mode=True,
        session_pnl_pct_prev=1.0, session_pnl_pct_now=-0.5,
    )
    assert res.verdict == "REJECT"


def test_str065_bounded_recommendation_path_not_applicable():
    """11. Bounded-recommendation path: parity decision NOT-APPLICABLE.

    The bounded path receives no session telemetry, so it cannot evaluate
    onset triggers; a well-formed bounded recommendation is still accepted
    there, and the triggers are enforced in validate() only.
    """
    gate = AdvisoryGate()
    rec = {
        "parameter": "adx_threshold",
        "current_value": 25.0,
        "proposed_value": 26.0,
        "maximum_delta": 5.0,
        "evidence": "STR-065 parity check: bounded path has no session telemetry.",
        "confidence": 0.8,
        "expiry": (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=4)).isoformat(),
        "authorization_required": True,
    }
    is_valid, reason, _ = gate.validate_bounded_recommendation(rec)
    assert is_valid is True
    assert reason == "Valid bounded recommendation."


def test_str065_trigger_records_audit_event_with_reason():
    """12. Audit event recorded with the STR-065 reason on a trigger REJECT."""
    gate = AdvisoryGate()
    recorder = MagicMock()
    with patch("advisory_gate.get_audit_manager", return_value=recorder):
        res = gate.validate(
            _valid_decision("DEC_STR065_12"), _params(), shadow_mode=False,
            session_pnl_pct_prev=1.0, session_pnl_pct_now=-0.5,
        )
    assert res.verdict == "REJECT"
    recorder.record_event.assert_called_once()
    kwargs = recorder.record_event.call_args.kwargs
    assert kwargs["event_type"] == "RECOMMENDATION_REJECTED"
    assert kwargs["status"] == "REJECTED"
    assert "STR-065" in kwargs["rationale"]
