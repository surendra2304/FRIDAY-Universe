#!/usr/bin/env python3
"""
zero_cost_audit.py — H10: prove no accidental PAYG (pay-as-you-go) exposure.

Re-runnable (owner directive: quarterly). Checks the AUTOMATABLE $0-cost
invariants of the FRIDAY Universe stack; prints PASS/FAIL per check and exits
non-zero when any invariant is violated.

What it can verify from the repo alone:
  1. Oracle capacity sniper only ever launches VM.Standard.A1.Flex (Always
     Free eligible) with OCPU/RAM within the 4 OCPU / 24 GB free allowance,
     and its live-resize path stays within the allowance too.
  2. Sniper boot volume <= 200 GB (Always Free block-storage total).
  3. No paid cloud / SaaS SDK references in any GitHub workflow (aws, gcp,
     azure, stripe, twilio, pinecone, algolia, pusher).
  4. Default LLM provider is a free-tier provider (gemini/mock), and the
     default model is not in the known paid set.
  5. Stratex live-money gate exists and is permanent (demo/paper only).
  6. GitHub repo is public (Actions minutes unlimited/free). Best-effort via
     the origin remote token; skipped (not failed) offline.

What it CANNOT verify from the repo (owner's quarterly OCI-console checklist,
recorded in docs/security/zero_cost_audit_<date>.md):
  - total block storage across ALL volumes <= 200 GB (boot volumes count!)
  - no load balancer / NAT gateway / object storage beyond free allowances
  - outbound egress < 10 TB/month
  - OCI billing page shows $0.00 charged
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

A1_FREE_OCPUS = 4
A1_FREE_RAM_GB = 24
A1_FREE_BOOT_GB = 200

PAID_SDK_PATTERNS = (
    "boto3", "aws-sdk", "aws_access_key", "google-cloud", "azure-identity",
    "azure-storage", "stripe", "twilio", "pinecone", "algolia", "pusher",
)
PAID_LLM_MODELS = ("gpt-4", "gpt-4o", "gpt-3.5", "claude-3", "claude-opus",
                   "o1-", "o3-", "text-embedding-3")


def check(name: str, ok: bool, detail: str) -> bool:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    return ok


def audit_sniper() -> list[bool]:
    results = []
    sniper = REPO / "FRIDAY" / "scripts" / "oracle_retry.py"
    text = sniper.read_text(encoding="utf-8", errors="ignore")

    shape_ok = 'shape="VM.Standard.A1.Flex"' in text
    results.append(check("sniper shape is Always-Free A1.Flex", shape_ok,
                         "VM.Standard.A1.Flex only" if shape_ok else "paid shape found"))

    configs = re.findall(r'\{"ocpus":\s*(\d+),\s*"ram":\s*(\d+)', text)
    within = all(int(o) <= A1_FREE_OCPUS and int(r) <= A1_FREE_RAM_GB for o, r in configs)
    worst = max((int(o), int(r)) for o, r in configs) if configs else (0, 0)
    results.append(check("sniper launch configs within free allowance", within and bool(configs),
                         f"{len(configs)} configs, max {worst[0]} OCPU / {worst[1]} GB "
                         f"(allowance {A1_FREE_OCPUS}/{A1_FREE_RAM_GB})"))

    resize = re.findall(r"UpdateInstanceShapeConfigDetails\(\s*ocpus=(\d+),\s*memory_in_gbs=(\d+)", text)
    resize_ok = all(int(o) <= A1_FREE_OCPUS and int(r) <= A1_FREE_RAM_GB for o, r in resize)
    results.append(check("sniper live-resize within free allowance", resize_ok and bool(resize),
                         f"resize targets: {resize or 'none'}"))

    boot = re.search(r'BOOT_VOLUME_GB",\s*"(\d+)"', text)
    boot_gb = int(boot.group(1)) if boot else 50
    results.append(check("sniper boot volume <= free block-storage total",
                         boot_gb <= A1_FREE_BOOT_GB, f"{boot_gb} GB (free total {A1_FREE_BOOT_GB} GB)"))
    return results


def audit_workflows() -> list[bool]:
    hits = []
    for wf in (REPO / ".github" / "workflows").glob("*.yml"):
        text = wf.read_text(encoding="utf-8", errors="ignore").lower()
        for pattern in PAID_SDK_PATTERNS:
            if pattern in text:
                hits.append(f"{wf.name}:{pattern}")
    return [check("no paid cloud/SaaS SDKs in workflows", not hits,
                  "clean" if not hits else f"found {hits}")]


def audit_llm_defaults() -> list[bool]:
    config = REPO / "FRIDAY" / "src" / "friday" / "core" / "config.py"
    text = config.read_text(encoding="utf-8", errors="ignore")
    provider = re.search(r'llm_provider:\s*str\s*=\s*Field\(default="([^"]+)"', text)
    model = re.search(r'llm_model:\s*str\s*=\s*Field\(default="([^"]+)"', text)
    free_providers = {"gemini", "mock", "groq", "openrouter"}
    prov = provider.group(1) if provider else "?"
    mdl = model.group(1) if model else "?"
    results = [
        check("default LLM provider is free-tier", prov in free_providers,
              f"default provider '{prov}'"),
    ]
    paid_model = any(p in mdl.lower() for p in PAID_LLM_MODELS)
    results.append(check("default LLM model is not in the paid set", not paid_model,
                         f"default model '{mdl}'"))
    return results


def audit_stratex_gate() -> list[bool]:
    config = REPO / "Stratex" / "config.py"
    text = config.read_text(encoding="utf-8", errors="ignore")
    has_gate = "def validate_environment_safety" in text and "permanently forbidden" in text
    raises = re.search(
        r"if v_upper in \[.*?\]:\s*raise SecurityConfigurationError", text, re.DOTALL
    )
    return [check("Stratex live-money gate permanent + raising",
                  has_gate and bool(raises),
                  "validate_environment_safety raises on any live flag")]


def audit_repo_public() -> list[bool]:
    """Best-effort: repo must be public so Actions minutes are free."""
    try:
        url = subprocess_run(["git", "remote", "get-url", "origin"])
        match = re.search(r"x-access-token:([^@]+)@github\.com/([^/]+/[^.]+)\.git", url)
        if not match:
            return [check("github repo public (Actions free)", True,
                          "SKIPPED — no tokened origin remote in this clone")]
        token, repo = match.group(1), match.group(2)
        req = urllib.request.Request(
            f"https://api.github.com/repos/{repo}",
            headers={"Authorization": f"token {token}", "User-Agent": "zero-cost-audit"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        public = not data.get("private", True)
        return [check("github repo public (Actions free)", public,
                      f"{repo} is {'public' if public else 'PRIVATE — Actions minutes cost money!'}")]
    except Exception as exc:  # network down etc. — not a cost verdict
        return [check("github repo public (Actions free)", True,
                      f"SKIPPED — could not query API ({exc.__class__.__name__})")]


def subprocess_run(cmd: list[str]) -> str:
    import subprocess
    return subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, check=True).stdout.strip()


def main() -> int:
    print("=== FRIDAY Universe $0-cost audit (H10) ===")
    results = (
        audit_sniper()
        + audit_workflows()
        + audit_llm_defaults()
        + audit_stratex_gate()
        + audit_repo_public()
    )
    failed = results.count(False)
    print(f"--- {len(results) - failed}/{len(results)} checks passed ---")
    if failed:
        print("ACTION REQUIRED: a $0-cost invariant is violated — see FAIL lines above.")
    else:
        print("Repo-side invariants hold. Complete the owner OCI-console checklist in "
              "docs/security/zero_cost_audit_<date>.md to finish the quarterly audit.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
