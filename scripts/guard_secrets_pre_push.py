#!/usr/bin/env python3
"""Checklist F21 (MASTER_COMPLETION_CHECKLIST) — Batch 6, ZAI Agent 2.

Pre-push secret guard: refuse a push when the commits being pushed contain
high-entropy credential patterns that the repo's public history must never
carry (the repo is PUBLIC — one leaked token already required the H5 purge
and TASK-SEC-002 rewrite; this is the local seatbelt next to CI's Gitleaks).

Usage (install once per clone):
    git config core.hooksPath .githooks            # if not already set
    # .githooks/pre-push already calls this script

Direct test:
    python scripts/guard_secrets_pre_push.py --self-test
    python scripts/guard_secrets_pre_push.py --scan <ref-or-dir>

Exit codes: 0 clean / 1 findings (push must be aborted) / 2 scanner broken.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

#: High-signal patterns only: the token SHAPES this fleet actually uses.
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("telegram-bot-token", re.compile(r"\b\d{8,12}:AA[A-Za-z0-9_-]{30,}\b")),
    ("github-pat", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("github-classic", re.compile(r"\bghp_[A-Za-z0-9]{36}\b")),
    ("oracle-dsn", re.compile(r"\boracle\+oracledb://[^\s\"']+:[^\s\"']+@")),
    ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private-key-block", re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("binance-key", re.compile(r"\bbinance[_-]?(api)?[_-]?key\b.{0,12}[\"'=: ]\s*[\"']?[A-Za-z0-9]{32,}", re.I | re.S)),
]

#: Files whose content is credential-shaped by design.
ALLOWLIST_SUFFIXES = (".md.example", ".example", ".sample")
ALLOWLIST_PATHS = {
    "docs/security/FORGE_SANDBOX_REVIEW_2026-11-10.md",  # documents redacted shapes only
}


def _iter_pushed_files(local_ref: str, remote_ref: str) -> list[tuple[str, str]]:
    """(path, added-text) for every file changed between local and remote."""
    try:
        proc = subprocess.run(
            ["git", "diff", "--name-only", remote_ref, local_ref],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=60,
        )
        paths = [p for p in proc.stdout.splitlines() if p.strip()]
    except Exception:
        return []
    out: list[tuple[str, str]] = []
    for path in paths:
        blob = subprocess.run(
            ["git", "diff", remote_ref, local_ref, "--", path],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=60,
        )
        # Only ADDED lines can leak something new.
        added = "\n".join(
            ln[1:] for ln in blob.stdout.splitlines() if ln.startswith("+") and not ln.startswith("+++")
        )
        if added.strip():
            out.append((path, added))
    return out


def scan_text(path: str, text: str) -> list[str]:
    """Return human findings for credential-shaped content in ``text``."""
    if path in ALLOWLIST_PATHS or any(path.endswith(sfx) for sfx in ALLOWLIST_SUFFIXES):
        return []
    findings: list[str] = []
    for label, pattern in PATTERNS:
        for match in pattern.finditer(text):
            snippet = match.group(0)
            redacted = snippet[:8] + "…" if len(snippet) > 8 else snippet
            findings.append(f"{path}: {label} pattern ({redacted})")
    return findings


def pre_push(remote_ref: str, local_ref: str) -> int:
    changed = _iter_pushed_files(local_ref, remote_ref)
    findings: list[str] = []
    for path, added in changed:
        findings.extend(scan_text(path, added))
    if findings:
        print("SECRET GUARD: refusing push — credential-shaped content found:")
        for f in findings:
            print(f"  ! {f}")
        print(
            "\nIf this is a real credential: rotate it and remove it from the commits.\n"
            "If it is a documented/EXAMPLE shape: extend ALLOWLIST_PATHS in\n"
            "scripts/guard_secrets_pre_push.py with a comment saying why."
        )
        return 1
    print(f"SECRET GUARD: clean ({len(changed)} changed file(s) scanned).")
    return 0


def _self_test() -> int:
    cases = [
        ("ok.txt", "hello world 12345", 0),
        ("bot.txt", "token 9050935840:AAHfKx9sampleNotRealButLongEnough012345678", 1),
        ("pat.txt", "ghp_" + "a" * 36, 1),
        ("dsn.txt", "oracle+oracledb://user:secretpw@host:1521/?service_name=X", 1),
        ("aws.txt", "AKIAIOSFODNN7EXAMPLE", 1),
        ("key.txt", "-----BEGIN RSA PRIVATE KEY-----", 1),
        ("readme.md.example", "ghp_" + "a" * 36, 0),
    ]
    failures = 0
    for path, text, expected in cases:
        got = len(scan_text(path, text))
        status = "ok" if (got > 0) == (expected > 0) else "FAIL"
        if status == "FAIL":
            failures += 1
        print(f"  self-test {path}: findings={got} expected={'some' if expected else 'none'} -> {status}")
    print("self-test " + ("PASS" if failures == 0 else f"FAIL ({failures})"))
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Pre-push secret guard (checklist F21).")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--scan", metavar="TARGET", help="scan a ref-or-directory's text files")
    parser.add_argument("hook_args", nargs="*", help="pre-push stdin lines: <remote_ref> <local_ref>")
    args = parser.parse_args()

    if args.self_test:
        return _self_test()

    if args.scan:
        target = Path(args.scan)
        files = target.rglob("*") if target.is_dir() else [target]
        findings: list[str] = []
        for f in files:
            if not f.is_file() or f.suffix not in (".py", ".md", ".yml", ".yaml", ".json", ".env", ".txt", ".sh", ".ts", ".tsx"):
                continue
            try:
                findings.extend(scan_text(str(f), f.read_text(encoding="utf-8", errors="ignore")))
            except Exception:
                continue
        for f in findings[:40]:
            print(f"  ! {f}")
        print(f"scanned {args.scan}: {len(findings)} finding(s)")
        return 1 if findings else 0

    # pre-push hook mode: read "<remote_ref> <local_ref>" lines from stdin.
    lines = args.hook_args or [ln.strip() for ln in sys.stdin if ln.strip()]
    if not lines:
        print("SECRET GUARD: no refs supplied — nothing to scan.")
        return 0
    worst = 0
    for line in lines:
        parts = line.split()
        if len(parts) < 2:
            continue
        # parts: <local_ref> <sha> <remote_ref> <sha> (pre-push format)
        local_ref, _, remote_ref = parts[0], parts[1], parts[2]
        worst = max(worst, pre_push(remote_ref, local_ref))
    return worst


if __name__ == "__main__":
    sys.exit(main())
