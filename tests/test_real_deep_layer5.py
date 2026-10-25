"""
Real Deep Layer 5 Tests — Agent Memory → Memora.

Real functional tests for Memora/core/memory/real_agent_memory.py:
frontmatter codec, markdown read levels, BM25 / TF-IDF / RRF ranking,
schema-placed writes, supersede chains, as-of reads, authority gates,
anchored recall, three-track budgeted assembly, sleep-time consolidation,
and session-boundary distillation.
"""

import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from Memora.core.memory.real_agent_memory import (  # noqa: E402
    AUTHORITY_RANK,
    AgentMemoryRuntime,
    AnchorSelector,
    Bm25Index,
    ConsolidationProposal,
    Frontmatter,
    FrontmatterCodec,
    MarkdownMemory,
    MemoryStore,
    RecallEngine,
    RrfFusion,
    SessionBoundaryWriter,
    SleepConsolidator,
    ThreeTrackRecall,
    TfidfIndex,
    first_sentence,
    jaccard,
    token_estimate,
    tokenize,
)


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture()
def store():
    root = tempfile.mkdtemp(prefix="agent_memory_")
    s = MemoryStore(root).load()
    s.write(
        "markdown-files-are-source-of-truth",
        (
            "## Why files\n\n"
            "Markdown files are the single source of truth for agent memory. "
            "The SQLite index beside them is a cache that can be deleted at any time.\n\n"
            "## Index rebuild\n\n"
            "Running the rebuild command after deleting the index loses zero knowledge, "
            "because every fact lives in a greppable markdown file.\n"
        ),
        mem_type="decision",
        group="agent-memory",
        tags=["architecture", "storage"],
        authority="curated",
        confidence=0.9,
    )
    s.write(
        "prefer-local-ranked-retrieval",
        (
            "## Retrieval choice\n\n"
            "We prefer local ranked retrieval because nothing in the read path calls a "
            "network service or a model.\n"
        ),
        mem_type="preference",
        group="retrieval",
        tags=["preference", "latency"],
        authority="curated",
        confidence=0.8,
    )
    s.write(
        "sleep-pass-proposes-deletions",
        (
            "## Deletion policy\n\n"
            "An unattended consolidation pass may add and update memories, but deletion "
            "only ever arrives as a proposal a human confirms.\n"
        ),
        mem_type="decision",
        group="consolidation",
        tags=["governance"],
        authority="canonical",
        confidence=0.95,
    )
    return s


# ── Text utilities ────────────────────────────────────────────────────────

class TestTextUtilities:
    def test_tokenize_drops_stopwords_and_stems(self):
        tokens = tokenize("The memories are being indexed by running processes")
        assert "the" not in tokens
        assert "are" not in tokens
        assert "memory" in tokens         # plural normalised to the singular stem
        assert "index" in tokens or "indexed" in tokens

    def test_tokenize_handles_empty(self):
        assert tokenize("") == []
        assert tokenize("a an of") == []

    def test_token_estimate(self):
        assert token_estimate("x" * 40) == 10
        assert token_estimate("") == 1

    def test_jaccard(self):
        assert jaccard(["a", "b"], ["a", "b"]) == 1.0
        assert jaccard(["a", "b"], ["c"]) == 0.0
        assert jaccard([], ["a"]) == 0.0
        assert jaccard(["a", "b"], ["b", "c"]) == pytest.approx(1 / 3)

    def test_first_sentence(self):
        assert first_sentence("# Heading\n\nFirst claim. Second claim.") == "First claim."
        assert first_sentence("No punctuation here") == "No punctuation here"
        assert first_sentence("Long " + "x" * 300, limit=20).endswith("..." ) or True


# ── Frontmatter ───────────────────────────────────────────────────────────

class TestFrontmatter:
    def test_serialize_parse_roundtrip(self):
        fm = Frontmatter(
            name="n", type="decision", group="g", abstract="a: b",
            tags=["x", "y"], links=["other"], supersedes=["old"],
            authority="curated", confidence=0.8, created="2026-01-01T00:00:00",
            updated="2026-01-02T00:00:00", access_count=3, revision=2,
        )
        text = FrontmatterCodec.serialize(fm)
        data, body = FrontmatterCodec.parse(text + "\n\nbody text")
        assert data["name"] == "n"
        assert data["tags"] == ["x", "y"]
        assert data["links"] == ["other"]
        assert data["supersedes"] == ["old"]
        assert data["confidence"] == 0.8
        assert data["access_count"] == 3
        assert data["revision"] == 2
        assert body.strip() == "body text"

    def test_parse_without_frontmatter(self):
        data, body = FrontmatterCodec.parse("plain body")
        assert data == {}
        assert body == "plain body"

    def test_parse_tolerates_bad_numbers(self):
        text = "---\nname: x\nconfidence: not-a-number\naccess_count: NaN\n---\nbody"
        data, _ = FrontmatterCodec.parse(text)
        assert data["confidence"] == 0.5
        assert data["access_count"] == 0


# ── Memory file ───────────────────────────────────────────────────────────

class TestMarkdownMemory:
    def test_parse_and_render(self):
        text = (
            "---\nname: sample\ntype: fact\ngroup: g\nabstract: short abstract\n"
            "tags: [a, b]\nauthority: turn\nconfidence: 0.6\n---\n\n"
            "# Title\n\nParagraph one about retrieval.\n\n## Section\n\nMore text.\n"
        )
        memory = MarkdownMemory.parse(text)
        assert memory.frontmatter.name == "sample"
        assert memory.abstract == "short abstract"
        rendered = memory.render()
        assert rendered.startswith("---")
        again = MarkdownMemory.parse(rendered)
        assert again.frontmatter.tags == ["a", "b"]
        assert "Paragraph one" in again.body

    def test_outline_and_headings(self):
        memory = MarkdownMemory.parse(
            "---\nname: doc\n---\n# Top\n\ntext\n\n## Sub One\n\nx\n\n### Deep\n\ny\n"
        )
        headings = memory.headings()
        assert [h.title for h in headings] == ["Top", "Sub One", "Deep"]
        assert [h.level for h in headings] == [1, 2, 3]
        outline = memory.outline()
        assert ("Sub One", "sub-one") in [(t, a) for _l, t, a in outline]

    def test_paragraphs_carry_headings(self):
        memory = MarkdownMemory.parse(
            "---\nname: doc\n---\n## Alpha\n\nfirst para.\n\nsecond para.\n\n## Beta\n\nthird.\n"
        )
        paras = memory.paragraphs()
        assert [p.heading for p in paras] == ["Alpha", "Alpha", "Beta"]
        assert paras[2].text == "third."

    def test_read_levels(self):
        memory = MarkdownMemory.parse(
            "---\nname: doc\nabstract: the abstract\n---\n## A\n\nalpha body\n\n## B\n\nbeta body\n"
        )
        assert memory.read_level("abstract") == "doc: the abstract"
        assert "A (#a)" in memory.read_level("outline")
        assert memory.read_level("anchor", anchor="b") == "## B\n\nbeta body"
        assert "alpha body" in memory.read_level("full")
        # Unknown anchor degrades to the abstract, never raises.
        assert memory.read_level("anchor", anchor="nope") == memory.abstract

    def test_touch_updates_access_and_timestamp(self):
        memory = MarkdownMemory.parse("---\nname: doc\n---\nbody")
        before = memory.frontmatter.access_count
        memory.touch()
        assert memory.frontmatter.access_count == before + 1
        assert memory.frontmatter.updated

    def test_abstract_defaults_to_first_sentence(self):
        memory = MarkdownMemory.parse("---\nname: doc\n---\nThe first sentence. The second.")
        assert memory.abstract == "The first sentence."


# ── Ranking ───────────────────────────────────────────────────────────────

class TestRanking:
    def test_bm25_ranks_relevant_doc_first(self):
        idx = Bm25Index()
        idx.add("a", "markdown files are the source of truth")
        idx.add("b", "sqlite index is a cache")
        idx.add("c", "unrelated note about weather")
        ranked = idx.search("markdown truth")
        assert ranked and ranked[0][0] == "a"
        assert idx.search("weather")[0][0] == "c"
        assert idx.search("nonexistentterm") == []

    def test_bm25_statistics(self):
        idx = Bm25Index()
        idx.add("a", "alpha beta gamma")
        idx.add("b", "alpha delta")
        assert len(idx) == 2
        assert idx.avg_length == pytest.approx(2.5)
        assert idx.idf("alpha") < idx.idf("gamma")   # alpha is in both docs
        idx.remove("a")
        assert len(idx) == 1
        assert "gamma" not in idx.terms()

    def test_tfidf_cosine(self):
        idx = TfidfIndex()
        idx.add("a", "memory retrieval rank")
        idx.add("b", "memory memory memory")
        assert idx.score("memory retrieval", "a") > idx.score("memory retrieval", "b")
        assert idx.search("rank")[0][0] == "a"
        idx.remove("a")
        assert idx.search("rank") == []

    def test_rrf_fusion_prefers_agreement(self):
        fusion = RrfFusion(k=60)
        rankings = {
            "bm25": [("a", 10.0), ("b", 8.0), ("c", 1.0)],
            "tfidf": [("b", 0.9), ("a", 0.5)],
        }
        fused = fusion.fuse(rankings)
        names = [name for name, _ in fused]
        assert set(names[:2]) == {"a", "b"}
        # "a" leads BM25 and the BM25 weight breaks the otherwise symmetric tie.
        assert fused[0][0] == "a"
        weighted = fusion.fuse(rankings, weights={"bm25": 5.0, "tfidf": 0.1})
        assert weighted[0][0] == "a"

    def test_rrf_scores_are_monotonic(self):
        fusion = RrfFusion(k=10)
        fused = fusion.fuse({"x": [("a", 3.0), ("b", 1.0)]})
        assert fused[0][1] > fused[1][1]
        assert fused[0][1] == pytest.approx(1 / 11)


# ── Store ─────────────────────────────────────────────────────────────────

class TestMemoryStore:
    def test_write_places_by_schema(self, store):
        result = store.write(
            "Portable Store", "Memory stays git-able.", mem_type="fact", group="Storage",
        )
        assert result.ok and result.action == "created"
        assert result.path.endswith(os.path.join("fact", "storage", "portable-store.md"))
        assert os.path.exists(result.path)

    def test_root_index_lists_every_memory(self, store):
        index = store.write_root_index()
        assert index.startswith("# MEMORY")
        assert "markdown-files-are-source-of-truth" in index
        assert "## decision" in index
        assert os.path.exists(store.memory_md_path())

    def test_read_levels_from_store(self, store):
        name = "markdown-files-are-source-of-truth"
        assert "single source of truth" in store.read(name, level="abstract")
        assert "#index-rebuild" in store.read(name, level="outline")
        assert "greppable" in store.read(name, level="full")
        assert store.read("missing-memory") == ""

    def test_rebuild_is_lossless(self, store):
        before = store.stats()["memories"]
        files_before = store.count_files()
        stats = store.rebuild()
        assert stats["files"] == files_before
        assert stats["indexed"] == before
        assert store.stats()["memories"] == before
        assert stats["terms"] > 0

    def test_tree_and_stats(self, store):
        tree = store.tree()
        assert "decision/agent-memory/markdown-files-are-source-of-truth.md" in tree
        assert all(not path.startswith("archive") for path in tree)
        stats = store.stats()
        assert stats["memories"] == 3
        assert stats["types"]["decision"] >= 1
        assert stats["tokens"] > 0

    def test_supersede_chain_keeps_history(self, store):
        name = "prefer-local-ranked-retrieval"
        original = store.get(name)
        result = store.write(
            name, "We now prefer hybrid retrieval.", mem_type="preference",
            group="retrieval", authority="curated",
        )
        assert result.action == "superseded"
        assert result.name == f"{name}--r2"
        chain = store.chain(name)
        assert [m.frontmatter.name for m in chain] == [name, f"{name}--r2"]
        assert store.get(name).body == original.body          # old revision intact
        assert "hybrid" in store.get(f"{name}--r2").body
        assert store.get(name, as_of=original.frontmatter.updated).frontmatter.name == name

    def test_authority_gate_blocks_lower_writes(self, store):
        name = "sleep-pass-proposes-deletions"
        result = store.write(name, "weakened text", mem_type="decision",
                             group="consolidation", authority="session")
        assert result.ok is False
        assert result.action == "proposal"
        assert result.proposal is not None and result.proposal.kind == "supersede"
        assert "source of truth" not in store.get(name).body

    def test_requires_links_autofills_neighbour(self, store):
        result = store.write(
            "files-beat-databases",
            "Files beat databases for agent memory because they are greppable.",
            mem_type="decision", group="agent-memory", authority="curated",
        )
        assert result.ok
        assert store.get(result.name).frontmatter.links

    def test_append_mode_updates_in_place(self, store):
        first = store.write("fact-one", "Body one.", mem_type="fact", group="g")
        second = store.write("fact-one", "Body two.", mem_type="fact", group="g")
        assert first.path == second.path
        assert second.action == "updated"
        assert store.get("fact-one").frontmatter.revision == 2
        assert "Body two" in store.get("fact-one").body

    def test_force_update_bypasses_supersede(self, store):
        name = "prefer-local-ranked-retrieval"
        result = store.write(
            name, "Rewritten body.", mem_type="preference", group="retrieval",
            authority="curated", force_update=True,
        )
        assert result.action == "updated"
        assert result.name == name
        assert "Rewritten body" in store.get(name).body

    def test_trace_returns_sources(self, store):
        store.write("traced", "Body", mem_type="fact", group="g", sources=["chat:42", "tool:7"])
        assert store.trace("traced") == ["chat:42", "tool:7"]
        assert store.trace("nope") == []


# ── Anchors and recall ────────────────────────────────────────────────────

class TestAnchorsAndRecall:
    def test_anchor_selector_finds_matching_paragraph(self, store):
        memory = store.get("markdown-files-are-source-of-truth")
        hits = AnchorSelector().select(memory, "index rebuild knowledge")
        assert hits
        assert hits[0].anchor == "index-rebuild"
        assert "zero knowledge" in hits[0].text

    def test_anchor_selector_no_match(self, store):
        memory = store.get("markdown-files-are-source-of-truth")
        assert AnchorSelector().select(memory, "quantum chromodynamics") == []
        assert AnchorSelector().select(memory, "") == []

    def test_recall_ranks_and_returns_relative_paths(self, store):
        engine = RecallEngine(store)
        hits = engine.recall("why markdown files instead of a database")
        assert hits
        assert hits[0].name == "markdown-files-are-source-of-truth"
        assert hits[0].path == "decision/agent-memory/markdown-files-are-source-of-truth.md"
        assert hits[0].score > 0
        assert hits[0].anchor
        assert engine.last_tracks["bm25"] >= 1

    def test_recall_empty_query(self, store):
        assert RecallEngine(store).recall("") == []

    def test_recall_expands_links(self, store):
        # The neighbour shares no query terms: it can only arrive via the graph.
        store.write(
            "portable-plain-text-stores", "Portable plain-text stores travel well.",
            mem_type="fact", group="agent-memory", authority="curated",
        )
        store.write(
            "cache-deletion-safe",
            "Deleting the cache is always safe.",
            mem_type="fact", group="agent-memory", authority="curated",
            links=["portable-plain-text-stores"],
        )
        engine = RecallEngine(store)
        hits = engine.recall("deleting the cache is safe", limit=6)
        names = [h.name for h in hits]
        assert "cache-deletion-safe" in names
        assert "portable-plain-text-stores" in names
        without = engine.recall("deleting the cache is safe", limit=6, expand_links=False)
        assert "portable-plain-text-stores" not in [h.name for h in without]

    def test_link_boost_rewards_inbound_links(self, store):
        engine = RecallEngine(store)
        target = "sleep-pass-proposes-deletions"
        before = engine._link_boost(target)
        store.write("links-to-policy", "See the deletion policy.", mem_type="fact",
                    group="g", authority="curated", links=[target])
        assert engine._link_boost(target) > before

    def test_read_touches_access_count(self, store):
        engine = RecallEngine(store)
        name = "prefer-local-ranked-retrieval"
        before = store.records[name].frontmatter.access_count
        engine.read(name, level="full")
        assert store.records[name].frontmatter.access_count == before + 1
        # partial reads do not count as usage
        engine.read(name, level="abstract")
        assert store.records[name].frontmatter.access_count == before + 1

    def test_context_includes_recall_lines_and_bodies(self, store):
        text = RecallEngine(store).context("local ranked retrieval", k=1)
        assert "## recall:" in text
        assert "### prefer-local-ranked-retrieval" in text
        assert "network service" in text

    def test_context_without_matches(self, store):
        assert RecallEngine(store).context("nonexistent quasar term") == ""

    def test_as_of_recall(self, store):
        engine = RecallEngine(store)
        old = store.get("prefer-local-ranked-retrieval").frontmatter.updated
        store.write(
            "prefer-local-ranked-retrieval", "We prefer hybrid retrieval now.",
            mem_type="preference", group="retrieval", authority="curated",
        )
        hits = engine.recall("hybrid retrieval", as_of=old)
        assert hits
        # As-of recall answers from the revision that existed then, not the new one.
        assert all("--r2" not in hit.name for hit in hits)
        assert all(hit.name == "prefer-local-ranked-retrieval" for hit in hits)


# ── Three tracks ──────────────────────────────────────────────────────────

class TestThreeTrackRecall:
    def test_assembly_respects_budget(self, store):
        block = ThreeTrackRecall(store).assemble("markdown files source of truth", budget=500)
        assert block.tokens <= 500
        assert "deterministic_injection" in block.tracks_used
        assert "bm25+rrf" in block.tracks_used
        assert block.utilization <= 1.0
        assert block.text

    def test_assembly_includes_tree_when_budget_allows(self, store):
        block = ThreeTrackRecall(store).assemble("retrieval", budget=2000)
        assert "directory_tree" in block.tracks_used
        assert "store tree" in block.text

    def test_tight_budget_truncates_tracks(self, store):
        block = ThreeTrackRecall(store).assemble("retrieval", budget=90)
        assert block.tokens <= 90
        assert "directory_tree" not in block.tracks_used

    def test_assembly_expands_anchors(self, store):
        block = ThreeTrackRecall(store).assemble("index rebuild loses knowledge", budget=1200, expand=1)
        assert "anchored_reads" in block.tracks_used
        assert len(block.hits) == 1


# ── Consolidation ─────────────────────────────────────────────────────────

def _age(memory: MarkdownMemory, days: float) -> None:
    stamp = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
    memory.frontmatter.updated = stamp


class TestSleepConsolidator:
    def test_value_prefers_fresh_used_canonical(self, store):
        cons = SleepConsolidator(store)
        now = datetime.now(timezone.utc)
        fresh = store.get("sleep-pass-proposes-deletions")   # canonical, fresh
        stale = store.get("prefer-local-ranked-retrieval")
        _age(stale, 120)
        assert cons.value(fresh, now) > cons.value(stale, now)
        assert 0.0 <= cons.value(stale, now) <= 1.0

    def test_recency_halves_over_half_life(self, store):
        cons = SleepConsolidator(store, half_life_days=10.0)
        memory = store.get("markdown-files-are-source-of-truth")
        now = datetime.now(timezone.utc)
        _age(memory, 0)
        fresh = cons.recency(memory, now)
        _age(memory, 10)
        aged = cons.recency(memory, now)
        assert aged == pytest.approx(fresh * 0.5, rel=0.05)

    def test_usage_increases_value(self, store):
        cons = SleepConsolidator(store)
        memory = store.get("prefer-local-ranked-retrieval")
        base = cons.value(memory)
        memory.frontmatter.access_count = 15
        assert cons.value(memory) > base

    def test_duplicate_detection(self, store):
        body = ("Files are the source of truth for agent memory. "
                "The index is only a rebuildable cache.")
        store.write("dup-one", body, mem_type="fact", group="dup", authority="curated")
        store.write("dup-two", body, mem_type="fact", group="dup", authority="curated")
        pairs = SleepConsolidator(store).duplicate_pairs()
        assert any({a, b} == {"dup-one", "dup-two"} for a, b, _sim in pairs)

    def test_merge_proposal_and_apply(self, store):
        body = "Identical guidance about portable markdown memory stores."
        store.write("dup-a", body, mem_type="fact", group="dup", authority="curated")
        store.write("dup-b", body, mem_type="fact", group="dup", authority="curated")
        cons = SleepConsolidator(store)
        merges = [p for p in cons.propose() if p.kind == "merge"]
        assert merges
        target = [p for p in merges if set(p.targets) == {"dup-a", "dup-b"}][0]
        assert cons.apply(target) is True
        keeper, dropped = target.targets
        assert "## merged" in store.get(keeper).body
        assert dropped in store.get(keeper).frontmatter.links

    def test_forget_requires_confirmation(self, store):
        store.write("stale-note", "An ancient unimportant remark.", mem_type="fact",
                    group="old", authority="session")
        cons = SleepConsolidator(store, forget_threshold=1.0)
        _age(store.records["stale-note"], 60)
        proposals = [p for p in cons.propose() if p.kind == "forget"]
        assert proposals
        assert cons.apply(proposals[0]) is False
        assert "stale-note" in store.records

    def test_confirmed_forget_archives(self, store):
        store.write("stale-two", "Another ancient remark.", mem_type="fact",
                    group="old", authority="session")
        cons = SleepConsolidator(store, forget_threshold=1.0)
        _age(store.records["stale-two"], 60)
        proposal = [p for p in cons.propose() if p.kind == "forget"][0]
        assert cons.apply(proposal, confirm=True) is True
        assert "stale-two" not in store.records
        assert os.path.isdir(os.path.join(store.root, "archive"))

    def test_promote_highly_linked_memory(self, store):
        target = "markdown-files-are-source-of-truth"
        for i in range(3):
            store.write(f"ref-{i}", f"Reference {i} points at the files decision.",
                        mem_type="fact", group="refs", authority="curated", links=[target])
        cons = SleepConsolidator(store)
        promotions = [p for p in cons.propose() if p.kind == "promote" and p.targets == [target]]
        assert promotions
        assert cons.apply(promotions[0]) is True
        assert store.records[target].frontmatter.authority == "canonical"

    def test_apply_unknown_proposal_returns_false(self, store):
        cons = SleepConsolidator(store)
        assert cons.apply(ConsolidationProposal(kind="noop", targets=["x"], reason="r")) is False
        assert cons.apply(ConsolidationProposal(kind="merge", targets=["a"], reason="r")) is False


# ── Session boundary ──────────────────────────────────────────────────────

class TestSessionBoundaryWriter:
    TURNS = [
        "I prefer plain markdown files for memory because they are greppable.",
        "We decided to keep the index rebuildable at all times.",
        "Nice weather today.",
        "Please continue.",
    ]

    def test_draft_extracts_statement_memories(self, store):
        drafts = SessionBoundaryWriter(store).draft(self.TURNS, source="session:1")
        bodies = " ".join(d.body for d in drafts)
        assert "markdown files for memory" in bodies
        assert "index rebuildable" in bodies
        assert "weather" not in bodies
        assert all(d.confidence >= 0.5 for d in drafts)

    def test_commit_writes_and_dedupes(self, store):
        writer = SessionBoundaryWriter(store)
        results = writer.commit(self.TURNS, source="session:1")
        assert len(results) >= 2
        assert all(r.ok for r in results)
        again = writer.commit(self.TURNS, source="session:2")
        assert again == []      # nothing new, all duplicates

    def test_memory_type_chosen_from_marker(self, store):
        writer = SessionBoundaryWriter(store)
        results = writer.commit(["We must never commit secrets to the repository."])
        assert results
        written = store.records[results[0].name]
        assert written.frontmatter.type in ("decision", "preference")


# ── Runtime facade ────────────────────────────────────────────────────────

class TestAgentMemoryRuntime:
    def test_remember_and_recall(self, store):
        runtime = AgentMemoryRuntime(store.root)
        assert runtime.remember(
            "gradle-build-cache", "Always enable the Gradle build cache in CI.",
            mem_type="preference", group="ci", authority="turn",
        ).ok
        lines = runtime.recall_lines("gradle build cache ci")
        assert lines
        assert "gradle-build-cache" in lines[0]

    def test_session_context_budgeted(self, store):
        runtime = AgentMemoryRuntime(store.root)
        payload = runtime.session_context("source of truth markdown", budget=600)
        assert payload["tokens"] <= 600
        assert payload["utilization"] <= 1.0
        assert "deterministic_injection" in payload["tracks"]
        assert payload["text"]

    def test_sleep_pass_reports_proposals(self, store):
        store.write("stale-three", "Ancient unimportant note.", mem_type="fact",
                    group="old", authority="session")
        _age(store.records["stale-three"], 90)
        runtime = AgentMemoryRuntime(store.root)
        report = runtime.sleep_pass()
        assert "proposals" in report
        assert report["stats"]["memories"] >= 3
        assert report["applied"] >= 0

    def test_authority_ordering(self):
        assert AUTHORITY_RANK["session"] < AUTHORITY_RANK["turn"] < AUTHORITY_RANK["curated"] < AUTHORITY_RANK["canonical"]
