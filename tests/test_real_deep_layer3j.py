"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
Tests for IntelX Deep Layer 3j — Intelligence X, IntelBase, Maltego, ShadowDragon
"""

import pytest


class TestIntelXSelector:
    """Test IntelX selector classification and validation."""

    def test_classify_email(self):
        from IntelX.app.agents.real_intelx_osint import IntelXSelector
        s = IntelXSelector(selector="test@example.com", selector_type="email")
        assert s.selector_type == "email"
        assert s.normalized == "test@example.com"

    def test_classify_domain(self):
        from IntelX.app.agents.real_intelx_osint import IntelXSelector
        s = IntelXSelector(selector="example.com", selector_type="domain")
        assert s.selector_type == "domain"

    def test_classify_ip(self):
        from IntelX.app.agents.real_intelx_osint import IntelXSelector
        s = IntelXSelector(selector="192.168.1.1", selector_type="ip")
        assert s.selector_type == "ip"

    def test_classify_cidr(self):
        from IntelX.app.agents.real_intelx_osint import IntelXSelector
        s = IntelXSelector(selector="10.0.0.0/8", selector_type="cidr")
        assert s.selector_type == "cidr"

    def test_classify_phone(self):
        from IntelX.app.agents.real_intelx_osint import IntelXSelector
        s = IntelXSelector(selector="+1-555-123-4567", selector_type="phone")
        assert s.selector_type == "phone"

    def test_classify_bitcoin(self):
        from IntelX.app.agents.real_intelx_osint import IntelXSelector
        s = IntelXSelector(selector="1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2", selector_type="bitcoin")
        assert s.selector_type == "bitcoin"

    def test_classify_sha256(self):
        from IntelX.app.agents.real_intelx_osint import IntelXSelector
        s = IntelXSelector(selector="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", selector_type="sha256")
        assert s.selector_type == "sha256"

    def test_validate_email(self):
        from IntelX.app.agents.real_intelx_osint import IntelXSelector
        valid, error = IntelXSelector.validate("test@example.com")
        assert valid
        assert error == ""

    def test_validate_invalid(self):
        from IntelX.app.agents.real_intelx_osint import IntelXSelector
        valid, error = IntelXSelector.validate("not a valid selector !!!")
        assert not valid
        assert "Unsupported" in error

    def test_classify_unknown(self):
        from IntelX.app.agents.real_intelx_osint import IntelXSelector
        s = IntelXSelector(selector="not_valid!!!", selector_type="unknown")
        assert s.selector_type == "unknown"


class TestIntelXBucket:
    """Test IntelX bucket system."""

    def test_all_buckets(self):
        from IntelX.app.agents.real_intelx_osint import IntelXBucket
        buckets = IntelXBucket.all_buckets()
        assert "pastes" in buckets
        assert "darknet.tor" in buckets
        assert "leaks" in buckets
        assert "whois" in buckets
        assert len(buckets) >= 10

    def test_pro_buckets(self):
        from IntelX.app.agents.real_intelx_osint import IntelXBucket
        pro = IntelXBucket.pro_buckets()
        assert "pastes" in pro
        assert "darknet.tor" in pro
        assert "public_web" not in pro


class TestIntelXSearchEngine:
    """Test IntelX search engine."""

    def test_search_by_email(self):
        from IntelX.app.agents.real_intelx_osint import IntelXSearchEngine, IntelXSearchQuery
        engine = IntelXSearchEngine()
        results = engine.search_by_email("test@example.com")
        assert isinstance(results, list)
        assert all(r.selector == "test@example.com" for r in results)

    def test_search_by_domain(self):
        from IntelX.app.agents.real_intelx_osint import IntelXSearchEngine
        engine = IntelXSearchEngine()
        results = engine.search_by_domain("example.com")
        assert isinstance(results, list)

    def test_search_by_ip(self):
        from IntelX.app.agents.real_intelx_osint import IntelXSearchEngine
        engine = IntelXSearchEngine()
        results = engine.search_by_ip("192.168.1.1")
        assert isinstance(results, list)

    def test_search_invalid_selector(self):
        from IntelX.app.agents.real_intelx_osint import IntelXSearchEngine
        engine = IntelXSearchEngine()
        results = engine.search_by_selector("not valid!!!")
        assert results == []

    def test_search_limit(self):
        from IntelX.app.agents.real_intelx_osint import IntelXSearchEngine, IntelXSearchQuery
        engine = IntelXSearchEngine()
        results = engine.search(IntelXSearchQuery(selector="test@example.com", limit=5))
        assert len(results) <= 5

    def test_search_sort_newest(self):
        from IntelX.app.agents.real_intelx_osint import IntelXSearchEngine, IntelXSearchQuery
        engine = IntelXSearchEngine()
        results = engine.search(IntelXSearchQuery(selector="test@example.com", sort_order="newest"))
        dates = [r.date for r in results]
        assert dates == sorted(dates, reverse=True)

    def test_get_unique_buckets(self):
        from IntelX.app.agents.real_intelx_osint import IntelXSearchEngine
        engine = IntelXSearchEngine()
        engine.search_by_email("test@example.com")
        buckets = engine.get_unique_buckets()
        assert len(buckets) > 0

    def test_get_result_count(self):
        from IntelX.app.agents.real_intelx_osint import IntelXSearchEngine
        engine = IntelXSearchEngine()
        engine.search_by_email("test@example.com")
        assert engine.get_result_count() > 0


class TestIntelXPhonebook:
    """Test IntelX phonebook lookup."""

    def test_search_domains(self):
        from IntelX.app.agents.real_intelx_osint import IntelXPhonebook
        phonebook = IntelXPhonebook()
        results = phonebook.search_domains("example.com")
        assert len(results) > 0
        assert all(r["type"] == "domain" for r in results)

    def test_search_emails(self):
        from IntelX.app.agents.real_intelx_osint import IntelXPhonebook
        phonebook = IntelXPhonebook()
        results = phonebook.search_emails("example.com")
        assert len(results) > 0
        assert all(r["type"] == "email" for r in results)

    def test_search_urls(self):
        from IntelX.app.agents.real_intelx_osint import IntelXPhonebook
        phonebook = IntelXPhonebook()
        results = phonebook.search_urls("example.com")
        assert len(results) > 0
        assert all(r["type"] == "url" for r in results)

    def test_full_lookup(self):
        from IntelX.app.agents.real_intelx_osint import IntelXPhonebook
        phonebook = IntelXPhonebook()
        result = phonebook.lookup("example.com")
        assert "domains" in result
        assert "emails" in result
        assert "urls" in result


class TestIntelBaseEmailLookup:
    """Test IntelBase email lookup."""

    def test_lookup_basic(self):
        from IntelX.app.agents.real_intelx_osint import IntelBaseEmailLookup
        lookup = IntelBaseEmailLookup()
        result = lookup.lookup("test@example.com")
        assert result.query == "test@example.com"
        assert result.query_type == "email"
        assert isinstance(result.accounts, list)
        assert isinstance(result.breaches, list)

    def test_lookup_platforms(self):
        from IntelX.app.agents.real_intelx_osint import IntelBaseEmailLookup
        lookup = IntelBaseEmailLookup()
        result = lookup.lookup("customer@gmail.com")
        assert result.platform_count >= 0
        assert result.breach_count >= 0

    def test_lookup_assessment(self):
        from IntelX.app.agents.real_intelx_osint import IntelBaseEmailLookup
        lookup = IntelBaseEmailLookup()
        result = lookup.lookup("test@example.com")
        assert 0 <= result.assessment.authenticity <= 100
        assert 0 <= result.assessment.exposure <= 100
        assert 0 <= result.assessment.ownership_score <= 5
        assert result.assessment.overall_risk in ("Critical", "High", "Medium", "Low")

    def test_account_structure(self):
        from IntelX.app.agents.real_intelx_osint import IntelBaseEmailLookup
        lookup = IntelBaseEmailLookup()
        result = lookup.lookup("test@example.com")
        for account in result.accounts:
            assert account.platform
            assert account.username
            assert account.account_id


class TestIntelBaseUsernameLookup:
    """Test IntelBase username lookup."""

    def test_lookup_basic(self):
        from IntelX.app.agents.real_intelx_osint import IntelBaseUsernameLookup
        lookup = IntelBaseUsernameLookup()
        result = lookup.lookup("johnsmith")
        assert result.query == "johnsmith"
        assert result.query_type == "username"
        assert isinstance(result.accounts, list)

    def test_lookup_dedup(self):
        from IntelX.app.agents.real_intelx_osint import IntelBaseUsernameLookup
        lookup = IntelBaseUsernameLookup()
        result = lookup.lookup("johnsmith")
        platforms = [a.platform for a in result.accounts]
        assert len(platforms) == len(set(platforms))


class TestEmailPermutator:
    """Test ShadowDragon email permutator."""

    def test_generate_basic(self):
        from IntelX.app.agents.real_intelx_osint import EmailPermutator
        perm = EmailPermutator()
        candidates = perm.generate("John", "Smith")
        assert len(candidates) > 0
        assert all("@" in c.email for c in candidates)

    def test_generate_org_mode(self):
        from IntelX.app.agents.real_intelx_osint import EmailPermutator
        perm = EmailPermutator()
        candidates = perm.generate("John", "Smith", org_domain="company.com", include_org_mode=True)
        org_candidates = [c for c in candidates if c.format == "org-mode"]
        assert len(org_candidates) > 0
        assert all("@company.com" in c.email for c in org_candidates)

    def test_generate_locale_ru(self):
        from IntelX.app.agents.real_intelx_osint import EmailPermutator
        perm = EmailPermutator()
        candidates = perm.generate("Ivan", "Petrov", locale="ru")
        assert len(candidates) > 0
        assert all(c.locale == "ru" for c in candidates)

    def test_validate(self):
        from IntelX.app.agents.real_intelx_osint import EmailPermutator
        perm = EmailPermutator()
        assert perm.validate("test@example.com")
        assert not perm.validate("invalid")

    def test_score(self):
        from IntelX.app.agents.real_intelx_osint import EmailPermutator
        perm = EmailPermutator()
        candidates = perm.generate("John", "Smith")
        scored = perm.score(candidates)
        assert len(scored) > 0
        # Higher confidence first
        for i in range(len(scored) - 1):
            assert scored[i].confidence >= scored[i + 1].confidence


class TestGoogleDorkAssistant:
    """Test ShadowDragon Google dork assistant."""

    def test_generate_filetype(self):
        from IntelX.app.agents.real_intelx_osint import GoogleDorkAssistant
        dork = GoogleDorkAssistant()
        results = dork.generate("confidential report", dork_type="filetype")
        assert len(results) > 0
        assert all("filetype:" in r["dork"] for r in results)

    def test_generate_site(self):
        from IntelX.app.agents.real_intelx_osint import GoogleDorkAssistant
        dork = GoogleDorkAssistant()
        results = dork.generate("target name", dork_type="site")
        assert len(results) > 0
        assert all("site:" in r["dork"] for r in results)

    def test_generate_all(self):
        from IntelX.app.agents.real_intelx_osint import GoogleDorkAssistant
        dork = GoogleDorkAssistant()
        results = dork.generate("research target")
        assert len(results) > 0
        assert all("explanation" in r for r in results)


class TestImageForensics:
    """Test ShadowDragon image forensics."""

    def test_compute_ela(self):
        from IntelX.app.agents.real_intelx_osint import ImageForensics
        ela = ImageForensics()
        result = ela.compute_ela(b"fake_image_data")
        assert "regions" in result
        assert "edited_regions" in result
        assert isinstance(result["regions"], list)

    def test_extract_metadata(self):
        from IntelX.app.agents.real_intelx_osint import ImageForensics
        ela = ImageForensics()
        metadata = ela.extract_metadata(b"fake_image_data")
        assert "camera_make" in metadata
        assert "date_taken" in metadata
        assert "has_exif" in metadata

    def test_compare_images(self):
        from IntelX.app.agents.real_intelx_osint import ImageForensics
        ela = ImageForensics()
        result = ela.compare_images(b"image1", b"image2")
        assert "similarity_percentage" in result
        assert 0 <= result["similarity_percentage"] <= 100


class TestOSINTChecklistGenerator:
    """Test ShadowDragon checklist generator."""

    def test_generate_person(self):
        from IntelX.app.agents.real_intelx_osint import OSINTChecklistGenerator
        gen = OSINTChecklistGenerator()
        result = gen.generate("person")
        assert result["target_type"] == "person"
        assert result["total_steps"] > 0
        assert len(result["steps"]) == result["total_steps"]

    def test_generate_domain(self):
        from IntelX.app.agents.real_intelx_osint import OSINTChecklistGenerator
        gen = OSINTChecklistGenerator()
        result = gen.generate("domain")
        assert result["target_type"] == "domain"

    def test_generate_with_custom(self):
        from IntelX.app.agents.real_intelx_osint import OSINTChecklistGenerator
        gen = OSINTChecklistGenerator()
        result = gen.generate("email", custom_steps=["Check for Telegram", "Check for Signal"])
        assert result["total_steps"] > 10

    def test_mark_step(self):
        from IntelX.app.agents.real_intelx_osint import OSINTChecklistGenerator
        gen = OSINTChecklistGenerator()
        result = gen.generate("person")
        result = gen.mark_step(result, 1)
        assert result["steps"][0]["completed"] is True
        assert "progress_percentage" in result


class TestOpenSourcesToolkit:
    """Test ShadowDragon open sources toolkit."""

    def test_get_sources_all(self):
        from IntelX.app.agents.real_intelx_osint import OpenSourcesToolkit
        toolkit = OpenSourcesToolkit()
        sources = toolkit.get_sources()
        assert len(sources) > 0

    def test_get_sources_category(self):
        from IntelX.app.agents.real_intelx_osint import OpenSourcesToolkit
        toolkit = OpenSourcesToolkit()
        sources = toolkit.get_sources("username")
        assert len(sources) > 0
        assert all("name" in s and "url" in s for s in sources)

    def test_search_sources(self):
        from IntelX.app.agents.real_intelx_osint import OpenSourcesToolkit
        toolkit = OpenSourcesToolkit()
        results = toolkit.search_sources("email")
        assert len(results) > 0


class TestIntelXOSINTEngine:
    """Test unified OSINT engine."""

    def test_search_email(self):
        from IntelX.app.agents.real_intelx_osint import IntelXOSINTEngine
        engine = IntelXOSINTEngine()
        results = engine.search_email("test@example.com")
        assert isinstance(results, list)

    def test_generate_emails(self):
        from IntelX.app.agents.real_intelx_osint import IntelXOSINTEngine
        engine = IntelXOSINTEngine()
        candidates = engine.generate_emails("John", "Smith", org_domain="company.com")
        assert len(candidates) > 0

    def test_generate_dorks(self):
        from IntelX.app.agents.real_intelx_osint import IntelXOSINTEngine
        engine = IntelXOSINTEngine()
        dorks = engine.generate_dorks("research target")
        assert len(dorks) > 0

    def test_analyze_image(self):
        from IntelX.app.agents.real_intelx_osint import IntelXOSINTEngine
        engine = IntelXOSINTEngine()
        result = engine.analyze_image(b"fake_data")
        assert "ela" in result
        assert "metadata" in result

    def test_generate_checklist(self):
        from IntelX.app.agents.real_intelx_osint import IntelXOSINTEngine
        engine = IntelXOSINTEngine()
        checklist = engine.generate_checklist("person")
        assert checklist["total_steps"] > 0

    def test_get_sources(self):
        from IntelX.app.agents.real_intelx_osint import IntelXOSINTEngine
        engine = IntelXOSINTEngine()
        sources = engine.get_sources("domain")
        assert len(sources) > 0

    def test_get_search_stats(self):
        from IntelX.app.agents.real_intelx_osint import IntelXOSINTEngine
        engine = IntelXOSINTEngine()
        engine.search_email("test@example.com")
        stats = engine.get_search_stats()
        assert "total_results" in stats
        assert "unique_buckets" in stats


# ─── Maltego Graph Tests ─────────────────────────────────────────────────────

class TestMaltegoEntity:
    """Test Maltego entity."""

    def test_generate_id(self):
        from IntelX.app.agents.real_maltego_graph import MaltegoEntity
        eid = MaltegoEntity.generate_id("person", "John Smith")
        assert eid.startswith("PER")
        assert len(eid) > 10

    def test_entity_properties(self):
        from IntelX.app.agents.real_maltego_graph import MaltegoEntity
        entity = MaltegoEntity(entity_type="person", entity_value="John")
        entity.add_property("age", 30)
        assert entity.get_property("age") == 30
        assert entity.get_property("missing", "default") == "default"


class TestMaltegoGraph:
    """Test Maltego graph."""

    def test_add_entity(self):
        from IntelX.app.agents.real_maltego_graph import MaltegoGraph, MaltegoEntity
        graph = MaltegoGraph()
        entity = MaltegoEntity(entity_type="person", entity_value="John")
        graph.add_entity(entity)
        assert graph.entity_count == 1
        assert graph.get_entity(entity.entity_id) is not None

    def test_add_relationship(self):
        from IntelX.app.agents.real_maltego_graph import MaltegoGraph, MaltegoEntity, MaltegoRelationship
        graph = MaltegoGraph()
        p1 = MaltegoEntity(entity_type="person", entity_value="John")
        p2 = MaltegoEntity(entity_type="person", entity_value="Jane")
        graph.add_entity(p1)
        graph.add_entity(p2)
        graph.add_relationship(MaltegoRelationship(
            source_id=p1.entity_id, target_id=p2.entity_id, relationship_type="knows"
        ))
        assert graph.relationship_count == 1
        assert len(graph.get_neighbors(p1.entity_id)) == 1

    def test_get_entities_by_type(self):
        from IntelX.app.agents.real_maltego_graph import MaltegoGraph, MaltegoEntity
        graph = MaltegoGraph()
        graph.add_entity(MaltegoEntity(entity_type="person", entity_value="John"))
        graph.add_entity(MaltegoEntity(entity_type="domain", entity_value="example.com"))
        people = graph.get_entities_by_type("person")
        assert len(people) == 1
        domains = graph.get_entities_by_type("domain")
        assert len(domains) == 1

    def test_shortest_path(self):
        from IntelX.app.agents.real_maltego_graph import MaltegoGraph, MaltegoEntity, MaltegoRelationship
        graph = MaltegoGraph()
        a = MaltegoEntity(entity_type="person", entity_value="A")
        b = MaltegoEntity(entity_type="person", entity_value="B")
        c = MaltegoEntity(entity_type="person", entity_value="C")
        for e in (a, b, c):
            graph.add_entity(e)
        graph.add_relationship(MaltegoRelationship(source_id=a.entity_id, target_id=b.entity_id, relationship_type="knows"))
        graph.add_relationship(MaltegoRelationship(source_id=b.entity_id, target_id=c.entity_id, relationship_type="knows"))
        path = graph.shortest_path(a.entity_id, c.entity_id)
        assert path == [a.entity_id, b.entity_id, c.entity_id]

    def test_density(self):
        from IntelX.app.agents.real_maltego_graph import MaltegoGraph, MaltegoEntity
        graph = MaltegoGraph()
        graph.add_entity(MaltegoEntity(entity_type="person", entity_value="A"))
        assert graph.density == 0.0

    def test_connected_components(self):
        from IntelX.app.agents.real_maltego_graph import MaltegoGraph, MaltegoEntity, MaltegoRelationship
        graph = MaltegoGraph()
        a = MaltegoEntity(entity_type="person", entity_value="A")
        b = MaltegoEntity(entity_type="person", entity_value="B")
        c = MaltegoEntity(entity_type="person", entity_value="C")
        for e in (a, b, c):
            graph.add_entity(e)
        graph.add_relationship(MaltegoRelationship(source_id=a.entity_id, target_id=b.entity_id, relationship_type="knows"))
        components = graph.get_connected_components()
        assert len(components) == 2  # {A,B} and {C}

    def test_find_pivots(self):
        from IntelX.app.agents.real_maltego_graph import MaltegoGraph, MaltegoEntity, MaltegoRelationship
        graph = MaltegoGraph()
        a = MaltegoEntity(entity_type="person", entity_value="A")
        b = MaltegoEntity(entity_type="person", entity_value="B")
        graph.add_entity(a)
        graph.add_entity(b)
        graph.add_relationship(MaltegoRelationship(source_id=a.entity_id, target_id=b.entity_id, relationship_type="knows"))
        pivots = graph.find_pivots(a.entity_id, depth=1)
        assert len(pivots) == 1
        assert pivots[0].entity_value == "B"

    def test_export_graph(self):
        from IntelX.app.agents.real_maltego_graph import MaltegoGraph, MaltegoEntity
        graph = MaltegoGraph()
        graph.add_entity(MaltegoEntity(entity_type="person", entity_value="John"))
        export = graph.export_graph()
        assert "entities" in export
        assert "relationships" in export
        assert "stats" in export

    def test_degree_centrality(self):
        from IntelX.app.agents.real_maltego_graph import MaltegoGraph, MaltegoEntity, MaltegoRelationship
        graph = MaltegoGraph()
        a = MaltegoEntity(entity_type="person", entity_value="A")
        b = MaltegoEntity(entity_type="person", entity_value="B")
        graph.add_entity(a)
        graph.add_entity(b)
        graph.add_relationship(MaltegoRelationship(source_id=a.entity_id, target_id=b.entity_id, relationship_type="knows"))
        centrality = graph.compute_degree_centrality()
        assert a.entity_id in centrality
        assert centrality[a.entity_id] > 0


class TestMaltegoTransformRegistry:
    """Test Maltego transform registry."""

    def test_builtin_transforms(self):
        from IntelX.app.agents.real_maltego_graph import MaltegoTransformRegistry
        registry = MaltegoTransformRegistry()
        assert len(registry.transforms) >= 10

    def test_get_transform(self):
        from IntelX.app.agents.real_maltego_graph import MaltegoTransformRegistry
        registry = MaltegoTransformRegistry()
        t = registry.get_transform("email.to.person")
        assert t is not None
        assert t.input_type == "email"

    def test_list_by_input_type(self):
        from IntelX.app.agents.real_maltego_graph import MaltegoTransformRegistry
        registry = MaltegoTransformRegistry()
        email_transforms = registry.list_transforms(input_type="email")
        assert len(email_transforms) > 0
        assert all(t.input_type == "email" for t in email_transforms)

    def test_execute_transform(self):
        from IntelX.app.agents.real_maltego_graph import MaltegoTransformRegistry, MaltegoGraph, MaltegoEntity
        registry = MaltegoTransformRegistry()
        graph = MaltegoGraph()
        email = MaltegoEntity(entity_type="email", entity_value="test@example.com")
        graph.add_entity(email)
        outputs = registry.execute_transform("email.to.person", graph, email.entity_id)
        assert len(outputs) > 0
        assert all(o.entity_type == "person" for o in outputs)


class TestMaltegoGraphAnalyzer:
    """Test Maltego graph analyzer."""

    def test_analyze(self):
        from IntelX.app.agents.real_maltego_graph import MaltegoGraphAnalyzer, MaltegoGraph, MaltegoEntity, MaltegoRelationship
        analyzer = MaltegoGraphAnalyzer()
        graph = MaltegoGraph()
        a = MaltegoEntity(entity_type="person", entity_value="A")
        b = MaltegoEntity(entity_type="person", entity_value="B")
        graph.add_entity(a)
        graph.add_entity(b)
        graph.add_relationship(MaltegoRelationship(source_id=a.entity_id, target_id=b.entity_id, relationship_type="knows"))
        analyzer.load_graph(graph)
        result = analyzer.analyze()
        assert "entity_count" in result
        assert "density" in result
        assert "most_connected" in result

    def test_detect_clusters(self):
        from IntelX.app.agents.real_maltego_graph import MaltegoGraphAnalyzer, MaltegoGraph, MaltegoEntity
        analyzer = MaltegoGraphAnalyzer()
        graph = MaltegoGraph()
        for i in range(3):
            graph.add_entity(MaltegoEntity(entity_type="person", entity_value=f"Person{i}"))
        analyzer.load_graph(graph)
        clusters = analyzer.detect_clusters()
        assert len(clusters) == 3

    def test_find_suspicious_patterns(self):
        from IntelX.app.agents.real_maltego_graph import MaltegoGraphAnalyzer, MaltegoGraph, MaltegoEntity
        analyzer = MaltegoGraphAnalyzer()
        graph = MaltegoGraph()
        graph.add_entity(MaltegoEntity(entity_type="person", entity_value="Isolated"))
        analyzer.load_graph(graph)
        patterns = analyzer.find_suspicious_patterns()
        assert len(patterns) > 0


class TestMalNetEngine:
    """Test MalNet IDS engine."""

    def test_correlate_ip(self):
        from IntelX.app.agents.real_maltego_graph import MalNetEngine
        engine = MalNetEngine()
        result = engine.correlate(ip="192.168.1.1")
        assert len(result["ip_findings"]) > 0

    def test_correlate_domain(self):
        from IntelX.app.agents.real_maltego_graph import MalNetEngine
        engine = MalNetEngine()
        result = engine.correlate(domain="evil.com")
        assert len(result["domain_findings"]) > 0

    def test_correlate_hash(self):
        from IntelX.app.agents.real_maltego_graph import MalNetEngine
        engine = MalNetEngine()
        result = engine.correlate(hash_val="d41d8cd98f00b204e9800998ecf8427e")
        assert len(result["hash_findings"]) > 0


class TestHorizonMonitorEngine:
    """Test Horizon Monitor alert engine."""

    def test_create_username_alert(self):
        from IntelX.app.agents.real_maltego_graph import HorizonMonitorEngine
        engine = HorizonMonitorEngine()
        alert = engine.create_alert_for_username("target_user")
        assert alert.alert_type == "username"
        assert alert.subject == "target_user"
        assert alert.match_count > 0

    def test_create_keyword_alert(self):
        from IntelX.app.agents.real_maltego_graph import HorizonMonitorEngine
        engine = HorizonMonitorEngine()
        alert = engine.create_alert_for_keyword("threat actor")
        assert alert.alert_type == "keyword"
        assert alert.is_critical

    def test_update_alert_status(self):
        from IntelX.app.agents.real_maltego_graph import HorizonMonitorEngine
        engine = HorizonMonitorEngine()
        alert = engine.create_alert_for_username("test")
        assert engine.update_alert_status(alert.alert_id, "resolved")
        assert not alert.is_active

    def test_alert_stats(self):
        from IntelX.app.agents.real_maltego_graph import HorizonMonitorEngine
        engine = HorizonMonitorEngine()
        engine.create_alert_for_username("user1")
        engine.create_alert_for_username("user2")
        engine.create_alert_for_keyword("threat")
        stats = engine.get_alert_stats()
        assert stats["total_alerts"] == 3
        assert stats["open_alerts"] == 3


class TestShadowDragonTrainingCatalog:
    """Test ShadowDragon training catalog."""

    def test_catalog_loaded(self):
        from IntelX.app.agents.real_maltego_graph import ShadowDragonTrainingCatalog
        catalog = ShadowDragonTrainingCatalog()
        assert len(catalog.modules) >= 10

    def test_get_modules_by_category(self):
        from IntelX.app.agents.real_maltego_graph import ShadowDragonTrainingCatalog
        catalog = ShadowDragonTrainingCatalog()
        core = catalog.get_modules("core")
        assert len(core) > 0
        assert all(m.category == "core" for m in core)

    def test_get_module(self):
        from IntelX.app.agents.real_maltego_graph import ShadowDragonTrainingCatalog
        catalog = ShadowDragonTrainingCatalog()
        module = catalog.get_module("osint_101")
        assert module is not None
        assert module.title == "OSINT 101"

    def test_total_training_hours(self):
        from IntelX.app.agents.real_maltego_graph import ShadowDragonTrainingCatalog
        catalog = ShadowDragonTrainingCatalog()
        hours = catalog.get_total_training_hours()
        assert hours > 0

    def test_recommend_learning_path_beginner(self):
        from IntelX.app.agents.real_maltego_graph import ShadowDragonTrainingCatalog
        catalog = ShadowDragonTrainingCatalog()
        path = catalog.recommend_learning_path("beginner")
        assert len(path) >= 3
        assert path[0].title == "OSINT 101"

    def test_recommend_learning_path_advanced(self):
        from IntelX.app.agents.real_maltego_graph import ShadowDragonTrainingCatalog
        catalog = ShadowDragonTrainingCatalog()
        path = catalog.recommend_learning_path("advanced")
        assert len(path) >= 5


class TestMaltegoOSINTEngine:
    """Test unified Maltego + ShadowDragon engine."""

    def test_create_person_graph(self):
        from IntelX.app.agents.real_maltego_graph import MaltegoOSINTEngine
        engine = MaltegoOSINTEngine()
        graph = engine.create_person_graph("John Smith", email="john@example.com", company="ACME Corp")
        assert graph.entity_count >= 3

    def test_run_transform_chain(self):
        from IntelX.app.agents.real_maltego_graph import MaltegoOSINTEngine
        engine = MaltegoOSINTEngine()
        engine.create_person_graph("John Smith")
        person = engine.graph.get_entities_by_type("person")[0]
        outputs = engine.run_transform_chain(["person.to.company"], person.entity_id)
        assert len(outputs) > 0

    def test_analyze_graph(self):
        from IntelX.app.agents.real_maltego_graph import MaltegoOSINTEngine
        engine = MaltegoOSINTEngine()
        engine.create_person_graph("John Smith", email="john@example.com")
        analysis = engine.analyze_graph()
        assert "entity_count" in analysis

    def test_get_learning_path(self):
        from IntelX.app.agents.real_maltego_graph import MaltegoOSINTEngine
        engine = MaltegoOSINTEngine()
        path = engine.get_learning_path("beginner")
        assert len(path) > 0

    def test_get_graph_stats(self):
        from IntelX.app.agents.real_maltego_graph import MaltegoOSINTEngine
        engine = MaltegoOSINTEngine()
        engine.create_person_graph("John Smith")
        stats = engine.get_graph_stats()
        assert stats["entity_count"] > 0
        assert stats["registered_transforms"] >= 10

    def test_create_alert(self):
        from IntelX.app.agents.real_maltego_graph import MaltegoOSINTEngine
        engine = MaltegoOSINTEngine()
        alert = engine.create_alert("target_user")
        assert alert.subject == "target_user"

    def test_alert_stats(self):
        from IntelX.app.agents.real_maltego_graph import MaltegoOSINTEngine
        engine = MaltegoOSINTEngine()
        engine.create_alert("user1")
        engine.create_alert("user2")
        stats = engine.get_alert_stats()
        assert stats["total_alerts"] == 2
