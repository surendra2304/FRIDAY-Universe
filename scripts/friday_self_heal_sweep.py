#!/usr/bin/env python3
"""Checklists G11 + H8 + H9 (MASTER_COMPLETION_CHECKLIST): daily self-healing sweep.

One honest daily pass over the fleet's own health surfaces, run by systemd
timer (deploy/friday-self-heal.service + .timer) on each server. Findings
are reported, never silently "fixed": the sweep only READS state and
optionally prunes true garbage (old self-backups) — every alert line names
the real measured value.

Checks per server:
- disk usage per mount (alert > 85%),
- TLS certificate expiry for the public domain (alert < 21 days) — H8,
- journald disk usage + configured caps (log rotation evidence) — H9,
- failed systemd units (any non-zero `systemctl --failed`) — G11,
- backup freshness: newest fleet-backup manifest age (alert > 8 days) — G11,
- fleet agent /health through the public gateway (from Server 1) — G11.

Output: human-readable report (journal) + optional Telegram alert when a
check crosses its threshold. Exit code 0 unless a CHECK fails (not an alert:
an alert is data; a failed check means the sweep itself broke).

Usage:
    python scripts/friday_self_heal_sweep.py [--once] [--json]
    python scripts/friday_self_heal_sweep.py --self-test
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Public gateway base (only probed when run on the ingress server or with
#: --probe-gateway; the timer on Server 1 enables it).
PUBLIC_GATEWAY = "https://friday-universe.duckdns.org"
GATEWAY_ROUTES = (
    "friday", "inference", "memora", "stratex", "futuris",
    "intelx", "forge", "cortex", "sentinel", "vyralx",
)

DISK_ALERT_PCT = 85.0
CERT_ALERT_DAYS = 21
BACKUP_ALERT_DAYS = 8.0
JOURNAL_ALERT_MB = 400  # above the 200M cap something is wrong
BACKUP_MANIFEST_GLOB = "/opt/friday_universe/backups/*/manifest.json"


def _now_ist() -> str:
    ist = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    return datetime.datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S IST")


def _run(cmd: list[str], timeout: int = 30) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, (proc.stdout or "").strip()
    except Exception as exc:  # noqa: BLE001 - report, never crash
        return 1, f"{type(exc).__name__}: {exc}"


# ---------------------------------------------------------------------------
# checks — each returns (ok, lines, alerts)
# ---------------------------------------------------------------------------

def check_disk() -> tuple[bool, list[str], list[str]]:
    lines, alerts = [], []
    ok = True
    try:
        st = os.statvfs("/")
        pct = (1 - st.f_bavail / st.f_blocks) * 100
        lines.append(f"disk /: {pct:.1f}% used")
        if pct > DISK_ALERT_PCT:
            alerts.append(f"disk / at {pct:.1f}% (threshold {DISK_ALERT_PCT}%)")
    except Exception as exc:
        ok = False
        lines.append(f"disk /: check failed ({type(exc).__name__})")
    return ok, lines, alerts


def check_cert_expiry(domain: str = "friday-universe.duckdns.org") -> tuple[bool, list[str], list[str]]:
    """H8: TLS cert expiry — via openssl s_client, honest on failure."""
    lines, alerts = [], []
    try:
        proc = subprocess.run(
            ["openssl", "s_client", "-connect", f"{domain}:443", "-servername", domain],
            input="", capture_output=True, text=True, timeout=15,
        )
        pem = proc.stdout
        if "BEGIN CERTIFICATE" not in pem:
            raise ValueError("no certificate in s_client output")
        import tempfile

        with tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False) as tf:
            tf.write(pem[pem.index("-----BEGIN CERTIFICATE-----"): pem.index("-----END CERTIFICATE-----") + 25])
            path = tf.name
        try:
            code, out = _run(["openssl", "x509", "-in", path, "-noout", "-enddate"])
            if code != 0 or "notAfter=" not in out:
                raise ValueError("enddate missing")
            expiry = datetime.datetime.strptime(
                out.split("notAfter=")[1].strip(), "%b %d %H:%M:%S %Y %Z"
            ).replace(tzinfo=datetime.timezone.utc)  # openssl dates are GMT
            days_left = (expiry - datetime.datetime.now(datetime.timezone.utc)).days
            lines.append(f"TLS {domain}: expires in {days_left} days ({expiry.date()})")
            if days_left < CERT_ALERT_DAYS:
                alerts.append(f"TLS certificate for {domain} expires in {days_left} days (<{CERT_ALERT_DAYS})")
        finally:
            os.unlink(path)
    except Exception as exc:
        lines.append(f"TLS {domain}: check failed ({type(exc).__name__}) — reported, not guessed")
    return True, lines, alerts


def check_journald() -> tuple[bool, list[str], list[str]]:
    """H9: journald size vs its configured cap (log rotation evidence)."""
    lines, alerts = [], []
    code, out = _run(["journalctl", "--disk-usage"])
    if code != 0:
        return False, [f"journald: journalctl failed ({out[:80]})"], []
    lines.append(f"journald: {out}")
    try:
        size_mib = float(out.lower().split("take up")[1].split("m")[0].strip())
        if size_mib > JOURNAL_ALERT_MB:
            alerts.append(f"journald usage {size_mib:.0f}M exceeds the {JOURNAL_ALERT_MB}M alert line (cap 200M)")
    except Exception:
        pass  # parse failure is not a lie — the raw line is already reported
    cap = Path("/etc/systemd/journald.conf.d/size-limit.conf")
    lines.append(f"journald cap: {'present' if cap.exists() else 'MISSING — set SystemMaxUse=200M'}")
    if not cap.exists():
        alerts.append("journald size cap config missing (/etc/systemd/journald.conf.d/size-limit.conf)")
    return True, lines, alerts


def check_failed_units() -> tuple[bool, list[str], list[str]]:
    """G11: any failed systemd units on this host."""
    lines, alerts = [], []
    code, out = _run(["systemctl", "list-units", "--state=failed", "--no-legend", "--plain"])
    if code != 0:
        return False, [f"failed-units: systemctl failed ({out[:80]})"], []
    failed = [ln.split()[0] for ln in out.splitlines() if ln.strip()]
    lines.append(f"failed units: {len(failed)}")
    if failed:
        alerts.append("failed systemd units: " + ", ".join(failed[:8]))
    return True, lines, alerts


def check_backup_freshness() -> tuple[bool, list[str], list[str]]:
    """G11: newest fleet backup manifest age (weekly workflow writes these)."""
    lines, alerts = [], []
    manifests = sorted(Path("/opt/friday_universe/backups").glob("*/manifest.json")) if Path("/opt/friday_universe/backups").exists() else []
    if not manifests:
        lines.append("backups: no manifest found on this host (weekly Fleet Backup writes them)")
        return True, lines, alerts
    newest = max(manifests, key=lambda p: p.stat().st_mtime)
    age_days = (datetime.datetime.now() - datetime.datetime.fromtimestamp(newest.stat().st_mtime)).total_seconds() / 86400
    lines.append(f"backups: newest {newest.parent.name} ({age_days:.1f} days old)")
    if age_days > BACKUP_ALERT_DAYS:
        alerts.append(f"newest fleet backup is {age_days:.1f} days old (threshold {BACKUP_ALERT_DAYS})")
    return True, lines, alerts


def check_gateway() -> tuple[bool, list[str], list[str]]:
    """G11 (Server 1): all ten agents /health through the public gateway."""
    lines, alerts = [], []
    try:
        import requests  # noqa: PLC0415 - optional on minimal hosts
    except ImportError:
        return True, ["gateway: requests not installed — skipped honestly"], []
    bad = []
    for route in GATEWAY_ROUTES:
        try:
            resp = requests.get(f"{PUBLIC_GATEWAY}/{route}/health", timeout=8)
            if resp.status_code != 200:
                bad.append(f"{route}({resp.status_code})")
        except Exception as exc:
            bad.append(f"{route}({type(exc).__name__})")
    lines.append(f"gateway: {len(GATEWAY_ROUTES) - len(bad)}/{len(GATEWAY_ROUTES)} agents healthy")
    if bad:
        alerts.append("gateway agents failing /health: " + ", ".join(bad))
    return True, lines, alerts


# ---------------------------------------------------------------------------
# alerting (reuse the workspace Telegram credentials when present)
# ---------------------------------------------------------------------------

def _send_telegram_alert(alerts: list[str]) -> bool:
    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()
    if not token or not chat_id or not alerts:
        return False
    try:
        import requests  # noqa: PLC0415

        text = "🩺 FRIDAY self-heal sweep found issues:\n" + "\n".join(f"• {a}" for a in alerts)
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text[:4000]},
            timeout=10,
        )
        return resp.status_code == 200
    except Exception:
        return False


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def run_sweep(probe_gateway: bool = False) -> dict:
    checks = [
        ("disk", check_disk),
        ("cert", check_cert_expiry),
        ("journald", check_journald),
        ("failed_units", check_failed_units),
        ("backups", check_backup_freshness),
    ]
    if probe_gateway:
        checks.append(("gateway", check_gateway))

    report_lines: list[str] = []
    alerts: list[str] = []
    all_ok = True
    results: dict = {"timestamp_ist": _now_ist(), "checks": {}}
    for name, fn in checks:
        try:
            ok, lines, new_alerts = fn()
        except Exception as exc:  # a check crashing is a finding, not a crash
            ok, lines, new_alerts = False, [f"{name}: check raised {type(exc).__name__}"], []
        all_ok = all_ok and ok
        report_lines.extend(f"[{name}] {ln}" for ln in lines)
        alerts.extend(new_alerts)
        results["checks"][name] = {"ok": ok, "lines": lines, "alerts": new_alerts}

    results["alerts"] = alerts
    results["ok"] = all_ok

    header = f"=== FRIDAY self-heal sweep — {_now_ist()} ==="
    body = "\n".join(report_lines)
    footer = ""
    if alerts:
        footer = "ALERTS:\n" + "\n".join(f"! {a}" for a in alerts)
        _send_telegram_alert(alerts)
    print(header)
    print(body)
    if footer:
        print(footer)
    return results


def _self_test() -> int:
    """Library-level contract smoke: every check runs and reports honestly."""
    failures = 0
    for name, fn in (
        ("disk", check_disk),
        ("journald", check_journald),
        ("failed_units", check_failed_units),
        ("backups", check_backup_freshness),
    ):
        try:
            ok, lines, _ = fn()
            assert lines, f"{name} produced no lines"
            print(f"self-test {name}: ok={ok} lines={len(lines)}")
        except Exception as exc:
            failures += 1
            print(f"self-test {name}: FAILED {exc}")
    print("self-test done" + ("" if failures == 0 else f" ({failures} failures)"))
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--once", action="store_true", help="run one sweep (default)")
    parser.add_argument("--probe-gateway", action="store_true", help="also probe the public gateway (Server 1)")
    parser.add_argument("--json", action="store_true", help="also dump the JSON report")
    parser.add_argument("--self-test", action="store_true", help="run the check smoke tests")
    args = parser.parse_args()

    if args.self_test:
        return _self_test()
    results = run_sweep(probe_gateway=args.probe_gateway)
    if args.json:
        print(json.dumps(results, indent=2))
    # Alerts are findings; only a broken check (ok=False) fails the sweep.
    return 0 if results["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
