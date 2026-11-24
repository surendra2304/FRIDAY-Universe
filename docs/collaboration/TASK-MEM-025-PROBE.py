#!/usr/bin/env python3
"""TASK-MEM-025 — auto-promotion proof, run 2 (Muse 8).

One failed-experiment lesson, written PRIVATE by sentinel, promoted
PRIVATE -> SHARED -> UNIVERSAL by repeated cross-agent need + sweep,
verified live against the Memora service on Oracle Server 1.

Run ON Server 1 (localhost Memora, default http://127.0.0.1:8002).
Keys are read from the service's own env file at runtime on the server
and NEVER printed or copied: only key *names* and presence are logged.

Method (replicates MEM-018 run 1 + MEM-024 run 3, lesson variant):
  Round 1: 8 needs from 4 distinct agents -> sweep -> PRIVATE -> SHARED
           (in place; lesson dual-copy rule fires only at UNIVERSAL).
  Round 2: 4 needs from 2 OUTSIDE agents (not on the SHARED allow-list)
           -> sweep -> SHARED -> UNIVERSAL via DUAL COPY: the original
           stays SHARED, a UNIVERSAL copy is created (MEM-021 decisive
           check: copy HMAC differs, content SHA identical).
Thresholds (Memora/core/memory/promotion.py, main):
  SHARED:    >= 2 distinct non-owner agents, >= 3 needs total.
  UNIVERSAL: >= 4 distinct non-owner agents, >= 8 needs total,
             >= 2 distinct needers NOT on the SHARED allow-list.

Outputs: numbered JSON files in OUTDIR (default /tmp/muse8_mem025/),
one per call, each with status + elapsed_ms. Exit 0 only if every
leg passes; prints a final SUMMARY line.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = os.environ.get("MEMORA_BASE_URL", "http://127.0.0.1:8002").rstrip("/")
ENV_FILE = os.environ.get(
    "MEMORA_ENV_FILE", "/opt/friday_universe/Memora/.env"
)
OUTDIR = os.environ.get("MEM025_OUTDIR", "/tmp/muse8_mem025")
PHRASE = "quasar harbor ninefold opal"
PREFIX = "MUSE8-TEST-MEM-025"

AGENT_KEY_VARS = {
    "sentinel": "SENTINEL_API_KEY",
    "friday": "FRIDAY_API_KEY",
    "intelx": "INTELX_API_KEY",
    "futuris": "FUTURIS_API_KEY",
    "cortex": "CORTEX_API_KEY",
    "inference": "INFERENCE_API_KEY",
    "stratex": "STRATEX_API_KEY",
    "memora": "MEMORA_API_KEY",
}

ROUND1 = [("friday", 2), ("intelx", 2), ("futuris", 2), ("cortex", 2)]
ROUND2 = [("inference", 2), ("stratex", 2)]

_counter = [0]
_results = []


def log(msg):
    print(msg, flush=True)


def load_env_file(path):
    """Load KEY=VALUE pairs from the service env file (keys stay on disk)."""
    found = []
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k in AGENT_KEY_VARS.values() and k not in os.environ:
                    os.environ[k] = v
                if k in AGENT_KEY_VARS.values():
                    found.append(k)
    except FileNotFoundError:
        log(f"WARN: env file not found: {path}")
    return found


def call(agent, method, path, body=None, auth=True):
    """One Memora API call. Returns (status, parsed_json_or_text, elapsed_ms).

    The API key is sent in the header only; it is never logged or saved.
    """
    _counter[0] += 1
    n = _counter[0]
    url = BASE_URL + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if auth:
        key_var = AGENT_KEY_VARS[agent]
        key = os.environ.get(key_var, "")
        if not key:
            raise SystemExit(f"missing key for agent {agent} ({key_var})")
        req.add_header("X-Agent-Name", agent)
        req.add_header("X-API-Key", key)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            raw = r.read().decode("utf-8", "replace")
            status = r.status
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        status = e.code
    elapsed_ms = (time.time() - t0) * 1000.0
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {"_raw": raw}
    rec = {
        "n": n,
        "agent": agent,
        "method": method,
        "path": path,
        "status": status,
        "elapsed_ms": round(elapsed_ms, 1),
        "response": parsed,
    }
    with open(os.path.join(OUTDIR, f"{n:02d}.json"), "w") as f:
        json.dump(rec, f, indent=2)
    _results.append(rec)
    log(f"[{n:02d}] {agent} {method} {path} -> {status} ({elapsed_ms:.1f} ms)")
    return status, parsed, elapsed_ms


def expect(cond, label):
    cond = bool(cond)
    log(("PASS " if cond else "FAIL ") + label)
    if not cond:
        _results.append({"check_failed": label})
    return cond


def find_in_search(parsed, memory_id):
    if not isinstance(parsed, list):
        return None
    for i, item in enumerate(parsed):
        if isinstance(item, dict) and item.get("id") == memory_id:
            return i, item
    return None


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    found = load_env_file(ENV_FILE)
    log(f"keys present from env file: {sorted(found)}")
    ok = True

    # 0. Health (no auth).
    s, health, _ = call("memora", "GET", "/health", auth=False)
    ok &= expect(s == 200, f"health 200 (got {s})")
    log(f"health: {json.dumps(health)[:300]}")

    # 1. Write the lesson PRIVATE as sentinel.
    lesson = (
        f"{PREFIX} — Lesson (synthetic test record, not a real experiment): "
        "a retry experiment that reused a circuit-breaker peer name within "
        "the 15 s recovery window failed with a fast-fail on the second "
        "attempt; the fix was to reset the circuit registry between runs. "
        f"Distinctive phrase: {PHRASE}. "
        "Provenance: failed-experiment lesson for the MEM-025 "
        "auto-promotion proof, run 2."
    )
    s, w, _ = call("sentinel", "POST", "/v1/memories", {
        "content_text": lesson,
        "target_namespace_path": "memora://sentinel/private",
        "memory_type": "episodic",
        "agent_id": "sentinel",
        "scope": "PRIVATE",
        "provenance": {
            "failed_experiment": True,
            "experiment_outcome": "failed",
            "lesson_type": "failed_experiment",
            "test_data": True,
            "task": "TASK-MEM-025",
        },
    })
    ok &= expect(s == 201, f"write PRIVATE 201 (got {s})")
    mid = w.get("id") if isinstance(w, dict) else None
    if not mid:
        log(f"FAIL no memory id in write response: {json.dumps(w)[:500]}")
        return 1
    log(f"memory id: {mid}")

    s, r, _ = call("sentinel", "GET", f"/v1/memories/{mid}")
    ok &= expect(s == 200 and r.get("scope") == "PRIVATE",
                 f"owner read 200 PRIVATE (got {s} {r.get('scope') if isinstance(r, dict) else ''})")
    s, r, _ = call("friday", "GET", f"/v1/memories/{mid}")
    ok &= expect(s == 404, f"non-owner read 404 (got {s})")

    # Needs before round 1 (audit baseline).
    s, a, _ = call("memora", "GET",
                   "/audit?action=MEMORY_NEED_RECORDED&limit=500")
    rows = a if isinstance(a, list) else a.get("results", []) if isinstance(a, dict) else []
    before = [x for x in rows if isinstance(x, dict)
              and x.get("memory_id") == mid]
    ok &= expect(len(before) == 0, f"0 need rows before round 1 (got {len(before)})")

    # 2. Round 1 needs: 8 needs, 4 distinct agents.
    for agent, count in ROUND1:
        for _ in range(count):
            s, n, _ = call(agent, "POST", "/v1/promotion/need",
                           {"memory_id": mid,
                            "reason": "TASK-MEM-025 auto-promotion proof run 2"})
            ok &= expect(s == 200, f"need {agent} 200 (got {s})")
    s, n, _ = call("sentinel", "POST", "/v1/promotion/need",
                   {"memory_id": mid, "reason": "owner need (expect ignored)"})
    ok &= expect(s == 200 and isinstance(n, dict)
                 and n.get("status") == "owner_need_ignored",
                 f"owner need ignored (got {s} {n})")

    # 3. Sweep 1 -> SHARED.
    s, sw, t_sweep1 = call("memora", "POST", "/v1/promotion/sweep",
                           {"window_days": 30})
    promos = sw.get("promotions", []) if isinstance(sw, dict) else []
    hit = [p for p in promos if p.get("memory_id") == mid]
    ok &= expect(s == 200 and len(hit) == 1
                 and hit[0].get("from_scope", hit[0].get("scope")) == "PRIVATE"
                 and hit[0].get("to_scope") == "SHARED"
                 and hit[0].get("path") == "auto_repeated_need",
                 f"sweep 1 promotes PRIVATE->SHARED auto (got {json.dumps(sw)[:400]})")
    ok &= expect(len(promos) == 1,
                 f"sweep 1 blast radius exactly 1 (got {len(promos)})")
    log(f"sweep 1 latency: {t_sweep1:.1f} ms")
    s, r, t_vis1 = call("sentinel", "GET", f"/v1/memories/{mid}")
    ok &= expect(s == 200 and r.get("scope") == "SHARED",
                 f"owner read after sweep 1: 200 SHARED (got {s})")
    log(f"sweep 1 -> promoted state visible on read: {t_sweep1 + t_vis1:.1f} ms")
    s, r, _ = call("friday", "GET", f"/v1/memories/{mid}")
    ok &= expect(s == 200 and r.get("scope") == "SHARED",
                 f"needer (friday) read 200 SHARED (got {s})")
    s, r, _ = call("inference", "GET", f"/v1/memories/{mid}")
    ok &= expect(s == 404, f"outsider (inference) read 404 at SHARED (got {s})")
    q = urllib.parse.quote(PHRASE)
    s, sr, _ = call("friday", "GET",
                    f"/v1/memories/search?q={q}&limit=50")
    hit_s = find_in_search(sr, mid) if s == 200 else None
    ok &= expect(s == 200 and hit_s is not None,
                 f"search finds target for friday at SHARED (got {s}, hit={hit_s is not None})")
    if hit_s:
        log(f"search friday: rank {hit_s[0] + 1}, "
            f"keyword_score {hit_s[1].get('keyword_score')}")

    # 4. Round 2 needs: 4 needs, 2 OUTSIDE agents (not on SHARED allow-list).
    for agent, count in ROUND2:
        for _ in range(count):
            s, n, _ = call(agent, "POST", "/v1/promotion/need",
                           {"memory_id": mid,
                            "reason": "TASK-MEM-025 auto-promotion proof run 2"})
            ok &= expect(s == 200, f"need {agent} 200 (got {s})")

    # 5. Sweep 2 -> UNIVERSAL via dual copy.
    s, sw, t_sweep2 = call("memora", "POST", "/v1/promotion/sweep",
                           {"window_days": 30})
    promos = sw.get("promotions", []) if isinstance(sw, dict) else []
    hit = [p for p in promos if p.get("memory_id") == mid]
    ok &= expect(s == 200 and len(hit) == 1
                 and hit[0].get("from_scope", hit[0].get("scope")) == "SHARED"
                 and hit[0].get("to_scope") == "UNIVERSAL"
                 and hit[0].get("path") == "auto_repeated_need"
                 and hit[0].get("status") == "promoted_dual_copy",
                 f"sweep 2 promotes SHARED->UNIVERSAL dual copy (got {json.dumps(sw)[:500]})")
    ok &= expect(len(promos) == 1,
                 f"sweep 2 blast radius exactly 1 (got {len(promos)})")
    log(f"sweep 2 latency: {t_sweep2:.1f} ms")
    copy_id = hit[0].get("universal_copy_id") if hit else None
    ok &= expect(bool(copy_id), f"universal_copy_id present (got {copy_id})")

    s, orig, _ = call("sentinel", "GET", f"/v1/memories/{mid}")
    ok &= expect(s == 200 and orig.get("scope") == "SHARED",
                 f"original stays SHARED after dual copy (got {s} {orig.get('scope') if isinstance(orig, dict) else ''})")
    s, r, _ = call("inference", "GET", f"/v1/memories/{mid}")
    ok &= expect(s == 404, f"original as outsider (inference) still 404 (got {s})")
    if copy_id:
        for agent in ("inference", "stratex", "friday", "futuris"):
            s, r, _ = call(agent, "GET", f"/v1/memories/{copy_id}")
            ok &= expect(s == 200 and r.get("scope") == "UNIVERSAL",
                         f"copy read {agent} 200 UNIVERSAL (got {s})")
        s, copy, _ = call("sentinel", "GET", f"/v1/memories/{copy_id}")
        op = orig.get("provenance", {}) if isinstance(orig, dict) else {}
        cp = copy.get("provenance", {}) if isinstance(copy, dict) else {}
        ok &= expect(
            cp.get("hmac_signature") and op.get("hmac_signature")
            and cp.get("hmac_signature") != op.get("hmac_signature")
            and cp.get("content_sha256", "")[:8] == op.get("content_sha256", "")[:8]
            and cp.get("content_sha256"),
            "MEM-021 decisive check: copy HMAC differs, content SHA identical "
            f"(orig hmac {str(op.get('hmac_signature'))[:12]}, "
            f"copy hmac {str(cp.get('hmac_signature'))[:12]}, "
            f"sha {str(cp.get('content_sha256'))[:12]})")
        ok &= expect(cp.get("promoted_from_memory_id") == mid,
                     f"copy promoted_from_memory_id == original (got {cp.get('promoted_from_memory_id')})")
        s, sr, _ = call("inference", "GET",
                        f"/v1/memories/search?q={q}&limit=50")
        hit_s = find_in_search(sr, copy_id) if s == 200 else None
        ok &= expect(s == 200 and hit_s is not None,
                     f"search finds copy for inference at UNIVERSAL (got {s})")
        if hit_s:
            log(f"search inference: rank {hit_s[0] + 1}, "
                f"keyword_score {hit_s[1].get('keyword_score')}")

    # 6. Audit: both promotion rows present.
    s, a, _ = call("memora", "GET",
                   "/audit?action=MEMORY_SCOPE_PROMOTED&limit=20")
    rows = a if isinstance(a, list) else a.get("results", []) if isinstance(a, dict) else []
    mine = [x for x in rows if isinstance(x, dict)
            and x.get("memory_id") == mid]
    ok &= expect(len(mine) >= 2,
                 f"audit has both promotion rows (got {len(mine)})")
    for x in mine:
        d = x.get("details", {}) if isinstance(x.get("details"), dict) else {}
        log(f"audit row: {d.get('from_scope')}->{d.get('to_scope')} "
            f"path={d.get('path')} dual={d.get('failed_experiment_dual')} "
            f"copy={str(d.get('universal_copy_id'))[:8]}")

    with open(os.path.join(OUTDIR, "SUMMARY.json"), "w") as f:
        json.dump({"memory_id": mid, "universal_copy_id": copy_id,
                   "phrase": PHRASE, "all_pass": bool(ok)}, f, indent=2)
    log(f"SUMMARY: {'ALL PASS' if ok else 'FAILURES PRESENT'} "
        f"memory={mid} copy={copy_id}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
