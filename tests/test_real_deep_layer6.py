"""
Real Deep Layer 6 Tests — Scientific Agent Skills → Inference.

Real functional tests for Inference/app/agents/real_scientific_skills.py:
distribution math, hypothesis tests with closed-form p-values, power analysis,
sequence/molecule analysis, unit conversion, the skill catalogue and matcher,
pipeline composition with provenance, hypothesis ranking, evidence auditing
and experimental design.

The module is loaded by path because Inference's package __init__ pulls in
optional service dependencies that this layer does not need.
"""

import importlib.util
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

MODULE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "Inference", "app", "agents",
    "real_scientific_skills.py",
)


def _load():
    spec = importlib.util.spec_from_file_location("real_scientific_skills", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["real_scientific_skills"] = module
    spec.loader.exec_module(module)
    return module


sci = _load()


# ── Distribution math ─────────────────────────────────────────────────────

class TestDistributionMath:
    def test_normal_cdf_and_ppf_are_inverses(self):
        for z in (-3.0, -1.0, 0.0, 0.5, 2.33):
            p = sci.normal_cdf(z)
            assert sci.normal_ppf(p) == pytest.approx(z, abs=1e-6)

    def test_known_normal_values(self):
        assert sci.normal_cdf(0.0) == pytest.approx(0.5)
        assert sci.normal_cdf(1.96) == pytest.approx(0.975, abs=1e-4)
        assert sci.normal_ppf(0.975) == pytest.approx(1.959964, abs=1e-5)
        assert sci.normal_ppf(0.0) == -math.inf
        assert sci.normal_ppf(1.0) == math.inf

    def test_incomplete_beta_identities(self):
        assert sci.regularized_incomplete_beta(2, 3, 0.0) == 0.0
        assert sci.regularized_incomplete_beta(2, 3, 1.0) == 1.0
        assert sci.regularized_incomplete_beta(1, 1, 0.42) == pytest.approx(0.42, abs=1e-9)

    def test_t_p_value_symmetry(self):
        assert sci.t_two_sided_p(0.0, 10) == pytest.approx(1.0)
        assert sci.t_two_sided_p(2.228, 10) == pytest.approx(0.05, abs=2e-3)
        assert sci.t_two_sided_p(-2.228, 10) == pytest.approx(sci.t_two_sided_p(2.228, 10))
        assert sci.t_two_sided_p(0.0, 0) == 1.0

    def test_chi2_and_f_survival(self):
        assert sci.chi2_survival(3.841, 1) == pytest.approx(0.05, abs=2e-3)
        assert sci.chi2_survival(0.0, 5) == 1.0
        assert sci.f_survival(4.9646, 1, 4) == pytest.approx(0.077, abs=2e-2)
        assert sci.f_survival(0.0, 1, 4) == 1.0

    def test_descriptive_helpers(self):
        assert sci.mean([1, 2, 3]) == 2
        assert sci.variance([1, 2, 3]) == pytest.approx(1.0)
        assert sci.stdev([2, 2, 2]) == 0.0
        assert sci.mean([]) == 0.0
        assert sci.variance([1]) == 0.0


# ── Hypothesis tests ──────────────────────────────────────────────────────

class TestStatisticalTests:
    def test_welch_t_known_example(self):
        result = sci.StatisticalTestSuite().t_test_independent(
            [1, 2, 3, 4, 5], [2, 3, 4, 5, 6]
        )
        assert result.statistic == pytest.approx(-1.0, abs=1e-9)
        assert result.p_value == pytest.approx(0.34659, abs=1e-4)
        assert result.significant is False
        assert result.effect_size < 0

    def test_welch_handles_unequal_variance(self):
        result = sci.StatisticalTestSuite().t_test_independent(
            [1, 2, 3], [10, 20, 30, 40, 50]
        )
        assert result.statistic < 0
        assert result.p_value < 0.05
        # Welch df is fractional and below the pooled value.
        assert 3.0 < result.df < 7.0
        assert "reject H0" in result.summary()

    def test_t_test_insufficient_data(self):
        assert sci.StatisticalTestSuite().t_test_independent([1], [2]).p_value == 1.0
        assert sci.StatisticalTestSuite().t_test_independent([5, 5], [5, 5]).p_value == 1.0

    def test_paired_t(self):
        result = sci.StatisticalTestSuite().t_test_paired(
            [10, 12, 14, 16, 20], [11, 13, 14, 18, 24]
        )
        assert result.df == 4
        assert 0 <= result.p_value <= 1
        assert sci.StatisticalTestSuite().t_test_paired([1], [2]).p_value == 1.0

    def test_mann_whitney_separated_groups(self):
        result = sci.StatisticalTestSuite().mann_whitney_u(
            [1, 2, 3, 4, 5], [6, 7, 8, 9, 10]
        )
        assert result.statistic == 0.0
        assert result.p_value < 0.05
        assert result.effect_size == pytest.approx(1.0)

    def test_mann_whitney_ties_are_handled(self):
        result = sci.StatisticalTestSuite().mann_whitney_u(
            [1, 2, 2, 3], [2, 3, 3, 4]
        )
        assert 0 <= result.p_value <= 1
        assert "z" in result.detail

    def test_chi_square_known_table(self):
        result = sci.StatisticalTestSuite().chi_square_independence([[10, 20], [30, 40]])
        assert result.statistic == pytest.approx(0.7937, abs=1e-4)
        assert result.p_value == pytest.approx(0.373, abs=1e-3)
        assert result.df == 1
        assert result.detail["min_expected"] == pytest.approx(12.0)

    def test_chi_square_detects_dependence(self):
        result = sci.StatisticalTestSuite().chi_square_independence([[50, 5], [5, 50]])
        assert result.significant
        assert result.effect_size > 0.5

    def test_chi_square_rejects_bad_input(self):
        assert sci.StatisticalTestSuite().chi_square_independence([[1, 2]]).p_value == 1.0
        assert sci.StatisticalTestSuite().chi_square_independence([[0, 0], [0, 0]]).p_value == 1.0

    def test_anova_known_example(self):
        result = sci.StatisticalTestSuite().one_way_anova([[1, 2, 3], [4, 5, 6]])
        assert result.statistic == pytest.approx(13.5)
        assert result.p_value == pytest.approx(0.0213, abs=1e-3)
        assert result.effect_size == pytest.approx(0.7714, abs=1e-3)

    def test_anova_three_groups_monotonic(self):
        result = sci.StatisticalTestSuite().one_way_anova([[1, 2, 3], [4, 5, 6], [7, 8, 9]])
        assert result.significant
        assert result.detail["df_within"] == 6.0
        assert sci.StatisticalTestSuite().one_way_anova([[1, 2]]).p_value == 1.0

    def test_correlation(self):
        suite = sci.StatisticalTestSuite()
        perfect = suite.pearson([1, 2, 3, 4, 5], [2, 4, 6, 8, 10])
        assert perfect.statistic == pytest.approx(1.0)
        inverse = suite.pearson([1, 2, 3, 4, 5], [10, 8, 6, 4, 2])
        assert inverse.statistic == pytest.approx(-1.0)
        assert suite.pearson([1, 2], [3, 4]).p_value == 1.0

    def test_spearman_is_rank_based(self):
        suite = sci.StatisticalTestSuite()
        monotone = suite.spearman([1, 2, 3, 4], [1, 4, 9, 16])
        assert monotone.statistic == pytest.approx(1.0)
        assert monotone.name == "spearman_rho"

    def test_effect_sizes(self):
        suite = sci.StatisticalTestSuite()
        assert suite.cohens_d([2, 2, 2], [2, 2, 2]) == 0.0
        assert suite.cohens_d([10, 11, 12], [1, 2, 3]) > 1.0
        assert suite.odds_ratio(10, 5, 5, 10) == pytest.approx(4.0)
        assert suite.odds_ratio(0, 5, 5, 10) > 0        # Haldane correction
        assert suite.relative_risk(10, 10, 5, 15) == pytest.approx(2.0)

    def test_benjamini_hochberg_known_output(self):
        p_values = [0.001, 0.008, 0.039, 0.041, 0.042, 0.06, 0.074, 0.205, 0.212, 0.216]
        result = sci.StatisticalTestSuite().benjamini_hochberg(p_values)
        assert result["q_values"][0] == pytest.approx(0.01)
        assert result["q_values"][1] == pytest.approx(0.04)
        assert result["q_values"][-1] == pytest.approx(0.216)
        assert result["discoveries"] == 2
        assert all(q >= p for q, p in zip(result["q_values"], p_values))

    def test_benjamini_hochberg_empty_and_bonferroni(self):
        suite = sci.StatisticalTestSuite()
        empty = suite.benjamini_hochberg([])
        assert empty["q_values"] == [] and empty["rejected"] == []
        bonf = suite.bonferroni([0.001, 0.04], alpha=0.05)
        assert bonf["adjusted"] == [pytest.approx(0.002), pytest.approx(0.08)]
        assert bonf["rejected"] == [True, False]

    def test_bootstrap_ci_brackets_mean_and_is_deterministic(self):
        suite = sci.StatisticalTestSuite()
        data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        first = suite.bootstrap_ci(data, n_resamples=500, seed=3)
        second = suite.bootstrap_ci(data, n_resamples=500, seed=3)
        assert first == second
        assert first["lower"] < first["mean"] < first["upper"]
        assert 2.5 < first["lower"] < 4.5
        assert suite.bootstrap_ci([])["mean"] == 0.0


# ── Power ─────────────────────────────────────────────────────────────────

class TestPowerAnalysis:
    def test_sample_size_matches_textbook(self):
        result = sci.PowerAnalysis().sample_size_two_sample(0.5, alpha=0.05, power=0.8)
        # Classic answer: 63 per group for d = 0.5.
        assert result.n_per_group == 63
        assert result.power == pytest.approx(0.80, abs=0.02)
        assert result.detectable_effect == pytest.approx(0.5, abs=0.02)

    def test_smaller_effects_need_more_samples(self):
        power = sci.PowerAnalysis()
        small = power.sample_size_two_sample(0.2).n_per_group
        large = power.sample_size_two_sample(0.8).n_per_group
        assert small > large
        assert power.sample_size_two_sample(0.0).n_per_group == 0

    def test_power_increases_with_n(self):
        power = sci.PowerAnalysis()
        assert power.power_two_sample(0.5, 10) < power.power_two_sample(0.5, 100)
        assert 0 <= power.power_two_sample(0.5, 1) <= 1

    def test_minimum_detectable_effect_shrinks_with_n(self):
        power = sci.PowerAnalysis()
        assert power.minimum_detectable_effect(200) < power.minimum_detectable_effect(20)
        assert power.minimum_detectable_effect(1) == math.inf

    def test_proportion_sample_size(self):
        result = sci.PowerAnalysis().sample_size_proportion(0.30, 0.45)
        assert result.n_per_group > 100
        assert result.effect_size == pytest.approx(0.15)
        assert sci.PowerAnalysis().sample_size_proportion(0.3, 0.3).n_per_group == 0


# ── Sequences ─────────────────────────────────────────────────────────────

class TestSequenceAnalysis:
    SEQ = "ATGGCCTATTTTAAACCCGGGTTTTAG"
    seq = sci.SequenceAnalysis()

    def test_gc_content(self):
        assert self.seq.gc_content("GGCC") == 1.0
        assert self.seq.gc_content("ATAT") == 0.0
        assert self.seq.gc_content("ATGC") == 0.5
        assert self.seq.gc_content(self.SEQ) == pytest.approx(11 / 27, abs=1e-6)

    def test_validation(self):
        with pytest.raises(ValueError):
            self.seq.gc_content("ATGCX")
        with pytest.raises(ValueError):
            self.seq.gc_content("")
        assert self.seq.gc_content("at gc at") == pytest.approx(1 / 3)  # whitespace stripped, lowercase ok

    def test_reverse_complement(self):
        assert self.seq.reverse_complement("ATGC") == "GCAT"
        assert self.seq.reverse_complement("AAAAC") == "GTTTT"
        rc = self.seq.reverse_complement(self.SEQ)
        assert self.seq.reverse_complement(rc) == self.SEQ

    def test_melting_temperature_rules(self):
        short = self.seq.melting_temp("ATGCATGCATGCA")     # 13 bp -> Wallace
        long = self.seq.melting_temp("ATGCATGCATGCATGC")
        assert short == pytest.approx(2 * 7 + 4 * 6)
        assert long == pytest.approx(64.9 + 41.0 * (8 - 16.4) / 16, abs=1e-6)

    def test_molecular_weight(self):
        single = self.seq.molecular_weight_dna("ATGC")
        double = self.seq.molecular_weight_dna("ATGC", double_stranded=True)
        assert single == pytest.approx(313.21 + 304.20 + 329.21 + 289.18 - 61.96, abs=1e-2)
        assert double == pytest.approx(single * 2 - 61.96, abs=1e-2)

    def test_translation_and_stop_codon(self):
        assert self.seq.translate("ATGGCCTAA") == "MA*"
        assert self.seq.translate(self.SEQ).startswith("MAYFKP")
        assert self.seq.translate(self.SEQ).endswith("*")

    def test_find_orfs(self):
        orfs = self.seq.find_orfs(self.SEQ, min_protein=3)
        assert orfs
        best = orfs[0]
        assert best.strand in ("+", "-")
        assert best.length_bp == len(best.protein) * 3
        assert best.protein.startswith("M")
        assert best.end <= len(self.SEQ)
        assert self.seq.find_orfs(self.SEQ, min_protein=1000) == []

    def test_kmers(self):
        counts = self.seq.kmer_counts("ATATAT", k=2)
        assert counts["AT"] == 3
        assert counts["TA"] == 2
        assert sum(counts.values()) == 5

    def test_hamming_distance(self):
        assert self.seq.hamming_distance("ATGC", "ATGG") == 1
        assert self.seq.hamming_distance("atgc", "ATGC") == 0
        with pytest.raises(ValueError):
            self.seq.hamming_distance("AT", "ATG")

    def test_protein_properties(self):
        protein = "MKWVTFISLL"
        assert self.seq.protein_molecular_weight(protein) == pytest.approx(1237.6, abs=1.0)
        assert self.seq.protein_molecular_weight("") == 0.0
        assert self.seq.gravy(protein) > 1.0            # hydrophobic leader peptide
        assert self.seq.gravy("DDDEEERRR") < 0
        assert self.seq.gravy("") == 0.0
        assert 0 <= self.seq.isoelectric_point_estimate("MKKKDDD") <= 14
        assert self.seq.isoelectric_point_estimate("") == 7.0


# ── Molecules ─────────────────────────────────────────────────────────────

class TestMolecularFormula:
    def test_parse_flat_formula(self):
        assert sci.MolecularFormula.parse("C6H12O6") == {"C": 6, "H": 12, "O": 6}
        assert sci.MolecularFormula.parse("H2O") == {"H": 2, "O": 1}

    def test_parse_groups_and_hydrates(self):
        assert sci.MolecularFormula.parse("Ca(OH)2") == {"Ca": 1, "O": 2, "H": 2}
        assert sci.MolecularFormula.parse("2H2O") == {"H": 4, "O": 2}
        assert sci.MolecularFormula.parse("CuSO4.5H2O") == {"Cu": 1, "S": 1, "O": 9, "H": 10}

    def test_parse_errors(self):
        with pytest.raises(ValueError):
            sci.MolecularFormula.parse("")
        with pytest.raises(ValueError):
            sci.MolecularFormula.parse("Xx2")
        with pytest.raises(ValueError):
            sci.MolecularFormula.parse("C6H12O6)")

    def test_molecular_weight(self):
        assert sci.MolecularFormula.molecular_weight("C6H12O6") == pytest.approx(180.156, abs=1e-2)
        assert sci.MolecularFormula.molecular_weight("H2O") == pytest.approx(18.015, abs=1e-2)
        assert sci.MolecularFormula.molecular_weight("NaCl") == pytest.approx(58.44, abs=0.2)

    def test_degree_of_unsaturation(self):
        assert sci.MolecularFormula.degree_of_unsaturation("C6H6") == 4.0
        assert sci.MolecularFormula.degree_of_unsaturation("C6H14") == 0.0
        assert sci.MolecularFormula.degree_of_unsaturation("C2H5Cl") == 0.0
        assert sci.MolecularFormula.degree_of_unsaturation("C2H3Cl") == 1.0

    def test_lipinski_rules(self):
        good = sci.MolecularFormula.lipinski("C16H18N2O4S", 1.8, 2, 5)
        assert good.drug_like
        assert good.molecular_weight < 500
        bad = sci.MolecularFormula.lipinski("C40H60O10", 6.5, 7, 12)
        assert not bad.drug_like
        assert len(bad.lipinski_violations) == 4
        assert bad.heavy_atoms == 50


# ── Units ─────────────────────────────────────────────────────────────────

class TestUnitConverter:
    conv = sci.UnitConverter()

    def test_metric_conversions(self):
        assert self.conv.convert(1, "km", "m") == pytest.approx(1000)
        assert self.conv.convert(1, "mg", "ug") == pytest.approx(1000)
        assert self.conv.convert(1, "kcal", "kJ") == pytest.approx(4.184)
        assert self.conv.convert(1, "atm", "mmHg") == pytest.approx(760, abs=0.1)
        assert self.conv.convert(1, "L", "mL") == pytest.approx(1000)

    def test_temperature_scales(self):
        assert self.conv.convert(100, "C", "F") == pytest.approx(212)
        assert self.conv.convert(0, "C", "K") == pytest.approx(273.15)
        assert self.conv.convert(32, "F", "C") == pytest.approx(0)
        assert self.conv.convert(0, "K", "R") == pytest.approx(0)
        assert self.conv.convert(300, "K", "K") == 300

    def test_dimension_checks(self):
        assert self.conv.compatible("kg", "lb")
        assert not self.conv.compatible("kg", "m")
        assert self.conv.dimension_of("eV") == "energy"
        with pytest.raises(ValueError):
            self.conv.convert(1, "kg", "m")
        with pytest.raises(ValueError):
            self.conv.dimension_of("smoot")


# ── Skill catalogue ───────────────────────────────────────────────────────

class TestSkillLibrary:
    def test_catalogue_shape(self):
        library = sci.SkillLibrary()
        assert len(library) >= 50
        report = library.coverage_report()
        assert report["categories"] >= 15
        assert report["with_validations"] == len(library)
        assert "PubChem" in report["databases"]
        assert report["skills"] == len(library)

    def test_lookup_helpers(self):
        library = sci.SkillLibrary()
        assert library.get("bulk-rnaseq").title.startswith("Bulk RNA-seq")
        assert library.get("nope") is None
        assert {s.skill_id for s in library.by_category("bioinformatics")} >= {"bulk-rnaseq"}
        assert sci.SkillSpec  # imported symbol exists
        assert "scanpy" in {p for s in library.by_package("scanpy") for p in s.packages}
        assert any(s.skill_id for s in library.with_database("clinvar"))

    def test_search_ranks_the_right_skill(self):
        library = sci.SkillLibrary()
        top = library.search("differential expression of rna-seq counts")
        assert top[0].skill.skill_id == "bulk-rnaseq"
        assert top[0].score > 0
        assert top[0].reasons

    def test_search_multiple_domains(self):
        library = sci.SkillLibrary()
        assert library.search("dock ligand into receptor binding site")[0].skill.skill_id == "molecular-docking"
        assert library.search("validate analytical method accuracy precision ich")[0].skill.skill_id == "method-validation"
        assert library.search("satellite raster ndvi geotiff")[0].skill.skill_id == "geospatial-raster"
        assert library.search("zzz qqq") == []

    def test_search_respects_limit(self):
        library = sci.SkillLibrary()
        assert len(library.search("protein structure sequence", limit=2)) <= 2

    def test_custom_library(self):
        custom = sci.SkillLibrary([sci.SkillSpec(
            skill_id="tiny", title="Tiny Skill", category="test",
            keywords=["tiny", "check"], produces=["out"],
        )])
        assert len(custom) == 1
        assert custom.search("tiny check")[0].skill.skill_id == "tiny"
        assert custom.by_category("test")[0].skill_id == "tiny"


class TestSkillMatcher:
    def test_match_and_best(self):
        matcher = sci.SkillMatcher()
        matches = matcher.match("single cell clustering with scanpy", limit=2)
        assert matches and matches[0].skill.skill_id == "single-cell-rnaseq"
        assert matcher.best("microbiome 16s amplicon") is not None
        assert matcher.best("zzz") is None

    def test_match_many(self):
        out = sci.SkillMatcher().match_many(["rna-seq counts", "battery cycling"])
        assert out["rna-seq counts"][0] == "bulk-rnaseq"
        assert "battery-cycling" in out["battery cycling"]

    def test_gaps(self):
        gaps = sci.SkillMatcher().gaps("rna-seq docking", threshold=2.0)
        assert isinstance(gaps, list)


# ── Composition ───────────────────────────────────────────────────────────

class TestProvenanceGraph:
    def test_lineage(self):
        graph = sci.ProvenanceGraph()
        graph.record("raw", "ingest", [])
        graph.record("clean", "qc", ["raw"])
        graph.record("table", "analysis", ["clean"])
        assert graph.ancestors("table") == ["clean", "raw"]
        assert [n["artifact"] for n in graph.lineage("table")] == ["raw", "clean", "table"]
        assert graph.unsourced() == ["raw"]

    def test_missing_parents_are_ignored(self):
        graph = sci.ProvenanceGraph()
        graph.record("a", "s", ["ghost"])
        assert "ghost" not in [n["artifact"] for n in graph.lineage("a")]
        assert graph.lineage("unknown") == []


class TestSkillComposer:
    def test_compose_matches_and_orders(self):
        composer = sci.SkillComposer()
        plan = composer.compose("differential expression rna-seq", limit=2)
        assert plan["goal"].startswith("differential")
        assert plan["steps"]
        assert [s["order"] for s in plan["steps"]] == list(range(1, len(plan["steps"]) + 1))
        assert plan["validation_checks"]
        assert plan["provenance"]
        assert isinstance(plan["missing_inputs"], list)

    def test_explicit_skills_respect_dependencies(self):
        composer = sci.SkillComposer()
        plan = composer.compose(
            "any goal", skill_ids=["statistical-analysis", "bulk-rnaseq"],
        )
        assert [s["skill"] for s in plan["steps"]] == ["bulk-rnaseq", "statistical-analysis"]
        assert plan["reasons"]["bulk-rnaseq"] == "explicitly requested"

    def test_topological_order_handles_missing_links(self):
        composer = sci.SkillComposer()
        assert composer.order_skills([]) == []
        assert composer.order_skills(["unknown-skill"]) == []
        ordered = composer.order_skills(["statistical-analysis"])
        assert ordered == ["statistical-analysis"]

    def test_cycle_detection(self):
        library = sci.SkillLibrary([
            sci.SkillSpec("a", "A", "c", ["a"], consumes=["y"], produces=["x"]),
            sci.SkillSpec("b", "B", "c", ["b"], consumes=["x"], produces=["y"]),
        ])
        composer = sci.SkillComposer(library)
        with pytest.raises(ValueError):
            composer.order_skills(["a", "b"])

    def test_compose_with_no_match(self):
        plan = sci.SkillComposer().compose("zzz qqq", limit=2)
        assert plan["steps"] == []
        assert plan["artifacts"] == []


# ── Hypotheses ────────────────────────────────────────────────────────────

class TestHypothesisGenerator:
    def test_supporting_evidence_raises_posterior(self):
        gen = sci.HypothesisGenerator()
        weak = gen.generate("growth rate", "transport", [sci.Observation("weak", 1.2)])
        strong = gen.generate("growth rate", "transport", [sci.Observation("strong", 8.0)])
        assert strong[0].posterior_probability > weak[0].posterior_probability
        assert all(0 < h.posterior_probability < 1 for h in strong)

    def test_hypotheses_are_ranked_and_falsifiable(self):
        hypotheses = sci.HypothesisGenerator().generate(
            "growth rate", "nutrient transport",
            [sci.Observation("dose response", 4.0), sci.Observation("replicated", 3.0)],
        )
        posteriors = [h.posterior_probability for h in hypotheses]
        assert posteriors == sorted(posteriors, reverse=True)
        assert all(h.falsification_test for h in hypotheses)
        assert all(h.evidence for h in hypotheses[:2])
        assert hypotheses[0].as_dict()["posterior"] == pytest.approx(
            round(hypotheses[0].posterior_probability, 4))

    def test_conflicting_evidence_lowers_posterior(self):
        gen = sci.HypothesisGenerator()
        positive = gen.generate("yield", "light", [sci.Observation("up", 5.0)])
        negative = gen.generate("yield", "light", [sci.Observation("down", 1 / 5.0)])
        assert positive[0].posterior_probability > negative[0].posterior_probability

    def test_update_accumulates(self):
        gen = sci.HypothesisGenerator()
        base = gen.generate("yield", "light", [])[0]
        updated = gen.update(base, [sci.Observation("replication", 4.0)])
        assert updated.posterior_probability > base.posterior_probability
        assert len(updated.evidence) == len(base.evidence) + 1


# ── Writing ───────────────────────────────────────────────────────────────

class TestScientificWriter:
    def _writer(self):
        return sci.ScientificWriter([
            sci.EvidenceRecord("e1", "Paper A", "Journal of Tests", "12"),
            sci.EvidenceRecord("e2", "Dataset B", "Zenodo", "0.4"),
        ])

    def test_audit_supported_and_unsupported(self):
        writer = self._writer()
        result = writer.audit([
            sci.Claim("Growth increased by 12%", ["e1"]),
            sci.Claim("The effect always holds", ["e1"]),
            sci.Claim("Uncited statement", []),
            sci.Claim("Referenced but missing", ["e9"]),
        ])
        assert result["claims"] == 4
        assert "Growth increased by 12%" in result["supported"]
        assert "The effect always holds" in result["unsupported"]
        assert result["unknown_evidence"] == ["e9"]
        assert result["traceability"] == pytest.approx(0.25)

    def test_audit_empty(self):
        result = sci.ScientificWriter().audit([])
        assert result["traceability"] == 0.0
        assert result["claims"] == 0

    def test_render_includes_citations_and_references(self):
        writer = self._writer()
        text = writer.render("Findings", [sci.Claim("Growth increased", ["e1", "e9"])])
        assert text.startswith("# Findings")
        assert "[e1]" in text
        assert "[e9]" not in text
        assert "## References" in text
        assert "Paper A" in text and "Dataset B" in text

    def test_add_evidence(self):
        writer = sci.ScientificWriter()
        writer.add_evidence(sci.EvidenceRecord("e3", "Trial C", "Registry"))
        assert writer.audit([sci.Claim("Trial found benefit", ["e3"])])["traceability"] == 1.0


# ── Design ────────────────────────────────────────────────────────────────

class TestExperimentDesigner:
    def test_factorial_expands_all_levels(self):
        designer = sci.ExperimentDesigner()
        rows = designer.factorial({"temperature": ["low", "high"], "ph": [6, 7, 8]})
        assert len(rows) == 6
        assert {row["ph"] for row in rows} == {6, 7, 8}
        assert {row["temperature"] for row in rows} == {"low", "high"}

    def test_randomisation_is_seeded_and_blocked(self):
        designer = sci.ExperimentDesigner()
        rows = designer.factorial({"a": [1, 2], "b": ["x", "y"]})
        first = designer.randomise(rows, blocks=2, seed=5)
        second = designer.randomise(rows, blocks=2, seed=5)
        assert [r.factors for r in first] == [r.factors for r in second]
        assert len(first) == 8
        assert {r.block for r in first} == {1, 2}
        assert [r.run for r in first] == list(range(1, 9))
        assert first[0].as_dict()["run"] == 1

    def test_randomisation_changes_with_seed(self):
        designer = sci.ExperimentDesigner()
        rows = designer.factorial({"a": list(range(6))})
        a = [r.factors for r in designer.randomise(rows, seed=1)]
        b = [r.factors for r in designer.randomise(rows, seed=2)]
        assert a != b

    def test_balance_counts_levels(self):
        designer = sci.ExperimentDesigner()
        rows = designer.factorial({"a": [1, 2], "b": ["x", "y", "z"]})
        balanced = designer.randomise(rows, blocks=3)
        counts = designer.balance(balanced)
        assert counts["a"]["1"] == 9
        assert counts["b"]["x"] == 6

    def test_power_plan(self):
        plan = sci.ExperimentDesigner().power_plan(0.5)
        assert plan["n_per_group"] == 63
        assert plan["total_units"] == 126
        assert plan["alpha"] == 0.05

    def test_bad_blocks_rejected(self):
        with pytest.raises(ValueError):
            sci.ExperimentDesigner().randomise([{"a": 1}], blocks=0)


# ── Engine ────────────────────────────────────────────────────────────────

class TestScientificAgentEngine:
    def test_plan(self):
        payload = sci.engine.plan("differential expression rna-seq")
        assert payload["skills"][0]["skill"] == "bulk-rnaseq"
        assert payload["skills"][0]["why"]
        assert payload["pipeline"]["steps"]

    def test_analyse_groups_two(self):
        result = sci.engine.analyse_groups([[1, 2, 3, 4, 5], [6, 7, 8, 9, 10]])
        assert result["significant"] is True
        assert result["test"] == "welch_t"
        assert result["nonparametric_p"] < 0.05
        assert "p_value" in result

    def test_analyse_groups_many(self):
        result = sci.engine.analyse_groups([[1, 2, 3], [4, 5, 6], [7, 8, 9]])
        assert result["test"] == "anova"
        assert result["significant"] is True
        assert result["effect_size"] > 0.5

    def test_analyse_groups_single(self):
        assert "error" in sci.engine.analyse_groups([[1, 2, 3]])
