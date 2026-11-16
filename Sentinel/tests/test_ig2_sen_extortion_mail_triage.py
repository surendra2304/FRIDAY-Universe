"""Tests for TASK-IG2-SEN-06 extortion_mail_triage (stdlib-only).

The $30,000 case mirrors the source reel (cluster #80): a ransom
demand the family correctly read as likely spam.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.extortion_mail_triage import triage_email  # noqa: E402


def test_classic_sextortion_scam():
    result = triage_email(
        subject="I recorded you",
        body=(
            "I hacked your computer and recorded you through your webcam "
            "while you visited adult sites. Pay 1500 dollars in bitcoin to "
            "my wallet address within 48 hours or else we will release "
            "the video to all your contacts."
        ),
    )
    assert result.category == "SEXTORTION_SCAM"
    assert "sextortion_claim" in result.signals
    assert result.as_dict()["engages_sender"] is False
    assert any("Do NOT pay" in g for g in result.guidance)


def test_thirty_thousand_ransom_demand_is_fake_ransom():
    result = triage_email(
        subject="You owe us",
        body=(
            "We have hacked your accounts. Send $30,000 in bitcoin within "
            "72 hours or we will expose your private data and destroy "
            "your reputation."
        ),
    )
    assert result.category == "FAKE_RANSOM_DEMAND"
    assert any("30,000" in a for a in result.amounts_mentioned)


def test_ransomware_claim_escalates_to_verification():
    result = triage_email(
        body=(
            "We have encrypted your files and downloaded your database. "
            "Pay the ransom in bitcoin to receive the decrypt key."
        ),
    )
    assert result.category == "RANSOMWARE_CLAIM"
    assert result.verify_first is True
    assert any("compromised-host triage" in g for g in result.guidance)


def test_shown_password_sets_verify_first_but_still_no_pay():
    result = triage_email(
        body=(
            "I know your password is hunter2-old. Pay in bitcoin within "
            "24 hours or we will leak everything we recorded."
        ),
    )
    assert result.category != "NOT_EXTORTION"
    assert result.verify_first is True
    assert any("burned" in g for g in result.guidance)


def test_ordinary_email_is_not_extortion():
    result = triage_email(
        subject="Your invoice",
        body="Hi, your monthly statement is ready. Total $120 due on the 1st.",
    )
    assert result.category == "NOT_EXTORTION"
    assert result.guidance == []


def test_reply_to_mismatch_is_a_named_signal():
    result = triage_email(
        body=(
            "Pay in bitcoin within 48 hours or we will publish the "
            "webcam video to your contacts."
        ),
        headers={"From": "alert@secure-notify.example",
                 "Reply-To": "collector@other.example"},
    )
    assert "reply_to_differs_from_from" in result.signals
    assert result.category == "SEXTORTION_SCAM"
