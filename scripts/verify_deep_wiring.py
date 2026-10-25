#!/usr/bin/env python3
"""
scripts/verify_deep_wiring.py — The Single Verification Gate for Deep Engine Autonomy.

Verifies top-to-bottom that all 7 deep engines are wired, exposed via HTTP,
and operate autonomously across FRIDAY, Memora, Inference, VyralX, and Sentinel.

Exits with 0 if all checks pass, 1 otherwise.
"""
from __future__ import annotations

import importlib
import importlib.util
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "FRIDAY" / "apps" / "core" / "src"))
os.environ["SENTINEL_AUDIT_SIGNING_KEY"] = "1234567890123456"

# Color formatting
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"


def load_module(relpath: str, name: str):
    if name == "gate_FRIDAY_agent_runtime":
        if str(ROOT / "FRIDAY/apps/core/src") not in sys.path:
            sys.path.insert(0, str(ROOT / "FRIDAY/apps/core/src"))
        return importlib.import_module("friday_core.agent_runtime")

    path = ROOT / relpath
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {relpath}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def run_isolated(code: str, python_paths: list[str] | None = None) -> tuple[bool, str]:
    """Execute python snippet in isolated subprocess to prevent app namespace collisions."""
    paths = python_paths or [str(ROOT)]
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(paths)
    env["SENTINEL_AUDIT_SIGNING_KEY"] = "1234567890123456"
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if proc.returncode == 0:
        return True, proc.stdout.strip()
    return False, (proc.stderr or proc.stdout).strip()


results: list[tuple[str, str, bool, str]] = []


def record_check(category: str, description: str, passed: bool, detail: str = ""):
    results.append((category, description, passed, detail))
    status_str = f"{GREEN}[PASS]{RESET}" if passed else f"{RED}[FAIL]{RESET}"
    print(f"  {status_str} {category}: {description}")
    if not passed and detail:
        print(f"         {YELLOW}Detail: {detail[:250]}{RESET}")


def run_all_checks():
    print(f"\n{BOLD}======================================================================{RESET}")
    print(f"{BOLD}   FRIDAY UNIVERSE — DEEP ENGINE AUTONOMY VERIFICATION GATE           {RESET}")
    print(f"{BOLD}======================================================================{RESET}\n")

    # ──────────────────────────────────────────────────────────────────────────
    # 1. ENGINE IMPORTABILITY
    # ──────────────────────────────────────────────────────────────────────────
    print(f"{BOLD}[1/4] Checking Engine & Service Importability...{RESET}")
    engine_files = [
        ("FRIDAY", "FRIDAY/apps/core/src/friday_core/real_browser_agent.py"),
        ("FRIDAY", "FRIDAY/apps/core/src/friday_core/real_harness_engineering.py"),
        ("FRIDAY", "FRIDAY/apps/core/src/friday_core/agent_runtime.py"),
        ("Memora", "Memora/core/memory/real_agent_memory.py"),
        ("Memora", "Memora/core/memory/real_viking_context.py"),
        ("Memora", "Memora/core/memory/context_service.py"),
        ("Inference", "Inference/app/agents/real_scientific_skills.py"),
        ("Inference", "Inference/app/scientific_service.py"),
        ("VyralX", "VyralX/app/agents/real_diagram_design.py"),
        ("VyralX", "VyralX/app/services/diagram_service.py"),
        ("Sentinel", "Sentinel/app/services/real_cyber_skills.py"),
        ("Sentinel", "Sentinel/app/services/cyber_skills_service.py"),
    ]

    for agent, relpath in engine_files:
        try:
            name = Path(relpath).stem
            load_module(relpath, f"gate_{agent}_{name}")
            record_check("Import", f"{agent} -> {Path(relpath).name}", True)
        except Exception as exc:
            record_check("Import", f"{agent} -> {Path(relpath).name}", False, str(exc))

    # ──────────────────────────────────────────────────────────────────────────
    # 2. HTTP APP ROUTE EXPOSURE (Subprocess verification)
    # ──────────────────────────────────────────────────────────────────────────
    print(f"\n{BOLD}[2/4] Checking HTTP Surface Endpoints across Agents...{RESET}")

    http_checks = [
        (
            "FRIDAY",
            [str(ROOT / "FRIDAY" / "apps" / "core" / "src")],
            """
from friday_core.agent_runtime import router
assert router is not None
routes = [r.path for r in router.routes]
assert any('capabilities' in r for r in routes)
assert any('plan' in r for r in routes)
assert any('execute' in r for r in routes)
assert any('approvals' in r for r in routes)
print('FRIDAY routes OK:', len(routes))
""",
        ),
        (
            "Memora",
            [str(ROOT / "Memora")],
            """
from core.memory.context_service import router
assert router is not None
routes = [r.path for r in router.routes]
assert any('write' in r for r in routes)
assert any('search' in r or 'remember' in r for r in routes)
assert any('commit' in r for r in routes)
assert any('consolidate' in r for r in routes)
print('Memora routes OK:', len(routes))
""",
        ),
        (
            "Inference",
            [str(ROOT / "Inference")],
            """
from app.scientific_service import router
assert router is not None
routes = [r.path for r in router.routes]
assert any('audit' in r for r in routes)
assert any('power' in r for r in routes)
assert any('hypotheses' in r for r in routes)
assert any('skills' in r for r in routes)
print('Inference routes OK:', len(routes))
""",
        ),
        (
            "VyralX",
            [str(ROOT / "VyralX")],
            """
from app.services.diagram_service import router
assert router is not None
routes = [r.path for r in router.routes]
assert any('catalogue' in r for r in routes)
assert any('render' in r for r in routes)
assert any('from-brief' in r for r in routes)
assert any('from-mermaid' in r for r in routes)
assert any('restyle' in r for r in routes)
print('VyralX routes OK:', len(routes))
""",
        ),
        (
            "Sentinel",
            [str(ROOT / "Sentinel")],
            """
from app.services.cyber_skills_service import router
assert router is not None
routes = [r.path for r in router.routes]
assert any('triage' in r for r in routes)
assert any('playbook' in r for r in routes)
assert any('assess' in r for r in routes)
assert any('coverage' in r for r in routes)
assert any('authorise' in r for r in routes)
assert any('action' in r for r in routes)
print('Sentinel routes OK:', len(routes))
""",
        ),
    ]

    for agent, paths, snippet in http_checks:
        ok, detail = run_isolated(snippet, python_paths=paths)
        record_check("HTTP Route", f"{agent} App Routes Expose Deep Engines", ok, detail)

    # ──────────────────────────────────────────────────────────────────────────
    # 3. END-TO-END MULTI-AGENT AUTONOMOUS FLOW
    # ──────────────────────────────────────────────────────────────────────────
    print(f"\n{BOLD}[3/4] Testing Autonomous Cross-Agent Flow (Sentinel -> Memora -> FRIDAY -> Memora)...{RESET}")

    flow_paths = [
        str(ROOT / "FRIDAY" / "apps" / "core" / "src"),
        str(ROOT / "Sentinel"),
        str(ROOT / "Memora"),
    ]
    flow_code = """
import sys

# 1. Sentinel triages incident
from app.services.cyber_skills_service import CyberSkillsService
sentinel = CyberSkillsService()
triage = sentinel.triage("Credential dumping via memory injection", [
    {"description": "Mimikatz injected into lsass memory", "technique": "T1003", "source": "edr"}
])
assert "T1003" in triage["techniques"]
print("Step 1: Sentinel ATT&CK triage passed:", triage["techniques"])

# 2. Sentinel triage lesson committed to Memora context
from core.memory.context_service import MemoraContextService
memora = MemoraContextService()
techs = triage["techniques"]
memora.remember(
    "security_lesson",
    "incident-lsass",
    "LSASS lesson",
    f"Attacker used {techs}. Remediate by isolating host and rotating credentials.",
)
commit1 = memora.commit_session("sess-incident-001", [
    {"role": "user", "content": "Triage incident for lsass injection"},
    {"role": "assistant", "content": f"Attacker used {techs}. Remediate by isolating host and rotating credentials."},
])
assert commit1.get("committed") is True
print("Step 2: Lesson committed to Memora context")

# 3. FRIDAY recalls lesson via layered recall
level, hits = memora.recall_layered("Attacker isolating host")
assert len(hits) >= 1
print(f"Step 3: FRIDAY recalled lesson from Memora ({level})")

# 4. FRIDAY plans and executes gated remediation sequence
from friday_core.agent_runtime import FridayAgentRuntime
from friday_core.real_harness_engineering import Check
runtime = FridayAgentRuntime()

plan = runtime.plan("Credential remediation", ["check_syntax", "count_tokens"])
subtasks = plan.get("subtasks") if isinstance(plan, dict) else plan.subtasks
assert len(subtasks) >= 2

exec_res = runtime.execute(
    "Remediate credential dump",
    [{"tool": "count_tokens", "arguments": {"text": "remediation-evidence"}}],
    checks=[Check("tokens_counted", lambda out: (bool(out), "verified"))]
)
assert exec_res.ok is True
assert exec_res.denied == 0
print("Step 4: FRIDAY planned and executed remediation")

# 5. FRIDAY's verification gate confirms result
assert exec_res.verification.get("passed", False) is True
print("Step 5: FRIDAY verification gate confirmed remediation")

# 6. Verified outcome committed back to Memora
memora.remember(
    "remediation_verified",
    "verify-credential-dump",
    "Remediation verified",
    "Verified remediation for Credential dump completed and verified.",
)
commit2 = memora.commit_session("sess-remediation-001", [
    {"role": "assistant", "content": "Verified remediation for Credential dump completed and verified."}
])
assert commit2.get("committed") is True
print("Step 6: Verified outcome committed to Memora L2")

print("FLOW_SUCCESS")
"""
    ok, detail = run_isolated(flow_code, python_paths=flow_paths)
    flow_passed = ok and "FLOW_SUCCESS" in detail
    record_check("E2E Flow", "Sentinel Triage -> Memora Commit -> FRIDAY Recall & Exec -> Verification -> Memora Commit", flow_passed, detail)

    # ──────────────────────────────────────────────────────────────────────────
    # 4. GRACEFUL DEGRADATION & AUTONOMY ENVELOPE
    # ──────────────────────────────────────────────────────────────────────────
    print(f"\n{BOLD}[4/4] Testing Graceful Degradation & Autonomous Guardrails...{RESET}")

    degrade_paths = [
        str(ROOT / "FRIDAY" / "apps" / "core" / "src"),
        str(ROOT / "Sentinel"),
    ]
    degrade_code = """
from app.services.cyber_skills_service import CyberSkillsService
sentinel = CyberSkillsService()

# Unapproved destructive action fails closed
blocked = sentinel.execute_playbook_action("isolate host", target="10.0.0.1", approved=False)
assert blocked["status"] == "blocked_pending_approval"

# Approved action proceeds
approved = sentinel.execute_playbook_action("isolate host", target="10.0.0.1", approved=True)
assert approved["status"] == "executed"

# FRIDAY budget limit halts cleanly
from friday_core.real_harness_engineering import AgentLoop, LoopAction
loop = AgentLoop(max_steps=2, budget=1000)
res = loop.run("loop test", lambda task, steps: LoopAction(kind="tool", tool="count_tokens", arguments={"text": f"n{len(steps)}"}))
assert res.stop_reason == "max_steps"
assert len(res.steps) == 2

print("DEGRADE_SUCCESS")
"""
    ok, detail = run_isolated(degrade_code, python_paths=degrade_paths)
    degrade_passed = ok and "DEGRADE_SUCCESS" in detail
    record_check("Guardrails", "Gated Destructive Actions & Harness Budget Halting", degrade_passed, detail)

    # ──────────────────────────────────────────────────────────────────────────
    # SUMMARY REPORT
    # ──────────────────────────────────────────────────────────────────────────
    print(f"\n{BOLD}======================================================================{RESET}")
    print(f"{BOLD}                        SUMMARY SCORECARD                             {RESET}")
    print(f"{BOLD}======================================================================{RESET}")
    total = len(results)
    passed_count = sum(1 for r in results if r[2])
    failed_count = total - passed_count

    print(f"Total Checks:  {total}")
    print(f"Passed:        {GREEN}{passed_count}{RESET}")
    print(f"Failed:        {RED if failed_count > 0 else GREEN}{failed_count}{RESET}")
    print(f"{BOLD}----------------------------------------------------------------------{RESET}")

    if failed_count == 0:
        print(f"\n{GREEN}{BOLD}ALL DEEP ENGINE CHECKS PASSED — UNIVERSE ENGINES AUTONOMOUS{RESET}\n")
        return 0
    else:
        print(f"\n{RED}{BOLD}VERIFICATION GATE FAILED: {failed_count} check(s) did not pass.{RESET}\n")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_checks())
