"""
TASK-MEM-032 — Memora offline knowledge pack (NOMAD pattern, adapted).

Proves the pack the board record asks for: one offline pack built and
answering a real query with the ADB path disabled — and that ADB still
wins whenever it is up.

* The pack loads from its bundled manifest + corpus, and the manifest's
  entry count and corpus SHA-256 match the files on disk, so a tampered
  or truncated pack fails loudly instead of answering wrong.
* ``resolve_knowledge`` is the fallback switch: ADB up means ADB wins
  (the pack is not even consulted); ADB down / empty / unconfigured
  means the pack answers and says so.
* The pack answers with the network made unavailable — the query path
  does no I/O after load, so disabling sockets cannot break it.

Runs in the Memora tier-1 CI step (listed in
.github/workflows/friday-universe-ci.yml).
"""
import hashlib
import json
import socket
from pathlib import Path

import pytest

from core.memory.offline_pack import OfflinePack, PackError, resolve_knowledge

PACK_DIR = Path(__file__).resolve().parent.parent / "core" / "memory" / "nomad_pack"


@pytest.fixture(scope="module")
def pack():
    return OfflinePack.load(PACK_DIR)


def _adb_down_error(query):  # noqa: ARG001 - signature is the adb_query contract
    raise ConnectionError("Oracle ADB unreachable: ORA-12170 TNS connect timeout")


def _adb_empty(query):  # noqa: ARG001
    return []


def test_pack_loads_and_manifest_matches_corpus(pack):
    info = pack.info()
    assert info["pack"] == "nomad-offline-pack", info
    assert info["version"] == "1.0.0", info
    assert info["task"] == "TASK-MEM-032", info
    assert info["entry_count"] == 16, info
    assert set(info["collections"]) == {"operations", "reference", "education"}, info

    manifest = json.loads((PACK_DIR / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["entry_count"] == pack.entry_count == 16
    raw = (PACK_DIR / "corpus.jsonl").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == manifest["entries_sha256"]
    assert len(raw.decode("utf-8").splitlines()) == 16


def test_corpus_entries_have_required_fields(pack):
    for lineno, line in enumerate((PACK_DIR / "corpus.jsonl").read_text(encoding="utf-8").splitlines(), start=1):
        row = json.loads(line)
        assert set(row) >= {"id", "title", "collection", "keywords", "body"}, (lineno, row)
        assert all(isinstance(row[k], str) and row[k].strip() for k in ("id", "title", "collection", "body")), lineno
        assert row["collection"] in ("operations", "reference", "education"), lineno
        assert pack.entry(row["id"]) is not None, lineno


def test_entry_lookup_by_id(pack):
    found = pack.entry("memora-adb-down")
    assert found is not None
    assert found["title"].startswith("Memora Oracle ADB is unreachable")
    assert "fails closed" in found["body"]
    assert pack.entry("does-not-exist") is None


def test_real_query_with_adb_disabled_answers(pack):
    """The board's Done: a real query answered with the ADB path disabled."""
    result = resolve_knowledge(
        "Memora database is down, what do I do",
        adb_query=_adb_down_error,
        pack=pack,
    )
    assert result["source"] == "offline_pack", result
    assert result["fallback_reason"] == "adb_unavailable", result
    assert "ConnectionError" in (result["adb_error"] or ""), result
    assert result["hits"], result
    top = result["hits"][0]
    assert top["id"] == "memora-adb-down", result["hits"]
    assert "fails closed" in top["body"]
    assert "offline pack" in top["body"]
    assert 0.0 < top["score"] <= 1.0


def test_adb_up_wins_over_pack():
    """ADB wins even where the pack has the stronger hit — and the pack
    is not consulted at all."""
    calls = {"adb": 0}

    def adb_answers(query):
        calls["adb"] += 1
        return [{"id": "adb-hit-1", "title": "Live ADB answer", "body": "from the live store"}]

    class _PackMustNotBeConsulted(OfflinePack):
        def query(self, query, top_k=3):  # noqa: ARG002
            raise AssertionError("pack must not be consulted when ADB answers")

    result = resolve_knowledge(
        "Memora database is down, what do I do",
        adb_query=adb_answers,
        pack=_PackMustNotBeConsulted.load(PACK_DIR),
    )
    assert result["source"] == "adb", result
    assert result["fallback_reason"] is None, result
    assert result["adb_error"] is None, result
    assert result["hits"] == [{"id": "adb-hit-1", "title": "Live ADB answer", "body": "from the live store"}]
    assert calls["adb"] == 1


def test_adb_empty_falls_through_to_pack(pack):
    result = resolve_knowledge(
        "Khan Academy offline courses",
        adb_query=_adb_empty,
        pack=pack,
    )
    assert result["source"] == "offline_pack", result
    assert result["fallback_reason"] == "adb_empty", result
    assert result["hits"] and result["hits"][0]["id"] == "kolibri-khan-academy", result["hits"]


def test_adb_probe_false_skips_adb_call(pack):
    calls = {"adb": 0}

    def adb_must_not_run(query):  # noqa: ARG001
        calls["adb"] += 1
        raise AssertionError("ADB must not be called when the probe says down")

    result = resolve_knowledge(
        "offline Wikipedia Kiwix ZIM files",
        adb_query=adb_must_not_run,
        adb_available=lambda: False,
        pack=pack,
    )
    assert result["source"] == "offline_pack", result
    assert result["fallback_reason"] == "adb_unavailable", result
    assert result["adb_error"] == "ADB probe reported unavailable", result
    assert calls["adb"] == 0
    assert result["hits"] and result["hits"][0]["id"] == "kiwix-zim-wikipedia", result["hits"]


def test_adb_not_configured_answers_from_pack(pack):
    result = resolve_knowledge("Stratex demo trading only, no live trades", pack=pack)
    assert result["source"] == "offline_pack", result
    assert result["fallback_reason"] == "adb_not_configured", result
    assert result["hits"] and result["hits"][0]["id"] == "stratex-demo-only", result["hits"]


def test_pack_answers_with_network_disabled(monkeypatch, pack):
    """Sockets made unavailable: the query path does no I/O after load,
    so the pack still answers. (The NOMAD offline-first guarantee, at
    Memora scale.)"""
    def _no_socket(*args, **kwargs):
        raise OSError("network is disabled for this test")

    monkeypatch.setattr(socket, "socket", _no_socket)
    monkeypatch.setattr(socket, "create_connection", _no_socket)

    hits = pack.query("FRIDAY cgroup memory guard warn 75 percent")
    assert hits, hits
    assert hits[0]["id"] == "friday-oom-guard", hits
    assert "75%" in hits[0]["body"]


def test_ranking_prefers_the_relevant_entry(pack):
    assert pack.query("offline Wikipedia Kiwix ZIM files")[0]["id"] == "kiwix-zim-wikipedia"
    assert pack.query("Khan Academy offline courses Kolibri")[0]["id"] == "kolibri-khan-academy"
    assert pack.query("local AI Ollama model memory")[0]["id"] == "ollama-local-ai"
    assert pack.query("offline maps ProtoMaps tiles")[0]["id"] == "protomaps-offline-maps"
    assert pack.query("never message Surendra report to Muse hub")[0]["id"] == "owner-reporting"
    assert pack.query("APInex fallback waterfall inference")[0]["id"] == "inference-apinex-fallback"


def test_unknown_query_returns_no_hits_not_an_invention(pack):
    assert pack.query("zxqv wjblorp fnord quux") == []
    assert pack.query("") == []
    assert pack.query("   ") == []


def test_empty_query_never_calls_adb(pack):
    calls = {"adb": 0}

    def adb_must_not_run(query):  # noqa: ARG001
        calls["adb"] += 1
        return [{"id": "adb-hit-1"}]

    result = resolve_knowledge("", adb_query=adb_must_not_run, pack=pack)
    assert result["source"] == "offline_pack", result
    assert result["fallback_reason"] == "empty_query", result
    assert result["hits"] == []
    assert calls["adb"] == 0


def test_corrupt_pack_fails_loudly(tmp_path):
    good_dir = PACK_DIR
    bad_dir = tmp_path / "nomad_pack"
    bad_dir.mkdir()
    (bad_dir / "manifest.json").write_text((good_dir / "manifest.json").read_text(encoding="utf-8"), encoding="utf-8")
    # Truncate the corpus: the manifest count + hash no longer match.
    lines = (good_dir / "corpus.jsonl").read_text(encoding="utf-8").splitlines()
    (bad_dir / "corpus.jsonl").write_text("\n".join(lines[:5]) + "\n", encoding="utf-8")
    with pytest.raises(PackError):
        OfflinePack.load(bad_dir)

    # Unknown collection is rejected even with a matching count + hash.
    manifest = json.loads((good_dir / "manifest.json").read_text(encoding="utf-8"))
    tampered = [
        json.loads(line) if i else {**json.loads(line), "collection": "no-such-collection"}
        for i, line in enumerate(lines)
    ]
    corpus_text = "\n".join(json.dumps(row) for row in tampered) + "\n"
    manifest["entries_sha256"] = hashlib.sha256(corpus_text.encode("utf-8")).hexdigest()
    (bad_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (bad_dir / "corpus.jsonl").write_text(corpus_text, encoding="utf-8")
    with pytest.raises(PackError):
        OfflinePack.load(bad_dir)
