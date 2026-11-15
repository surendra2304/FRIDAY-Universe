"""TASK-IG-INF-03 — repeatable new-model evaluation pipeline.

Corpus sources: the free/open-model discovery reels (4 sources →
"a feed of new free models is only useful if each one is proven
before it is routed to"), MiniMax as a candidate route (DZPYR_0y4VV),
Bytez as a candidate aggregator (DbyNa6Np-pz, De4qvI2zaCe), and the
LMArena-style side-by-side idea (folded in here as the candidate-vs-
reference comparison table).

THE DISCIPLINE (INF-005, binding): a model enters the catalogue only
after a benchmark shows it actually SERVES. INF-005's evidence:

* gemini-3.8-flash was named in the catalogue for a day while serving
  0/15 requests — every call was silently substituted by another
  model. A response is therefore evidence of serving ONLY when the
  served model id equals the requested id.
* The gateway's L1 cache replays report prompt_tokens=0 AND
  completion_tokens=0; a live call always consumes prompt tokens.
  A 0/0-usage response is a replay signature, never a serve
  (benchmarks/score.py flags the same signature as cache_suspect).

Pipeline: candidate spec → credential/route gate → serve-check
(N distinct-nonce probes, all must genuinely serve) → the fixed
INF-005 bench (benchmarks/testset.json, deterministic programmatic
checkers from benchmarks/score.py — no LLM judge) → side-by-side
against the recorded reference baseline → verdict:

* ADMIT — serve-check passed and bench overall >= the spec's
  admit_threshold. (Admission itself is still a human/coordinator
  step: add the model to MODEL_CATALOG + REL-043 rankings. This
  pipeline produces the evidence; it does not edit the catalogue.)
* REJECT — reason NEVER_SERVES (0 probes genuinely served: the
  gemini-3.8-flash pattern), UNRELIABLE_SERVE (some probes served,
  some did not), or BELOW_THRESHOLD (serves, but quality under bar),
  with per-probe and per-item evidence attached.
* BLOCKED_NO_CREDENTIALS / BLOCKED_NO_ROUTE — the spec names an
  api_key_env that is unset, or lacks a base_url/model_id. No
  network call is made; the report lists exactly what is missing.
  This is the honest state of the MiniMax and Bytez candidates
  until an operator provisions keys on the server.

Usage (library): evaluate_candidate(spec, chat) where chat is any
async callable (model_id, messages, max_tokens) -> ChatResult;
make_http_chat() builds one for any OpenAI-compatible endpoint —
including this repo's own gateway and, via TASK-IG-INF-02, any
custom endpoint. CLI: benchmarks/evaluate_candidate.py.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

BENCH_DIR = Path(__file__).resolve().parent


def _load_checkers() -> dict:
    spec = importlib.util.spec_from_file_location("inf005_score", BENCH_DIR / "score.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("inf005_score", module)
    spec.loader.exec_module(module)  # main() is __main__-guarded; import is inert
    return module.CHECKERS


CHECKERS = _load_checkers()

#: The INF-005 bench, fixed. Changing the bench means a new version
#: and re-baselining every recorded score — never edit in place.
TESTSET_PATH = BENCH_DIR / "testset.json"


def load_testset() -> list[dict]:
    return json.loads(TESTSET_PATH.read_text(encoding="utf-8"))["items"]


# ---------------------------------------------------------------------------
# Candidate spec
# ---------------------------------------------------------------------------


@dataclass
class CandidateSpec:
    candidate: str
    model_id: str | None = None
    base_url: str | None = None
    api_key_env: str | None = None
    provider: str = ""
    admit_threshold: float = 0.80
    reference_model: str = "gpt-oss-120b"
    reference_overall: float | None = None
    reference_source: str = ""
    notes: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "CandidateSpec":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})

    @classmethod
    def load(cls, path: str | Path) -> "CandidateSpec":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def missing_route(self, environ: Any) -> list[str]:
        """What stands between this spec and an evaluable route."""
        missing = []
        if not self.base_url:
            missing.append("base_url")
        if not self.model_id:
            missing.append("model_id")
        if self.api_key_env and not (environ.get(self.api_key_env) or "").strip():
            missing.append(f"credential env {self.api_key_env}")
        return missing


# ---------------------------------------------------------------------------
# Chat abstraction
# ---------------------------------------------------------------------------


@dataclass
class ChatResult:
    content: str = ""
    served_model: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    error: str | None = None
    latency_s: float = 0.0


ChatFn = Callable[[str, list[dict], int], Awaitable[ChatResult]]


def make_http_chat(base_url: str, api_key: str | None, timeout: float = 120.0) -> ChatFn:
    """Build a chat callable for any OpenAI-compatible endpoint."""
    import httpx

    url = base_url.rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    async def chat(model_id: str, messages: list[dict], max_tokens: int) -> ChatResult:
        started = time.perf_counter()
        try:
            # trust_env=False: the evaluation must reach the operator-
            # specified endpoint directly (LAN rigs, localhost, provider
            # APIs). An ambient HTTP(S)_PROXY from the environment would
            # reroute — or break — those calls and could carry the
            # candidate's key to a third party.
            async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
                resp = await client.post(
                    url,
                    headers=headers,
                    json={"model": model_id, "messages": messages, "max_tokens": max_tokens},
                )
        except Exception as exc:  # transport failure is evidence, not a crash
            return ChatResult(error=f"{exc.__class__.__name__}: {exc}", latency_s=time.perf_counter() - started)
        latency = time.perf_counter() - started
        if resp.status_code != 200:
            return ChatResult(error=f"HTTP {resp.status_code}", latency_s=latency)
        try:
            body = resp.json()
            choice = (body.get("choices") or [{}])[0]
            content = ((choice.get("message") or {}).get("content")) or ""
            usage = body.get("usage") or {}
            return ChatResult(
                content=content,
                served_model=body.get("model"),
                prompt_tokens=usage.get("prompt_tokens"),
                completion_tokens=usage.get("completion_tokens"),
                latency_s=latency,
            )
        except Exception as exc:
            return ChatResult(error=f"unparseable response: {exc.__class__.__name__}", latency_s=latency)

    return chat


# ---------------------------------------------------------------------------
# Serve-check — the INF-005 lesson, mechanised
# ---------------------------------------------------------------------------

_PROBE_PROMPTS = (
    "Reply with exactly one word: the colour of a clear daytime sky.",
    "What is 17 + 25? Reply with the number only.",
    "In one short sentence, say what a lighthouse is for.",
)


def probe_genuinely_served(result: ChatResult, model_id: str) -> tuple[bool, str]:
    """Whether one response is evidence the named model actually served.

    Returns (served, reason). The three rejection reasons are the
    three ways INF-005 was fooled: an error/empty answer, a silent
    substitution, and a cache replay (0 prompt AND 0 completion
    tokens — a live call always consumes prompt tokens).
    """
    if result.error:
        return False, f"error: {result.error}"
    if not (result.content or "").strip():
        return False, "empty content"
    if result.served_model != model_id:
        return False, f"substituted: served by {result.served_model!r}, not {model_id!r}"
    if result.prompt_tokens == 0 and result.completion_tokens == 0:
        return False, "cache replay signature (prompt_tokens=0 and completion_tokens=0)"
    return True, "served"


async def serve_check(chat: ChatFn, model_id: str, probes: int = 3) -> dict:
    """Probe the candidate with distinct-nonce prompts.

    Every probe carries a unique nonce so an exact-match cache cannot
    replay an earlier answer and masquerade as a live serve.
    """
    evidence = []
    served_count = 0
    for i in range(max(1, probes)):
        nonce = uuid.uuid4().hex[:12]
        prompt = f"{_PROBE_PROMPTS[i % len(_PROBE_PROMPTS)]} (probe ref {nonce})"
        try:
            result = await chat(model_id, [{"role": "user", "content": prompt}], 64)
        except Exception as exc:
            result = ChatResult(error=f"{exc.__class__.__name__}: {exc}")
        served, reason = probe_genuinely_served(result, model_id)
        served_count += 1 if served else 0
        evidence.append(
            {
                "probe": i + 1,
                "served": served,
                "reason": reason,
                "served_model": result.served_model,
                "prompt_tokens": result.prompt_tokens,
                "completion_tokens": result.completion_tokens,
                "latency_s": round(result.latency_s, 3),
            }
        )
    if served_count == len(evidence):
        verdict = "SERVED"
    elif served_count == 0:
        verdict = "NEVER_SERVES"
    else:
        verdict = "UNRELIABLE_SERVE"
    return {"verdict": verdict, "served": served_count, "probes": evidence}


# ---------------------------------------------------------------------------
# Bench — the fixed INF-005 testset, deterministic checkers
# ---------------------------------------------------------------------------


async def run_bench(chat: ChatFn, model_id: str, items: list[dict] | None = None) -> dict:
    items = load_testset() if items is None else items
    detail = []
    for item in items:
        try:
            result = await chat(
                model_id, [{"role": "user", "content": item["prompt"]}], int(item.get("max_tokens", 256))
            )
        except Exception as exc:
            result = ChatResult(error=f"{exc.__class__.__name__}: {exc}")
        served, reason = probe_genuinely_served(result, model_id)
        # An answer the named model did not genuinely produce scores 0 —
        # a substitute's quality is not the candidate's quality.
        score = CHECKERS[item["check"]["kind"]](result.content, item["check"]) if served else 0.0
        detail.append(
            {
                "item": item["id"],
                "type": item["type"],
                "served": served,
                "serve_note": reason,
                "score": round(float(score), 3),
            }
        )
    per_type: dict[str, float] = {}
    for task_type in sorted({d["type"] for d in detail}):
        scores = [d["score"] for d in detail if d["type"] == task_type]
        per_type[task_type] = round(sum(scores) / len(scores), 3)
    overall = round(sum(d["score"] for d in detail) / len(detail), 3) if detail else 0.0
    return {"overall": overall, "per_type": per_type, "items": detail}


# ---------------------------------------------------------------------------
# Full evaluation
# ---------------------------------------------------------------------------


async def evaluate_candidate(
    spec: CandidateSpec,
    chat: ChatFn | None = None,
    environ: Any = None,
    items: list[dict] | None = None,
    probes: int = 3,
) -> dict:
    """Run the full pipeline for one candidate spec. Never raises on
    candidate-side failures — they are the report's content."""
    environ = os.environ if environ is None else environ
    report: dict[str, Any] = {
        "candidate": spec.candidate,
        "provider": spec.provider,
        "model_id": spec.model_id,
        "base_url": spec.base_url,
        "admit_threshold": spec.admit_threshold,
        "reference": {
            "model": spec.reference_model,
            "overall": spec.reference_overall,
            "source": spec.reference_source,
        },
        "notes": spec.notes,
        "verdict": None,
        "reason": None,
    }
    missing = spec.missing_route(environ)
    if missing:
        report["missing"] = missing
        report["verdict"] = (
            "BLOCKED_NO_CREDENTIALS"
            if any(m.startswith("credential env") for m in missing)
            else "BLOCKED_NO_ROUTE"
        )
        report["reason"] = "missing: " + ", ".join(missing)
        return report
    if chat is None:
        key = (environ.get(spec.api_key_env) or "").strip() if spec.api_key_env else None
        chat = make_http_chat(spec.base_url or "", key or None)
    serve = await serve_check(chat, spec.model_id or "", probes=probes)
    report["serve_check"] = serve
    if serve["verdict"] != "SERVED":
        report["verdict"] = "REJECT"
        report["reason"] = serve["verdict"]
        return report
    bench = await run_bench(chat, spec.model_id or "", items=items)
    report["bench"] = bench
    if bench["overall"] >= spec.admit_threshold:
        report["verdict"] = "ADMIT"
    else:
        report["verdict"] = "REJECT"
        report["reason"] = "BELOW_THRESHOLD"
    return report


def render_markdown(report: dict) -> str:
    lines = [
        f"# Candidate evaluation — {report['candidate']}",
        "",
        f"- Provider: {report.get('provider') or '-'}",
        f"- Model id: {report.get('model_id') or '-'}",
        f"- Base URL: {report.get('base_url') or '-'}",
        f"- **Verdict: {report['verdict']}**"
        + (f" ({report['reason']})" if report.get("reason") else ""),
        f"- Admit threshold: {report['admit_threshold']}",
    ]
    ref = report.get("reference") or {}
    if ref.get("overall") is not None:
        lines.append(
            f"- Reference: {ref['model']} overall {ref['overall']} ({ref.get('source') or 'recorded baseline'})"
        )
    if report.get("missing"):
        lines += ["", "Missing before evaluation can run: " + ", ".join(report["missing"])]
    serve = report.get("serve_check")
    if serve:
        lines += ["", f"## Serve-check: {serve['verdict']} ({serve['served']}/{len(serve['probes'])} probes)"]
        for p in serve["probes"]:
            lines.append(
                f"- probe {p['probe']}: served={p['served']} — {p['reason']} "
                f"(served_model={p['served_model']!r}, tokens={p['prompt_tokens']}/{p['completion_tokens']}, {p['latency_s']}s)"
            )
    bench = report.get("bench")
    if bench:
        lines += ["", f"## Bench (inf005-bench-v1): overall {bench['overall']}"]
        for task_type, score in bench["per_type"].items():
            lines.append(f"- {task_type}: {score}")
    if report.get("notes"):
        lines += ["", report["notes"]]
    return "\n".join(lines) + "\n"
