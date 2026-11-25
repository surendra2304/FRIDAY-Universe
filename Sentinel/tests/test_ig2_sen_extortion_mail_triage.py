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


def test_tracking_pixel_detected_and_explained():
    # SE-01: the classic sextortion mail carrying a 1x1 remote pixel.
    result = triage_email(
        subject="I recorded you",
        body=(
            "I hacked your computer and recorded you through your webcam "
            "while you visited adult sites. Pay 1500 dollars in bitcoin to "
            "my wallet address within 48 hours or else we will release "
            "the video to all your contacts."
            '<img src="https://mailstat.example/o/abc123.gif" width="1" height="1">'
        ),
    )
    assert result.category == "SEXTORTION_SCAM"
    assert result.tracking_pixel is True
    assert "tracking_pixel_present" in result.signals
    assert result.as_dict()["tracking_pixel"] is True
    assert any("tracking pixel" in g for g in result.guidance)
    assert "Tracking pixel" in result.to_markdown()


def test_tracking_path_image_counts_even_at_normal_size():
    result = triage_email(
        body='<img src="https://x.example/track/open?id=99" width="300">',
    )
    assert result.tracking_pixel is True
    # A pixel alone never manufactures an extortion verdict.
    assert result.category == "NOT_EXTORTION"
    assert result.guidance == []


def test_ordinary_remote_image_is_not_a_tracking_pixel():
    result = triage_email(
        subject="Your invoice",
        body=(
            "Hi, your monthly statement is ready. Total $120 due on the 1st."
            '<img src="https://cdn.example/logo.png" width="200" height="50">'
        ),
    )
    assert result.tracking_pixel is False
    assert "tracking_pixel_present" not in result.signals
    assert result.category == "NOT_EXTORTION"


def test_calm_guidance_warns_against_opening_and_loading_images_without_pixel():
    # TASK-SEN-026: the standing do-not-open / do-not-load-images line
    # is in the base calm-response guidance, so an extortion mail whose
    # pixel evades detection still tells the owner about images.
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
    assert result.tracking_pixel is False
    assert any(
        "Do not open this message again" in g and "load its images" in g
        for g in result.guidance
    )
    # No pixel-specific line when no pixel was detected.
    assert not any("carries a tracking pixel" in g for g in result.guidance)


def test_pixel_mail_carries_both_warnings():
    # TASK-SEN-026: with a pixel, the base line and the pixel-specific
    # line both appear, and the markdown carries the pixel warning.
    result = triage_email(
        subject="I recorded you",
        body=(
            "I hacked your computer and recorded you through your webcam "
            "while you visited adult sites. Pay 1500 dollars in bitcoin to "
            "my wallet address within 48 hours or else we will release "
            "the video to all your contacts."
            '<img src="https://mailstat.example/o/abc123.gif" width="1" height="1">'
        ),
    )
    assert result.category == "SEXTORTION_SCAM"
    assert result.tracking_pixel is True
    assert any(
        "Do not open this message again" in g and "load its images" in g
        for g in result.guidance
    )
    assert any("carries a tracking pixel" in g for g in result.guidance)
    assert "Tracking pixel" in result.to_markdown()
    assert "Do not open this message again" in result.to_markdown()


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
