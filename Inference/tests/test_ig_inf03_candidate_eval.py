"""TASK-IG-INF-03: the new-model evaluation pipeline.

Pins the INF-005 discipline in executable form:
- a candidate whose key env is unset is BLOCKED_NO_CREDENTIALS and
  NO network call is made (the shipped MiniMax/Bytez specs are in
  exactly this state);
- substitution is not serving (the gemini-3.8-flash pattern: named
  for a day, served 0/15) — serve-check says NEVER_SERVES;
- a 0/0-usage response is a cache replay, not a serve;
- partial serving is UNRELIABLE_SERVE, not a pass;
- a substitute's bench answers score 0 for the candidate;
- ADMIT requires serve-check pass AND bench >= threshold;
- end-to-end against the repo's deterministic local model rig:
  the rig genuinely serves (serve-check passes) and is honestly
  REJECTED on bench quality — the pipeline never confuses
  "reachable" with "good".
"""

import importlib.util
import json
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

_BENCH_DIR = Path(__file__).resolve().parent.parent / "benchmarks"
_spec = importlib.util.spec_from_file_location("candidate_eval", _BENCH_DIR / "candidate_eval.py")
ce = importlib.util.module_from_spec(_spec)
sys.modules["candidate_eval"] = ce  # dataclass processing looks the module up here
_spec.loader.exec_module(ce)

CandidateSpec = ce.CandidateSpec
ChatResult = ce.ChatResult

TINY_TESTSET = [
    {
        "id": "t1",
        "type": "chat",
        "prompt": "Reply with exactly one word: the chemical symbol for gold.",
        "max_tokens": 16,
        "check": {"kind": "one_word", "expected": "au"},
    },
    {
        "id": "t2",
        "type": "reason",
        "prompt": "All zorks are blue. Fenn is a zork. Is Fenn blue? Begin your answer with the word yes.",
        "max_tokens": 64,
        "check": {"kind": "starts_with", "expected": "yes"},
    },
]


def _spec(**overrides):
    base = {
        "candidate": "test-candidate",
        "model_id": "cand-1",
        "base_url": "https://cand.example.test/v1",
        "provider": "test",
        "reference_overall": 0.988,
    }
    base.update(overrides)
    return CandidateSpec.from_dict(base)


def _good_chat(model_id_holder=None):
    async def chat(model_id, messages, max_tokens):
        prompt = messages[-1]["content"]
        if "chemical symbol" in prompt:
            content = "Au"
        elif "zork" in prompt:
            content = "Yes, Fenn is blue."
        else:
            content = "blue"
        return ChatResult(
            content=content, served_model=model_id, prompt_tokens=11, completion_tokens=3, latency_s=0.01
        )

    return chat


# ---------------------------------------------------------------------------
# Credential / route gate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_blocked_no_credentials_makes_no_call():
    async def forbidden_chat(*args):
        raise AssertionError("chat must not be called when credentials are missing")

    report = await ce.evaluate_candidate(
        _spec(api_key_env="IG_INF03_MISSING_KEY"), chat=forbidden_chat, environ={}
    )
    assert report["verdict"] == "BLOCKED_NO_CREDENTIALS"
    assert report["missing"] == ["credential env IG_INF03_MISSING_KEY"]


@pytest.mark.asyncio
async def test_blocked_no_route():
    report = await ce.evaluate_candidate(_spec(base_url=None), chat=_good_chat(), environ={})
    assert report["verdict"] == "BLOCKED_NO_ROUTE"
    assert "base_url" in report["missing"]


@pytest.mark.asyncio
async def test_shipped_candidate_specs_are_blocked_without_keys():
    for name in ("minimax.json", "bytez.json"):
        spec = CandidateSpec.load(_BENCH_DIR / "candidates" / name)
        report = await ce.evaluate_candidate(spec, chat=_good_chat(), environ={})
        assert report["verdict"] == "BLOCKED_NO_CREDENTIALS", name
        assert spec.reference_overall == 0.988
        assert (spec.base_url or "").startswith("https://")


# ---------------------------------------------------------------------------
# Serve-check: the three INF-005 failure shapes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_substitution_is_never_serves():
    async def substituting_chat(model_id, messages, max_tokens):
        return ChatResult(
            content="a fine answer", served_model="some-other-model",
            prompt_tokens=10, completion_tokens=5,
        )

    serve = await ce.serve_check(substituting_chat, "cand-1")
    assert serve["verdict"] == "NEVER_SERVES"
    assert all("substituted" in p["reason"] for p in serve["probes"])

    report = await ce.evaluate_candidate(_spec(), chat=substituting_chat, environ={})
    assert report["verdict"] == "REJECT" and report["reason"] == "NEVER_SERVES"
    assert "bench" not in report  # never reaches the bench


@pytest.mark.asyncio
async def test_cache_replay_is_never_serves():
    async def replay_chat(model_id, messages, max_tokens):
        return ChatResult(
            content="replayed answer", served_model=model_id, prompt_tokens=0, completion_tokens=0
        )

    serve = await ce.serve_check(replay_chat, "cand-1")
    assert serve["verdict"] == "NEVER_SERVES"
    assert all("cache replay" in p["reason"] for p in serve["probes"])


@pytest.mark.asyncio
async def test_partial_serving_is_unreliable():
    state = {"calls": 0}

    async def flaky_chat(model_id, messages, max_tokens):
        state["calls"] += 1
        if state["calls"] == 1:
            return ChatResult(content="ok", served_model=model_id, prompt_tokens=5, completion_tokens=2)
        return ChatResult(error="HTTP 503")

    serve = await ce.serve_check(flaky_chat, "cand-1")
    assert serve["verdict"] == "UNRELIABLE_SERVE"
    assert serve["served"] == 1


# ---------------------------------------------------------------------------
# Bench + verdicts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admit_when_serving_and_above_threshold():
    report = await ce.evaluate_candidate(_spec(), chat=_good_chat(), environ={}, items=TINY_TESTSET)
    assert report["verdict"] == "ADMIT"
    assert report["serve_check"]["verdict"] == "SERVED"
    assert report["bench"]["overall"] == 1.0
    assert report["reference"]["overall"] == 0.988


@pytest.mark.asyncio
async def test_reject_below_threshold():
    async def wrong_chat(model_id, messages, max_tokens):
        return ChatResult(
            content="banana", served_model=model_id, prompt_tokens=9, completion_tokens=1
        )

    report = await ce.evaluate_candidate(_spec(), chat=wrong_chat, environ={}, items=TINY_TESTSET)
    assert report["verdict"] == "REJECT" and report["reason"] == "BELOW_THRESHOLD"
    assert report["bench"]["overall"] == 0.0


@pytest.mark.asyncio
async def test_bench_scores_substitute_answers_zero():
    async def substituting_chat(model_id, messages, max_tokens):
        prompt = messages[-1]["content"]
        content = "Au" if "chemical symbol" in prompt else "Yes, Fenn is blue."
        return ChatResult(
            content=content, served_model="some-other-model", prompt_tokens=10, completion_tokens=3
        )

    bench = await ce.run_bench(substituting_chat, "cand-1", items=TINY_TESTSET)
    assert bench["overall"] == 0.0
    assert all(not d["served"] for d in bench["items"])


def test_markdown_report_renders_verdict_and_evidence():
    report = {
        "candidate": "x",
        "provider": "p",
        "model_id": "m",
        "base_url": "https://x.test/v1",
        "admit_threshold": 0.8,
        "reference": {"model": "gpt-oss-120b", "overall": 0.988, "source": "INF-005"},
        "verdict": "BLOCKED_NO_CREDENTIALS",
        "reason": "missing: credential env X_KEY",
        "missing": ["credential env X_KEY"],
        "notes": "",
    }
    md = ce.render_markdown(report)
    assert "BLOCKED_NO_CREDENTIALS" in md and "credential env X_KEY" in md


# ---------------------------------------------------------------------------
# End-to-end against the repo's deterministic local model rig
# ---------------------------------------------------------------------------


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.asyncio
async def test_rig_serves_but_is_rejected_on_quality():
    inference_dir = Path(__file__).resolve().parent.parent
    port = _free_port()
    proc = subprocess.Popen(
        [
            sys.executable,
            str(inference_dir / "scripts" / "local_model_server.py"),
            "--port",
            str(port),
            "--model",
            "rig-8b",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.time() + 15
        while True:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as r:
                    if r.status == 200:
                        break
            except Exception:
                if time.time() > deadline:
                    raise RuntimeError("local model rig did not become ready")
                time.sleep(0.2)
        spec = _spec(candidate="local-rig", model_id="rig-8b", base_url=f"http://127.0.0.1:{port}/v1")
        report = await ce.evaluate_candidate(spec, environ={})
        assert report["serve_check"]["verdict"] == "SERVED"
        assert report["verdict"] == "REJECT" and report["reason"] == "BELOW_THRESHOLD"
        assert report["bench"]["overall"] < spec.admit_threshold
    finally:
        proc.terminate()
        proc.wait(timeout=10)
