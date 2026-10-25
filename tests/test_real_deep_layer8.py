"""
Real Deep Layer 8 Tests — Anthropic Cybersecurity Skills → Sentinel.

Real functional tests for Sentinel/app/services/real_cyber_skills.py:
framework tables and mappings, the 47-skill catalogue, technique/kill-chain
resolution, NIST CSF assessment, detection coverage, skill recommendation,
playbook composition, rules-of-engagement authorization, F3 fraud mapping,
incident reporting and the engine facade.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from Sentinel.app.services.real_cyber_skills import (  # noqa: E402
    AI_RMF_FUNCTIONS,
    ATTACK_TACTICS,
    CSF_CATEGORIES,
    CSF_FUNCTIONS,
    D3FEND_TECHNIQUES,
    F3_TACTICS,
    F3_TECHNIQUES,
    TACTIC_ORDER,
    TACTIC_RISK_WEIGHT,
    TECHNIQUE_TACTICS,
    AuthorizationScope,
    ControlAssessment,
    CoverageResult,
    CyberSkillsEngine,
    DetectionCoverageEngine,
    DetectionRule,
    FraudMapper,
    FrameworkMapping,
    IncidentEvent,
    IncidentReport,
    NistCsfAssessor,
    PlaybookComposer,
    SecuritySkill,
    SkillCatalog,
    SkillRecommender,
    TechniqueResolver,
    engine,
    normalise_technique,
    resolve_tactics,
    severity_for,
    sub_technique_of,
    tactic_id,
)


@pytest.fixture()
def catalog():
    return SkillCatalog()


# ── Reference tables ──────────────────────────────────────────────────────

class TestFrameworkTables:
    def test_attack_tactics(self):
        assert len(ATTACK_TACTICS) == 15
        assert ATTACK_TACTICS["TA0001"] == "Initial Access"
        assert ATTACK_TACTICS["TA0040"] == "Impact"
        assert ATTACK_TACTICS["TA0112"] == "Defense Impairment"
        assert len(TACTIC_ORDER) == 15
        assert tactic_id("Impact") == "TA0040"
        assert tactic_id("nope") == ""

    def test_csf(self):
        assert len(CSF_FUNCTIONS) == 6
        assert len(CSF_CATEGORIES) == 22
        assert CSF_CATEGORIES["DE.CM"] == "Continuous Monitoring"
        assert all(category.split(".")[0] in CSF_FUNCTIONS for category in CSF_CATEGORIES)

    def test_other_frameworks(self):
        assert len(D3FEND_TECHNIQUES) >= 15
        assert len(AI_RMF_FUNCTIONS) == 4
        assert F3_TACTICS["FA0002"] == "Monetization"
        assert F3_TECHNIQUES["F1005.003"] == "Add Beneficiary"

    def test_technique_normalisation(self):
        assert normalise_technique("t1566.001") == "T1566"
        assert normalise_technique("T1071") == "T1071"
        assert normalise_technique("kerberoasting") == "T1558"
        assert normalise_technique("") == ""
        assert sub_technique_of("T1566.001") == "T1566.001"
        assert sub_technique_of("T1566") == ""

    def test_tactic_resolution(self):
        assert resolve_tactics("T1566") == ["Initial Access"]
        assert resolve_tactics("TA0006") == ["Credential Access"]
        assert resolve_tactics("Impact") == ["Impact"]
        assert resolve_tactics("T1078") == ["Initial Access", "Persistence", "Privilege Escalation"]
        assert resolve_tactics("T9999") == []
        assert resolve_tactics("") == []

    def test_all_tactics_have_risk_weights(self):
        for tactic in ATTACK_TACTICS.values():
            assert 0 < TACTIC_RISK_WEIGHT[tactic] <= 1.0


class TestFrameworkMapping:
    def test_tactics_and_frameworks(self):
        mapping = FrameworkMapping(
            attack=["T1566", "T1071"], csf=["DE.CM"], atlas=["AML.T0051"],
            d3fend=["D3-NTA"], ai_rmf=["MEASURE"], f3=["F1005"],
        )
        assert set(mapping.tactics()) == {"Initial Access", "Command and Control"}
        assert mapping.frameworks() == ["attack", "csf", "atlas", "d3fend", "ai_rmf", "f3"]
        assert mapping.count() == 7
        assert mapping.unknown() == []
        assert mapping.as_dict()["attack"] == ["T1566", "T1071"]

    def test_unknown_identifiers(self):
        mapping = FrameworkMapping(
            attack=["T9999"], csf=["ZZ.ZZ"], atlas=["AML.T9999"],
            d3fend=["D3-NOPE"], ai_rmf=["NOPE"], f3=["F9999"],
        )
        problems = mapping.unknown()
        assert len(problems) == 6
        assert any("ATT&CK" in p for p in problems)
        assert any("CSF" in p for p in problems)

    def test_f3_tactics_are_valid_mappings(self):
        assert FrameworkMapping(f3=["FA0002"]).unknown() == []


# ── Catalogue ─────────────────────────────────────────────────────────────

class TestSkillCatalog:
    def test_size_domains_and_tiers(self, catalog):
        report = catalog.coverage_report()
        assert len(catalog) >= 45
        assert report["domains"] >= 30
        assert report["invalid_mappings"] == []
        assert report["attack_mapped"] > 35
        assert report["offensive"] >= 4
        assert report["requires_authorization"] >= 4
        assert {"defensive", "offensive", "governance", "dual-use"} <= {
            s.tier for s in catalog.skills.values()
        }

    def test_every_skill_is_complete(self, catalog):
        for skill in catalog.skills.values():
            assert skill.name and skill.summary
            assert skill.workflow
            assert skill.mapping.csf or skill.domain in ("osint", "sigint", "humint")
            assert skill.mapping.count() >= 1
            assert skill.requires_authorization == (skill.tier == "offensive")

    def test_lookup_helpers(self, catalog):
        assert catalog.get("ransomware-response").tier == "defensive"
        assert catalog.get("nope") is None
        assert catalog.by_domain("identity")
        assert {s.tier for s in catalog.by_tier("offensive")} == {"offensive"}
        assert "kerberoasting-detection" in [s.skill_id for s in catalog.by_tactic("Credential Access")]
        assert catalog.by_framework("nope") == []
        assert catalog.by_framework("atlas")

    def test_technique_coverage_lookup(self, catalog):
        assert "ransomware-response" in [s.skill_id for s in catalog.covering("T1486")]
        assert "kerberoasting-detection" in [s.skill_id for s in catalog.covering("T1558.003")]
        assert catalog.covering("T9999") == []

    def test_search_by_prose_and_technique(self, catalog):
        top = catalog.search("ransomware encryption recovery")
        assert top[0].skill.skill_id == "ransomware-response"
        assert top[0].reasons

        technique_hits = catalog.search("T1558 kerberoasting")
        assert technique_hits[0].skill.skill_id == "kerberoasting-detection"
        assert any("covers T1558" in reason for reason in technique_hits[0].reasons)
        assert catalog.search("zzz qqq") == []

    def test_search_limit_and_order(self, catalog):
        results = catalog.search("network traffic dns", limit=2)
        assert len(results) <= 2
        assert [r.score for r in results] == sorted((r.score for r in results), reverse=True)

    def test_coverage_report_shape(self, catalog):
        report = catalog.coverage_report()
        assert report["skills"] == len(catalog)
        assert "per_tactic" in report and "per_domain" in report
        assert report["frameworks"]["attack"] == report["attack_mapped"]

    def test_custom_catalog(self):
        minimal = SkillCatalog([
            SecuritySkill(
                skill_id="test-skill", name="Test", domain="testing", tier="defensive",
                summary="A test skill.", mapping=FrameworkMapping(attack=["T1071"], csf=["DE.CM"]),
                workflow=["do the thing"],
            )
        ])
        assert len(minimal) == 1
        assert minimal.coverage_report()["domains"] == 1
        assert minimal.search("T1071")[0].skill.skill_id == "test-skill"

    def test_skill_search_text_and_relevance(self, catalog):
        skill = catalog.get("dns-tunneling-detection")
        assert "dns" in skill.search_text()
        assert skill.relevance({"dns"}) > 0
        assert skill.relevance(set()) == 0.0
        assert skill.as_dict()["tier"] == "defensive"


# ── Techniques ────────────────────────────────────────────────────────────

class TestTechniqueResolver:
    resolver = TechniqueResolver()

    def test_resolve_sub_technique(self):
        position = self.resolver.resolve("T1566.001")
        assert position.parent == "T1566"
        assert position.sub_technique == "T1566.001"
        assert position.stage == "Initial Access"
        assert position.risk_weight == pytest.approx(0.9)

    def test_resolve_unknown(self):
        position = self.resolver.resolve("T9999")
        assert position.tactics == []
        assert position.stage == ""
        assert position.risk_weight == 0.0

    def test_tactics_for_is_kill_chain_ordered(self):
        tactics = self.resolver.tactics_for(["T1486", "T1566", "T1003"])
        assert tactics == ["Initial Access", "Credential Access", "Impact"]

    def test_kill_chain_rows(self):
        rows = self.resolver.kill_chain(["T1486", "T1566", "T1071"])
        assert [row["stage"] for row in rows] == [
            "Initial Access", "Command and Control", "Impact"
        ]
        assert all("risk_weight" in row for row in rows)

    def test_coverage_rows(self):
        result = self.resolver.coverage(["T1566", "T1486", "T1601"])
        assert result["covered"] == 2
        assert result["total"] == 3
        assert result["ratio"] == pytest.approx(2 / 3, abs=1e-4)
        assert "T1601" in [row["technique"] for row in result["techniques"] if not row["covered"]]

    def test_unknown_techniques(self):
        assert self.resolver.unknown(["T1566", "T9999"]) == ["T9999"]


# ── CSF assessment ────────────────────────────────────────────────────────

class TestNistCsfAssessor:
    def _assessor(self):
        assessor = NistCsfAssessor()
        assessor.assess("GV.OC", 4, evidence=["policy"], owner="ciso")
        assessor.assess("ID.AM", 3, evidence=["cmdb"])
        assessor.assess("PR.AA", 2, evidence=["sso"])
        assessor.assess("DE.CM", 3)
        assessor.assess("DE.AE", 1)
        return assessor

    def test_scores(self):
        assessor = self._assessor()
        assert assessor.function_scores()["DE"] == pytest.approx((3 + 1) / 2 / 5, abs=1e-4)
        assert assessor.function_scores()["GV"] == pytest.approx(0.8)
        assert assessor.overall() == pytest.approx(13 / 25, abs=1e-4)
        assert assessor.category_scores()["PR.AA"] == pytest.approx(0.4)

    def test_coverage_and_unassessed(self):
        assessor = self._assessor()
        assert assessor.coverage() == pytest.approx(5 / 22, abs=1e-4)
        assert len(assessor.unassessed()) == 22 - 5
        assert NistCsfAssessor().overall() == 0.0

    def test_gaps_and_actions(self):
        assessor = self._assessor()
        gaps = assessor.gaps(target=3)
        assert gaps[0]["category"] == "DE.AE"       # biggest deficit
        assert gaps[0]["deficit"] == 2
        actions = assessor.prioritized_actions(limit=2)
        assert actions and actions[0].startswith("Raise DE.AE")

    def test_validation(self):
        with pytest.raises(ValueError):
            ControlAssessment(category="ZZ.ZZ", maturity=2)
        with pytest.raises(ValueError):
            ControlAssessment(category="DE.CM", maturity=9)
        record = ControlAssessment(category="DE.CM", maturity=3)
        assert record.function == "DE"

    def test_assess_replaces_record(self):
        assessor = self._assessor()
        assessor.assess("PR.AA", 5)
        assert assessor.category_scores()["PR.AA"] == 1.0


# ── Detection coverage ────────────────────────────────────────────────────

class TestDetectionCoverage:
    def _engine(self):
        return DetectionCoverageEngine([
            DetectionRule("r1", "ransomware", ["T1486"], fidelity=0.9),
            DetectionRule("r2", "c2", ["T1071"], enabled=False),
            DetectionRule("r3", "phishing", ["T1566"], fidelity=0.5),
        ])

    def test_evaluate(self):
        result = self._engine().evaluate(["T1486", "T1071", "T1566", "T1003"])
        assert isinstance(result, CoverageResult)
        assert result.per_technique["T1486"] == pytest.approx(0.9)
        assert result.per_technique["T1071"] == 0.0        # disabled rule
        assert result.per_technique["T1566"] == pytest.approx(0.5)
        assert result.per_technique["T1003"] == 0.0
        assert set(result.covered) == {"T1486", "T1566"}
        assert set(result.gaps) == {"T1071", "T1003"}
        assert 0 < result.weighted < 1
        assert result.rules == 3

    def test_weighted_coverage_prioritises_high_risk(self):
        both = ["T1486", "T1595"]
        covers_high = DetectionCoverageEngine([
            DetectionRule("r1", "impact", ["T1486"], fidelity=1.0),
        ]).evaluate(both)
        covers_low = DetectionCoverageEngine([
            DetectionRule("r1", "recon", ["T1595"], fidelity=1.0),
        ]).evaluate(both)
        # missing the Impact technique must hurt more than missing reconnaissance
        assert covers_high.weighted > covers_low.weighted
        assert covers_low.weighted < 0.5

    def test_per_tactic_and_matrix(self):
        engine = self._engine()
        result = engine.evaluate(["T1486", "T1566"])
        assert result.per_tactic["Impact"] == pytest.approx(0.9)
        assert result.per_tactic["Initial Access"] == pytest.approx(0.5)
        matrix = engine.matrix(["T1486", "T1566", "T1003"])
        assert matrix["Impact"]["T1486"] == pytest.approx(0.9)
        assert "T1003" not in matrix

    def test_recommendations_ordered_by_risk(self):
        recommendations = self._engine().recommendations(
            ["T1071", "T1003"], catalog=SkillCatalog(), limit=3,
        )
        assert recommendations
        assert recommendations[0]["risk_weight"] >= recommendations[-1]["risk_weight"]
        assert all("skill" in row for row in recommendations)

    def test_empty_and_unknown(self):
        engine = self._engine()
        result = engine.evaluate([])
        assert result.weighted == 0.0
        assert result.as_dict()["rules"] == 3
        assert engine.recommendations([], limit=3) == []

    def test_add_rule(self):
        engine = DetectionCoverageEngine()
        assert engine.evaluate(["T1486"]).gaps == ["T1486"]
        engine.add(DetectionRule("r", "new", ["T1486"], fidelity=1.0))
        assert engine.evaluate(["T1486"]).covered == ["T1486"]


# ── Recommendation ────────────────────────────────────────────────────────

class TestSkillRecommender:
    def test_technique_match_dominates(self):
        results = SkillRecommender().recommend(["T1486"], keywords="", tier="defensive", limit=3)
        assert results[0]["skill"] == "ransomware-response"
        assert results[0]["breakdown"]["technique"] > 0
        assert results[0]["score"] > 0

    def test_domain_and_tier_bonus(self, catalog):
        results = SkillRecommender(catalog).recommend(
            keywords="kerberos", domain="identity", tier="defensive", limit=3,
        )
        identity = [r for r in results if r["breakdown"]["domain"] > 0]
        assert identity
        assert identity[0]["breakdown"]["tier"] == 0.5

    def test_offensive_flagged(self):
        results = SkillRecommender().recommend(["T1566"], tier="offensive", limit=2)
        assert any(r["requires_authorization"] for r in results)

    def test_empty_query_returns_nothing(self):
        assert SkillRecommender().recommend(limit=3) == []


# ── Severity and playbooks ────────────────────────────────────────────────

class TestSeverity:
    def test_escalates_with_impact_and_breadth(self):
        low = severity_for(["T1595"])                       # reconnaissance only
        high = severity_for(["T1566", "T1486", "T1041"], assets=25)
        assert low["severity"] == "low"
        assert high["severity"] == "critical"
        assert high["score"] > low["score"]
        assert "Impact" in high["tactics"]

    def test_no_techniques(self):
        assert severity_for([])["severity"] == "low"
        assert severity_for([])["score"] == 0.0

    def test_asset_count_matters(self):
        small = severity_for(["T1486"], assets=1)
        large = severity_for(["T1486"], assets=500)
        assert large["score"] >= small["score"]


class TestPlaybookComposer:
    def test_compose_structure(self):
        playbook = PlaybookComposer().compose(
            "Ransomware on file server", ["T1486", "T1490", "T1071"], assets=12,
        )
        assert playbook.severity in ("high", "critical")
        assert playbook.techniques == ["T1486", "T1490", "T1071"]
        coverage = playbook.phase_coverage()
        assert set(coverage) == {
            "Preparation", "Detection & Analysis", "Containment",
            "Eradication", "Recovery", "Lessons Learned",
        }
        assert coverage["Preparation"] >= 1
        assert coverage["Recovery"] >= 1
        assert coverage["Lessons Learned"] >= 1
        assert all(step.order >= 1 for step in playbook.steps)
        assert playbook.steps[0].phase == "Preparation"

    def test_steps_are_ordered_by_phase(self):
        playbook = PlaybookComposer().compose("Cloud key theft", ["T1078", "T1530"])
        phases = [step.phase for step in playbook.steps]
        order = ["Preparation", "Detection & Analysis", "Containment",
                 "Eradication", "Recovery", "Lessons Learned"]
        assert phases == sorted(phases, key=order.index)

    def test_framework_refs_and_coverage(self):
        composer = PlaybookComposer()
        playbook = composer.compose("Ransomware", ["T1486"])
        counts = composer.framework_coverage(playbook)
        assert counts["ATTACK"] >= 1
        assert counts["CSF"] >= 1
        assert set(playbook.frameworks) >= {"ATTACK", "CSF"}

    def test_markdown_render(self):
        playbook = PlaybookComposer().compose("BEC", ["T1566", "T1114"])
        markdown = playbook.render_markdown()
        assert markdown.startswith("# BEC")
        assert "**Severity:**" in markdown
        assert "## Detection & Analysis" in markdown
        assert "T1566" in markdown

    def test_offensive_skill_marked(self):
        playbook = PlaybookComposer().compose("Phishing exercise", ["T1566"], assets=1)
        assert any(step.requires_authorization for step in playbook.steps)

    def test_dict_shape(self):
        payload = PlaybookComposer().compose("Impact", ["T1486"]).as_dict()
        assert payload["title"] == "Impact"
        assert payload["severity"]
        assert payload["phase_coverage"]
        assert isinstance(payload["steps"], list)


# ── Authorization ─────────────────────────────────────────────────────────

class TestAuthorizationScope:
    def _scope(self, **kwargs):
        defaults = dict(
            engagement="eng-2026-01",
            authorized_networks=["10.10.0.0/16", "2001:db8::/32"],
            authorized_domains=["*.acme.test", "api.acme.test"],
            allowed_tiers=["offensive", "defensive"],
            window_start="2026-01-01T00:00:00+00:00",
            window_end="2026-12-31T00:00:00+00:00",
            approver="ciso",
        )
        defaults.update(kwargs)
        return AuthorizationScope(**defaults)

    def test_network_targets(self, catalog):
        scope = self._scope()
        device = catalog.get("phishing-simulation")
        when = datetime(2026, 6, 1, tzinfo=timezone.utc)
        assert scope.check(device, "10.10.5.7", when=when).allowed is True
        assert scope.check(device, "192.168.1.5", when=when).allowed is False
        assert scope.check(device, "2001:db8::1", when=when).allowed is True
        assert scope.check(device, "10.10.0.0/24", when=when).allowed is True
        assert scope.check(device, "10.20.0.0/24", when=when).allowed is False

    def test_domain_targets(self, catalog):
        scope = self._scope()
        device = catalog.get("phishing-simulation")
        when = datetime(2026, 6, 1, tzinfo=timezone.utc)
        assert scope.check(device, "mail.acme.test", when=when).allowed is True
        assert scope.check(device, "api.acme.test", when=when).allowed is True
        assert scope.check(device, "evil.test", when=when).allowed is False
        assert scope.check(device, "mail.acme.test:443", when=when).allowed is True

    def test_window(self, catalog):
        scope = self._scope()
        device = catalog.get("phishing-simulation")
        assert scope.check(device, "10.10.5.7", when=datetime(2025, 6, 1, tzinfo=timezone.utc)).allowed is False
        assert scope.check(device, "10.10.5.7", when=datetime(2027, 6, 1, tzinfo=timezone.utc)).allowed is False
        naive = datetime(2026, 6, 1)
        assert scope.check(device, "10.10.5.7", when=naive).allowed is True
        assert self._scope(window_start="2026-06-01T00:00:00+00:00").in_window(
            datetime(2026, 1, 1, tzinfo=timezone.utc)) is False

    def test_tier_gate(self, catalog):
        scope = self._scope(allowed_tiers=["defensive"])
        assert scope.check(catalog.get("phishing-simulation"), "10.10.5.7").allowed is False
        decision = scope.check(catalog.get("ransomware-response"), "10.10.5.7")
        assert decision.allowed is True          # defensive skills pass the tier gate
        assert "not approved" in scope.check(catalog.get("exploit-development"), "10.10.5.7").reason

    def test_requires_engagement(self, catalog):
        scope = AuthorizationScope()
        decision = scope.check(catalog.get("exploit-development"), "10.0.0.1")
        assert decision.allowed is False
        assert decision.reason == "no engagement on record"

    def test_audit_and_report(self, catalog):
        scope = self._scope()
        device = catalog.get("phishing-simulation")
        when = datetime(2026, 6, 1, tzinfo=timezone.utc)
        scope.check(device, "10.10.5.7", when=when)
        scope.check(device, "8.8.8.8", when=when)
        assert len(scope.audit) == 2
        report = scope.report()
        assert report["checks"] == 2
        assert report["allowed"] == 1 and report["denied"] == 1
        assert report["networks"] == ["10.10.0.0/16", "2001:db8::/32"]
        assert report["approver"] == "ciso"

    def test_string_skill_reference(self):
        scope = self._scope()
        decision = scope.check("some-offensive-skill", "10.10.5.7")
        assert decision.allowed is True
        assert decision.skill_id == "some-offensive-skill"

    def test_bad_inputs(self):
        scope = self._scope()
        assert scope.target_authorized("") is False
        assert scope.target_authorized("not a network/../") is False
        assert scope._parse("not-a-date") is None


# ── Fraud ─────────────────────────────────────────────────────────────────

class TestFraudMapper:
    def test_monetization_path(self):
        payload = FraudMapper().monetization_path(["F1025.003", "F1032"])
        assert payload["tactics"] == ["Monetization"]
        assert payload["known"] is True
        assert {t["name"] for t in payload["techniques"]} == {"Wire Transfer", "Money Mule Layering"}

    def test_unknown_technique(self):
        payload = FraudMapper().monetization_path(["F9999"])
        assert payload["known"] is False
        assert payload["techniques"][0]["name"] == "unknown"

    def test_coverage(self, catalog):
        coverage = FraudMapper(catalog).coverage()
        assert coverage["fraud_skills"] >= 4
        assert "F1005" in coverage["techniques"]
        assert coverage["skills"]

    def test_skills_for_technique(self, catalog):
        assert "detecting-business-email-compromise" in FraudMapper(catalog).skills_for_technique("T1566")


# ── Incident report ───────────────────────────────────────────────────────

class TestIncidentReport:
    def _report(self):
        report = IncidentReport("BEC to wire fraud")
        report.add_event(IncidentEvent("2026-10-01T10:00:00", "Phishing email delivered",
                                       "T1566", "mail01", "email gateway"))
        report.add_event(IncidentEvent("2026-10-01T09:59:00", "Mailbox rule created",
                                       "T1114", "mail01", "audit log"))
        report.add_event(IncidentEvent("2026-10-01T11:30:00", "Wire transfer requested",
                                       "T1657", "fin01"))
        return report

    def test_build(self):
        payload = self._report().build()
        assert payload["title"] == "BEC to wire fraud"
        assert payload["techniques"] == ["T1566", "T1114", "T1657"]
        assert payload["assets"] == ["fin01", "mail01"]
        assert payload["severity"]["severity"] in ("medium", "high", "critical")
        assert len(payload["events"]) == 3

    def test_timeline_is_sorted(self):
        events = self._report().timeline()
        timestamps = [e.timestamp for e in events]
        assert timestamps == sorted(timestamps)
        assert events[0].description == "Mailbox rule created"

    def test_crosswalk(self):
        crosswalk = self._report().crosswalk()
        assert "Initial Access" in crosswalk["tactics"]
        assert crosswalk["csf"]
        assert crosswalk["skills"]
        assert "detecting-business-email-compromise" in crosswalk["skills"]

    def test_markdown(self):
        markdown = self._report().render_markdown()
        assert markdown.startswith("# BEC to wire fraud")
        assert "## Timeline" in markdown
        assert "`2026-10-01T09:59:00`" in markdown
        assert "## ATT&CK tactics" in markdown
        assert "T1566" in markdown

    def test_empty_report(self):
        report = IncidentReport("Nothing happened")
        payload = report.build()
        assert payload["severity"]["severity"] == "low"
        assert payload["crosswalk"]["skills"] == []
        assert report.render_markdown().startswith("# Nothing happened")


# ── Facade ────────────────────────────────────────────────────────────────

class TestCyberSkillsEngine:
    def test_catalog_summary(self):
        summary = engine.catalog_summary()
        assert summary["skills"] >= 45
        assert summary["domains"] >= 30
        assert summary["invalid_mappings"] == []

    def test_select_skills(self):
        results = engine.select_skills(["T1558"], keywords="kerberos", limit=3)
        assert results
        assert results[0]["skill"] in (
            "kerberoasting-detection", "active-directory-hardening",
        )
        assert {"skill", "score", "breakdown", "tactics"} <= set(results[0])

    def test_coverage(self):
        payload = engine.coverage(
            ["T1486", "T1071"],
            rules=[DetectionRule("r1", "ransom", ["T1486"], fidelity=0.8)],
        )
        assert payload["covered"] == ["T1486"]
        assert payload["gaps"] == ["T1071"]
        assert payload["recommendations"]

    def test_playbook(self):
        payload = engine.playbook("Ransomware", ["T1486", "T1490"], assets=4)
        assert payload["title"] == "Ransomware"
        assert payload["steps"]
        assert payload["framework_coverage"]["ATTACK"] >= 1
        assert payload["markdown"].startswith("# Ransomware")

    def test_triage(self):
        payload = engine.triage("Suspicious login", [
            {"timestamp": "2026-10-01T00:00:00", "description": "Impossible travel",
             "technique": "T1078", "host": "vpn01"},
            {"timestamp": "2026-10-01T00:05:00", "description": "C2 beacon",
             "technique": "T1071", "host": "vpn01"},
        ])
        assert payload["severity"]["severity"] in ("medium", "high", "critical")
        assert payload["assets"] == ["vpn01"]
        assert "T1078" in payload["techniques"]
        assert payload["markdown"]

    def test_custom_engine(self, catalog):
        custom = CyberSkillsEngine(catalog)
        assert custom.catalog is catalog
        assert custom.select_skills(["T1486"], limit=1)[0]["skill"] == "ransomware-response"
