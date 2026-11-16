"""
Sentinel/app/services/extortion_mail_triage.py — Extortion / ransom
email triage for the owner's mailbox.

TASK-IG2-SEN-06 (IG wave 2, cluster #80; source shortcode DU3rtSlk9mi —
a narrator received a ransom-demand email demanding $30,000; her
parents correctly identified it as likely spam and nobody paid).
DEFENSIVE ONLY: this classifies an email the owner *received* and
produces calm do-not-pay guidance for the owner. It NEVER replies to,
engages, or contacts the sender, and it never follows links or opens
attachments — it reads the text/headers it is handed, nothing more.

Why this exists
---------------
Sextortion and fake-ransom mail is a volume scam: the sender has
usually compromised nothing, bought/breached an old password list, and
is betting on panic. The correct response is boring and fixed — do not
pay, do not reply, verify calmly from a clean state, preserve the
evidence, report it. This module encodes that response so the owner
gets it in seconds instead of in a panic.

Classification (deterministic signal scoring over subject+body+headers)
-----------------------------------------------------------------------
Categories:
- SEXTORTION_SCAM        — claims webcam/compromising-video access,
                           threatens release unless paid (the classic
                           bulk scam; the claimed footage almost never
                           exists)
- FAKE_RANSOM_DEMAND     — ransom/extortion demand with no credible
                           evidence of compromise
- RANSOMWARE_CLAIM       — claims files/systems are encrypted or data
                           exfiltrated; POSSIBLE real incident — this
                           category always escalates to verification
                           steps against the owner's own systems (via
                           the compromised-host triage, SEN-05) because
                           the claim, unlike sextortion, is checkable
- THREAT_OTHER           — threats/extortion language that fits none
                           of the above
- NOT_EXTORTION          — no extortion signals found

Signals are named and returned with the verdict so the owner can see
*why* — a black-box "scam score" would train distrust. A real
compromise is never ruled out by this module: where the sender shows
a *current* password or other apparently genuine private detail, the
verdict carries ``verify_first=True`` and the guidance leads with
rotating that credential from a clean device — while still: do not pay.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_AMOUNT_RE = re.compile(
    r"(?:\$|usd|rs\.?|inr|€|£)\s?\d[\d,]*(?:\.\d+)?|\d[\d,]*(?:\.\d+)?\s?(?:usd|dollars|bitcoin|btc)",
    re.IGNORECASE,
)
_CRYPTO_RE = re.compile(r"\b(bitcoin|btc|ethereum|crypto|wallet address|1[a-km-zA-HJ-NP-Z1-9]{25,34}|bc1[a-z0-9]{25,})\b", re.IGNORECASE)
_DEADLINE_RE = re.compile(r"\b(within|in)\s+\d+\s*(hours?|hrs?|days?)\b|\b(48|72|24)\s*(hours?|hrs?)\b|deadline|or else", re.IGNORECASE)
_PAYMENT_DEMAND_RE = re.compile(r"\b(pay|send|transfer|deposit)\b.{0,60}\b(bitcoin|btc|money|ransom|payment|wallet|gift cards?)\b", re.IGNORECASE | re.DOTALL)
_SEXTORTION_RE = re.compile(r"\b(webcam|masturbat|adult (sites?|videos?)|porn|compromising (video|footage)|your contacts will (receive|get)|send (it|the video) to (all )?your)\b", re.IGNORECASE)
_RANSOMWARE_RE = re.compile(r"\b(encrypted your|files are encrypted|data (has been )?(stolen|exfiltrated|leaked)|decrypt|ransomware|we have (downloaded|copied) your (data|files|database))\b", re.IGNORECASE)
_THREAT_RE = re.compile(r"\b(we will (leak|publish|release|destroy|expose)|will be (leaked|published|released)|destroy your|ruin your|expose (you|your))\b", re.IGNORECASE)
_PASSWORD_LEAD_RE = re.compile(r"\b(your password is|password[:\s]+[^\s]{4,}|i know your password)\b", re.IGNORECASE)
_HACK_CLAIM_RE = re.compile(r"\b(i (have )?hacked|we (have )?hacked|i have access to your|breached your|infected your (computer|device|phone))\b", re.IGNORECASE)

DO_NOT_PAY_GUIDANCE: tuple[str, ...] = (
    "Do NOT pay — payment marks you as a payer, funds the next round, and buys nothing: these senders almost never delete or withhold anything.",
    "Do NOT reply to the sender and do not click links or open attachments in the message.",
    "Preserve the evidence: keep the original email with full headers (do not forward-and-delete); screenshot the demand and the amount/address asked.",
    "Verify calmly, separately from the email: check your own accounts/devices directly (never via links in the message). If it claims your files are encrypted, run the compromised-host triage on that machine.",
    "If the message shows a password you recognise, treat that password as burned: change it — and anywhere you reused it — from a clean device, and enable MFA. Old breached passwords are the usual source; the sender rarely has live access.",
    "Report it: mark as phishing in your mail provider and, in India, optionally report at cybercrime.gov.in; then delete or archive it.",
    "Tell anyone the message threatens to contact: bulk sextortion mail is sent to thousands; the threatened material almost never exists.",
)


@dataclass
class ExtortionTriage:
    category: str
    score: int
    signals: list[str] = field(default_factory=list)
    amounts_mentioned: list[str] = field(default_factory=list)
    verify_first: bool = False
    guidance: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "score": self.score,
            "signals": self.signals,
            "amounts_mentioned": self.amounts_mentioned,
            "verify_first": self.verify_first,
            "guidance": self.guidance,
            "engages_sender": False,
        }

    def to_markdown(self) -> str:
        lines = [
            "# Sentinel extortion-mail triage",
            f"Category: **{self.category}** (signal score {self.score})",
        ]
        if self.amounts_mentioned:
            lines.append(
                "Amounts mentioned: " + ", ".join(self.amounts_mentioned)
            )
        if self.signals:
            lines.append("Signals: " + ", ".join(self.signals))
        if self.verify_first:
            lines.append(
                "**Verify first:** the message contains an apparently "
                "genuine private detail — rotate that credential from a "
                "clean device before anything else. Still do not pay."
            )
        if self.guidance:
            lines.append("What to do:")
            lines.extend(f"{i}. {g}" for i, g in enumerate(self.guidance, 1))
        return "\n".join(lines)


def triage_email(subject: str = "", body: str = "",
                 headers: dict[str, str] | None = None) -> ExtortionTriage:
    """Classify one received email. Pure text analysis; no network,
    no reply, no link-following — ever."""
    text = f"{subject}\n{body}"
    headers = headers or {}
    signals: list[str] = []
    score = 0

    def hit(name: str, pattern: re.Pattern, weight: int) -> bool:
        nonlocal score
        if pattern.search(text):
            signals.append(name)
            score += weight
            return True
        return False

    has_payment = hit("payment_demand", _PAYMENT_DEMAND_RE, 3)
    has_crypto = hit("crypto_payment_rail", _CRYPTO_RE, 2)
    hit("deadline_pressure", _DEADLINE_RE, 2)
    has_threat = hit("threat_of_harm_or_release", _THREAT_RE, 2)
    has_sextortion = hit("sextortion_claim", _SEXTORTION_RE, 3)
    has_ransomware_claim = hit("encryption_or_exfiltration_claim", _RANSOMWARE_RE, 3)
    has_hack_claim = hit("hack_access_claim", _HACK_CLAIM_RE, 1)
    has_password_lead = hit("password_shown_as_proof", _PASSWORD_LEAD_RE, 2)

    amounts = sorted({m.group(0).strip() for m in _AMOUNT_RE.finditer(text)})
    if amounts:
        signals.append("monetary_amount_mentioned")
        score += 1

    # Spoof hygiene: a Reply-To that does not match From is common in
    # bulk extortion and worth naming (it proves nothing alone).
    from_h = (headers.get("From") or "").lower()
    reply_h = (headers.get("Reply-To") or "").lower()
    if from_h and reply_h and reply_h not in from_h and from_h not in reply_h:
        signals.append("reply_to_differs_from_from")
        score += 1

    extortion_core = has_payment or (has_crypto and (has_threat or has_hack_claim))
    if has_ransomware_claim and (extortion_core or amounts):
        category = "RANSOMWARE_CLAIM"
    elif has_sextortion and (extortion_core or has_threat):
        category = "SEXTORTION_SCAM"
    elif extortion_core and (has_threat or has_hack_claim or amounts):
        category = "FAKE_RANSOM_DEMAND"
    elif has_threat and (has_hack_claim or amounts):
        category = "THREAT_OTHER"
    else:
        return ExtortionTriage(
            category="NOT_EXTORTION", score=score, signals=signals,
            amounts_mentioned=amounts,
        )

    return ExtortionTriage(
        category=category,
        score=score,
        signals=signals,
        amounts_mentioned=amounts,
        # A shown password (or a checkable encryption claim) earns a
        # verification lead — never a payment.
        verify_first=bool(has_password_lead or category == "RANSOMWARE_CLAIM"),
        guidance=list(DO_NOT_PAY_GUIDANCE),
    )
