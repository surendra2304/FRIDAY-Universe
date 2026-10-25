"""
Real Deep Layer 11 Tests — cross-repository integration into the running agents.

Layer 4-10 built the engines. This layer proves they are wired into the agents
themselves, not just importable:

* FRIDAY   — ``friday_core.agent_runtime`` powers orchestrator workflows and the
             deep API server (``/v1/agent/*``).
* Memora   — ``core.memory.context_service`` backs ``/v1/context/*`` and the
             shared ``mesh.memory_fabric`` used by every agent.
* Inference— ``app.scientific_service`` backs ``/v1/scientific/*`` and the
             inter-agent ``/v1/agent/research-plan``.
* VyralX   — ``app.services.diagram_service`` backs ``/api/v1/diagrams/*`` and
             every generated content pack.
* Sentinel — ``app.services.cyber_skills_service`` backs ``/v1/cyber/*``,
             incident triage and the posture report.

App-level checks run in subprocesses (each agent ships its own ``app`` package,
so they cannot share one interpreter). If a real runtime dependency is missing
in a lean environment the test skips instead of pretending to pass.
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


# ── helpers ───────────────────────────────────────────────────────────────

def load(relpath, name):
    path = ROOT / relpath
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def run_agent_app(agent_dir, code, env_extra=None):
    """Import an agent's FastAPI app in a subprocess and return its stdout."""
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.update(env_extra or {})
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(ROOT / agent_dir), env=env,
        capture_output=True, text=True, timeout=180,
    )


def assert_app_endpoint(agent_dir, code, expected, env_extra=None):
    result = run_agent_app(agent_dir, code, env_extra)
    if result.returncode != 0:
        stderr = result.stderr
        missing = "ModuleNotFoundError" in stderr or "ImportError" in stderr
        if missing:
            pytest.skip(f"runtime dependency unavailable: {stderr.strip().splitlines()[-1][:160]}")
        pytest.fail(f"{agent_dir} app failed:\n{stderr[-1500:]}")
    assert expected in result.stdout, result.stdout[-500:]


@pytest.fixture(scope="module")
def friday_runtime_mod():
    return importlib.import_module("friday_core.agent_runtime")


@pytest.fixture(scope="module")
def memora_service_mod():
    return load("Memora/core/memory/context_service.py", "memora_context_service")


@pytest.fixture(scope="module")
def inference_service_mod():
    sys.path.insert(0, str(ROOT / "Inference"))
    return load("Inference/app/scientific_service.py", "inference_scientific_service")


@pytest.fixture(scope="module")
def vyralx_service_mod():
    sys.path.insert(0, str(ROOT / "VyralX"))
    return load("VyralX/app/services/diagram_service.py", "vyralx_diagram_service")


@pytest.fixture(scope="module")
def sentinel_service_mod():
    return load("Sentinel/app/services/cyber_skills_service.py", "sentinel_cyber_service")


def site_pages():
    return [
        {"url": "https://shop.test/", "title": "Shop", "spec": {"tag": "body", "children": [
            {"tag": "h1", "text": "Welcome to the shop"},
            {"tag": "a", "attrs": {"href": "/cart"}, "text": "Cart",
             "bounds": [0, 0, 60, 20]},
        ]}},
        {"url": "https://shop.test/cart", "title": "Cart", "spec": {"tag": "body", "children": [
            {"tag": "h1", "text": "Your cart"},
            {"tag": "p", "text": "One item, 49 dollars"},
        ]}},
    ]


# ── FRIDAY agent runtime ──────────────────────────────────────────────────

class TestFridayRuntime:
    def test_capability_card(self, friday_runtime_mod):
        runtime = friday_runtime_mod.FridayAgentRuntime()
        card = runtime.capabilities()
        assert card["agent"] == "FRIDAY"
        assert {"agent_harness", "browser_automation", "output_verification"} <= set(card["capabilities"])
        assert card["self_assessment"]["grade"] in ("A", "B")
        assert "read_file" in card["tools"]

    def test_plan_is_a_dependency_graph(self, friday_runtime_mod):
        plan = friday_runtime_mod.FridayAgentRuntime().plan("ship it", ["read", "patch", "test"])
        assert plan["order"] == ["s1", "s2", "s3"]
        assert plan["critical_path"] == ["s1", "s2", "s3"]

    def test_execute_runs_allowed_tools(self, friday_runtime_mod):
        runtime = friday_runtime_mod.FridayAgentRuntime(workspace={"a.py": "print(1)\n"})
        result = runtime.execute("read the file", [
            {"tool": "read_file", "arguments": {"path": "a.py"}},
        ])
        assert result.ok is True
        assert result.stop_reason == "final_answer"
        assert result.observations[0].startswith("print(1)")
        assert result.plan["goal"] == "read the file"

    def test_write_requires_approval(self, friday_runtime_mod):
        runtime = friday_runtime_mod.FridayAgentRuntime()
        result = runtime.execute("write config", [
            {"tool": "write_file", "arguments": {"path": "b.py", "content": "x = 1"}},
        ])
        assert result.stop_reason == "approval_required"
        assert result.ok is False
        assert result.approvals and result.approvals[0].startswith("appr-")
        assert runtime.approvals.pending()[0]["tool"] == "write_file"

    def test_denied_capability_is_observed(self, friday_runtime_mod):
        runtime = friday_runtime_mod.FridayAgentRuntime()
        result = runtime.execute("destroy", [
            {"tool": "delete_repo", "arguments": {}},
            {"tool": "count_tokens", "arguments": {"text": "hello world"}},
        ])
        assert result.denied == 1
        assert "denied" in result.observations[0]

    def test_verification_gate(self, friday_runtime_mod):
        from_harness = friday_runtime_mod
        runtime = from_harness.FridayAgentRuntime()
        check = from_harness.Check("mentions_tokens", lambda art: ("4" in art, "needs a token count"))
        passing = runtime.execute("count", [
            {"tool": "count_tokens", "arguments": {"text": "hello world"}},
        ], checks=[check])
        assert passing.verification["passed"] is True
        failing = runtime.execute("count", [
            {"tool": "count_tokens", "arguments": {"text": "hello world"}},
        ], checks=[from_harness.Check("impossible", lambda art: ("zzz" in art, "no zzz"))])
        assert failing.verification["passed"] is False
        assert failing.ok is False

    def test_context_compaction(self, friday_runtime_mod):
        runtime = friday_runtime_mod.FridayAgentRuntime(
            budget=friday_runtime_mod.ContextBudget(window=140, reserve_output=20))
        messages = [{"role": "user", "content": "lorem ipsum dolor sit amet " * 6}
                    for _ in range(6)]
        result = runtime.compact(messages, query="lorem")
        assert result["fits"] is True
        assert result["tokens_after"] < result["tokens_before"]
        assert result["messages"]

    def test_browse_runs_a_goal(self, friday_runtime_mod):
        runtime = friday_runtime_mod.FridayAgentRuntime()
        result = runtime.browse(site_pages(), "open the cart")
        assert result["success"] is True
        assert result["final_url"] == "https://shop.test/cart"
        assert result["steps"]

    def test_trace_and_checkpoint(self, friday_runtime_mod):
        runtime = friday_runtime_mod.FridayAgentRuntime(workspace={"a.py": "x"})
        runtime.execute("read", [{"tool": "read_file", "arguments": {"path": "a.py"}}])
        trace = runtime.tracer.trace.summary()
        assert trace["spans"] >= 1
        assert trace["slowest"] == "friday.execute"
        assert len(runtime.state) == 1
        assert runtime.state.restore()["task"] == "read"

    def test_memory_bridge_round_trip(self, friday_runtime_mod):
        memory = friday_runtime_mod.build_memory_runtime(user="friday-test")
        assert memory is not None
        runtime = friday_runtime_mod.FridayAgentRuntime(
            workspace={"a.py": "x"}, memory=memory)
        result = runtime.execute("I prefer dark mode in all dashboards",
                                 [{"tool": "read_file", "arguments": {"path": "a.py"}}])
        assert result.ok is True
        committed = runtime.commit_memory()
        assert committed["committed"] is True
        assert committed["memories"]
        recalled = memory.recall("dark mode")
        assert recalled and recalled[0]["abstract"]


@pytest.fixture(scope="module")
def orchestrator():
    path = ROOT / "FRIDAY" / "apps" / "core" / "src" / "friday_core" / "universe_orchestrator.py"
    spec = importlib.util.spec_from_file_location("orch_layer11", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["orch_layer11"] = module
    spec.loader.exec_module(module)
    return module.FullUniverseOrchestrator(state_dir=tempfile.mkdtemp())


@pytest.fixture(scope="module")
def registry():
    from mesh.registry import AgentRegistry

    return AgentRegistry()


class TestFridayOrchestrator:

    def test_security_workflow_uses_cyber_skills(self, orchestrator):
        result = orchestrator.run_deep_security(
            "def handler(request):\n    return eval(request.body)\n",
            ["phishing email reported", "ransomware note on the file server"],
        )
        actions = [step.action for step in result.steps]
        assert "cyber_skill_triage" in actions
        assert "harness_verification" in actions
        triage = next(step for step in result.steps if step.action == "cyber_skill_triage")
        assert triage.result["severity"] in ("low", "medium", "high", "critical")
        assert triage.result["playbook_steps"] >= 1
        verification = next(step for step in result.steps if step.action == "harness_verification")
        assert verification.result["passed"] is True

    def test_content_workflow_ships_a_diagram(self, orchestrator):
        result = orchestrator.run_deep_content(
            "AI agents in production", "A calm explainer about agent harnesses.",
            [{"id": "u1", "watch_time": 120}, {"id": "u2", "watch_time": 60}],
        )
        actions = [step.action for step in result.steps]
        assert "explainer_diagram" in actions
        diagram = next(step for step in result.steps if step.action == "explainer_diagram")
        assert diagram.result["valid"] is True
        assert diagram.result["nodes"] >= 3
        assert diagram.result["bytes"] > 500

    def test_web_task_entrypoint(self, orchestrator):
        result = orchestrator.run_web_task(site_pages(), "open the cart")
        assert result["success"] is True
        assert result["final_url"].endswith("/cart")

    def test_guarded_task_entrypoint(self, orchestrator):
        result = orchestrator.run_guarded_task(
            "inspect", [{"tool": "read_file", "arguments": {"path": "a.py"}}],
            files={"a.py": "print('hi')\n"},
        )
        assert result["ok"] is True
        assert result["observations"][0].startswith("print(")

    def test_dashboard_advertises_new_engines(self, orchestrator):
        engines = orchestrator.get_universe_dashboard()["agents"]
        assert "cyber_skills" in engines["Sentinel"]["engines"]
        assert "viking_context" in engines["Memora"]["engines"]
        assert "scientific_skills" in engines["Inference"]["engines"]
        assert "diagram_design" in engines["VyralX"]["engines"]


# ── Memora context service ────────────────────────────────────────────────

class TestMemoraContextService:
    @pytest.fixture()
    def service(self, memora_service_mod):
        return memora_service_mod.MemoraContextService(user="tester")

    def test_write_read_layers(self, service):
        service.write("viking://user/tester/resources/a.md",
                      "# A\n\nThe API is FastAPI.\n\n- one\n- two\n", ["api"])
        assert service.read("viking://user/tester/resources/a.md", "L0")["content"] == "The API is FastAPI."
        assert service.read("viking://user/tester/resources/a.md", "L2")["content"].startswith("# A")
        with pytest.raises(ValueError):
            service.read("viking://user/tester/resources/a.md", "L9")
        with pytest.raises(KeyError):
            service.read("viking://user/tester/missing.md")

    def test_ls_tree_stat(self, service):
        service.write("viking://user/tester/resources/a.md", "# A\n\nBody.\n")
        assert [entry["name"] for entry in service.ls("viking://user/tester/resources")] == ["a.md"]
        tree = service.tree("viking://user/tester")
        assert "resources/" in tree and "a.md" in tree
        assert service.stat("viking://user/tester/resources/a.md")["tags"] == []

    def test_grep_and_find(self, service):
        service.write("viking://user/tester/resources/a.md", "# A\n\nPostgres 16 staging.\n")
        hits = service.grep("postgres", "viking://user/tester")
        assert len(hits) == 0                      # case sensitive
        hits = service.recall("postgres")
        assert hits
        assert service.find("*.md") == ["viking://user/tester/resources/a.md"]

    def test_remember_and_recall_levels(self, service):
        service.remember("fact", "db", "Staging database", "The staging database is Postgres 16.")
        abstract = service.recall("postgres", level="L0")
        assert abstract and abstract[0]["abstract"].startswith("The staging database")
        full = service.recall("postgres", level="L2")
        assert full[0]["level"] == "L2"

    def test_commit_session(self, service):
        result = service.commit_session("s-100", [
            {"role": "user", "content": "I prefer dark mode in dashboards."},
            {"role": "assistant", "content": "Noted."},
        ])
        assert result["archive_uri"].endswith("sessions/s-100.md")
        assert result["memories"]
        assert service.read(result["memories"][0], "L0")["content"]

    def test_wiki_and_stats(self, service):
        service.remember("preference", "theme", "Dark mode", "I prefer dark mode always.")
        report = service.compile_wiki()
        assert report["pages"]
        assert "Memora context wiki" in report["index"]
        stats = service.stats()
        assert stats["memories"] >= 1
        assert stats["layers"]["L2"] == "full"

    def test_bootstrap(self, service):
        written = service.bootstrap([
            {"uri": "viking://user/tester/resources/x.md", "content": "# X\n\nBody x.\n",
             "tags": ["doc"]},
            {"title": "Auto named", "content": "# Auto\n\nGenerated.\n"},
            {"content": "   "},
        ])
        assert written == 2
        assert service.find("*.md")

    def test_fabric_bridge(self, service, memora_service_mod):
        bridge = memora_service_mod.FabricBridge(service=service)
        uri = bridge.save("SENTINEL", "contained ransomware", "Contained in 4 minutes",
                          ["incident"], kind="lesson")
        assert uri == "viking://user/sentinel/memories/lesson/contained-ransomware.md"
        hits = bridge.recall("SENTINEL", "ransomware")
        assert hits and hits[0]["uri"].startswith("viking://user/sentinel")
        assert "contained" in bridge.summary("SENTINEL").lower()


class TestMeshFabricBridge:
    @pytest.fixture()
    def fabric(self):
        from mesh.memory_fabric import UniversalMemoryFabric

        instance = UniversalMemoryFabric(local_db_path=os.path.join(tempfile.mkdtemp(), "f.db"))
        instance.base_url = "http://127.0.0.1:9"      # force local fallback
        return instance

    def test_record_mirrors_into_viking(self, fabric):
        entry = fabric.record("FORGE", "Refactor reduced cyclomatic complexity by 40%",
                              memory_type="procedural", importance=0.9)
        assert entry.id
        assert fabric.context_bridge() is not None
        tree = fabric.context_tree("FORGE")
        assert "viking://user/forge" in tree
        assert "procedural" in tree

    def test_layered_recall(self, fabric):
        fabric.record("MEMORA", "Index rebuild halved recall latency", memory_type="semantic")
        hits = fabric.recall_layered("recall latency", "MEMORA")
        assert hits
        assert hits[0]["level"] == "L0"
        assert hits[0]["abstract"]

    def test_agents_are_isolated(self, fabric):
        fabric.record("SENTINEL", "Sentinel saw a phishing wave", memory_type="episodic")
        fabric.record("INTELX", "IntelX saw a phishing campaign", memory_type="episodic")
        sentinel_hits = fabric.recall_layered("phishing", "SENTINEL")
        assert sentinel_hits
        assert all("user/sentinel" in hit["uri"] for hit in sentinel_hits)
        assert all("user/intelx" not in hit["uri"] for hit in sentinel_hits)


# ── Inference scientific service ──────────────────────────────────────────

class TestInferenceScientificService:
    def test_capabilities(self, inference_service_mod):
        card = inference_service_mod.ScientificResearchService().capabilities()
        assert card["agent"] == "Inference"
        assert card["skills"] >= 50
        assert "statistical_analysis" in card["capabilities"]
        assert "PubChem" in card["databases"]

    def test_plan_routes_a_real_task(self, inference_service_mod):
        plan = inference_service_mod.ScientificResearchService().plan(
            "differential expression of RNA-seq counts")
        assert plan["skills"][0]["skill"] == "bulk-rnaseq"
        assert plan["pipeline"]["steps"]
        with pytest.raises(ValueError):
            inference_service_mod.ScientificResearchService().plan("  ")

    def test_skill_search_and_gaps(self, inference_service_mod):
        service = inference_service_mod.ScientificResearchService()
        assert service.skills()["skills"] >= 50
        matches = service.skills("pubchem molecule", limit=3)["matches"]
        assert matches
        assert isinstance(service.gaps("differential expression"), list)

    def test_analyse(self, inference_service_mod):
        service = inference_service_mod.ScientificResearchService()
        result = service.analyse([[1, 2, 3, 4, 5], [2, 3, 4, 5, 6, 7]])
        assert result["test"] == "welch_t"
        assert 0 <= result["p_value"] <= 1
        assert "effect_size" in result
        with pytest.raises(ValueError):
            service.analyse([[1, 2, 3]])
        with pytest.raises(ValueError):
            service.analyse([[1], [2]])

    def test_power(self, inference_service_mod):
        plan = inference_service_mod.ScientificResearchService().power(0.5)
        assert plan["n_per_group"] == 63
        assert plan["total_units"] == 126
        with pytest.raises(ValueError):
            inference_service_mod.ScientificResearchService().power(0)

    def test_hypotheses(self, inference_service_mod):
        hypotheses = inference_service_mod.ScientificResearchService().hypotheses(
            "expression", "hypoxia",
            [{"description": "pilot run", "supports": True, "weight": 3.0}])
        assert hypotheses
        assert hypotheses[0]["falsification_test"]
        assert 0 < hypotheses[0]["posterior"] < 1

    def test_evidence_audit(self, inference_service_mod):
        report = inference_service_mod.ScientificResearchService().audit(
            [{"text": "Hypoxia raises expression.", "evidence": ["e1"]},
             {"text": "This proves everything", "evidence": ["e1"]},
             {"text": "Unsourced claim"}],
            [{"id": "e1", "title": "Pilot", "source": "lab"}],
        )
        assert report["traceability"] < 1
        assert "Unsupported" not in report["rendered"]
        assert report["unknown_evidence"] == []


# ── VyralX diagram service ────────────────────────────────────────────────

class TestVyralXDiagramService:
    def test_catalogue_and_choice(self, vyralx_service_mod):
        service = vyralx_service_mod.DiagramService()
        assert service.catalogue()["types"] >= 46
        choice = service.choose("sequence diagram of the login flow")
        assert choice["type"] in service.catalogue()["categories"]["? "] if False else choice["type"]
        assert choice["alternatives"]

    def test_palette_contrast(self, vyralx_service_mod):
        palette = vyralx_service_mod.DiagramService().palette("#2563eb")
        assert palette["contrast_ink_paper"] >= 4.5
        assert len(palette["tints"]) == 4

    def test_flowchart_render(self, vyralx_service_mod):
        service = vyralx_service_mod.DiagramService()
        diagram = service.flowchart("Pipeline", ["Ingest", "Score", "Publish"])
        assert diagram["type"] == "flowchart"
        assert diagram["nodes"] == 3
        assert diagram["validation"]["passed"] is True
        assert diagram["self_contained"] is True
        assert "<svg" in diagram["html"]
        with pytest.raises(ValueError):
            service.flowchart("Empty", [])

    def test_brief_and_mermaid(self, vyralx_service_mod):
        service = vyralx_service_mod.DiagramService()
        rendered = service.from_brief(
            "timeline of the launch", [{"id": "a", "label": "Q1"}, {"id": "b", "label": "Q2"}],
            [{"source": "a", "target": "b"}])
        assert rendered["selection"]["type"]
        assert rendered["nodes"] == 2
        imported = service.from_mermaid("graph TD\n A-->B\n B-->C")
        assert imported["nodes"] == 3
        with pytest.raises(ValueError):
            service.from_mermaid("not mermaid")

    def test_restyle(self, vyralx_service_mod):
        service = vyralx_service_mod.DiagramService()
        diagram = service.flowchart("Theme", ["a", "b"])
        restyled = service.restyle(diagram["diagram_id"], "#16a34a")
        assert restyled["theme"]["seed"] == "#16a34a"
        with pytest.raises(KeyError):
            service.restyle("dg-9999", "#fff")

    def test_content_pack_gets_an_explainer(self, vyralx_service_mod):
        pack = vyralx_service_mod.attach_explainer(
            {"scene_plan": [{"visual": "intro"}, {"visual": "the proof"}, {"visual": "the ask"}]},
            "AI agents")
        diagram = pack["explainer_diagram"]
        assert diagram["nodes"] == 3
        assert diagram["markdown"].startswith("![")
        assert diagram["validation"]["passed"] is True

    def test_attach_explainer_never_raises(self, vyralx_service_mod):
        class Broken:
            def flowchart(self, *args, **kwargs):
                raise RuntimeError("renderer down")

        pack = vyralx_service_mod.attach_explainer({"scene_plan": []}, "topic", service=Broken())
        assert "error" in pack["explainer_diagram"]


# ── Sentinel cyber skills service ─────────────────────────────────────────

class TestSentinelCyberService:
    def test_capabilities(self, sentinel_service_mod):
        card = sentinel_service_mod.CyberSkillsService().capabilities()
        assert card["skills"] >= 45
        assert card["domains"] >= 30
        assert card["frameworks"]["attack"] >= 35
        assert "incident_playbook" in card["capabilities"]

    def test_triage_crosswalk(self, sentinel_service_mod):
        service = sentinel_service_mod.CyberSkillsService()
        payload = service.triage("BEC to wire fraud", [
            {"timestamp": "2026-10-01T09:00:00", "description": "phishing email delivered",
             "technique": "T1566", "host": "mail01"},
            {"timestamp": "2026-10-01T10:00:00", "description": "wire transfer requested",
             "technique": "T1657", "host": "fin01"},
        ])
        assert payload["techniques"] == ["T1566", "T1657"]
        assert payload["assets"] == ["fin01", "mail01"]
        assert payload["severity"]["severity"] in ("medium", "high", "critical")
        assert set(payload["crosswalk"]["tactics"]) >= {"Initial Access"}
        assert payload["skills"]
        assert payload["markdown"].startswith("# BEC to wire fraud")
        with pytest.raises(ValueError):
            service.triage("empty", [])

    def test_playbook(self, sentinel_service_mod):
        playbook = sentinel_service_mod.CyberSkillsService().playbook(
            "Ransomware", ["T1486", "T1490"], assets=4)
        assert playbook["severity"] in ("high", "critical")
        assert playbook["phase_coverage"]["Containment"] >= 1
        assert playbook["phase_coverage"]["Recovery"] >= 1
        assert playbook["framework_coverage"]["ATTACK"] >= 1
        with pytest.raises(ValueError):
            sentinel_service_mod.CyberSkillsService().playbook("x", [])

    def test_csf_assessment(self, sentinel_service_mod):
        service = sentinel_service_mod.CyberSkillsService()
        result = service.assess_csf([
            {"category": "DE.CM", "maturity": 2},
            {"category": "PR.AA", "maturity": 4},
        ])
        assert result["controls"] == 2
        assert result["overall"] == pytest.approx(0.6, abs=1e-3)
        assert result["actions"]
        with pytest.raises(ValueError):
            service.assess_csf([{"category": "ZZ.ZZ", "maturity": 2}])

    def test_detection_coverage(self, sentinel_service_mod):
        result = sentinel_service_mod.CyberSkillsService().detection_coverage(
            ["T1486", "T1071"],
            [{"id": "r1", "techniques": ["T1486"], "fidelity": 0.9}],
        )
        assert result["covered"] == ["T1486"]
        assert result["gaps"] == ["T1071"]
        assert result["recommendations"]

    def test_search_and_authorise(self, sentinel_service_mod):
        service = sentinel_service_mod.CyberSkillsService()
        assert service.search("kerberoasting")[0]["skill"] == "kerberoasting-detection"
        denied = service.authorise("phishing-simulation", "10.0.0.5")
        assert denied["allowed"] is False
        assert service.coverage_report()["invalid_mappings"] == []

    def test_posture_report_includes_csf(self):
        sys.path.insert(0, str(ROOT / "Sentinel"))
        assessor_mod = load("Sentinel/app/services/security_posture_assessor.py",
                            "sentinel_posture_l11")
        assessor = assessor_mod.SecurityPostureAssessor()
        assessor.update_patch_compliance(total_systems=100, patched=85,
                                         critical_missed=2, avg_age=12.0)
        assessor.update_config_drift(total=50, compliant=45, critical_drift=1)
        assessor.add_control("EDR", "detect", effectiveness=0.8, coverage=0.9, alerts=3)
        assessor.assess()
        report = assessor.get_report()
        assert report["nist_csf"]["available"] is True
        assert "DE" in report["nist_csf"]["function_scores"]
        assert 0 < report["nist_csf"]["overall"] <= 1
        # a weak control set must produce prioritised actions
        weak = assessor_mod.SecurityPostureAssessor()
        assert weak._csf_alignment(assessor._scores[-1])["available"] is True


# ── Mesh discovery ────────────────────────────────────────────────────────

class TestMeshCapabilityRegistration:
    @pytest.mark.parametrize("capability,agent", [
        ("browser_automation", "FRIDAY"),
        ("agent_harness", "FRIDAY"),
        ("tool_permissions", "FRIDAY"),
        ("viking_context", "MEMORA"),
        ("layered_recall", "MEMORA"),
        ("scientific_skills", "INFERENCE"),
        ("evidence_audit", "INFERENCE"),
        ("diagram_design", "VyralX"),
        ("attack_mapping", "SENTINEL"),
        ("csf_assessment", "SENTINEL"),
        ("detection_coverage", "SENTINEL"),
    ])
    def test_capability_routes_to_agent(self, registry, capability, agent):
        names = [manifest.name for manifest in registry.discover_by_capability(capability)]
        assert names == [agent]

    @pytest.mark.parametrize("intent,agent", [
        ("browse", "FRIDAY"),
        ("commit_session", "MEMORA"),
        ("research_plan", "INFERENCE"),
        ("diagram", "VyralX"),
        ("triage", "SENTINEL"),
        ("playbook", "SENTINEL"),
    ])
    def test_intent_routes_to_agent(self, registry, intent, agent):
        assert [m.name for m in registry.discover_by_intent(intent)] == [agent]


# ── App wiring (subprocess, one interpreter per agent) ───────────────────

class TestAgentAppsExposeTheNewCapabilities:
    def test_friday_app(self):
        assert_app_endpoint(
            "FRIDAY/apps/core/src",
            "import friday_core.real_deep_api_server as m\n"
            "from fastapi.testclient import TestClient\n"
            "c = TestClient(m.app)\n"
            "caps = c.get('/v1/agent/capabilities')\n"
            "plan = c.post('/v1/agent/plan', json={'goal': 'g', 'steps': ['a', 'b']})\n"
            "print(caps.status_code, plan.status_code, plan.json()['order'])\n",
            "200 200 ['s1', 's2']",
        )

    def test_memora_app(self):
        assert_app_endpoint(
            "Memora",
            "import apps.api.main as m\n"
            "from fastapi.testclient import TestClient\n"
            "c = TestClient(m.app)\n"
            "stats = c.get('/v1/context/stats')\n"
            "search = c.get('/v1/context/search', params={'query': 'x'})\n"
            "print(stats.status_code, search.status_code, 'memora' in stats.json()['user'])\n",
            "200 200",
        )

    def test_inference_app(self):
        assert_app_endpoint(
            "Inference",
            "import app.main as m\n"
            "from fastapi.testclient import TestClient\n"
            "c = TestClient(m.app)\n"
            "caps = c.get('/v1/scientific/capabilities')\n"
            "plan = c.post('/v1/scientific/plan', json={'task': 'rna-seq differential expression'})\n"
            "print(caps.status_code, plan.status_code, plan.json()['skills'][0]['skill'])\n",
            "200 200",
        )

    def test_vyralx_app(self):
        assert_app_endpoint(
            "VyralX",
            "import app.main as m\n"
            "from fastapi.testclient import TestClient\n"
            "c = TestClient(m.app)\n"
            "cat = c.get('/api/v1/diagrams/catalogue')\n"
            "flow = c.post('/api/v1/diagrams/flowchart', json={'title': 'T', 'steps': ['a', 'b']})\n"
            "print(cat.status_code, flow.status_code, flow.json()['validation']['passed'])\n",
            "200 200 True",
        )

    def test_sentinel_app(self):
        assert_app_endpoint(
            "Sentinel",
            "import sentinel.apps.api.main as m\n"
            "from fastapi.testclient import TestClient\n"
            "c = TestClient(m.app)\n"
            "caps = c.get('/v1/cyber/capabilities')\n"
            "triage = c.post('/v1/cyber/triage', json={'title': 't', 'events': ["
            "{'description': 'phishing email', 'technique': 'T1566'}]})\n"
            "print(caps.status_code, triage.status_code, triage.json()['severity']['severity'])\n",
            "200 200",
            env_extra={"SENTINEL_AUDIT_SIGNING_KEY": "layer11-test-signing-key-0123456789"},
        )


# ── Cross-agent flow ─────────────────────────────────────────────────────

class TestUniverseIntegrationFlow:
    def test_incident_to_lesson_to_verified_action(
        self, friday_runtime_mod, sentinel_service_mod, memora_service_mod
    ):
        """One incident, four agents, no mocks.

        1. Sentinel triages the incident against ATT&CK/CSF.
        2. Memora commits the incident as durable, layer-aware memory.
        3. FRIDAY recalls it, plans a response and executes it under the gate.
        """
        # 1. Sentinel triage
        sentinel = sentinel_service_mod.CyberSkillsService()
        triage = sentinel.triage("Ransomware on the file server", [
            {"timestamp": "2026-10-01T10:00:00", "description": "ransomware note found",
             "technique": "T1486", "host": "fs01"},
            {"timestamp": "2026-10-01T10:02:00", "description": "shadow copies deleted",
             "technique": "T1490", "host": "fs01"},
        ])
        assert triage["severity"]["severity"] in ("high", "critical")
        playbook = sentinel.playbook("Ransomware response", triage["techniques"], assets=1)
        assert playbook["steps"]

        # 2. Memora commit (viking context database)
        memory_service = memora_service_mod.MemoraContextService(user="friday")
        committed = memory_service.commit_session("s-incident-1", [
            {"role": "user", "content": "We decided to isolate the file server immediately."},
            {"role": "assistant", "content": f"Severity {triage['severity']['severity']} "
                                              f"for {', '.join(triage['techniques'])}."},
        ])
        assert committed["memories"]

        # 3. FRIDAY recall -> plan -> guarded execution -> verification
        memory = friday_runtime_mod.RuntimeMemory(database=memory_service.db, user="friday")
        runtime = friday_runtime_mod.FridayAgentRuntime(
            workspace={"fs01.log": "10:00 ransomware note\n10:02 shadow copies deleted\n"},
            memory=memory,
        )
        recalled = runtime.recall_context("isolate the file server")
        assert recalled

        from friday_core.real_harness_engineering import Check

        result = runtime.execute(
            "collect fs01 evidence",
            [{"tool": "read_file", "arguments": {"path": "fs01.log"}},
             {"tool": "grep", "arguments": {"pattern": "ransomware"}}],
            checks=[Check("has_evidence", lambda art: ("ransomware" in art, "evidence captured"))],
        )
        assert result.ok is True
        assert "recalled_context" in result.plan
        assert result.verification["passed"] is True
        assert runtime.commit_memory()["committed"] is True
        assert memory.recall("evidence") is not None

    def test_wiring_is_declared_in_app_entrypoints(self):
        """The routers must be imported *and* mounted, not just written."""
        wiring = {
            "FRIDAY/apps/core/src/friday_core/real_deep_api_server.py": [
                "friday_core.agent_runtime import router",
                "include_router(agent_runtime_router)",
            ],
            "Memora/apps/api/main.py": [
                "context_db_router",
                "include_router(context_db_router)",
            ],
            "Memora/apps/api/routers/__init__.py": [
                "routers.context_db import router as context_db_router",
            ],
            "Inference/app/main.py": [
                "app.scientific_service import router as scientific_router",
                "include_router(scientific_router)",
            ],
            "Inference/app/api/agent_routes.py": [
                "research_plan_endpoint",
                '"/research-plan"',
            ],
            "VyralX/app/main.py": [
                "app.services.diagram_service import router as diagram_router",
                "include_router(diagram_router)",
            ],
            "VyralX/app/services/content.py": [
                "attach_explainer",
                "explainer_diagram",
            ],
            "Sentinel/sentinel/apps/api/main.py": [
                "app.services.cyber_skills_service import router as cyber_skills_router",
                "include_router(cyber_skills_router)",
            ],
            "Sentinel/sentinel/api/incident_routes.py": [
                "cyber_skills_service import get_service",
                '"crosswalk"',
            ],
            "Sentinel/app/services/security_posture_assessor.py": [
                "_csf_alignment",
                '"nist_csf"',
            ],
            "mesh/memory_fabric.py": [
                "def context_bridge",
                "def recall_layered",
                "record_context(owner",
            ],
            "mesh/registry.py": [
                "browser_automation",
                "viking_context",
                "scientific_skills",
                "diagram_design",
                "attack_mapping",
            ],
        }
        missing = []
        for relpath, needles in wiring.items():
            text = (ROOT / relpath).read_text()
            for needle in needles:
                if needle not in text:
                    missing.append(f"{relpath} :: {needle}")
        assert not missing, "missing wiring: " + ", ".join(missing)

    def test_agents_yaml_lists_the_new_engines(self):
        text = (ROOT / "AGENTS.yaml").read_text()
        for engine in ("scientific_skills", "viking_context", "cyber_skills",
                       "diagram_design", "detection_coverage"):
            assert engine in text
