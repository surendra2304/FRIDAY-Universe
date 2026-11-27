"""TASK-SEN-028 — Sentinel 7-step digital-footprint cleanup walkthrough.

Owner-operated CLI checklist (checkpoint 2: walkthrough skeleton, JSON
status store, HIBP reuse seam, tests). No owner data ever leaves the
machine: every live check is owner-initiated, no credentials are stored,
and a step that cannot be checked reports ``unavailable`` instead of
``clean``.

Steps (board acceptance, TASK-SEN-028):
  1. hibp          — HIBP breach check (reuses TASK-IG2-INT-06,
                      IntelX/intelx/osint/breach_check.py)
  2. justdeleteme  — JustDeleteMe account-deletion directory (guidance)
  3. aliases       — email-alias inventory (guidance, owner-managed)
  4. my-activity   — Google My Activity cleanup (guidance, owner session)
  5. digital-rights — YourDigitalRights.org erasure templates (guidance)
  6. exiftool      — ExifTool metadata stripping (local binary only)
  7. cover-tracks  — EFF Cover Your Tracks browser test (guidance)

Wired into the Sentinel CLI as ``sentinel footprint ...`` (see
``sentinel/apps/cli/main.py``). State lives in the owner's home
directory (``~/.sentinel/footprint-cleanup.json``), never in the repo.
"""

from __future__ import annotations

import asyncio
import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import typer

STATUSES = ("pending", "done", "skipped", "blocked", "unavailable")

STEPS = (
    {
        "id": "hibp",
        "title": "Have I Been Pwned breach check",
        "kind": "live",
        "summary": "Check the owner's email against HIBP breached-account data.",
        "owner_action": (
            "Give the owner's email. If the owner supplies an HIBP API key it is "
            "pasted for this run only and never stored; without a key the step "
            "reports unavailable, never clean."
        ),
    },
    {
        "id": "justdeleteme",
        "title": "JustDeleteMe account-deletion directory",
        "kind": "guidance",
        "summary": "Walk the owner's accounts through JustDeleteMe deletion links.",
        "owner_action": (
            "Owner clicks through in their own browser; the tool records which "
            "accounts were deleted, it deletes nothing itself."
        ),
    },
    {
        "id": "aliases",
        "title": "Email-alias inventory",
        "kind": "guidance",
        "summary": "Record which email aliases exist and where each is used.",
        "owner_action": (
            "Owner lists their aliases; the tool records the inventory, it "
            "creates no accounts."
        ),
    },
    {
        "id": "my-activity",
        "title": "Google My Activity cleanup",
        "kind": "guidance",
        "summary": "Guide the owner through deleting Google activity history.",
        "owner_action": (
            "Owner works in their own Google session; the tool records what was "
            "cleared, it handles no credentials."
        ),
    },
    {
        "id": "digital-rights",
        "title": "YourDigitalRights.org erasure templates",
        "kind": "guidance",
        "summary": "GDPR erasure-request templates the owner sends themselves.",
        "owner_action": (
            "Owner picks the services and sends the templated requests; the tool "
            "records which were sent."
        ),
    },
    {
        "id": "exiftool",
        "title": "ExifTool metadata stripping",
        "kind": "local-binary",
        "summary": "Strip metadata from owner-selected files with local ExifTool.",
        "owner_action": (
            "Owner selects the files; dry run lists them first, stripping runs "
            "only with --apply and only on those files. No upload."
        ),
    },
    {
        "id": "cover-tracks",
        "title": "EFF Cover Your Tracks browser test",
        "kind": "guidance",
        "summary": "Run the EFF browser-fingerprint test and record the result.",
        "owner_action": (
            "Owner runs the test in their own browser and reports the result; "
            "the tool records it as the owner reports it."
        ),
    },
)

STEP_IDS = tuple(step["id"] for step in STEPS)


def get_step(step_id: str) -> dict:
    """Return the step record for ``step_id`` or raise KeyError."""
    for step in STEPS:
        if step["id"] == step_id:
            return step
    raise KeyError(f"unknown footprint step {step_id!r}; known: {', '.join(STEP_IDS)}")


def default_state_path() -> Path:
    """Owner-local state file; never in the repo, never synced."""
    return Path.home() / ".sentinel" / "footprint-cleanup.json"


@dataclass
class FootprintState:
    """Per-step status store, persisted as JSON in the owner's home."""

    path: Path
    _data: dict = field(default_factory=dict, repr=False)

    @classmethod
    def load(cls, path: Path | None = None) -> "FootprintState":
        state_path = Path(path) if path is not None else default_state_path()
        data: dict = {}
        if state_path.exists():
            data = json.loads(state_path.read_text(encoding="utf-8"))
        state = cls(path=state_path, _data=data)
        state._data.setdefault("version", 1)
        state._data.setdefault("steps", {})
        for step_id in STEP_IDS:
            state._data["steps"].setdefault(step_id, {"status": "pending"})
        return state

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")

    def status(self, step_id: str) -> str:
        get_step(step_id)
        return str(self._data["steps"][step_id].get("status", "pending"))

    def mark(self, step_id: str, status: str, evidence: str = "") -> None:
        get_step(step_id)
        if status not in STATUSES:
            raise ValueError(f"invalid status {status!r}; known: {', '.join(STATUSES)}")
        record = {
            "status": status,
            "evidence": evidence,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._data["steps"][step_id] = record
        self.save()

    def reset(self) -> None:
        self._data = {"version": 1, "steps": {}}
        for step_id in STEP_IDS:
            self._data["steps"][step_id] = {"status": "pending"}
        self.save()


def hibp_email_status(email: str, api_key: str | None = None, _checker=None):
    """Check ``email`` against HIBP; returns ``(status, detail)``.

    Status is one of ``breaches_found`` | ``no_breaches`` | ``unavailable``
    | ``error``. The real checker is IntelX's ``check_email_breaches``
    (TASK-IG2-INT-06): without an API key it returns ``unavailable``
    itself, and when the module cannot be imported from Sentinel the step
    reports ``unavailable`` here too — never ``no_breaches``. ``_checker``
    is a test seam (an async callable taking ``(email, api_key=...)``).
    """
    if _checker is None:
        try:
            from intelx.osint.breach_check import (  # noqa: PLC0415 — lazy, cross-package
                check_email_breaches as _real,
            )
        except Exception as exc:  # noqa: BLE001 — any import failure is "unavailable"
            return "unavailable", f"HIBP reuse module not importable from Sentinel: {exc}"
        _checker = _real
    try:
        result = asyncio.run(_checker(email, api_key=api_key))
    except ValueError:
        raise
    except Exception as exc:  # noqa: BLE001 — a failed lookup is "error", never clean
        return "error", f"HIBP lookup failed: {exc}"
    status = getattr(result, "status", "error")
    if status == "breaches_found":
        breaches = getattr(result, "breaches", ()) or ()
        names = ", ".join(str(b.get("Name", "")) for b in breaches if isinstance(b, dict))
        return "breaches_found", f"breaches found: {names or len(breaches)}"
    if status == "no_breaches":
        return "no_breaches", "no breaches found for this email"
    if status == "unavailable":
        return "unavailable", getattr(result, "reason", "") or "HIBP check unavailable"
    return "error", getattr(result, "reason", "") or f"HIBP check returned {status!r}"


def hibp_password_status(password: str, _checker=None):
    """Check ``password`` via Pwned Passwords k-anonymity (free, no key).

    Returns ``(found, occurrences, detail)``. Only the first 5 hex chars
    of the SHA-1 ever leave the machine (see TASK-IG2-INT-06). ``_checker``
    is a test seam (an async callable taking ``(password,)``).
    """
    if _checker is None:
        try:
            from intelx.osint.breach_check import (  # noqa: PLC0415 — lazy, cross-package
                check_password_breach as _real,
            )
        except Exception as exc:  # noqa: BLE001 — any import failure is "not checked"
            return False, 0, f"HIBP reuse module not importable from Sentinel: {exc}"
        _checker = _real
    try:
        result = asyncio.run(_checker(password))
    except ValueError:
        raise
    except Exception as exc:  # noqa: BLE001 — a failed lookup is "not checked"
        return False, 0, f"HIBP lookup failed: {exc}"
    return bool(result.found), int(result.occurrences), (
        f"password appears {result.occurrences} time(s) in breach corpora"
        if result.found
        else "password not found in breach corpora"
    )


def exiftool_available() -> bool:
    """True when a local ExifTool binary exists; nothing is installed."""
    return shutil.which("exiftool") is not None


def exiftool_dry_run(paths: list[str]) -> list[str]:
    """Files that would be stripped. Never modifies anything."""
    return [str(p) for p in paths if Path(p).is_file()]


footprint_app = typer.Typer(
    help="7-step digital-footprint cleanup walkthrough (TASK-SEN-028)",
    add_completion=False,
)


def _state(state_file: str | None) -> FootprintState:
    return FootprintState.load(Path(state_file) if state_file else None)


@footprint_app.command("status")
def status_command(
    state_file: str | None = typer.Option(None, "--state-file", help="State file path."),
) -> None:
    """Show per-step status for all 7 steps."""
    state = _state(state_file)
    typer.echo("Digital-footprint cleanup — per-step status")
    for step in STEPS:
        typer.echo(f"  {step['id']:<15} {state.status(step['id']):<12} {step['title']}")


@footprint_app.command("step")
def step_command(step_id: str = typer.Argument(..., help="Step id, e.g. hibp.")) -> None:
    """Show what one step needs from the owner."""
    step = get_step(step_id)
    typer.echo(f"{step['id']} — {step['title']} [{step['kind']}]")
    typer.echo(step["summary"])
    typer.echo(f"Owner action: {step['owner_action']}")


@footprint_app.command("mark")
def mark_command(
    step_id: str = typer.Argument(..., help="Step id, e.g. hibp."),
    status: str = typer.Argument(..., help=f"One of: {', '.join(STATUSES)}."),
    evidence: str = typer.Option("", "--evidence", help="What was done / observed."),
    state_file: str | None = typer.Option(None, "--state-file", help="State file path."),
) -> None:
    """Record the owner's reported outcome for a step."""
    state = _state(state_file)
    try:
        state.mark(step_id, status, evidence)
    except (KeyError, ValueError) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"{step_id}: {status}")


@footprint_app.command("reset")
def reset_command(
    state_file: str | None = typer.Option(None, "--state-file", help="State file path."),
) -> None:
    """Reset all 7 steps to pending."""
    _state(state_file).reset()
    typer.echo("footprint cleanup state reset: all steps pending")


@footprint_app.command("hibp")
def hibp_command(
    email: str = typer.Argument(..., help="Owner email to check."),
    api_key: str | None = typer.Option(
        None, "--api-key", envvar="HIBP_API_KEY", help="Pasted for this run only; never stored."
    ),
) -> None:
    """Run the HIBP email check for one email (owner-initiated)."""
    status, detail = hibp_email_status(email, api_key=api_key)
    typer.echo(f"hibp {email}: {status} — {detail}")
    if status in ("breaches_found", "error"):
        raise typer.Exit(code=1)
