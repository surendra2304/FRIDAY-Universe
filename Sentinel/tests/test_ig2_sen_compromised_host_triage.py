"""Tests for TASK-IG2-SEN-05 compromised_host_triage (stdlib-only)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.compromised_host_triage import (  # noqa: E402
    INDICATORS, UnknownIndicatorError, checklist, evaluate,
)


def test_no_observations_is_no_signs():
    result = evaluate([])
    assert result.verdict == "NO_SIGNS"
    assert result.score == 0
    assert result.hard_signs == []


def test_single_weak_sign_is_monitor():
    result = evaluate(["fan_running_hard"])
    assert result.verdict == "MONITOR"
    assert result.score == 1


def test_stacked_signs_are_suspicious_with_triage_first():
    result = evaluate(
        ["unknown_startup_apps", "av_firewall_disabled", "sudden_slowness"]
    )
    assert result.verdict == "SUSPICIOUS"
    # Containment comes before investigation in the plan.
    assert "Disconnect" in result.action_plan[0]


def test_hard_sign_alone_escalates_to_likely_compromised():
    for hard in ("files_encrypted", "ransom_note_present",
                 "camera_mic_unexpected", "messages_sent_without_user"):
        result = evaluate([hard])
        assert result.verdict == "LIKELY_COMPROMISED", hard
        assert result.hard_signs == [hard]
        plan = " ".join(result.action_plan)
        assert "clean device" in plan or "DIFFERENT, clean device" in plan
        assert "Reinstall" in plan


def test_high_score_without_hard_sign_is_likely_compromised():
    result = evaluate([
        "new_admin_accounts", "unexplained_outbound_traffic",
        "login_alerts_unfamiliar",
    ])
    assert result.score >= 8
    assert result.verdict == "LIKELY_COMPROMISED"


def test_unknown_indicator_is_rejected_loudly():
    with pytest.raises(UnknownIndicatorError):
        evaluate(["fan_running_hard", "made_up_indicator"])


def test_duplicates_counted_once_and_sections_grouped():
    result = evaluate(["sudden_slowness", "sudden_slowness", "fan_running_hard"])
    assert result.score == 2
    assert result.by_section == {
        "01_warning_signs": ["sudden_slowness", "fan_running_hard"]
    }


def test_checklist_covers_all_five_source_sections():
    sections = {item["section"] for item in checklist()}
    assert sections == {
        "01_warning_signs", "02_system_indicators", "03_network_account",
    }
    assert len(checklist()) == len(INDICATORS) == 18
