"""
Real Deep Layer 10 Tests — OpenViking → Memora.

Real functional tests for Memora/core/memory/real_viking_context.py:
viking:// path handling, L0/L1/L2 projection, the virtual filesystem with
generated directory summaries, BM25 ranking, scoped search, sessions,
memory extraction, session commits with supersede, and wiki compilation.
"""

import importlib.util
import os
import sys

import pytest

MODULE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "Memora", "core", "memory", "real_viking_context.py")

spec = importlib.util.spec_from_file_location("real_viking_context", MODULE_PATH)
vk = importlib.util.module_from_spec(spec)
sys.modules["real_viking_context"] = vk
spec.loader.exec_module(vk)

ARCH = ("# Architecture\n\nThe staging database is Postgres 16.\n\n"
        "- API: FastAPI\n- Queue: Redis\n")
API = ("# API notes\n\nAll endpoints return envelopes.\n\n"
       "See [[Architecture]] for the deployment picture.\n")
RUNBOOK = "# On-call runbook\n\nCheck dashboards first.\n"


@pytest.fixture()
def fs():
    tree = vk.VikingFS()
    tree.write("viking://resources/design/architecture.md", ARCH,
               tags=("design", "infra"))
    tree.write("viking://resources/design/api.md", API, tags=("api",))
    tree.write("viking://resources/runbooks/oncall.md", RUNBOOK, tags=("ops",))
    return tree


def _session(session_id="s-001", user="alice"):
    return vk.Session(session_id, user)


def _populated_session():
    session = _session()
    session.add("user", "I prefer dark mode in all dashboards.")
    session.add("user", "We decided to use Postgres 16 for staging.")
    session.add("assistant", "Thanks!")
    session.add("user", "Remember to rotate the API keys weekly.")
    session.add("user", "The staging database is Postgres 16.")
    session.add("tool", "grep output")
    return session


# ── Paths ─────────────────────────────────────────────────────────────────

class TestVikingPath:
    def test_parse_and_uri(self):
        path = vk.VikingPath.parse("viking://resources/design/architecture.md")
        assert path.segments == ("resources", "design", "architecture.md")
        assert path.uri == "viking://resources/design/architecture.md"
        assert path.name == "architecture.md"
        assert path.scope == "resources"
        assert path.is_root is False
        assert path.parent.uri == "viking://resources/design"

    def test_root_and_trailing_slash(self):
        root = vk.VikingPath.parse("viking://")
        assert root.is_root is True
        assert root.segments == ()
        assert root.parent is None
        assert root.uri == "viking://"
        assert vk.VikingPath.parse("viking://user/").segments == ("user",)
        assert vk.VikingPath.parse("  viking://a/b  ").segments == ("a", "b")

    @pytest.mark.parametrize("bad", [
        "http://resources/a.md",
        "resources/a.md",
        "",
        "viking://a/../b",
        "viking://a/./b",
        "viking://a//b",
        "viking://a b/c",
    ])
    def test_rejects_bad_uris(self, bad):
        with pytest.raises(ValueError):
            vk.VikingPath.parse(bad)

    def test_child_and_relative(self):
        parent = vk.VikingPath.parse("viking://user/alice")
        child = parent.child("memories")
        assert child.uri == "viking://user/alice/memories"
        with pytest.raises(ValueError):
            parent.child("bad/name")
        with pytest.raises(ValueError):
            parent.child("")
        deep = vk.VikingPath.parse("viking://user/alice/sessions/s-001.md")
        assert deep.relative_to(parent) == ("sessions", "s-001.md")
        assert deep.is_inside(parent) is True
        assert parent.is_inside(deep) is False
        with pytest.raises(ValueError):
            parent.relative_to(deep)

    def test_string_and_frozen(self):
        path = vk.VikingPath.parse("viking://resources")
        assert str(path) == "viking://resources"
        with pytest.raises(Exception):
            path.segments = ("nope",)  # frozen dataclass


# ── Projection ────────────────────────────────────────────────────────────

class TestProjection:
    def test_strip_and_parse_frontmatter(self):
        text = "---\nkey: a\ntitle: A page\ntags: x, y\n---\n\n# Heading\n\nBody.\n"
        assert vk.strip_frontmatter(text).startswith("\n# Heading")
        fields = vk.parse_frontmatter(text)
        assert fields == {"key": "a", "title": "A page", "tags": "x, y"}
        assert vk.parse_frontmatter("# no frontmatter") == {}
        assert vk.strip_frontmatter("plain") == "plain"

    def test_abstract_skips_frontmatter_and_headings(self):
        text = "---\ntitle: X\n---\n\n# Heading\n\nFirst body sentence here. Second one.\n"
        assert vk.abstract_of(text) == "First body sentence here. Second one."
        assert vk.abstract_of("") == ""
        assert vk.abstract_of("# Only a heading") == "Only a heading"
        assert vk.abstract_of("x" * 300).endswith("…")
        assert len(vk.abstract_of("word " * 100, max_chars=40)) <= 41

    def test_collapse_and_first_sentence(self):
        assert vk.collapse("a   b\n c") == "a b c"
        assert vk.first_sentence("One. Two.") == "One."

    def test_overview(self):
        text = ("---\ntitle: X\n---\n\n# Heading\n\nIntro paragraph.\n\n"
                "- bullet one\n- bullet two\n\nOther prose ignored.\n")
        overview = vk.overview_of(text)
        assert overview.splitlines()[0] == "# Heading"
        assert "- bullet one" in overview
        assert "- bullet two" in overview
        assert "Other prose" not in overview
        assert len(vk.overview_of(text, max_lines=1).splitlines()) == 1
        assert vk.overview_of("") == ""

    def test_projector_levels(self):
        text = "# H\n\nBody sentence.\n\n- bullet\n"
        assert vk.PROJECTOR.project(text, "L0") == "Body sentence."
        assert vk.PROJECTOR.project(text, "L1").startswith("# H")
        assert vk.PROJECTOR.project(text, "L2") == text
        assert vk.PROJECTOR.project(text, "l0") == "Body sentence."
        assert vk.PROJECTOR.describe()["L2"] == "full"
        with pytest.raises(ValueError):
            vk.PROJECTOR.project(text, "L9")

    def test_glob_match(self):
        assert vk.glob_match("*.md", "a.md") is True
        assert vk.glob_match("a?c", "abc") is True
        assert vk.glob_match("*.py", "a.md") is False


# ── Filesystem ────────────────────────────────────────────────────────────

class TestVikingFS:
    def test_write_creates_parents(self):
        tree = vk.VikingFS()
        node = tree.write("viking://user/alice/memories/fact/a.md", "hello", tags=("fact",))
        assert node.is_dir is False
        assert node.path.name == "a.md"
        assert tree.exists("viking://user/alice/memories/fact")
        assert tree.stat("viking://user/alice/memories/fact")["is_dir"] is True

    def test_write_updates_and_tokens(self):
        tree = vk.VikingFS()
        first = tree.write("viking://resources/a.md", "one two")
        before = first.tokens
        second = tree.write("viking://resources/a.md", "one two three four five six")
        assert second is first
        assert second.tokens > before
        assert second.tags == ()
        assert second.modified >= second.created
        assert tree.read("viking://resources/a.md") == "one two three four five six"

    def test_write_errors(self):
        tree = vk.VikingFS()
        tree.mkdir("viking://resources")
        with pytest.raises(IsADirectoryError):
            tree.write("viking://resources", "x")
        with pytest.raises(IsADirectoryError):
            tree.write("viking://", "x")
        tree.write("viking://resources/a.md", "x")
        with pytest.raises(FileExistsError):
            tree.mkdir("viking://resources/a.md")

    def test_read_levels(self, fs):
        uri = "viking://resources/design/architecture.md"
        assert fs.read(uri, "L2") == ARCH
        assert fs.read(uri, "L0") == "The staging database is Postgres 16."
        overview = fs.read(uri, "L1")
        assert "# Architecture" in overview and "- API: FastAPI" in overview
        with pytest.raises(FileNotFoundError):
            fs.read("viking://resources/missing.md")
        with pytest.raises(IsADirectoryError):
            fs.read("viking://resources/design")

    def test_ls_sorted_dirs_first(self, fs):
        entries = fs.ls("viking://resources")
        assert [entry["name"] for entry in entries] == ["design", "runbooks"]
        assert entries[0]["is_dir"] is True
        assert entries[0]["abstract"].startswith("2 file(s)")
        files = fs.ls("viking://resources/design")
        assert [entry["name"] for entry in files] == ["api.md", "architecture.md"]
        assert files[0]["is_dir"] is False
        assert files[0]["abstract"] == "All endpoints return envelopes."
        with pytest.raises(NotADirectoryError):
            fs.ls("viking://resources/design/api.md")

    def test_tree(self, fs):
        tree = fs.tree("viking://resources")
        assert tree.splitlines()[0] == "viking://resources"
        assert "├── design/" in tree or "└── design/" in tree
        assert "api.md" in tree and "oncall.md" in tree
        assert "tokens)" in tree
        assert fs.tree("viking://resources", depth=1).count("\n") == 2
        with pytest.raises(ValueError):
            fs.tree("viking://resources", depth=0)

    def test_stat(self, fs):
        payload = fs.stat("viking://resources/design/architecture.md")
        assert payload["uri"].endswith("architecture.md")
        assert payload["is_dir"] is False
        assert payload["tags"] == ["design", "infra"]
        assert payload["lines"] == 6
        assert payload["abstract"].startswith("The staging database")
        folder = fs.stat("viking://resources/design")
        assert folder["files"] == 2 and folder["dirs"] == 0
        assert folder["tokens"] > 0

    def test_walk_and_files(self, fs):
        uris = [path.uri for path in fs.walk("viking://resources")]
        assert uris[0] == "viking://resources/design"
        assert "viking://resources/design/api.md" in uris
        assert len(fs.files()) == 3
        assert fs.files("viking://resources/design") == [
            "viking://resources/design/api.md",
            "viking://resources/design/architecture.md",
        ]

    def test_grep(self, fs):
        hits = fs.grep("postgres", ignore_case=True)
        assert len(hits) == 1
        assert hits[0].uri.endswith("architecture.md")
        assert hits[0].line == 3
        assert hits[0].text.startswith("The staging database")
        assert fs.grep("postgres") == []
        assert fs.grep("Postgres", "viking://resources/design/api.md") == []
        assert fs.grep("POSTGRES", "viking://resources", ignore_case=True)[0].as_dict()["line"] == 3
        assert fs.grep("^#")[0].text.startswith("#")

    def test_find(self, fs):
        assert len(fs.find("*.md")) == 3
        assert fs.find("*.md", "viking://resources/design") == [
            "viking://resources/design/api.md",
            "viking://resources/design/architecture.md",
        ]
        assert fs.find("api*") == ["viking://resources/design/api.md"]
        assert fs.find("*.py") == []

    def test_remove_and_move(self, fs):
        assert fs.remove("viking://resources/design/api.md") is True
        assert fs.remove("viking://resources/design/api.md") is False
        assert fs.exists("viking://resources/design/api.md") is False
        with pytest.raises(ValueError):
            fs.remove("viking://")
        fs.write("viking://resources/design/api.md", API)
        moved = fs.move("viking://resources/design/api.md", "viking://resources/api.md")
        assert moved.path.uri == "viking://resources/api.md"
        assert fs.exists("viking://resources/design/api.md") is False
        with pytest.raises(FileExistsError):
            fs.move("viking://resources/api.md", "viking://resources/runbooks/oncall.md")
        fs.mkdir("viking://resources/design/nested")
        with pytest.raises(ValueError):
            fs.move("viking://resources/design", "viking://resources/design/nested/design")

    def test_move_directory_rebases_children(self, fs):
        fs.move("viking://resources/design", "viking://resources/archive")
        assert fs.exists("viking://resources/archive/architecture.md")
        assert fs.read("viking://resources/archive/api.md", "L0") == "All endpoints return envelopes."
        assert fs.stat("viking://resources/archive/api.md")["uri"].endswith("archive/api.md")

    def test_stat_missing(self):
        with pytest.raises(FileNotFoundError):
            vk.VikingFS().stat("viking://nope/a.md")


class TestDirectorySummaries:
    def test_summary_shape_and_cache(self, fs):
        summary = fs.summary("viking://resources/design")
        assert summary.uri == "viking://resources/design"
        assert summary.files == 2 and summary.dirs == 0
        assert "architecture.md" in summary.abstract
        assert summary.tokens > 0
        assert summary.as_dict()["files"] == 2
        assert fs.summary("viking://resources/design") is summary     # cached
        with pytest.raises(NotADirectoryError):
            fs.summary("viking://resources/design/api.md")

    def test_summary_refreshes_after_write(self, fs):
        before = fs.summary("viking://resources/design").abstract
        fs.write("viking://resources/design/new.md", "# New\n\nA brand new note.\n")
        after = fs.summary("viking://resources/design").abstract
        assert after != before
        assert "3 file(s)" in after
        assert "new.md" in after

    def test_nested_abstracts_roll_up(self, fs):
        root = fs.summary("viking://resources")
        assert root.files == 0 and root.dirs == 2
        assert "design/" in root.abstract
        assert "postgres" in root.abstract.lower()

    def test_overview_lists_children(self, fs):
        overview = fs.summary("viking://resources").overview
        assert "viking://resources" in overview
        assert "- design/" in overview
        assert "- runbooks/" in overview
        assert "api.md" in overview

    def test_read_subtree_layers(self, fs):
        l0 = fs.read_subtree("viking://resources", "L0")
        assert l0.startswith("0 file(s)")
        l1 = fs.read_subtree("viking://resources", "L1")
        assert "- design/" in l1
        l2 = fs.read_subtree("viking://resources", "L2")
        assert "## viking://resources/design/api.md" in l2
        assert fs.read_subtree("viking://resources/design/api.md", "L2") == API


# ── Ranking and search ────────────────────────────────────────────────────

class TestBm25:
    def test_scores_rank_best_first(self):
        ranker = vk.Bm25Ranker({
            "a": "postgres database staging",
            "b": "redis queue cache",
            "c": "postgres staging postgres",
        })
        scores = ranker.scores("postgres")
        assert list(scores)[0] == "c"
        assert set(scores) == {"a", "c"}
        assert ranker.scores("redis queue") == {"b": 1.9617}

    def test_idf_and_empty(self):
        ranker = vk.Bm25Ranker({"a": "x y", "b": "x z"})
        assert ranker.idf("x") < ranker.idf("y")
        assert ranker.scores("") == {}
        assert ranker.scores("absent") == {}
        assert vk.Bm25Ranker({}).scores("x") == {}
        assert vk.Bm25Ranker({}).rank("x") == []

    def test_rank_limit(self):
        ranker = vk.Bm25Ranker({"a": "alpha beta", "b": "alpha", "c": "alpha alpha"})
        ranked = ranker.rank("alpha", limit=2)
        assert len(ranked) == 2
        assert ranked[0][1] >= ranked[1][1]
        assert ranker.rank("alpha", limit=0) == []

    def test_validation(self):
        with pytest.raises(ValueError):
            vk.Bm25Ranker({}, b=1.5)
        with pytest.raises(ValueError):
            vk.Bm25Ranker({}, k1=0)


class TestScopedSearch:
    def test_scope_is_respected(self):
        tree = vk.VikingFS()
        tree.write("viking://resources/a/postgres.md", "# Postgres\n\nPostgres tuning notes.\n")
        tree.write("viking://user/bob/postgres.md", "# Postgres\n\nUser notes on postgres.\n")
        engine = vk.ScopedSearchEngine(tree)
        hits = engine.search("postgres", "viking://resources", limit=5)
        assert hits
        assert all(hit.uri.startswith("viking://resources") for hit in hits)
        assert any(hit.uri.endswith("postgres.md") for hit in hits)
        assert all("user/bob" not in hit.uri for hit in hits)

    def test_hit_shape_and_levels(self, fs):
        engine = vk.ScopedSearchEngine(fs)
        hit = engine.search("postgres", "viking://resources", level="L2", limit=1)[0]
        assert hit.level == "L2"
        assert hit.score > 0
        assert hit.kind in ("file", "dir")
        assert "postgres" in hit.abstract.lower()
        assert hit.as_dict()["uri"] == hit.uri
        assert engine.search("postgres", "viking://resources", level="L0")

    def test_kind_and_tag_filters(self, fs):
        engine = vk.ScopedSearchEngine(fs)
        files = engine.search("postgres", "viking://resources", kinds=["file"], limit=5)
        assert files and all(hit.kind == "file" for hit in files)
        dirs = engine.search("endpoints", "viking://resources", kinds=["dir"], limit=5)
        assert dirs and all(hit.kind == "dir" for hit in dirs)
        tagged = engine.search("postgres", "viking://resources", tags=["infra"], limit=5)
        assert tagged
        assert all(hit.uri.endswith("architecture.md") for hit in tagged)

    def test_empty_query_and_limits(self, fs):
        engine = vk.ScopedSearchEngine(fs)
        assert engine.search("", "viking://resources") == []
        assert engine.search("postgres", "viking://resources", limit=0) == []
        assert len(engine.search("md", "viking://resources", limit=1)) <= 1

    def test_explain(self, fs):
        payload = vk.ScopedSearchEngine(fs).explain("postgres", "viking://resources")
        assert payload["terms"] == ["postgres"]
        assert payload["candidates"] > 0
        assert payload["matched"] >= 1
        assert payload["idf"]["postgres"] > 0
        assert payload["top"][0].startswith("viking://resources")

    def test_errors(self, fs):
        engine = vk.ScopedSearchEngine(fs)
        with pytest.raises(FileNotFoundError):
            engine.search("x", "viking://missing")
        with pytest.raises(ValueError):
            engine.search("x", "viking://resources", level="L7")


# ── Sessions and extraction ───────────────────────────────────────────────

class TestSessions:
    def test_turns_and_stats(self):
        session = _session()
        turn = session.add("user", "Hello there, how are you?")
        session.add("assistant", "Doing well.")
        session.add("tool", "grep output")
        assert turn.role == "user"
        assert turn.tokens > 0
        assert session.tokens() > 0
        stats = session.stats()
        assert stats["turns"] == 3
        assert stats["user_turns"] == 1
        assert stats["assistant_turns"] == 1
        assert stats["tool_turns"] == 1
        assert stats["questions"] == 1
        assert stats["tokens"] == session.tokens()

    def test_transcript(self):
        session = _session()
        session.add("user", "One")
        session.add("assistant", "Two")
        assert session.transcript() == "**user:** One\n\n**assistant:** Two"
        assert vk.SessionTurn("user", "x").as_dict()["role"] == "user"

    def test_role_validation(self):
        session = _session()
        with pytest.raises(ValueError):
            session.add("robot", "beep")
        assert vk.SessionTurn("user", "x").as_dict()["role"] == "user"


class TestMemoryExtractor:
    def setup_method(self):
        self.extractor = vk.MemoryExtractor()
        self.session = _populated_session()

    def test_extracts_all_kinds(self):
        memories = self.extractor.extract(self.session)
        kinds = [memory.kind for memory in memories]
        assert kinds == ["preference", "decision", "todo", "fact"]
        assert memories[0].key == "i-prefer-dark-mode-in-all"
        assert memories[1].key == "we-decided-to-use-postgres-16"
        assert memories[2].key == "remember-to-rotate-the-api-keys"
        assert memories[3].key == "the-staging-database-is-postgres-16"
        assert all(memory.source == "s-001" for memory in memories)

    def test_confidence_and_title(self):
        memories = self.extractor.extract(self.session)
        for memory in memories:
            assert 0.5 <= memory.confidence <= 0.95
            assert not memory.title.endswith(".")
        decision = next(memory for memory in memories if memory.kind == "decision")
        assert decision.confidence == 0.9
        long = self.extractor.extract(vk.Session("s-9"))
        assert long == []

    def test_chitchat_and_questions_skipped(self):
        assert self.extractor.classify("Thanks!") is None
        assert self.extractor.classify("hi") is None
        assert self.extractor.classify("Should we use Postgres?") is None
        assert self.extractor.classify("ok then") is None

    def test_classify_rules(self):
        assert self.extractor.classify("I always use uv for Python packages.")[0] == "preference"
        assert self.extractor.classify("Let's use Redis for the queue.")[0] == "decision"
        assert self.extractor.classify("TODO: delete the old bucket")[0] == "todo"
        assert self.extractor.classify("The API gateway is behind Cloudflare.")[0] == "fact"

    def test_duplicates_collapse(self):
        session = _session()
        session.add("user", "I prefer dark mode in all dashboards.")
        session.add("user", "I prefer dark mode in all dashboards.")
        memories = self.extractor.extract(session)
        assert len(memories) == 1

    def test_min_confidence(self):
        strict = vk.MemoryExtractor(min_confidence=0.9)
        memories = strict.extract(self.session)
        assert [memory.kind for memory in memories] == ["decision"]

    def test_markdown_and_tags(self):
        memory = self.extractor.extract(self.session)[0]
        markdown = memory.to_markdown()
        fields = vk.parse_frontmatter(markdown)
        assert fields["key"] == memory.key
        assert fields["kind"] == "preference"
        assert fields["source"] == "s-001"
        assert "preference" in fields["tags"]
        assert markdown.strip().splitlines()[-1].startswith("I prefer")

    def test_only_conversation_roles(self):
        session = _session()
        session.add("tool", "I prefer dark mode in all dashboards.")
        session.add("system", "We decided to use Postgres 16 for staging.")
        assert self.extractor.extract(session) == []


# ── Database and commits ──────────────────────────────────────────────────

class TestContextDatabase:
    def test_constructor_layout(self):
        db = vk.ContextDatabase(user="alice")
        assert db.exists("viking://resources")
        assert db.exists("viking://user/alice/memories")
        assert db.exists("viking://user/alice/sessions")
        stats = db.stats()
        assert stats["user"] == "alice"
        assert stats["files"] == 0
        assert stats["memories"] == 0
        assert stats["layers"]["L0"] == "abstract"
        with pytest.raises(ValueError):
            vk.ContextDatabase(user="bad user")

    def test_write_read_ls_passthrough(self):
        db = vk.ContextDatabase()
        db.write("viking://resources/a.md", "# A\n\nBody text.\n", tags=("doc",))
        assert db.read("viking://resources/a.md", "L0") == "Body text."
        assert [entry["name"] for entry in db.ls("viking://resources")] == ["a.md"]
        assert "a.md" in db.tree("viking://resources")
        assert db.stat("viking://resources/a.md")["tags"] == ["doc"]
        assert db.grep("Body")[0].line == 3
        assert db.find("*.md") == ["viking://resources/a.md"]
        assert db.summary("viking://resources").files == 1
        assert db.rm("viking://resources/a.md") is True
        assert db.exists("viking://resources/a.md") is False

    def test_commit_archives_and_extracts(self):
        db = vk.ContextDatabase(user="alice")
        result = db.commit_session(_populated_session())
        assert result.session_id == "s-001"
        assert result.archive_uri == "viking://user/alice/sessions/s-001.md"
        assert result.turns == 6
        assert len(result.memories) == 4
        assert result.as_dict()["extracted"] == 4
        assert db.exists(result.archive_uri)
        archive = db.read(result.archive_uri, "L2")
        assert "kind: session" in archive
        assert "**user:** I prefer dark mode" in archive
        assert all(db.exists(uri) for uri in result.memories)
        assert db.read(result.memories[1], "L0").startswith("We decided to use Postgres")
        assert db.stats()["memories"] == 4
        assert db.stats()["commits"] == 1

    def test_session_ids_are_unique(self):
        db = vk.ContextDatabase(user="bob")
        first = db.open_session()
        second = db.open_session()
        assert (first.session_id, second.session_id) == ("s-001", "s-002")
        db.commit_session(first)
        manual = _session("s-001")
        manual.add("user", "I prefer tabs over spaces.")
        db.commit_session(manual)
        third = db.open_session()
        assert third.session_id == "s-003"
        db.commit_session("s-002")

    def test_recommit_skips_identical_memories(self):
        db = vk.ContextDatabase(user="alice")
        session = _populated_session()
        first = db.commit_session(session)
        second = db.commit_session(session)
        assert second.memories == []
        assert len(second.skipped) == len(first.memories)
        assert second.superseded == []

    def test_new_session_supersedes_and_keeps_history(self):
        db = vk.ContextDatabase(user="carol")
        first = db.open_session()
        first.add("user", "I prefer tabs over spaces.")
        db.commit_session(first)
        second = db.open_session()
        second.add("user", "I prefer tabs over spaces.")
        result = db.commit_session(second)
        assert len(result.superseded) == 1
        uri = result.superseded[0]
        assert uri == "viking://user/carol/memories/preference/i-prefer-tabs-over-spaces.md"
        assert result.memories == []
        history = "viking://user/carol/memories/.history/preference-i-prefer-tabs-over-spaces-1.md"
        assert db.exists(history)
        assert "source: s-001" in db.read(history, "L2")
        assert "source: s-002" in db.read(uri, "L2")

    def test_remember_and_search(self):
        db = vk.ContextDatabase(user="dave")
        uri = db.remember("fact", "Team Timezone", "Team timezone is IST",
                          "Team timezone is IST, no DST.")
        assert uri == "viking://user/dave/memories/fact/team-timezone.md"
        assert db.exists(uri)
        hits = db.search("timezone", kinds=["file"])
        assert hits and hits[0].uri == uri
        assert db.search("timezone", tags=["fact"])
        assert db.explain_search("timezone")["matched"] >= 1
        assert db.search("timezone", root="viking://resources") == []
        assert db.stats()["memories"] == 1

    def test_unknown_session(self):
        db = vk.ContextDatabase()
        with pytest.raises(KeyError):
            db.commit_session("s-404")


# ── Wiki compilation ──────────────────────────────────────────────────────

class TestWikiCompiler:
    def _db(self):
        db = vk.ContextDatabase(user="erin")
        db.remember("preference", "Theme", "Dark mode preferred",
                    "I prefer dark mode in all dashboards.")
        db.remember("preference", "Theme 2", "Light mode fallback",
                    "I prefer light mode on projectors.")
        db.remember("decision", "Database", "Postgres for staging",
                    "We decided to use Postgres 16 for staging.")
        return db

    def test_pages_and_explicit_links(self, fs):
        report = vk.WikiCompiler(fs).compile("viking://resources")
        assert len(report.pages) == 3
        titles = {page.title for page in report.pages}
        assert titles == {"Architecture", "API notes", "On-call runbook"}
        api = next(page for page in report.pages if page.title == "API notes")
        architecture = next(page for page in report.pages if page.title == "Architecture")
        assert api.links == [architecture.uri]
        assert architecture.links == [api.uri]
        assert report.orphans == ["viking://resources/runbooks/oncall.md"]
        assert report.components == 2

    def test_tag_links_and_hubs(self):
        db = self._db()
        report = db.compile()
        assert len(report.pages) == 3
        preference = [page for page in report.pages if page.kind == "preference"]
        assert len(preference) == 2
        assert preference[0].uri in preference[1].links
        assert all(page.links for page in preference)
        assert report.components == 2
        assert "viking://user/erin/memories/decision/database.md" in report.orphans
        assert len(report.hubs) == 2
        assert all(degree >= 1 for _, degree in report.hubs)

    def test_render_index_and_persist(self):
        db = self._db()
        report = db.compile(persist=True)
        rendered = report.render_index()
        assert rendered.startswith("# Memora context wiki")
        assert "](viking://user/erin/memories/preference/theme.md)" in rendered
        assert "## Hubs" in rendered
        assert "## Orphans" in rendered
        assert report.index_uri == "viking://user/erin/_index.md"
        assert db.exists(report.index_uri)
        assert "# Memora context wiki" in db.read(report.index_uri, "L2")
        assert db.read(report.index_uri, "L0")
        assert report.as_dict()["components"] == 2

    def test_empty_and_no_links(self):
        db = vk.ContextDatabase(user="frank")
        report = db.compile()
        assert report.pages == []
        assert report.orphans == []
        assert report.hubs == []
        assert report.components == 0
        assert "none" in report.render_index()

    def test_database_stats_after_compile(self):
        db = self._db()
        db.compile(persist=True)
        stats = db.stats()
        assert stats["memories"] == 3
        assert stats["files"] >= 4          # three memories + index
        assert stats["dirs"] >= 4
        assert stats["tokens"] > 0

    def test_seed_resources(self):
        db = vk.default_database(user="gina")
        vk.seed_resources(db)
        assert db.exists("viking://resources/design/architecture.md")
        assert db.summary("viking://resources/design").files == 2
        hits = db.search("postgres", root="viking://resources", limit=3)
        assert hits
        assert hits[0].uri.startswith("viking://resources")
