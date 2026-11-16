"""
Sentinel/app/services/compromised_host_triage.py — Executable
compromised-laptop triage checklist for the owner's own devices.

TASK-IG2-SEN-05 (IG wave 2, cluster #76; source shortcode DXrixKzEVza —
a sectioned "CYBER SECURITY // OPSEC" infographic, sweep crew-15:
"COMPROMISED LAPTOP? HOW TO SPOT A MACHINE THAT MAY NO LONGER BE
CLEAN"). DEFENSIVE ONLY, and scoped to the owner's own devices: the
checklist *evaluates observations the owner (or a future device
companion) reports about his own machine*. It executes nothing on any
host, scans nothing, and touches no third party.

Structure (the infographic's five sections, made executable)
------------------------------------------------------------
01 Common warning signs      — slowness, fan, battery, pop-ups,
                               camera/mic activation, encrypted files
02 System-level indicators   — unknown startup apps, new admin
                               accounts, disabled AV/firewall, unknown
                               software, strange USB prompts, ransom
                               notes / .locked files
03 Network & account flags   — unexplained outbound traffic, login
                               alerts from unfamiliar locations,
                               unsolicited password resets, cloud sync
                               anomalies, messages sent without the
                               user, idle-time webcam/network use
04 Quick triage sequence     — the ordered containment steps
05 Escalation / next steps   — when signs stack up

Scoring: each observed indicator carries a weight; a small set of
indicators are *hard signs* (encrypted files / ransom note, camera or
mic activation the user did not start, messages sent without the user)
— any one of them alone escalates the verdict. Verdicts:

- NO_SIGNS            score 0 and no hard signs
- MONITOR             low score — watch, re-check, run a trusted scan
- SUSPICIOUS          mid score — run the full quick-triage sequence
- LIKELY_COMPROMISED  high score or any hard sign — containment first:
                      disconnect, do not log into sensitive accounts
                      from this machine, change passwords from a
                      *clean* device, preserve evidence, clean reinstall

The action plan is returned in execution order and always puts
containment (disconnect) before investigation, exactly as the source
checklist does. Unknown indicator ids are rejected loudly — a typo
must never silently read as "not observed".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

# id -> (section, label, weight, hard_sign)
INDICATORS: dict[str, tuple[str, str, int, bool]] = {
    # 01 — common warning signs
    "sudden_slowness": ("01_warning_signs", "Sudden slowness / unexplained performance drop", 1, False),
    "fan_running_hard": ("01_warning_signs", "Fan running hard while idle", 1, False),
    "battery_draining_fast": ("01_warning_signs", "Battery draining much faster than usual", 1, False),
    "unexpected_popups": ("01_warning_signs", "Unexpected pop-ups or browser redirects", 2, False),
    "camera_mic_unexpected": ("01_warning_signs", "Camera/microphone activated without the user starting them", 4, True),
    "files_encrypted": ("01_warning_signs", "Files suddenly encrypted / unreadable", 5, True),
    # 02 — system-level indicators
    "unknown_startup_apps": ("02_system_indicators", "Unknown apps in the startup list", 2, False),
    "new_admin_accounts": ("02_system_indicators", "New admin accounts the user did not create", 4, False),
    "av_firewall_disabled": ("02_system_indicators", "Antivirus or firewall found disabled", 3, False),
    "unknown_software_installed": ("02_system_indicators", "Unknown software installed", 2, False),
    "strange_usb_prompts": ("02_system_indicators", "Strange USB / device-pairing prompts", 2, False),
    "ransom_note_present": ("02_system_indicators", "Ransom note or .locked files present", 5, True),
    # 03 — network & account red flags
    "unexplained_outbound_traffic": ("03_network_account", "Unexplained outbound network traffic", 3, False),
    "login_alerts_unfamiliar": ("03_network_account", "Login alerts from unfamiliar locations/devices", 3, False),
    "unsolicited_password_resets": ("03_network_account", "Password-reset emails the user did not request", 3, False),
    "cloud_sync_anomalies": ("03_network_account", "Cloud sync uploading/changing files on its own", 2, False),
    "messages_sent_without_user": ("03_network_account", "Messages sent from the user's accounts that they did not send", 4, True),
    "idle_webcam_network_activity": ("03_network_account", "Webcam/network activity while the machine is idle", 3, False),
}

QUICK_TRIAGE_STEPS: tuple[str, ...] = (
    "Disconnect Wi-Fi / unplug Ethernet — containment before investigation",
    "Do NOT log into sensitive accounts (bank, email) from this machine",
    "Check Task Manager / Activity Monitor for unknown high-CPU processes; note names, do not delete yet",
    "Review startup items and user accounts against what you recognise",
    "Run a full scan with a trusted, up-to-date security tool",
    "Change important passwords from a DIFFERENT, clean device, and enable MFA",
)

ESCALATION_STEPS: tuple[str, ...] = (
    "Back up personal files only (documents/photos) to external media — do not restore programs or system images",
    "Preserve evidence: photos of any ransom note / alerts, note times and what was observed",
    # Source §05 residue (IG full-watch SE-04 / supervisor AUDIT-2):
    # the one escalation step the wave-2 pass had not carried over.
    "Report to IT or security if it is a work device",
    "Treat credentials used on this machine as exposed; rotate them from a clean device",
    "Reinstall the operating system from official media before trusting the machine again",
    "Monitor linked accounts (bank, email, cloud) for unfamiliar activity for the next weeks",
)

SUSPICIOUS_THRESHOLD = 4
LIKELY_THRESHOLD = 8


class UnknownIndicatorError(ValueError):
    """An observation named an indicator id the checklist does not define."""


@dataclass
class TriageResult:
    verdict: str  # NO_SIGNS | MONITOR | SUSPICIOUS | LIKELY_COMPROMISED
    score: int
    observed: list[str] = field(default_factory=list)
    hard_signs: list[str] = field(default_factory=list)
    by_section: dict[str, list[str]] = field(default_factory=dict)
    action_plan: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "score": self.score,
            "observed": self.observed,
            "hard_signs": self.hard_signs,
            "by_section": self.by_section,
            "action_plan": self.action_plan,
        }

    def to_markdown(self) -> str:
        lines = [
            "# Sentinel compromised-laptop triage",
            f"Verdict: **{self.verdict}** (score {self.score})",
        ]
        if self.observed:
            lines.append("Observed indicators:")
            for indicator_id in self.observed:
                section, label, weight, hard = INDICATORS[indicator_id]
                marker = " — HARD SIGN" if hard else ""
                lines.append(f"- [{section}] {label} (weight {weight}){marker}")
        else:
            lines.append("No indicators observed.")
        if self.action_plan:
            lines.append("Action plan (in order):")
            lines.extend(
                f"{i}. {step}" for i, step in enumerate(self.action_plan, 1)
            )
        return "\n".join(lines)


def checklist() -> list[dict[str, Any]]:
    """The full checklist, for a UI/companion to render as questions."""
    return [
        {
            "id": indicator_id,
            "section": section,
            "label": label,
            "weight": weight,
            "hard_sign": hard,
        }
        for indicator_id, (section, label, weight, hard) in INDICATORS.items()
    ]


def evaluate(observations: Iterable[str]) -> TriageResult:
    """Score a set of observed indicator ids into a verdict + plan."""
    observed = list(dict.fromkeys(observations))  # dedupe, keep order
    unknown = [o for o in observed if o not in INDICATORS]
    if unknown:
        raise UnknownIndicatorError(
            f"unknown indicator id(s): {', '.join(sorted(unknown))}"
        )
    score = sum(INDICATORS[o][2] for o in observed)
    hard_signs = [o for o in observed if INDICATORS[o][3]]
    by_section: dict[str, list[str]] = {}
    for o in observed:
        by_section.setdefault(INDICATORS[o][0], []).append(o)

    if hard_signs or score >= LIKELY_THRESHOLD:
        verdict = "LIKELY_COMPROMISED"
        plan = list(QUICK_TRIAGE_STEPS) + list(ESCALATION_STEPS)
    elif score >= SUSPICIOUS_THRESHOLD:
        verdict = "SUSPICIOUS"
        plan = list(QUICK_TRIAGE_STEPS)
    elif score > 0:
        verdict = "MONITOR"
        plan = [
            "Run a full scan with a trusted, up-to-date security tool",
            "Review startup items and user accounts against what you recognise",
            "Re-run this triage if any further indicator appears",
        ]
    else:
        verdict = "NO_SIGNS"
        plan = ["No action needed; keep routine updates and backups current"]
    return TriageResult(
        verdict=verdict, score=score, observed=observed,
        hard_signs=hard_signs, by_section=by_section, action_plan=plan,
    )
