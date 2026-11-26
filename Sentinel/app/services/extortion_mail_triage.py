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

Tracking pixels (IG full-watch SE-01; same source item DU3rtSlk9mi)
------------------------------------------------------------------
Scam/extortion mail routinely embeds a tracking pixel — a tiny or
hidden remote image whose load tells the sender the mail was opened
(time, rough location, device class). This module detects the pixel
in the HTML body it is handed and reports it as the named signal
``tracking_pixel_present`` plus a ``tracking_pixel`` flag on the
verdict: the awareness matters because *opening* the mail (or its
attachment "to check") is itself the signal the sender is fishing
for. A pixel alone never makes a verdict — newsletters carry them
too — and a pixel is not access to the machine: it reports an open,
nothing more. Detection covers the HTML body text passed in; a
pixel inside a PDF attachment is visible only if the caller's
extractor preserves the markup.

TASK-SEN-026: the calm-response guidance also carries the standing
do-not-open / do-not-load-images line (DO_NOT_PAY_GUIDANCE) on every
extortion verdict, pixel or not — the pixel-specific line alone left
extortion mail with an undetected pixel without any instruction
about images.

Family codeword (IG full-watch SE-03; TASK-SEN-027)
---------------------------------------------------
The "in trouble abroad, send money" plea is the impersonation scam
this triage sees most: a message, call or voice note claiming a
family member is in trouble and needs money now — exactly the shape
AI voice cloning now fakes convincingly. The defence is a practice,
not a feature, banked in Sentinel/docs/SECURITY_REFERENCE_IG.md §5:
one secret phrase agreed with family offline, which any urgent
money/credentials/secrecy request must produce before anything
moves. This module detects the plea shape (trouble marker + money
request) and surfaces the practice as the named guidance item
FAMILY_CODEWORD_GUIDANCE, with the named signal
``family_impersonation_plea`` and a ``family_plea`` flag on the
verdict. Unlike the tracking pixel (common in legitimate mail, and
never manufactures a verdict), a trouble-plea + money-request is
itself the scam shape the codeword guards — so the guidance fires
even when the mail is not extortion (category stays NOT_EXTORTION;
no verdict is manufactured). The phrase itself is never stored by
the fleet: the module accepts no phrase, stores none, and says so
in the guidance — there is nothing to look up, only something to
ask for.
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
_IMG_TAG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
_IMG_SRC_RE = re.compile(r"""src\s*=\s*["']?(https?://[^\s"'>]+)""", re.IGNORECASE)
_IMG_TINY_RE = re.compile(r"""(width|height)\s*=\s*["']?[01]\b""", re.IGNORECASE)
_IMG_HIDDEN_STYLE_RE = re.compile(
    r"style\s*=\s*[\"'][^\"']*(display\s*:\s*none|visibility\s*:\s*hidden|(width|height)\s*:\s*[01]px)",
    re.IGNORECASE,
)
_TRACKING_PATH_RE = re.compile(r"/(pixel|track|tracker|open|beacon)\b", re.IGNORECASE)
# TASK-SEN-027 (SE-03): the trouble-plea shape — a family member
# supposedly in trouble, needing money now. Bare "abroad"/"overseas"
# is deliberately NOT a marker on its own (a tuition mail would
# match); it counts only inside "stuck/stranded abroad/overseas".
# The plea gate also needs a money request (payment demand or an
# amount) — trouble without a money ask is a notification, not a
# plea, and a money ask without trouble is any other mail.
_TROUBLE_PLEA_RE = re.compile(
    r"\b(in trouble|stranded|stuck abroad|stuck overseas|in jail|locked up|"
    r"arrested|in (the )?hospital|had an accident|emergency)\b",
    re.IGNORECASE,
)

TRACKING_PIXEL_GUIDANCE = (
    "This mail carries a tracking pixel: opening it (or opening an attachment 'to check') can "
    "tell the sender when and roughly where it was opened and on what device — nothing more; "
    "it is not access to your machine. Keep remote images blocked in your mail client."
)

# TASK-SEN-027 (SE-03): the named family-codeword guidance item.
# The practice, as banked in Sentinel/docs/SECURITY_REFERENCE_IG.md
# §5: agree one secret phrase with family offline, in person, before
# travel; any urgent request for money, credentials or secrecy — from
# any channel, in any voice — must produce it before anything moves.
# The phrase itself is never stored by the fleet: this module accepts
# no phrase, stores none, and the guidance says so.
FAMILY_CODEWORD_GUIDANCE = (
    "Family codeword check (SE-03): an urgent 'we are in trouble, send money' claim — "
    "by message, call or voice note, in any voice — must produce the family codeword "
    "before anything moves. No codeword, no transfer: call the person back on a number "
    "you already trust instead. Agree one codeword with family offline, in person, "
    "before travel; never write it into a chat, email or note. If it is ever spoken "
    "under pressure, demanded by a third party, or suspected shared, treat it as burned "
    "and re-agree a new one in person. The fleet never stores the codeword — there is "
    "nothing to look up, only something to ask for."
)


def _has_tracking_pixel(body: str) -> bool:
    """Detect a tracking pixel in an HTML mail body.

    A remote image counts as a tracking pixel when it is tiny
    (width/height 0–1), CSS-hidden, or served from a tracking path
    (/pixel, /track, /open, /beacon …). Ordinary remote images in
    legitimate mail do not match.
    """
    for tag in _IMG_TAG_RE.findall(body or ""):
        src = _IMG_SRC_RE.search(tag)
        if not src:
            continue  # inline/data images phone home to nobody
        if _IMG_TINY_RE.search(tag) or _IMG_HIDDEN_STYLE_RE.search(tag):
            return True
        if _TRACKING_PATH_RE.search(src.group(1)):
            return True
    return False

DO_NOT_PAY_GUIDANCE: tuple[str, ...] = (
    "Do NOT pay — payment marks you as a payer, funds the next round, and buys nothing: these senders almost never delete or withhold anything.",
    "Do NOT reply to the sender and do not click links or open attachments in the message.",
    # TASK-SEN-026: the standing do-not-open / do-not-load-images line.
    # It belongs in the base guidance, not only in the pixel-specific
    # line: an extortion mail whose pixel evades detection (hidden in
    # an attachment, or a tracking image the heuristics miss) still
    # needs the owner told not to open it again or load its images —
    # each open or image load can confirm to the sender that this
    # address is live and being read.
    "Do not open this message again or load its images: each open or image load can tell the sender this address is live and being read. Keep remote images blocked in your mail client.",
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
    tracking_pixel: bool = False
    family_plea: bool = False
    guidance: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "score": self.score,
            "signals": self.signals,
            "amounts_mentioned": self.amounts_mentioned,
            "verify_first": self.verify_first,
            "tracking_pixel": self.tracking_pixel,
            "family_plea": self.family_plea,
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
        if self.tracking_pixel:
            lines.append(
                "**Tracking pixel:** this mail embeds a tracking image — "
                "opening it can report the open (time, rough location, "
                "device) to the sender. That is all it reports; it is "
                "not access to your machine."
            )
        if self.family_plea:
            lines.append(
                "**Family codeword (SE-03):** this reads as an 'in trouble, "
                "send money' plea — ask for the family codeword before "
                "anything moves. No codeword, no transfer; call back on a "
                "number you already trust. The fleet never stores the "
                "codeword."
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

    # Tracking pixel: awareness signal only — it never feeds the
    # category logic (legitimate mail carries pixels too).
    has_pixel = _has_tracking_pixel(body)
    if has_pixel:
        signals.append("tracking_pixel_present")
        score += 1

    amounts = sorted({m.group(0).strip() for m in _AMOUNT_RE.finditer(text)})
    if amounts:
        signals.append("monetary_amount_mentioned")
        score += 1

    # Family impersonation plea (SE-03; TASK-SEN-027): trouble marker
    # + money request (payment demand or an amount). A named signal
    # like the pixel — it never feeds the category logic — but unlike
    # the pixel its guidance fires even on NOT_EXTORTION: the plea
    # shape is itself the scam the codeword guards.
    has_family_plea = bool(_TROUBLE_PLEA_RE.search(text)) and (
        has_payment or bool(amounts)
    )
    if has_family_plea:
        signals.append("family_impersonation_plea")
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
        # A trouble plea carries the codeword guidance even when the
        # mail is not extortion — the plea shape is the scam the
        # codeword guards; the category is still NOT_EXTORTION.
        plea_guidance = [FAMILY_CODEWORD_GUIDANCE] if has_family_plea else []
        return ExtortionTriage(
            category="NOT_EXTORTION", score=score, signals=signals,
            amounts_mentioned=amounts, tracking_pixel=has_pixel,
            family_plea=has_family_plea, guidance=plea_guidance,
        )

    guidance = list(DO_NOT_PAY_GUIDANCE)
    if has_pixel:
        guidance.append(TRACKING_PIXEL_GUIDANCE)
    if has_family_plea:
        guidance.append(FAMILY_CODEWORD_GUIDANCE)
    return ExtortionTriage(
        category=category,
        score=score,
        signals=signals,
        amounts_mentioned=amounts,
        # A shown password (or a checkable encryption claim) earns a
        # verification lead — never a payment.
        verify_first=bool(has_password_lead or category == "RANSOMWARE_CLAIM"),
        tracking_pixel=has_pixel,
        family_plea=has_family_plea,
        guidance=guidance,
    )
