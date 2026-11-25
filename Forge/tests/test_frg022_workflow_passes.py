"""TASK-FRG-022: Reality Checker + AI Code Auditor as workflow passes.

Pins the two adopted Agency roles (msitarzewski/agency-agents, MIT) as
deterministic Forge passes, coordinated by the Agents Orchestrator:

  * Reality Checker — default NEEDS_WORK; READY only on overwhelming
    proof (every spec item evidenced, tests green, claims cross-checked
    against real files); automatic-fail triggers for failing tests,
    missing claimed files, unevidenced spec items, mismatched test
    numbers, and fantasy claims.
  * AI Code Auditor — hardcoded secrets (CWE-798), client-exposed env
    prefixes, service_role in client code, RLS holes (CWE-862/863),
    prompt-injection sinks (CWE-1426, LLM01/LLM06); CWE-mapped findings
    worst-first, stable fingerprints, scan/fix/rescan diff. Never prints
    a raw secret value; the documented-safe patterns stay silent.
  * Agents Orchestrator — audit gate, then reality gate, then ship;
    max 3 attempts before escalation; fail-closed.

Hermetic: stdlib + pytest only. No DB, no network, no server.

Secret hygiene: every fixture secret below is built at runtime from short
fragments (``_k(*parts)``) so no key-shaped literal is committed to the
repo — Gitleaks scans committed text, not runtime values. The planted
values are synthetic fixtures, never real credentials.
"""

from __future__ import annotations

from workflow_passes.ai_code_auditor import AICodeAuditor
from workflow_passes.orchestrator import AgentsOrchestrator
from workflow_passes.reality_checker import (
    EvidenceItem,
    RealityChecker,
    ShipCandidate,
)


def _k(*parts: str) -> str:
    """Build a synthetic secret-shaped value from fragments at runtime."""
    return "".join(parts)


def _clean_candidate(**overrides) -> ShipCandidate:
    base = ShipCandidate(
        name="frg022-clean-ship",
        claim="Implemented the two workflow passes with tests.",
        spec=["Two named passes exist", "Coordinated by an orchestrator"],
        evidence=[
            EvidenceItem(
                kind="test_run",
                reference="pytest Forge/tests/test_frg022_workflow_passes.py",
                detail="all tests pass",
                passed=True,
                tests_passed=29,
                tests_total=29,
                spec_refs=(0, 1),
            ),
            EvidenceItem(
                kind="file",
                reference="Forge/workflow_passes/reality_checker.py",
                detail="Reality Checker pass",
                spec_refs=(0,),
            ),
            EvidenceItem(
                kind="file",
                reference="Forge/workflow_passes/orchestrator.py",
                detail="Agents Orchestrator coordination",
                spec_refs=(1,),
            ),
        ],
        files={
            "Forge/workflow_passes/reality_checker.py": "class RealityChecker: ...\n",
            "Forge/workflow_passes/ai_code_auditor.py": "class AICodeAuditor: ...\n",
            "Forge/workflow_passes/orchestrator.py": "class AgentsOrchestrator: ...\n",
        },
        claimed_files=[
            "Forge/workflow_passes/reality_checker.py",
            "Forge/workflow_passes/ai_code_auditor.py",
            "Forge/workflow_passes/orchestrator.py",
        ],
        claimed_tests_passed=29,
        claimed_tests_total=29,
        revision_cycles=0,
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


# ---------------------------------------------------------------------------
# Reality Checker
# ---------------------------------------------------------------------------


def test_reality_clean_candidate_is_ready_first_pass_capped_at_b():
    report = RealityChecker().check(_clean_candidate())
    assert report.verdict == "READY"
    assert report.rating == "B"  # first pass: capped, per the role
    assert report.overwhelming_proof is True
    assert report.blockers == []
    assert any(i.code == "first-pass" for i in report.issues)


def test_reality_revised_candidate_reaches_b_plus():
    report = RealityChecker().check(_clean_candidate(revision_cycles=1))
    assert report.verdict == "READY"
    assert report.rating == "B+"


def test_reality_no_evidence_is_needs_work():
    report = RealityChecker().check(_clean_candidate(evidence=[]))
    assert report.verdict == "NEEDS_WORK"
    assert report.rating == "C+"
    assert any(i.code == "no-evidence" for i in report.blockers)


def test_reality_failing_tests_are_automatic_fail():
    candidate = _clean_candidate(
        evidence=[
            EvidenceItem(
                kind="test_run",
                reference="pytest Forge/tests/test_frg022_workflow_passes.py",
                detail="3 failures",
                passed=False,
                tests_passed=22,
                tests_total=25,
                spec_refs=(0, 1),
            )
        ]
    )
    report = RealityChecker().check(candidate)
    assert report.verdict == "NEEDS_WORK"
    assert any(i.code == "failing-tests" for i in report.blockers)


def test_reality_missing_claimed_file_blocks():
    candidate = _clean_candidate(
        claimed_files=["Forge/workflow_passes/reality_checker.py", "Forge/workflow_passes/nope.py"]
    )
    report = RealityChecker().check(candidate)
    assert report.verdict == "NEEDS_WORK"
    assert any(
        i.code == "claim-not-in-file" and "nope.py" in i.message for i in report.blockers
    )


def test_reality_empty_claimed_file_blocks():
    candidate = _clean_candidate(
        files={"Forge/workflow_passes/reality_checker.py": "   \n"},
        claimed_files=["Forge/workflow_passes/reality_checker.py"],
    )
    report = RealityChecker().check(candidate)
    assert report.verdict == "NEEDS_WORK"
    assert any(i.code == "claim-not-in-file" for i in report.blockers)


def test_reality_spec_item_without_evidence_blocks():
    candidate = _clean_candidate(
        evidence=[
            EvidenceItem(
                kind="test_run",
                reference="pytest",
                detail="green",
                passed=True,
                tests_passed=29,
                tests_total=29,
                spec_refs=(0,),
            )
        ]
    )
    report = RealityChecker().check(candidate)
    assert report.verdict == "NEEDS_WORK"
    assert any(i.code == "spec-unevidenced" for i in report.blockers)
    assert report.spec_compliance[1].evidenced is False
    assert report.spec_compliance[0].evidenced is True


def test_reality_claimed_test_numbers_must_match_evidence():
    report = RealityChecker().check(
        _clean_candidate(claimed_tests_passed=24, claimed_tests_total=25)
    )
    assert report.verdict == "NEEDS_WORK"
    assert any(i.code == "claim-test-mismatch" for i in report.blockers)


def test_reality_fantasy_claim_without_proof_blocks():
    candidate = _clean_candidate(
        claim="Perfect implementation, zero issues found, 98/100, production ready!",
        evidence=[],
    )
    report = RealityChecker().check(candidate)
    assert report.verdict == "NEEDS_WORK"
    assert any(i.code == "fantasy-claim" for i in report.blockers)


def test_reality_fantasy_claim_with_overwhelming_proof_is_warning_only():
    candidate = _clean_candidate(
        claim="All green, zero issues found in the final scan."
    )
    report = RealityChecker().check(candidate)
    assert report.verdict == "READY"
    assert any(i.code == "fantasy-claim" and i.severity == "warning" for i in report.issues)


# ---------------------------------------------------------------------------
# AI Code Auditor
# ---------------------------------------------------------------------------


def test_auditor_hardcoded_key_is_critical_in_client_code():
    key = _k("sk-", "live-", "a1b2c3d4e5f6a7b8")
    files = {"app/page.tsx": f'"use client";\nconst openai = new OpenAI({{ apiKey: "{key}" }});\n'}
    report = AICodeAuditor().audit(files, client_reachable={"app/page.tsx"})
    assert len(report.findings) == 1
    finding = report.findings[0]
    assert finding.severity == "critical"
    assert finding.cwe == "CWE-798"
    assert finding.category == "hardcoded-secret"
    assert finding.line == 2
    # The raw value never travels in any output.
    assert key not in finding.render()
    assert key not in finding.preview
    assert "ROTATE" in finding.fix


def test_auditor_hardcoded_key_is_high_in_server_code():
    key = _k("AKIA", "IOSFODNN7", "EXAMPLE")
    files = {"server.py": f'aws_key = "{key}"\n'}
    report = AICodeAuditor().audit(files)
    assert len(report.findings) == 1
    assert report.findings[0].severity == "high"
    assert report.findings[0].cwe == "CWE-798"
    assert key not in report.findings[0].render()


def test_auditor_github_token_and_private_key_block():
    token = _k("ghp_", "a1b2c3d4e5f6a7b8c9d0e1f2a3b4")
    header = _k("-----BEGIN ", "RSA PRIVATE KEY-----")
    files = {
        "deploy.sh": f'export TOKEN="{token}"\n',
        "key.pem": header + "\nMIIEowIBAAKCAQEA\n",
    }
    report = AICodeAuditor().audit(files)
    assert {f.category for f in report.findings} == {"hardcoded-secret"}
    assert token not in "\n".join(f.render() for f in report.findings)


def test_auditor_env_read_and_placeholder_are_silent():
    files = {
        "server.py": (
            'import os\napi_key = os.environ["OPENAI_API_KEY"]\n'
            'other = os.getenv("DB_PASSWORD", "changeme-xxx")\n'
        ),
        "config.py": 'api_key = "xxx-placeholder-value"\n',
    }
    assert AICodeAuditor().audit(files).findings == []


def test_auditor_generic_secret_literal_fires():
    files = {"app.py": 'api_key = "hunter2-secret-value"\n'}
    report = AICodeAuditor().audit(files)
    assert len(report.findings) == 1
    assert report.findings[0].category == "hardcoded-secret"
    assert "hunter2-secret-value" not in report.findings[0].render()


def test_auditor_client_env_prefix_secret_fires_but_anon_does_not():
    files = {
        "app/page.tsx": 'const key = process.env.NEXT_PUBLIC_OPENAI_KEY;\n',
        "app/lib/supabase.ts": 'const anon = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;\n',
        "app/vite.ts": 'const key = import.meta.env.VITE_STRIPE_SECRET;\n',
    }
    report = AICodeAuditor().audit(files)
    flagged = {f.path for f in report.findings}
    assert flagged == {"app/page.tsx", "app/vite.ts"}
    assert all(f.category == "client-secret" for f in report.findings)


def test_auditor_service_role_in_client_code_is_critical():
    files = {"app/lib/supabase.ts": "import { createClient } from '@supabase/supabase-js';\nconst key = 'service_role';\n"}
    report = AICodeAuditor().audit(files, client_reachable={"app/lib/supabase.ts"})
    assert len(report.findings) == 1
    assert report.findings[0].severity == "critical"
    assert report.findings[0].category == "service-role-client"
    # Same content in server-only code does not fire.
    assert AICodeAuditor().audit(files).findings == []


def test_auditor_rls_using_true_and_user_metadata():
    files = {
        "migrations/0002.sql": (
            "alter table public.orders enable row level security;\n"
            'create policy "read" on public.orders for select using ( true );\n'
        ),
        "policies.sql": (
            "create policy admin_only on public.docs for select "
            "using (auth.jwt() -> 'user_metadata' ->> 'role' = 'admin');\n"
        ),
    }
    report = AICodeAuditor().audit(files)
    by_category = {f.category for f in report.findings}
    assert by_category == {"rls-using-true", "user-metadata-auth"}
    assert all(f.severity == "high" for f in report.findings)


def test_auditor_missing_rls_fires_but_enabled_rls_does_not():
    bare = {"migrations/0001.sql": "create table public.profiles ( id uuid primary key, email text );\n"}
    report = AICodeAuditor().audit(bare)
    assert len(report.findings) == 1
    assert report.findings[0].category == "rls-missing"
    assert report.findings[0].confidence == "medium"
    guarded = {
        "migrations/0001.sql": (
            "create table public.profiles ( id uuid primary key, email text );\n"
            "alter table public.profiles enable row level security;\n"
            "create policy \"owner reads own\" on public.profiles for select using ( auth.uid() = user_id );\n"
        )
    }
    assert AICodeAuditor().audit(guarded).findings == []


def test_auditor_prompt_injection_system_prompt_medium():
    files = {
        "app/api/agent/route.ts": (
            "export async function POST(req) {\n"
            "  const { instruction } = await req.json();\n"
            "  await openai.chat.completions.create({\n"
            '    model: "gpt-4o",\n'
            '    messages: [{ role: "system", content: `You are support. ${instruction}` }],\n'
            "  });\n"
            "}\n"
        )
    }
    report = AICodeAuditor().audit(files)
    assert len(report.findings) == 1
    finding = report.findings[0]
    assert finding.category == "prompt-injection"
    assert finding.severity == "medium"
    assert finding.cwe == "CWE-1426"
    assert finding.confidence == "medium"


def test_auditor_prompt_injection_with_tools_is_high():
    files = {
        "app/api/agent/route.ts": (
            "export async function POST(req) {\n"
            "  const { instruction } = await req.json();\n"
            "  await openai.chat.completions.create({\n"
            '    model: "gpt-4o",\n'
            '    messages: [{ role: "system", content: `You are support. ${instruction}` }],\n'
            "    tools: [{ type: \"function\", function: { name: \"issueRefund\" } }],\n"
            "  });\n"
            "}\n"
        )
    }
    report = AICodeAuditor().audit(files)
    assert len(report.findings) == 1
    assert report.findings[0].severity == "high"


def test_auditor_safe_user_role_pattern_stays_silent():
    files = {
        "app/api/agent/route.ts": (
            "export async function POST(req) {\n"
            "  const { userMessage } = await req.json();\n"
            "  await openai.chat.completions.create({\n"
            '    model: "gpt-4o",\n'
            '    messages: [\n'
            '      { role: "system", content: "You are support." },\n'
            "      { role: \"user\", content: userMessage },\n"
            "    ],\n"
            "  });\n"
            "}\n"
        )
    }
    assert AICodeAuditor().audit(files).findings == []


def test_auditor_rescan_diff_tracks_resolved_and_new():
    auditor = AICodeAuditor()
    key = _k("sk-", "live-", "a1b2c3d4e5f6a7b8")
    before = auditor.audit({"a.py": f'api_key = "{key}"\n', "b.py": "x = 1\n"})
    after = auditor.audit({"a.py": 'import os\napi_key = os.environ["K"]\n', "b.py": 'token = "hunter2-secret-value"\n'})
    diff = after.rescan_diff(before)
    assert len(diff.resolved) == 1
    assert diff.resolved[0].path == "a.py"
    assert len(diff.newly_introduced) == 1
    assert diff.newly_introduced[0].path == "b.py"
    assert diff.still_present == []


def test_auditor_fingerprints_stable_and_worst_first():
    auditor = AICodeAuditor()
    key = _k("sk-", "live-", "a1b2c3d4e5f6a7b8")
    files = {
        "a.py": 'x = "using ( true )"\n',  # RLS rule is text-based: fires
        "b.py": f'api_key = "{key}"\n',
    }
    first = auditor.audit(files, client_reachable={"b.py"})
    second = auditor.audit(files, client_reachable={"b.py"})
    assert [f.fingerprint for f in first.findings] == [f.fingerprint for f in second.findings]
    severities = [f.severity for f in first.findings]
    assert severities == sorted(severities, key=lambda s: {"critical": 0, "high": 1, "medium": 2, "low": 3}[s])


# ---------------------------------------------------------------------------
# Agents Orchestrator
# ---------------------------------------------------------------------------


def _dirty_files() -> dict[str, str]:
    key = _k("sk-", "live-", "a1b2c3d4e5f6a7b8")
    return {"app/page.tsx": f'"use client";\nconst openai = new OpenAI({{ apiKey: "{key}" }});\n'}


def test_orchestrator_dirty_ship_blocked_at_audit():
    verdict = AgentsOrchestrator().run(
        _clean_candidate(), _dirty_files(), client_reachable={"app/page.tsx"}
    )
    assert verdict.status == "BLOCKED"
    assert verdict.phase == "audit"
    assert verdict.reality is None  # no advancement past a failed gate
    assert verdict.audit is not None and verdict.audit.blocking
    assert "Revise and resubmit (attempt 1/3)" in verdict.next_action


def test_orchestrator_audit_clean_but_unproven_blocked_at_reality():
    candidate = _clean_candidate(evidence=[])
    verdict = AgentsOrchestrator().run(candidate, {"clean.py": "x = 1\n"})
    assert verdict.status == "BLOCKED"
    assert verdict.phase == "reality"
    assert verdict.audit is not None and verdict.audit.findings == []
    assert verdict.reality is not None and verdict.reality.verdict == "NEEDS_WORK"


def test_orchestrator_clean_ship_is_ready():
    verdict = AgentsOrchestrator().run(_clean_candidate(), {"clean.py": "x = 1\n"})
    assert verdict.status == "READY_TO_SHIP"
    assert verdict.phase == "complete"
    assert verdict.ship_blocked is False
    assert verdict.audit is not None and verdict.reality is not None


def test_orchestrator_escalates_after_max_attempts():
    verdict = AgentsOrchestrator().run(
        _clean_candidate(evidence=[]), {"clean.py": "x = 1\n"}, attempt=3
    )
    assert verdict.status == "ESCALATED"
    assert "Escalate" in verdict.next_action


def test_orchestrator_status_report_names_phases_and_blockers():
    verdict = AgentsOrchestrator().run(
        _clean_candidate(), _dirty_files(), client_reachable={"app/page.tsx"}
    )
    report = verdict.status_report()
    assert "frg022-clean-ship" in report
    assert "BLOCKED" in report
    assert "Audit Pass" in report
    assert "CWE-798" in report
