#!/usr/bin/env python3
"""TASK-SEN-032 live probes — PRODUCTION-VERIFY IG2-SEN-02..06.

Runs the five Sentinel corpus items against the real surface, on the
live Sentinel host (Oracle Server 1, 10.0.0.121):

  /opt/friday_universe/venv/bin/python \
      /opt/friday_universe/Sentinel/scripts/sen032_live_probes.py \
      [--image PATH] [--observe ID ...]

Safety — read-only by design:
- No approval is submitted: no POST /api/v1/approvals/request, no
  Telegram message, no ledger write. (None of the five items touches
  the approval path — verified: no production code imports any of
  them — so no approval-path legs are owed by this task; see the
  evidence doc.)
- No file is written outside /tmp: the SEN-03 baseline lives in a
  /tmp/sen032-baseline-*.json scratch file, deleted at exit.
- SEN-02 uses the modules' own connect-only TCP, TLS-handshake and
  HTTP-GET probes against fleet hosts only (OutOfScopeError otherwise).
- SEN-04 reads one image file. SEN-05/SEN-06 are pure functions on the
  observations / text handed to them. Nothing is executed on any host.

Output: one JSON object on stdout with a per-item result.
Exit code 0 unless the driver itself fails.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import socket
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve()
_SENTINEL_DIR = _HERE.parent.parent  # <repo>/Sentinel or /opt/friday_universe/Sentinel
_REPO_ROOT = _SENTINEL_DIR.parent
for _candidate in (str(_SENTINEL_DIR), str(_REPO_ROOT)):
    if _candidate not in sys.path:
        sys.path.insert(0, _candidate)

try:  # live tree: /opt/friday_universe/Sentinel/app/services/...
    from app.services.audit_baseline import (  # noqa: E402
        BaselineMemorist,
        JsonBaselineStore,
    )
    from app.services.compromised_host_triage import evaluate as triage_evaluate  # noqa: E402
    from app.services.extortion_mail_triage import triage_email  # noqa: E402
    from app.services.fleet_audit_pipeline import (  # noqa: E402
        AuditTarget,
        FleetAuditPipeline,
        FleetHost,
        FleetService,
        OutOfScopeError,
        PlannedCheck,
        default_fleet_inventory,
    )
    from app.services.media_ela import (  # noqa: E402
        ElaInputError,
        analyse_image,
        analyse_image_bytes,
    )
except ImportError:  # repo checkout: Sentinel/app/services/...
    from Sentinel.app.services.audit_baseline import (  # noqa: E402
        BaselineMemorist,
        JsonBaselineStore,
    )
    from Sentinel.app.services.compromised_host_triage import (  # noqa: E402
        evaluate as triage_evaluate,
    )
    from Sentinel.app.services.extortion_mail_triage import triage_email  # noqa: E402
    from Sentinel.app.services.fleet_audit_pipeline import (  # noqa: E402
        AuditTarget,
        FleetAuditPipeline,
        FleetHost,
        FleetService,
        OutOfScopeError,
        PlannedCheck,
        default_fleet_inventory,
    )
    from Sentinel.app.services.media_ela import (  # noqa: E402
        ElaInputError,
        analyse_image,
        analyse_image_bytes,
    )

# Owner order 7138538710 (2026-11-24 fleet re-layout): Memora / Forge /
# Sentinel / Cortex on Oracle Server 1; FRIDAY+Inference, Stratex,
# VyralX, IntelX+Futuris on their own servers; bridge+repo on Oracle
# Server 2. The module's default_fleet_inventory() still lists the
# pre-layout placement (FRIDAY 10000, Inference 8001, Stratex 8003,
# Futuris 8004, IntelX 8005 on server-1; Sentinel/Cortex/VyralX on
# server-2) and is therefore STALE — it is not used for findings. The
# staleness is filed as a fix-task candidate in the evidence doc.
CORRECTED_INVENTORY: list[FleetHost] = [
    FleetHost("server-1", "10.0.0.121", (
        FleetService("Memora", 8002),
        FleetService("Forge", 8006),
        FleetService("Sentinel", 8008),
        FleetService("Cortex", 8009),
    )),
]

# Oracle Server 2 (10.0.0.120) hosts bridge+repo only in the current
# layout — no agent service with a known port — so it contributes no
# service target. It still gets the unexpected-ports check, carried by
# this target (only its address is used by that check).
S2_UNEXPECTED_PORTS_TARGET = AuditTarget(
    "server-2", "10.0.0.120", "bridge-host", 0, "http",
)

# Corpus source text, reconstructed from the module docstring (IG wave 2,
# cluster #80, shortcode DU3rtSlk9mi): a narrator received a ransom
# demand for $30,000. No live inbox mail was read for this task.
CORPUS_RANSOM_SCENARIO = {
    "subject": "Your files have been encrypted — pay $30,000 in Bitcoin within 48 hours or else",
    "body": (
        "We have hacked your computer and copied your files. "
        "Your files are encrypted and your data has been stolen. "
        "Pay $30,000 in Bitcoin (BTC) to our wallet address within 48 hours "
        "or we will leak your data and destroy your files. "
        "Do not contact the police. Your password is hunter2 — we have access to your computer.\n"
        '<img src="https://tracker.example.com/pixel?id=abc" width="1" height="1">'
    ),
    "headers": {
        "From": "ransom@example.com",
        "Reply-To": "other@example.net",
    },
}

BENIGN_NEWSLETTER = {
    "subject": "Your weekly community newsletter",
    "body": "Here is this week's update from the community garden group. No action needed.",
    "headers": {"From": "garden@example.org"},
}

PIXEL_ONLY_NEWSLETTER = {
    "subject": "Your weekly community newsletter",
    "body": (
        "Here is this week's update."
        '<img src="https://news.example.org/track/open?id=1" width="1" height="1">'
    ),
    "headers": {"From": "garden@example.org"},
}


def corrected_inventory() -> list[FleetHost]:
    """The fleet as laid out by owner order 7138538710 (S1 services)."""
    return list(CORRECTED_INVENTORY)


def deployed_head() -> str | None:
    """Best-effort git HEAD of the deployed Sentinel tree (read-only)."""
    try:
        out = subprocess.run(
            ["git", "-C", str(_SENTINEL_DIR), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=15,
        )
        return out.stdout.strip() or None
    except Exception:
        return None


def gather_host_facts() -> dict[str, Any]:
    """Read-only facts about this host, the SEN-05 observation basis."""
    facts: dict[str, Any] = {"hostname": socket.gethostname()}
    try:
        with open("/proc/loadavg", encoding="utf-8") as handle:
            facts["loadavg_1m"] = float(handle.read().split()[0])
    except Exception as exc:  # noqa: BLE001 - record, do not fail the run
        facts["loadavg_error"] = str(exc)
    try:
        with open("/proc/uptime", encoding="utf-8") as handle:
            facts["uptime_seconds"] = float(handle.read().split()[0])
    except Exception as exc:  # noqa: BLE001
        facts["uptime_error"] = str(exc)
    return facts


def run_sen02(inventory: list[FleetHost]) -> dict[str, Any]:
    """IG2-SEN-02: multi-role defensive audit pipeline, live fleet."""
    pipeline = FleetAuditPipeline(inventory=inventory)
    report = pipeline.run()
    # S2 unexpected-ports check (no service target exists for it): the
    # executor only needs the target's address for this check.
    s2_check = PlannedCheck(S2_UNEXPECTED_PORTS_TARGET, "unexpected-ports")
    s2_findings = pipeline.executor.run_check(s2_check)
    s2_verified, s2_dropped = pipeline.reflector.verify(s2_findings, [s2_check])
    # Failure case: an off-inventory address must be refused before probing.
    try:
        pipeline.researcher.assert_in_scope("8.8.8.8")
        scope_failure = {"raised": False}
    except OutOfScopeError as exc:
        scope_failure = {"raised": True, "error": type(exc).__name__, "detail": str(exc)}
    default_targets = len(default_fleet_inventory())
    return {
        "report": report.as_dict(),
        "server2_unexpected_ports": {
            "findings": [f.as_dict() for f in s2_verified],
            "dropped": s2_dropped,
        },
        "scope_failure_case": scope_failure,
        "inventory_note": (
            f"default_fleet_inventory() lists {default_targets} hosts "
            "with pre-re-layout services; not used — see evidence doc."
        ),
    }


def run_sen03(findings: list[dict[str, Any]]) -> dict[str, Any]:
    """IG2-SEN-03: baseline memorist over the SEN-02 findings (/tmp only)."""
    tmp = tempfile.NamedTemporaryFile(
        prefix="sen032-baseline-", suffix=".json", delete=False,
    )
    tmp.close()
    try:
        memorist = BaselineMemorist(JsonBaselineStore(tmp.name))
        baseline = memorist.accept_baseline(findings)
        diff, alerts = memorist.record_run(findings)
        # Failure/regression case: same finding id, severity raised.
        regressed = [dict(f) for f in findings]
        if regressed:
            regressed[0]["severity"] = "CRITICAL"
            reg_diff, reg_alerts = memorist.record_run(regressed)
        else:
            reg_diff, reg_alerts = None, []
        return {
            "baseline_path": tmp.name,
            "baseline_accepted_at": baseline["accepted_at"],
            "baseline_findings": len(baseline["findings"]),
            "repeat_run_diff": diff.as_dict(),
            "repeat_run_alerts": alerts,
            "regression_case": (
                {"diff": reg_diff.as_dict(), "alerts": reg_alerts}
                if reg_diff is not None else None
            ),
        }
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def run_sen04(image_path: str | None) -> dict[str, Any]:
    """IG2-SEN-04: ELA on a real fleet JPEG + failure cases."""
    result: dict[str, Any] = {"image_path": image_path}
    if image_path:
        try:
            ela = analyse_image(image_path)
            result["real_image"] = ela.as_dict()
        except Exception as exc:  # noqa: BLE001 - record, do not fail the run
            result["real_image"] = {
                "error": type(exc).__name__, "detail": str(exc),
            }
    # Failure case 1: undecodable bytes must raise ElaInputError.
    try:
        analyse_image_bytes(b"this is not an image at all")
        result["non_image_bytes"] = {"raised": False}
    except ElaInputError as exc:
        result["non_image_bytes"] = {
            "raised": True, "error": type(exc).__name__,
        }
    # Failure case 2: PNG input is INCONCLUSIVE by design.
    from PIL import Image  # noqa: E402  (Pillow is the fleet image lib)
    buffer = io.BytesIO()
    Image.new("RGB", (128, 128), color=(200, 30, 30)).save(buffer, "PNG")
    png_result = analyse_image_bytes(buffer.getvalue())
    result["png_input"] = png_result.as_dict()
    return result


def run_sen05(observations: list[str]) -> dict[str, Any]:
    """IG2-SEN-05: compromised-host triage on observed indicators."""
    result = triage_evaluate(observations)
    out: dict[str, Any] = {
        "observations": observations,
        "result": result.as_dict(),
    }
    # Failure case 1: unknown indicator ids must be rejected loudly.
    try:
        triage_evaluate(["not_a_real_indicator"])
        out["unknown_indicator"] = {"raised": False}
    except Exception as exc:  # noqa: BLE001 - UnknownIndicatorError expected
        out["unknown_indicator"] = {
            "raised": True, "error": type(exc).__name__,
        }
    # Failure case 2: a hard sign must escalate to LIKELY_COMPROMISED.
    out["hard_sign_case"] = triage_evaluate(["files_encrypted"]).as_dict()
    return out


def run_sen06() -> dict[str, Any]:
    """IG2-SEN-06: extortion-mail triage on the corpus scenario text."""
    corpus = triage_email(**CORPUS_RANSOM_SCENARIO)
    benign = triage_email(**BENIGN_NEWSLETTER)
    pixel_only = triage_email(**PIXEL_ONLY_NEWSLETTER)
    return {
        "corpus_scenario": corpus.as_dict(),
        "benign_newsletter": benign.as_dict(),
        "pixel_only_newsletter": pixel_only.as_dict(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default=None,
                        help="real JPEG on this host for the SEN-04 check")
    parser.add_argument("--observe", nargs="*", default=[],
                        help="SEN-05 indicator ids actually observed on this host")
    args = parser.parse_args(argv)

    started = datetime.now(timezone.utc).isoformat()
    sen02 = run_sen02(corrected_inventory())
    sen03 = run_sen03(sen02["report"]["findings"])
    sen04 = run_sen04(args.image)
    sen05 = run_sen05(list(args.observe))
    sen06 = run_sen06()
    payload = {
        "task": "TASK-SEN-032",
        "started_at_utc": started,
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "hostname": socket.gethostname(),
        "deployed_head": deployed_head(),
        "host_facts": gather_host_facts(),
        "sen02_fleet_audit_pipeline": sen02,
        "sen03_baseline_memorist": sen03,
        "sen04_ela": sen04,
        "sen05_compromised_host_triage": sen05,
        "sen06_extortion_mail_triage": sen06,
    }
    print(json.dumps(payload, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
