#!/usr/bin/env python3
"""TASK-MEM-027 — three-section live proof, run 4 (Muse TP11).

One real write/read/promotion cycle across private / inter-agent /
universal sections, against the live Memora service on Oracle Server 1.
Worker: Muse TP11 · Date: 2026-11-27 · Branch:
musetp11/task-mem-027-three-section-live-proof-run-4.

Replicates MEM-024 run 3 (Muse 11, full three-section proof) and
MEM-025 run 2 (Muse 8, auto-promotion lesson, dual copy on the auto
path), with the run-3 script defects fixed (see
TASK-MEM-027-CHECKPOINT-1.md).

Run ON Server 1 (localhost Memora, default http://127.0.0.1:8002).
Keys are read from the service's own env file at runtime on the server
and NEVER printed or copied: only key *names* and presence are logged.

Legs:
  M1  owner-promotion ladder, plain memory: PRIVATE -> SHARED
      (shared_with friday, intelx) -> UNIVERSAL, with reads + search
      at every rung.
  M2  auto-promotion lesson: PRIVATE -> SHARED -> UNIVERSAL by
      repeated need + sweep, dual copy at UNIVERSAL (MEM-021
      decisive check: copy HMAC differs, content SHA identical).
  M3  write-time SHARED control.
  M4  direct UNIVERSAL write control (expect 403).
Thresholds (Memora/core/memory/promotion.py, main):
  SHARED:    >= 2 distinct non-owner agents, >= 3 needs total.
  UNIVERSAL: >= 4 distinct non-owner agents, >= 8 needs total,
             >= 2 distinct needers NOT on the SHARED allow-list.

Outputs: numbered JSON files in OUTDIR (default /tmp/musetp11_mem026/),
one per call, each with status + elapsed_ms. Exit 0 only if every
leg passes; prints a final SUMMARY line. Launch with nohup in the
background (bridge 45 s per-call transport limit); poll for
SUMMARY.json.
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
OUTDIR = os.environ.get("MEM026_OUTDIR", "/tmp/musetp11_mem026")
PHRASE_M1 = "cobalt summit ninefold opal"
PHRASE_M2 = "crimson tide fourfold jasper"
PHRASE_M3 = "amber ridge sixfold pearl"
PREFIX = "MUSETP11-TEST-MEM-027"

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


def audit_rows(action, memory_id, limit=500):
    s, a, _ = call("memora", "GET", f"/audit?action={action}&limit={limit}")
    rows = a if isinstance(a, list) else a.get("results", []) if isinstance(a, dict) else []
    mine = [x for x in rows if isinstance(x, dict) and x.get("memory_id") == memory_id]
    return s, mine


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    found = load_env_file(ENV_FILE)
    log(f"keys present from env file: {sorted(found)}")
    ok = True
    ids = {}

    # 0. Health (no auth).
    s, health, _ = call("memora", "GET", "/health", auth=False)
    ok &= expect(s == 200, f"health 200 (got {s})")
    log(f"health: {json.dumps(health)[:300]}")

    # ---- M1: owner-promotion ladder (plain memory) ----
    m1 = (
        f"{PREFIX} — Ladder record (synthetic test record, not a real "
        "memory): a probe note for the three-section promotion ladder. "
        f"Distinctive phrase: {PHRASE_M1}. "
        "Provenance: three-section proof run 4."
    )
    s, w, _ = call("sentinel", "POST", "/v1/memories", {
        "content_text": m1,
        "target_namespace_path": "memora://sentinel/private",
        "memory_type": "episodic",
        "agent_id": "sentinel",
        "scope": "PRIVATE",
        "provenance": {"test_data": True, "task": "TASK-MEM-027"},
    })
    ok &= expect(s == 201, f"M1 write PRIVATE 201 (got {s})")
    m1_id = w.get("id") if isinstance(w, dict) else None
    if not m1_id:
        log(f"FAIL no memory id in M1 write response: {json.dumps(w)[:500]}")
        return 1
    ids["m1"] = m1_id
    log(f"M1 memory id: {m1_id}")

    s, r, _ = call("sentinel", "GET", f"/v1/memories/{m1_id}")
    ok &= expect(s == 200 and r.get("scope") == "PRIVATE",
                 f"M1 owner read 200 PRIVATE (got {s} {r.get('scope') if isinstance(r, dict) else ''})")
    s, r, _ = call("friday", "GET", f"/v1/memories/{m1_id}")
    ok &= expect(s == 404, f"M1 non-owner read 404 (got {s})")

    s, p, t_prom1 = call("sentinel", "POST", "/v1/promotion/promote", {
        "memory_id": m1_id, "target_scope": "SHARED",
        "shared_with": ["friday", "intelx"],
    })
    ok &= expect(s == 200 and isinstance(p, dict)
                 and p.get("status") == "promoted"
                 and p.get("scope") == "SHARED"
                 and p.get("from_scope") == "PRIVATE",
                 f"M1 promote -> SHARED 200 (got {s} {json.dumps(p)[:300]})")
    log(f"M1 promote -> SHARED latency: {t_prom1:.1f} ms")
    for agent in ("friday", "intelx"):
        s, r, _ = call(agent, "GET", f"/v1/memories/{m1_id}")
        ok &= expect(s == 200 and r.get("scope") == "SHARED",
                     f"M1 recipient {agent} read 200 SHARED (got {s})")
    s, r, _ = call("futuris", "GET", f"/v1/memories/{m1_id}")
    ok &= expect(s == 404, f"M1 outsider (futuris) read 404 at SHARED (got {s})")
    q1 = urllib.parse.quote(PHRASE_M1)
    s, sr, _ = call("friday", "GET", f"/v1/memories/search?q={q1}&limit=50")
    hit_s = find_in_search(sr, m1_id) if s == 200 else None
    ok &= expect(s == 200 and hit_s is not None,
                 f"M1 search finds target for friday at SHARED (got {s})")
    if hit_s:
        log(f"M1 search friday: rank {hit_s[0] + 1}, "
            f"keyword_score {hit_s[1].get('keyword_score')}")

    s, p, t_prom2 = call("sentinel", "POST", "/v1/promotion/promote", {
        "memory_id": m1_id, "target_scope": "UNIVERSAL",
    })
    ok &= expect(s == 200 and isinstance(p, dict)
                 and p.get("status") == "promoted"
                 and p.get("scope") == "UNIVERSAL"
                 and p.get("from_scope") == "SHARED",
                 f"M1 promote -> UNIVERSAL 200 (got {s} {json.dumps(p)[:300]})")
    log(f"M1 promote -> UNIVERSAL latency: {t_prom2:.1f} ms")
    for agent in ("futuris", "friday"):
        s, r, _ = call(agent, "GET", f"/v1/memories/{m1_id}")
        ok &= expect(s == 200 and r.get("scope") == "UNIVERSAL",
                     f"M1 {agent} read 200 UNIVERSAL (got {s})")
    s, sr, _ = call("futuris", "GET", f"/v1/memories/search?q={q1}&limit=50")
    hit_s = find_in_search(sr, m1_id) if s == 200 else None
    ok &= expect(s == 200 and hit_s is not None,
                 f"M1 search finds target for futuris at UNIVERSAL (got {s})")
    _, m1_rows = audit_rows("MEMORY_SCOPE_PROMOTED", m1_id, limit=20)
    ok &= expect(len(m1_rows) >= 2,
                 f"M1 audit has both promotion rows (got {len(m1_rows)})")

    # ---- M2: auto-promotion lesson (MEM-025 core, re-proved) ----
    lesson = (
        f"{PREFIX} — Lesson (synthetic test record, not a real experiment): "
        "a retry experiment that reused a circuit-breaker peer name within "
        "the 15 s recovery window failed with a fast-fail on the second "
        "attempt; the fix was to reset the circuit registry between runs. "
        f"Distinctive phrase: {PHRASE_M2}. "
        "Provenance: failed-experiment lesson for the MEM-027 "
        "auto-promotion proof, run 4."
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
            "task": "TASK-MEM-027",
        },
    })
    ok &= expect(s == 201, f"M2 write PRIVATE 201 (got {s})")
    m2_id = w.get("id") if isinstance(w, dict) else None
    if not m2_id:
        log(f"FAIL no memory id in M2 write response: {json.dumps(w)[:500]}")
        return 1
    ids["m2"] = m2_id
    log(f"M2 memory id: {m2_id}")

    s, r, _ = call("sentinel", "GET", f"/v1/memories/{m2_id}")
    ok &= expect(s == 200 and r.get("scope") == "PRIVATE",
                 f"M2 owner read 200 PRIVATE (got {s} {r.get('scope') if isinstance(r, dict) else ''})")
    s, r, _ = call("friday", "GET", f"/v1/memories/{m2_id}")
    ok &= expect(s == 404, f"M2 non-owner read 404 (got {s})")

    _, before = audit_rows("MEMORY_NEED_RECORDED", m2_id)
    ok &= expect(len(before) == 0, f"M2 0 need rows before round 1 (got {len(before)})")

    for agent, count in ROUND1:
        for _ in range(count):
            s, n, _ = call(agent, "POST", "/v1/promotion/need",
                           {"memory_id": m2_id,
                            "reason": "TASK-MEM-027 auto-promotion proof run 4"})
            ok &= expect(s == 200, f"M2 need {agent} 200 (got {s})")
    s, n, _ = call("sentinel", "POST", "/v1/promotion/need",
                   {"memory_id": m2_id, "reason": "owner need (expect ignored)"})
    ok &= expect(s == 200 and isinstance(n, dict)
                 and n.get("status") == "owner_need_ignored",
                 f"M2 owner need ignored (got {s} {n})")

    s, sw, t_sweep1 = call("memora", "POST", "/v1/promotion/sweep",
                           {"window_days": 30})
    promos = sw.get("promotions", []) if isinstance(sw, dict) else []
    hit = [p for p in promos if p.get("memory_id") == m2_id]
    ok &= expect(s == 200 and len(hit) == 1
                 and hit[0].get("from_scope", hit[0].get("scope")) == "PRIVATE"
                 and hit[0].get("to_scope") == "SHARED"
                 and hit[0].get("path") == "auto_repeated_need",
                 f"M2 sweep 1 promotes PRIVATE->SHARED auto (got {json.dumps(sw)[:400]})")
    ok &= expect(len(promos) == 1,
                 f"M2 sweep 1 blast radius exactly 1 (got {len(promos)})")
    log(f"M2 sweep 1 latency: {t_sweep1:.1f} ms")
    s, r, t_vis1 = call("sentinel", "GET", f"/v1/memories/{m2_id}")
    ok &= expect(s == 200 and r.get("scope") == "SHARED",
                 f"M2 owner read after sweep 1: 200 SHARED (got {s})")
    log(f"M2 sweep 1 -> promoted state visible on read: {t_sweep1 + t_vis1:.1f} ms")
    s, r, _ = call("friday", "GET", f"/v1/memories/{m2_id}")
    ok &= expect(s == 200 and r.get("scope") == "SHARED",
                 f"M2 needer (friday) read 200 SHARED (got {s})")
    s, r, _ = call("inference", "GET", f"/v1/memories/{m2_id}")
    ok &= expect(s == 404, f"M2 outsider (inference) read 404 at SHARED (got {s})")
    q2 = urllib.parse.quote(PHRASE_M2)
    s, sr, _ = call("friday", "GET",
                    f"/v1/memories/search?q={q2}&limit=50")
    hit_s = find_in_search(sr, m2_id) if s == 200 else None
    ok &= expect(s == 200 and hit_s is not None,
                 f"M2 search finds target for friday at SHARED (got {s})")
    if hit_s:
        log(f"M2 search friday: rank {hit_s[0] + 1}, "
            f"keyword_score {hit_s[1].get('keyword_score')}")

    for agent, count in ROUND2:
        for _ in range(count):
            s, n, _ = call(agent, "POST", "/v1/promotion/need",
                           {"memory_id": m2_id,
                            "reason": "TASK-MEM-027 auto-promotion proof run 4"})
            ok &= expect(s == 200, f"M2 need {agent} 200 (got {s})")

    s, sw, t_sweep2 = call("memora", "POST", "/v1/promotion/sweep",
                           {"window_days": 30})
    promos = sw.get("promotions", []) if isinstance(sw, dict) else []
    hit = [p for p in promos if p.get("memory_id") == m2_id]
    ok &= expect(s == 200 and len(hit) == 1
                 and hit[0].get("from_scope", hit[0].get("scope")) == "SHARED"
                 and hit[0].get("to_scope") == "UNIVERSAL"
                 and hit[0].get("path") == "auto_repeated_need"
                 and hit[0].get("status") == "promoted_dual_copy",
                 f"M2 sweep 2 promotes SHARED->UNIVERSAL dual copy (got {json.dumps(sw)[:500]})")
    ok &= expect(len(promos) == 1,
                 f"M2 sweep 2 blast radius exactly 1 (got {len(promos)})")
    log(f"M2 sweep 2 latency: {t_sweep2:.1f} ms")
    copy_id = hit[0].get("universal_copy_id") if hit else None
    ok &= expect(bool(copy_id), f"M2 universal_copy_id present (got {copy_id})")
    ids["m2_copy"] = copy_id

    s, orig, _ = call("sentinel", "GET", f"/v1/memories/{m2_id}")
    ok &= expect(s == 200 and orig.get("scope") == "SHARED",
                 f"M2 original stays SHARED after dual copy (got {s} {orig.get('scope') if isinstance(orig, dict) else ''})")
    s, r, _ = call("inference", "GET", f"/v1/memories/{m2_id}")
    ok &= expect(s == 404, f"M2 original as outsider (inference) still 404 (got {s})")
    if copy_id:
        for agent in ("inference", "stratex", "friday", "futuris"):
            s, r, _ = call(agent, "GET", f"/v1/memories/{copy_id}")
            ok &= expect(s == 200 and r.get("scope") == "UNIVERSAL",
                         f"M2 copy read {agent} 200 UNIVERSAL (got {s})")
        s, copy, _ = call("sentinel", "GET", f"/v1/memories/{copy_id}")
        op = orig.get("provenance", {}) if isinstance(orig, dict) else {}
        cp = copy.get("provenance", {}) if isinstance(copy, dict) else {}
        ok &= expect(
            cp.get("hmac_signature") and op.get("hmac_signature")
            and cp.get("hmac_signature") != op.get("hmac_signature")
            and cp.get("content_sha256", "")[:8] == op.get("content_sha256", "")[:8]
            and cp.get("content_sha256"),
            "M2 MEM-021 decisive check: copy HMAC differs, content SHA identical "
            f"(orig hmac {str(op.get('hmac_signature'))[:12]}, "
            f"copy hmac {str(cp.get('hmac_signature'))[:12]}, "
            f"sha {str(cp.get('content_sha256'))[:12]})")
        ok &= expect(cp.get("promoted_from_memory_id") == m2_id,
                     f"M2 copy promoted_from_memory_id == original (got {cp.get('promoted_from_memory_id')})")
        s, sr, _ = call("inference", "GET",
                        f"/v1/memories/search?q={q2}&limit=50")
        hit_s = find_in_search(sr, copy_id) if s == 200 else None
        ok &= expect(s == 200 and hit_s is not None,
                     f"M2 search finds copy for inference at UNIVERSAL (got {s})")
        if hit_s:
            log(f"M2 search inference: rank {hit_s[0] + 1}, "
                f"keyword_score {hit_s[1].get('keyword_score')}")

    _, m2_rows = audit_rows("MEMORY_SCOPE_PROMOTED", m2_id, limit=20)
    ok &= expect(len(m2_rows) >= 2,
                 f"M2 audit has both promotion rows (got {len(m2_rows)})")
    for x in m2_rows:
        d = x.get("details", {}) if isinstance(x.get("details"), dict) else {}
        log(f"M2 audit row: {d.get('from_scope')}->{d.get('to_scope')} "
            f"path={d.get('path')} dual={d.get('failed_experiment_dual')} "
            f"copy={str(d.get('universal_copy_id'))[:8]}")

    # ---- M3: write-time SHARED control ----
    m3 = (
        f"{PREFIX} — Write-time SHARED control (synthetic test record): "
        "written directly at SHARED scope for one recipient. "
        f"Distinctive phrase: {PHRASE_M3}."
    )
    s, w, _ = call("sentinel", "POST", "/v1/memories", {
        "content_text": m3,
        "target_namespace_path": "memora://sentinel/private",
        "memory_type": "episodic",
        "agent_id": "sentinel",
        "scope": "SHARED",
        "shared_with": ["friday"],
        "provenance": {"test_data": True, "task": "TASK-MEM-027"},
    })
    ok &= expect(s == 201, f"M3 write-time SHARED 201 (got {s})")
    m3_id = w.get("id") if isinstance(w, dict) else None
    if m3_id:
        ids["m3"] = m3_id
        s, r, _ = call("friday", "GET", f"/v1/memories/{m3_id}")
        ok &= expect(s == 200 and r.get("scope") == "SHARED",
                     f"M3 recipient (friday) read 200 SHARED (got {s})")
        s, r, _ = call("intelx", "GET", f"/v1/memories/{m3_id}")
        ok &= expect(s == 404, f"M3 non-recipient (intelx) read 404 (got {s})")
    else:
        log(f"FAIL no memory id in M3 write response: {json.dumps(w)[:500]}")
        ok = False

    # ---- M4: direct UNIVERSAL write control ----
    s, w, _ = call("sentinel", "POST", "/v1/memories", {
        "content_text": f"{PREFIX} — Direct UNIVERSAL write control "
                        "(synthetic test record, expect 403).",
        "target_namespace_path": "memora://sentinel/private",
        "memory_type": "episodic",
        "agent_id": "sentinel",
        "scope": "UNIVERSAL",
        "provenance": {"test_data": True, "task": "TASK-MEM-027"},
    })
    ok &= expect(s == 403, f"M4 direct UNIVERSAL write 403 (got {s})")

    with open(os.path.join(OUTDIR, "SUMMARY.json"), "w") as f:
        json.dump({"memory_ids": ids, "phrases": {
            "m1": PHRASE_M1, "m2": PHRASE_M2, "m3": PHRASE_M3},
            "all_pass": bool(ok)}, f, indent=2)
    log(f"SUMMARY: {'ALL PASS' if ok else 'FAILURES PRESENT'} ids={ids}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
