"""Tests for the Inference discovery feed (TASK-INF-041).

No network: every test feeds stub payloads into the pure functions in
scripts/discovery_feed.py. The live sources are exercised by the
scheduled workflow run and by the manual proof run in the evidence doc.
"""

import datetime as _dt
import importlib.util
import json
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "discovery_feed.py"
_spec = importlib.util.spec_from_file_location("discovery_feed", _SCRIPT)
feed = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(feed)

RUN_DATE = _dt.date(2026, 11, 25)


def _free_model(model_id, created, description="A test model."):
    return {
        "id": model_id,
        "name": model_id,
        "created": created,
        "description": description,
        "pricing": {"prompt": "0", "completion": "0"},
    }


def _hf_model(model_id, created_at, pipeline="text-generation", downloads=10):
    return {
        "id": model_id,
        "author": model_id.split("/")[0],
        "createdAt": created_at,
        "pipeline_tag": pipeline,
        "downloads": downloads,
    }


def test_openrouter_free_detected():
    payload = {
        "data": [
            _free_model("a/free-model", 1795564800),  # 2026-11-25
            {
                "id": "b/paid-model",
                "name": "b",
                "created": 1795564800,
                "pricing": {"prompt": "0.001", "completion": "0.002"},
            },
        ]
    }
    items = feed.openrouter_items(payload)
    assert [i["source_id"] for i in items] == ["a/free-model"]
    assert items[0]["date"] == "2026-11-25"
    assert items[0]["route"]["provider"] == "openrouter"


def test_openrouter_missing_pricing_not_free():
    payload = {"data": [{"id": "c/no-pricing", "created": 1795564800}]}
    assert feed.openrouter_items(payload) == []


def test_huggingface_text_models_only():
    payload = [
        _hf_model("deepseek-ai/new-text", "2026-11-24T10:00:00.000Z"),
        _hf_model(
            "deepseek-ai/new-image",
            "2026-11-24T10:00:00.000Z",
            pipeline="text-to-image",
        ),
    ]
    items, skipped = feed.huggingface_items(payload, "deepseek-ai")
    assert [i["source_id"] for i in items] == ["deepseek-ai/new-text"]
    assert skipped == []


def test_huggingface_derivative_artefacts_skipped():
    payload = [
        _hf_model("nvidia/qwen3-4b-draft", "2026-11-24T10:00:00.000Z"),
        _hf_model("microsoft/aion-2-3b-onnx-webgpu", "2026-11-24T10:00:00.000Z"),
        _hf_model("microsoft/aion-2-3b", "2026-11-24T10:00:00.000Z"),
    ]
    items, skipped = feed.huggingface_items(payload, "microsoft")
    assert [i["source_id"] for i in items] == ["microsoft/aion-2-3b"]
    assert skipped == [
        "nvidia/qwen3-4b-draft",
        "microsoft/aion-2-3b-onnx-webgpu",
    ]


def test_is_new_window_rule():
    state = {"seen": {}, "filed": []}
    fresh = {"source": "openrouter", "source_id": "x/new", "date": "2026-11-20"}
    old = {"source": "openrouter", "source_id": "x/old", "date": "2026-10-01"}
    undated = {"source": "openrouter", "source_id": "x/nodate", "date": None}
    assert feed.is_new(fresh, state, set(), RUN_DATE, 14) is True
    assert feed.is_new(old, state, set(), RUN_DATE, 14) is False
    assert feed.is_new(undated, state, set(), RUN_DATE, 14) is False


def test_is_new_skips_seen_and_existing_candidates():
    state = {"seen": {"openrouter:x/seen": "2026-11-24"}, "filed": []}
    seen = {"source": "openrouter", "source_id": "x/seen", "date": "2026-11-24"}
    assert feed.is_new(seen, state, set(), RUN_DATE, 14) is False
    fresh = {"source": "openrouter", "source_id": "x/cand", "date": "2026-11-24"}
    assert feed.is_new(fresh, state, {"x/cand"}, RUN_DATE, 14) is False
    assert feed.is_new(fresh, state, set(), RUN_DATE, 14) is True


def test_record_schema_and_provenance():
    item = {
        "source": "openrouter",
        "source_id": "x/new",
        "name": "x/new",
        "date": "2026-11-24",
        "claim": "Free model x/new listed on OpenRouter",
        "source_url": feed.OPENROUTER_MODELS_URL,
        "route": {"provider": "openrouter", "model_id": "x/new"},
    }
    record = feed.build_record(item, RUN_DATE)
    assert record["schema"] == feed.SCHEMA_RECORD
    assert record["id"] == "openrouter-x-new"
    assert record["status"] == "filed"
    assert "not admitted" in record["evaluation"]
    assert record["date"] == "2026-11-24"
    assert record["discovered_at"] == "2026-11-25"


def test_record_id_slug():
    assert feed.record_id_for(
        {"source": "huggingface", "source_id": "deepseek-ai/DeepSeek-V4.1-Flash-1017"}
    ) == ("huggingface-deepseek-ai-deepseek-v4-1-flash-1017")


def test_prune_seen_drops_old_entries():
    state = {"seen": {"a:old": "2026-10-01", "a:recent": "2026-11-20"}, "filed": []}
    feed.prune_seen(state, RUN_DATE)
    assert state["seen"] == {"a:recent": "2026-11-20"}


def test_existing_candidate_ids(tmp_path):
    candidates = tmp_path / "candidates"
    candidates.mkdir()
    (candidates / "minimax.json").write_text(
        json.dumps({"model_id": "MiniMax-M3", "candidate": "minimax-m3"})
    )
    (candidates / "broken.json").write_text("{not json")
    ids = feed.existing_candidate_ids(candidates)
    assert ids == {"MiniMax-M3", "minimax-m3"}


def test_run_scan_dry_run_writes_nothing(monkeypatch, tmp_path):
    discovery = tmp_path / "discovery"
    discovery.mkdir()
    (tmp_path / "candidates").mkdir()
    payload = {"data": [_free_model("z/fresh", 1795478400)]}  # 2026-11-24
    monkeypatch.setattr(
        feed, "_fetch_json", lambda url: payload if "openrouter" in url else []
    )
    summary = feed.run_scan(
        discovery, 14, dry_run=True, bootstrap=False, today=RUN_DATE, pause_s=0
    )
    assert summary["filed"] == ["openrouter-z-fresh"]
    assert list(discovery.glob("*.json")) == []
    assert not (discovery / "state.json").exists()


def test_run_scan_second_run_files_nothing(monkeypatch, tmp_path):
    discovery = tmp_path / "discovery"
    discovery.mkdir()
    (tmp_path / "candidates").mkdir()
    payload = {"data": [_free_model("z/fresh", 1795478400)]}
    monkeypatch.setattr(
        feed, "_fetch_json", lambda url: payload if "openrouter" in url else []
    )
    first = feed.run_scan(
        discovery, 14, dry_run=False, bootstrap=False, today=RUN_DATE, pause_s=0
    )
    assert first["filed"] == ["openrouter-z-fresh"]
    assert (discovery / "openrouter-z-fresh.json").exists()
    second = feed.run_scan(
        discovery, 14, dry_run=False, bootstrap=False, today=RUN_DATE, pause_s=0
    )
    assert second["filed"] == []
    assert second["failures"] == []


def test_run_scan_source_failure_is_loud(monkeypatch, tmp_path):
    discovery = tmp_path / "discovery"
    discovery.mkdir()
    (tmp_path / "candidates").mkdir()

    def _boom(url):
        raise RuntimeError("network down")

    monkeypatch.setattr(feed, "_fetch_json", _boom)
    summary = feed.run_scan(
        discovery, 14, dry_run=False, bootstrap=False, today=RUN_DATE, pause_s=0
    )
    assert summary["filed"] == []
    assert summary["failures"], "a failed source must be reported, not hidden"


def test_bootstrap_seeds_state_without_filing(monkeypatch, tmp_path):
    discovery = tmp_path / "discovery"
    discovery.mkdir()
    (tmp_path / "candidates").mkdir()
    payload = {"data": [_free_model("z/fresh", 1795478400)]}
    monkeypatch.setattr(
        feed, "_fetch_json", lambda url: payload if "openrouter" in url else []
    )
    summary = feed.run_scan(
        discovery, 14, dry_run=False, bootstrap=True, today=RUN_DATE, pause_s=0
    )
    assert summary["filed"] == []
    state = json.loads((discovery / "state.json").read_text())
    assert "openrouter:z/fresh" in state["seen"]
    assert list(discovery.glob("openrouter-*.json")) == []


def test_run_scan_skips_record_already_on_disk(monkeypatch, tmp_path):
    """A record file on disk is filed even if state.json forgot it."""
    discovery = tmp_path / "discovery"
    discovery.mkdir()
    (tmp_path / "candidates").mkdir()
    (discovery / "openrouter-z-fresh.json").write_text(
        json.dumps({"id": "openrouter-z-fresh", "status": "filed"})
    )
    payload = {"data": [_free_model("z/fresh", 1795478400)]}  # 2026-11-24
    monkeypatch.setattr(
        feed, "_fetch_json", lambda url: payload if "openrouter" in url else []
    )
    summary = feed.run_scan(
        discovery, 14, dry_run=False, bootstrap=False, today=RUN_DATE, pause_s=0
    )
    assert summary["filed"] == []
    state = json.loads((discovery / "state.json").read_text())
    assert "openrouter:z/fresh" in state["seen"]
