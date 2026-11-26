#!/usr/bin/env python3
"""TASK-INF-041 — Inference automated discovery feed.

A scheduled scan of model/tool release sources that files candidate
records (source, date, claim, provenance) into Inference's
candidate-evaluation pipeline. The feed FILES records; it does not
adopt them — every filed record still passes the normal evaluation
gate (benchmarks/evaluate_candidate.py, TASK-IG-INF-03) before any
model enters the catalogue or any route is wired.

Sources (v1, all public, no key, no auth):
  * OpenRouter model catalogue (https://openrouter.ai/api/v1/models)
    — the gateway's own discovery source; a model is a candidate
    when the catalogue lists $0 prompt AND $0 completion pricing.
  * Hugging Face models API (https://huggingface.co/api/models) for a
    curated watchlist of labs that publish open models — a model is
    a candidate when it was created inside the scan window.

Filing rule: an item is filed only when its release/creation date is
inside the window (default 14 days) AND its id is not already in
state.json (seen) AND its model id is not already a candidate spec in
benchmarks/candidates/. A second run files nothing new (idempotent);
state.json is the dedup memory, pruned to 30 days each run.

Layout (relative to Inference/):
  benchmarks/discovery/<record>.json   filed records (seeds + auto)
  benchmarks/discovery/state.json     dedup state + last run

Usage:
  python scripts/discovery_feed.py [--window-days 14] [--dry-run]
  python scripts/discovery_feed.py --bootstrap   # seed state, file nothing

Exit codes: 0 = scan ok (0+ records filed), 2 = a source failed.
A failed source fails the run loudly: a silent empty scan would look
like "no new models" while actually being blind.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

SCHEMA_RECORD = "inference.discovery-record/v1"
SCHEMA_STATE = "inference.discovery-state/v1"

DEFAULT_WINDOW_DAYS = 14
STATE_PRUNE_DAYS = 30
REQUEST_TIMEOUT_S = 30
MAX_RETRIES = 2
# Pause between source fetches. The Hugging Face public API rate-limits
# anonymous bursts (429); pacing is prevention, not a retry-after-429 —
# a 429 still fails that source loudly (see _fetch_json).
REQUEST_PAUSE_S = 5.0

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
HUGGINGFACE_MODELS_URL = "https://huggingface.co/api/models"

# Labs that publish open models. Curated and reviewable: adding an org
# here is a deliberate scope change, not a silent widening.
HF_WATCHLIST_ORGS = [
    "deepseek-ai",
    "google",
    "meta-llama",
    "microsoft",
    "mistralai",
    "NousResearch",
    "nvidia",
    "Qwen",
    "reflection",
]

# Pipeline tags the feed treats as candidate models (text-first).
HF_TEXT_PIPELINES = {"text-generation", "text2text-generation", "conversational"}

# Id markers for derivative artefacts, not new models: speculative-decoding
# draft models, export-format repacks and quantised repacks. The base model
# (when it is itself new) is filed separately; the derivative is skipped and
# listed in the run summary so the omission is auditable, not silent.
HF_DERIVATIVE_MARKERS = (
    "-draft",
    "-onnx",
    "-webgpu",
    "-gguf",
    "-awq",
    "-gptq",
    "-int4",
    "-fp4",
    "-fp8",
    "-bnb",
    "-mlx",
)


def is_derivative_hf(model_id: str) -> bool:
    lowered = model_id.lower()
    return any(marker in lowered for marker in HF_DERIVATIVE_MARKERS)


USER_AGENT = "FRIDAY-Universe inference-discovery-feed/1.0 (+TASK-INF-041)"


def _today() -> _dt.date:
    return _dt.datetime.now(_dt.timezone.utc).date()


def _parse_date(value: str | None) -> _dt.date | None:
    """Parse YYYY-MM-DD or an ISO datetime; None when unparseable."""
    if not value:
        return None
    try:
        return _dt.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _slug(text: str) -> str:
    out = []
    for ch in text.lower():
        out.append(ch if ch.isalnum() else "-")
    slug = "".join(out).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "unnamed"


def _fetch_json(url: str) -> dict | list:
    """GET a JSON URL with retries on transient failures. Raises on failure."""
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if isinstance(exc, urllib.error.HTTPError) and exc.code < 500:
                raise
            time.sleep(2**attempt)
    raise RuntimeError(f"fetch failed after {MAX_RETRIES + 1} tries: {url}: {last_error}")


# ---------------------------------------------------------------------------
# Source adapters: raw payload -> normalised items
# ---------------------------------------------------------------------------


def is_free_openrouter(model: dict) -> bool:
    """Free on OpenRouter = $0 prompt AND $0 completion pricing."""
    pricing = model.get("pricing") or {}
    try:
        return float(pricing.get("prompt", "1")) == 0 and float(pricing.get("completion", "1")) == 0
    except (TypeError, ValueError):
        return False


def openrouter_items(payload: dict) -> list[dict]:
    """Normalise OpenRouter /models payload to feed items."""
    items = []
    for model in payload.get("data") or []:
        if not is_free_openrouter(model):
            continue
        created = model.get("created")
        date = None
        if isinstance(created, (int, float)) and created > 0:
            date = _dt.datetime.fromtimestamp(created, tz=_dt.timezone.utc).date()
        items.append(
            {
                "source": "openrouter",
                "source_id": model.get("id", ""),
                "name": model.get("name") or model.get("id", ""),
                "date": date.isoformat() if date else None,
                "claim": (
                    f"Free model {model.get('id', '')} listed on OpenRouter "
                    f"($0 prompt / $0 completion pricing)"
                    + (f": {(model.get('description') or '')[:300]}" if model.get("description") else "")
                ),
                "source_url": OPENROUTER_MODELS_URL,
                "route": {
                    "provider": "openrouter",
                    "model_id": model.get("id", ""),
                    "base_url": "https://openrouter.ai/api/v1",
                    "api_key_env": "OPENROUTER_API_KEY",
                },
            }
        )
    return items


def huggingface_items(payload: list, org: str) -> tuple[list[dict], list[str]]:
    """Normalise one Hugging Face /api/models page to feed items.

    Returns (items, skipped_derivative_ids). Derivatives are skipped by
    design (see HF_DERIVATIVE_MARKERS); the skip is reported, not hidden.
    """
    items = []
    skipped: list[str] = []
    for model in payload or []:
        model_id = model.get("id", "")
        if is_derivative_hf(model_id):
            skipped.append(model_id)
            continue
        pipeline = model.get("pipeline_tag")
        if pipeline is not None and pipeline not in HF_TEXT_PIPELINES:
            continue
        date = _parse_date(model.get("createdAt"))
        items.append(
            {
                "source": "huggingface",
                "source_id": model.get("id", ""),
                "name": model.get("id", ""),
                "date": date.isoformat() if date else None,
                "claim": (
                    f"New model {model.get('id', '')} published on Hugging Face "
                    f"by {org}"
                    + (f" ({pipeline})" if pipeline else "")
                    + (f", {model.get('downloads', 0)} downloads" if model.get("downloads") else "")
                ),
                "source_url": f"https://huggingface.co/{model.get('id', '')}",
                "route": {
                    "provider": "huggingface",
                    "model_id": model.get("id", ""),
                    "base_url": "",
                    "api_key_env": "",
                },
            }
        )
    return items, skipped


# ---------------------------------------------------------------------------
# Filing
# ---------------------------------------------------------------------------


def record_id_for(item: dict) -> str:
    return f"{item['source']}-{_slug(item['source_id'])}"


def build_record(item: dict, run_date: _dt.date) -> dict:
    """A discovery record: source, date, claim, provenance. Never an adoption."""
    return {
        "schema": SCHEMA_RECORD,
        "id": record_id_for(item),
        "name": item["name"],
        "kind": "model",
        "source": item["source"],
        "source_url": item["source_url"],
        "date": item["date"],
        "discovered_at": run_date.isoformat(),
        "claim": item["claim"],
        "provenance": (
            f"Filed automatically by the Inference discovery feed "
            f"(TASK-INF-041) from {item['source']} on {run_date.isoformat()}. "
            f"Source listing only — no serve-check, no bench, no free-tier "
            f"verification has been run on this record."
        ),
        "verification": "pending — source listing only; not evaluated",
        "route": item.get("route") or {},
        "status": "filed",
        "evaluation": "pending — IG-INF-03 gate (benchmarks/evaluate_candidate.py); not admitted, not routed",
        "filed_by": "discovery-feed",
    }


def load_state(discovery_dir: Path) -> dict:
    path = discovery_dir / "state.json"
    if not path.exists():
        return {
            "schema": SCHEMA_STATE,
            "version": 1,
            "last_run": None,
            "window_days": DEFAULT_WINDOW_DAYS,
            "seen": {},
            "filed": [],
        }
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(discovery_dir: Path, state: dict) -> None:
    (discovery_dir / "state.json").write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def existing_candidate_ids(candidates_dir: Path) -> set[str]:
    """Model ids already filed as evaluation specs — never re-file them."""
    ids: set[str] = set()
    if not candidates_dir.is_dir():
        return ids
    for spec_path in candidates_dir.glob("*.json"):
        try:
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        for key in ("model_id", "candidate"):
            if spec.get(key):
                ids.add(str(spec[key]))
    return ids


def is_new(item: dict, state: dict, known_ids: set[str], run_date: _dt.date, window_days: int) -> bool:
    """In-window AND unseen AND not already a candidate spec."""
    if item["source_id"] in known_ids:
        return False
    seen_key = f"{item['source']}:{item['source_id']}"
    if seen_key in state.get("seen", {}):
        return False
    item_date = _parse_date(item.get("date"))
    if item_date is None:
        return False
    age = (run_date - item_date).days
    return 0 <= age <= window_days


def prune_seen(state: dict, run_date: _dt.date) -> None:
    """Drop seen entries older than the prune horizon (bounded state)."""
    cutoff = run_date - _dt.timedelta(days=STATE_PRUNE_DAYS)
    seen = state.setdefault("seen", {})
    for key in [k for k, v in seen.items() if (_parse_date(v) or _dt.date.min) < cutoff]:
        del seen[key]


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------


def run_scan(
    discovery_dir: Path,
    window_days: int,
    dry_run: bool,
    bootstrap: bool,
    today: _dt.date | None = None,
    pause_s: float = REQUEST_PAUSE_S,
) -> dict:
    """Scan sources, file new records, update state. Returns a summary."""
    run_date = today or _today()
    state = load_state(discovery_dir)
    benchmarks_dir = discovery_dir.parent
    known_ids = existing_candidate_ids(benchmarks_dir / "candidates")

    items: list[dict] = []
    failures: list[str] = []
    skipped_derivatives: list[str] = []
    try:
        items.extend(openrouter_items(_fetch_json(OPENROUTER_MODELS_URL)))
    except Exception as exc:  # noqa: BLE001 - fail loudly, keep scanning
        failures.append(f"openrouter: {exc}")
    for org in HF_WATCHLIST_ORGS:
        # NOTE: the HF API rejects sort=created (400); sort by
        # lastModified and filter on createdAt client-side instead.
        # limit=100: lastModified is a moving window, and a new release
        # must not fall out of the page while older models are updated.
        url = f"{HUGGINGFACE_MODELS_URL}?author={org}&sort=lastModified&direction=-1&limit=100"
        if pause_s:
            time.sleep(pause_s)
        try:
            page_items, page_skipped = huggingface_items(_fetch_json(url), org)
            items.extend(page_items)
            skipped_derivatives.extend(page_skipped)
        except Exception as exc:  # noqa: BLE001 - fail loudly, keep scanning
            failures.append(f"huggingface/{org}: {exc}")

    filed: list[str] = []
    for item in items:
        seen_key = f"{item['source']}:{item['source_id']}"
        if bootstrap:
            state.setdefault("seen", {})[seen_key] = run_date.isoformat()
            continue
        # A record file already on disk is filed, whatever state.json
        # says — the workflow commits records and state together, but
        # the file is the durable memory if state ever goes stale.
        if (discovery_dir / f"{record_id_for(item)}.json").exists():
            state.setdefault("seen", {})[seen_key] = item.get("date") or run_date.isoformat()
            continue
        if not is_new(item, state, known_ids, run_date, window_days):
            state.setdefault("seen", {})[seen_key] = item.get("date") or run_date.isoformat()
            continue
        record = build_record(item, run_date)
        if not dry_run:
            (discovery_dir / f"{record['id']}.json").write_text(
                json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            state.setdefault("seen", {})[seen_key] = item.get("date") or run_date.isoformat()
            state.setdefault("filed", []).append(record["id"])
        filed.append(record["id"])

    if not dry_run:
        prune_seen(state, run_date)
        state["last_run"] = run_date.isoformat()
        state["window_days"] = window_days
        save_state(discovery_dir, state)

    return {
        "run_date": run_date.isoformat(),
        "scanned": len(items),
        "filed": filed,
        "skipped_derivatives": sorted(set(skipped_derivatives)),
        "failures": failures,
        "bootstrap": bootstrap,
        "dry_run": dry_run,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inference automated discovery feed (TASK-INF-041).")
    parser.add_argument(
        "--window-days",
        type=int,
        default=DEFAULT_WINDOW_DAYS,
        help="file items created within this many days (default 14)",
    )
    parser.add_argument("--dry-run", action="store_true", help="report what would be filed; write nothing")
    parser.add_argument("--bootstrap", action="store_true", help="seed state from current catalogues; file nothing")
    parser.add_argument("--discovery-dir", type=Path, default=None, help="override benchmarks/discovery (tests only)")
    args = parser.parse_args(argv)

    inference_root = Path(__file__).resolve().parent.parent
    discovery_dir = args.discovery_dir or (inference_root / "benchmarks" / "discovery")
    discovery_dir.mkdir(parents=True, exist_ok=True)

    summary = run_scan(discovery_dir, args.window_days, args.dry_run, args.bootstrap)
    print(f"discovery feed run {summary['run_date']}: scanned={summary['scanned']} filed={len(summary['filed'])}")
    for record_id in summary["filed"]:
        print(f"  filed {record_id}")
    for skipped_id in summary["skipped_derivatives"]:
        print(f"  skipped (derivative artefact): {skipped_id}")
    for failure in summary["failures"]:
        print(f"  SOURCE FAILED: {failure}", file=sys.stderr)
    if summary["failures"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
