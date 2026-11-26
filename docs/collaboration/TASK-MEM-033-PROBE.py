#!/usr/bin/env python3
"""TASK-MEM-033 — Memora three-section proof, run 4 (Muse 15).

Replicates MEM-024 run 3 (Muse 11) on the live Memora service, Oracle
Server 1, using the MEM-025 probe script as the base. One real
write/read/promotion cycle across private / inter-agent / universal
sections, with promotion latency filed.

Run ON Server 1 (localhost Memora, default http://127.0.0.1:8002).
Keys are read from the service's own env file at runtime on the server
and NEVER printed or copied: only key *names* and presence are logged.

Legs:
  M1   owner-promotion ladder PRIVATE -> SHARED -> UNIVERSAL.
  M1b  direct PRIVATE -> UNIVERSAL (in-place, plain content).
  M1b2 failed-experiment lesson PRIVATE -> UNIVERSAL (dual copy;
       MEM-021 decisive check: copy HMAC differs, content SHA identical).
  M2   auto-promotion: 9 needs from 4 distinct agents -> sweep ->
       PRIVATE -> SHARED, blast radius exactly 1; owner need ignored.
  M3   write-time SHARED (recipient 200, non-recipient 404).
  M4   direct UNIVERSAL write -> 403.
Latency: wall-clock per call + sweep-to-visible, logged per call.
Journal check is done separately (bridge oracle_get_logs / journalctl).

Outputs: numbered JSON files in OUTDIR (default /tmp/muse15_mem033/),
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
OUTDIR = os.environ.get("MEM033_OUTDIR", "/tmp/muse15_mem033")
PREFIX = "MUSE15-TEST-MEM-033"
TASK = "TASK-MEM-033"

PHRASE_M1 = "velvet comet fivefold sapphire"
PHRASE_M1B = "copper falcon sevenfold topaz"   # shared M1b + M1b2 by design
PHRASE_M2 = "silver willow fourfold garnet"
PHRASE_M3 = "amber harbor twofold quartz"

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

M2_NEEDS = [("friday", 2), ("intelx", 1), ("futuris", 3), ("cortex", 3)]

_counter = [0]
_results = []


def log(msg):
    print(time.strftime("%H:%M:%S") + " " + msg, flush=True)


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
    if isinstance(parsed, dict):
        parsed = parsed.get("results", parsed.get("memories", []))
    if not isinstance(parsed, list):
        return None
    for i, item in enumerate(parsed):
        if isinstance(item, dict) and item.get("id") == memory_id:
            return i, item
    return None


def audit_rows(parsed):
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        return parsed.get("results", parsed.get("rows", []))
    return []


def write_memory(agent, content, scope, provenance_extra=None,
                 shared_with=None):
    body = {
        "content_text": content,
        "target_namespace_path": "memora://sentinel/private",
        "memory_type": "episodic",
        "agent_id": agent,
        "scope": scope,
        "provenance": {
            "test_data": True,
            "task": TASK,
        },
    }
    if provenance_extra:
        body["provenance"].update(provenance_extra)
    if shared_with is not None:
        body["shared_with"] = shared_with
    return call(agent, "POST", "/v1/memories", body)


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    found = load_env_file(ENV_FILE)
    log(f"keys present from env file: {sorted(found)}")
    ok = True
    ids = {}

    # 0. Health (no auth).
    s, health, _ = call("memora", "GET", "/health", auth=False)
    ok &= expect(s == 200, f"health 200 (got {s})")
    log(f"health: {json.dumps(health)[:200]}")

    # ---- M1: owner-promotion ladder -------------------------------------
    m1 = (
        f"{PREFIX} — M1 ladder (synthetic test record): the night-shift "
        f"operator logged that a cache flush at 03:12 cut p99 read latency "
        f"from 410 ms to 88 ms. Distinctive phrase: {PHRASE_M1}."
    )
    s, w, _ = write_memory("sentinel", m1, "PRIVATE")
    ok &= expect(s == 201, f"M1 write PRIVATE 201 (got {s})")
    m1_id = w.get("id") if isinstance(w, dict) else None
    if not m1_id:
        log(f"FAIL no memory id in M1 write: {json.dumps(w)[:400]}")
        return 1
    ids["m1"] = m1_id
    log(f"M1 memory id: {m1_id}")
    s, r, _ = call("sentinel", "GET", f"/v1/memories/{m1_id}")
    ok &= expect(s == 200 and r.get("scope") == "PRIVATE",
                 f"M1 owner read 200 PRIVATE (got {s})")
    s, r, _ = call("friday", "GET", f"/v1/memories/{m1_id}")
    ok &= expect(s == 404, f"M1 non-owner read 404 (got {s})")
    s, p, t_p1 = call("sentinel", "POST", "/v1/promotion/promote",
                      {"memory_id": m1_id, "target_scope": "SHARED",
                       "shared_with": ["friday", "intelx"]})
    ok &= expect(s == 200 and p.get("status") == "promoted"
                 and p.get("scope") == "SHARED"
                 and p.get("from_scope") == "PRIVATE"
                 and p.get("path") == "owner_judgement",
                 f"M1 promote PRIVATE->SHARED 200 (got {s} {json.dumps(p)[:200]})")
    log(f"M1 promote -> SHARED latency: {t_p1:.1f} ms")
    for agent in ("friday", "intelx"):
        s, r, _ = call(agent, "GET", f"/v1/memories/{m1_id}")
        ok &= expect(s == 200 and r.get("scope") == "SHARED",
                     f"M1 recipient {agent} read 200 SHARED (got {s})")
    s, r, _ = call("futuris", "GET", f"/v1/memories/{m1_id}")
    ok &= expect(s == 404, f"M1 outsider read 404 at SHARED (got {s})")
    q = urllib.parse.quote(PHRASE_M1)
    s, sr, _ = call("friday", "GET",
                    f"/v1/memories/search?q={q}&limit=50")
    hit_s = find_in_search(sr, m1_id) if s == 200 else None
    ok &= expect(s == 200 and hit_s is not None,
                 f"M1 search finds target for friday (got {s})")
    if hit_s:
        log(f"M1 search friday: rank {hit_s[0] + 1}, "
            f"keyword_score {hit_s[1].get('keyword_score')}")
    s, p, t_p2 = call("sentinel", "POST", "/v1/promotion/promote",
                      {"memory_id": m1_id, "target_scope": "UNIVERSAL"})
    ok &= expect(s == 200 and p.get("status") == "promoted"
                 and p.get("scope") == "UNIVERSAL"
                 and p.get("from_scope") == "SHARED"
                 and "universal_copy_id" not in p,
                 f"M1 promote SHARED->UNIVERSAL 200 in-place (got {s} {json.dumps(p)[:200]})")
    log(f"M1 promote -> UNIVERSAL latency: {t_p2:.1f} ms")
    for agent in ("futuris", "friday"):
        s, r, _ = call(agent, "GET", f"/v1/memories/{m1_id}")
        ok &= expect(s == 200 and r.get("scope") == "UNIVERSAL",
                     f"M1 {agent} read 200 UNIVERSAL (got {s})")

    # ---- M1b: direct PRIVATE -> UNIVERSAL (in-place) --------------------
    m1b = (
        f"{PREFIX} — M1b direct (synthetic test record): a plain status "
        f"note with no lesson provenance, promoted straight to UNIVERSAL. "
        f"Distinctive phrase: {PHRASE_M1B}."
    )
    s, w, _ = write_memory("sentinel", m1b, "PRIVATE")
    ok &= expect(s == 201, f"M1b write PRIVATE 201 (got {s})")
    m1b_id = w.get("id") if isinstance(w, dict) else None
    if not m1b_id:
        log(f"FAIL no memory id in M1b write: {json.dumps(w)[:400]}")
        return 1
    ids["m1b"] = m1b_id
    log(f"M1b memory id: {m1b_id}")
    s, p, t_p3 = call("sentinel", "POST", "/v1/promotion/promote",
                      {"memory_id": m1b_id, "target_scope": "UNIVERSAL"})
    ok &= expect(s == 200 and p.get("status") == "promoted"
                 and p.get("scope") == "UNIVERSAL"
                 and p.get("from_scope") == "PRIVATE"
                 and "universal_copy_id" not in p,
                 f"M1b promote PRIVATE->UNIVERSAL 200 no copy (got {s} {json.dumps(p)[:200]})")
    log(f"M1b promote -> UNIVERSAL latency: {t_p3:.1f} ms")
    for agent in ("friday", "futuris"):
        s, r, _ = call(agent, "GET", f"/v1/memories/{m1b_id}")
        ok &= expect(s == 200 and r.get("scope") == "UNIVERSAL",
                     f"M1b {agent} read 200 UNIVERSAL (got {s})")

    # ---- M1b2: failed-experiment lesson (dual copy) ---------------------
    m1b2 = (
        f"{PREFIX} — M1b2 lesson (synthetic test record, not a real "
        f"experiment): a retry experiment that reused a circuit-breaker "
        f"peer name within the 15 s recovery window failed with a fast-fail "
        f"on the second attempt; the fix was to reset the circuit registry "
        f"between runs. Distinctive phrase: {PHRASE_M1B}."
    )
    s, w, _ = write_memory("sentinel", m1b2, "PRIVATE", {
        "failed_experiment": True,
        "experiment_outcome": "failed",
        "lesson_type": "failed_experiment",
    })
    ok &= expect(s == 201, f"M1b2 write PRIVATE 201 (got {s})")
    m1b2_id = w.get("id") if isinstance(w, dict) else None
    if not m1b2_id:
        log(f"FAIL no memory id in M1b2 write: {json.dumps(w)[:400]}")
        return 1
    ids["m1b2"] = m1b2_id
    log(f"M1b2 memory id: {m1b2_id}")
    s, p, t_p4 = call("sentinel", "POST", "/v1/promotion/promote",
                      {"memory_id": m1b2_id, "target_scope": "UNIVERSAL"})
    copy_id = p.get("universal_copy_id") if isinstance(p, dict) else None
    ok &= expect(s == 200 and p.get("status") == "promoted_dual_copy"
                 and p.get("to_scope") == "UNIVERSAL" and bool(copy_id),
                 f"M1b2 promote -> UNIVERSAL dual copy 200 (got {s} {json.dumps(p)[:300]})")
    log(f"M1b2 promote -> UNIVERSAL latency: {t_p4:.1f} ms")
    ids["m1b2_copy"] = copy_id
    if copy_id:
        log(f"M1b2 copy id: {copy_id}")
    s, r, _ = call("friday", "GET", f"/v1/memories/{m1b2_id}")
    ok &= expect(s == 404, f"M1b2 original as other 404 (got {s})")
    s, r, _ = call("sentinel", "GET", f"/v1/memories/{m1b2_id}")
    ok &= expect(s == 200 and r.get("scope") == "PRIVATE",
                 f"M1b2 original as owner 200 PRIVATE (got {s})")
    if copy_id:
        for agent in ("friday", "futuris"):
            s, r, _ = call(agent, "GET", f"/v1/memories/{copy_id}")
            ok &= expect(s == 200 and r.get("scope") == "UNIVERSAL",
                         f"M1b2 copy {agent} read 200 UNIVERSAL (got {s})")
        s, orig, _ = call("sentinel", "GET", f"/v1/memories/{m1b2_id}")
        s, copy, _ = call("sentinel", "GET", f"/v1/memories/{copy_id}")
        op = orig.get("provenance", {}) if isinstance(orig, dict) else {}
        cp = copy.get("provenance", {}) if isinstance(copy, dict) else {}
        o_hmac = op.get("hmac_signature") or op.get("hmac_prefix")
        c_hmac = cp.get("hmac_signature") or cp.get("hmac_prefix")
        o_sha = op.get("content_sha256", "")
        c_sha = cp.get("content_sha256", "")
        log(f"M1b2 decisive: orig hmac {str(o_hmac)[:16]} sha {str(o_sha)[:16]} | "
            f"copy hmac {str(c_hmac)[:16]} sha {str(c_sha)[:16]} | "
            f"copy promoted_from {cp.get('promoted_from') or cp.get('promoted_from_memory_id')}")
        ok &= expect(bool(o_hmac) and bool(c_hmac) and o_hmac != c_hmac
                     and bool(o_sha) and bool(c_sha)
                     and o_sha[:12] == c_sha[:12],
                     "M1b2 MEM-021 decisive: copy HMAC differs, content SHA identical")
        ok &= expect((cp.get("promoted_from") or
                       cp.get("promoted_from_memory_id")) == m1b2_id,
                      "M1b2 copy promoted_from == original id")
        q2 = urllib.parse.quote(PHRASE_M1B)
        for agent in ("friday", "sentinel", "futuris"):
            s, sr, _ = call(agent, "GET",
                            f"/v1/memories/search?q={q2}&limit=50")
            hit_s = find_in_search(sr, copy_id) if s == 200 else None
            ok &= expect(s == 200 and hit_s is not None,
                         f"M1b2 search finds copy for {agent} (got {s})")
            if hit_s:
                log(f"M1b2 search {agent}: rank {hit_s[0] + 1}, "
                    f"keyword_score {hit_s[1].get('keyword_score')}")

    # ---- M2: auto-promotion (needs + sweep) ------------------------------
    m2 = (
        f"{PREFIX} — M2 auto-promotion (synthetic test record): a runbook "
        f"note that four agents independently asked for during the same "
        f"incident window. Distinctive phrase: {PHRASE_M2}."
    )
    s, w, _ = write_memory("sentinel", m2, "PRIVATE")
    ok &= expect(s == 201, f"M2 write PRIVATE 201 (got {s})")
    m2_id = w.get("id") if isinstance(w, dict) else None
    if not m2_id:
        log(f"FAIL no memory id in M2 write: {json.dumps(w)[:400]}")
        return 1
    ids["m2"] = m2_id
    log(f"M2 memory id: {m2_id}")
    s, a, _ = call("memora", "GET",
                   "/audit?action=MEMORY_NEED_RECORDED&limit=500")
    rows = audit_rows(a)
    before = [x for x in rows if isinstance(x, dict)
              and x.get("memory_id") == m2_id]
    ok &= expect(len(before) == 0,
                 f"M2 0 need rows before (got {len(before)})")
    for agent, count in M2_NEEDS:
        for _ in range(count):
            s, n, _ = call(agent, "POST", "/v1/promotion/need",
                           {"memory_id": m2_id,
                            "reason": "TASK-MEM-033 auto-promotion proof run 4"})
            ok &= expect(s == 200, f"M2 need {agent} 200 (got {s})")
    s, n, _ = call("sentinel", "POST", "/v1/promotion/need",
                   {"memory_id": m2_id, "reason": "owner need (expect ignored)"})
    ok &= expect(s == 200 and isinstance(n, dict)
                 and n.get("status") == "owner_need_ignored",
                 f"M2 owner need ignored (got {s} {json.dumps(n)[:200]})")
    s, sw, t_sweep = call("memora", "POST", "/v1/promotion/sweep",
                          {"window_days": 30})
    promos = sw.get("promotions", []) if isinstance(sw, dict) else []
    hit = [p for p in promos if p.get("memory_id") == m2_id]
    log(f"M2 sweep promotions: {json.dumps(promos)[:600]}")
    ok &= expect(s == 200 and len(hit) == 1
                 and hit[0].get("from_scope") == "PRIVATE"
                 and hit[0].get("to_scope") == "SHARED"
                 and hit[0].get("path") == "auto_repeated_need",
                 f"M2 sweep promotes PRIVATE->SHARED auto (got {s})")
    ok &= expect(len(promos) == 1,
                 f"M2 sweep blast radius exactly 1 (got {len(promos)})")
    log(f"M2 sweep latency: {t_sweep:.1f} ms")
    s, r, t_vis = call("sentinel", "GET", f"/v1/memories/{m2_id}")
    ok &= expect(s == 200 and r.get("scope") == "SHARED",
                 f"M2 owner read after sweep 200 SHARED (got {s})")
    log(f"M2 sweep -> promoted state visible on read: {t_sweep + t_vis:.1f} ms")
    s, r, _ = call("friday", "GET", f"/v1/memories/{m2_id}")
    ok &= expect(s == 200 and r.get("scope") == "SHARED",
                 f"M2 needer (friday) read 200 SHARED (got {s})")

    # ---- M3 / M4: write-time controls ------------------------------------
    m3 = (
        f"{PREFIX} — M3 write-time SHARED (synthetic test record): a "
        f"handoff note written directly as SHARED for friday. "
        f"Distinctive phrase: {PHRASE_M3}."
    )
    s, w, _ = write_memory("sentinel", m3, "SHARED", shared_with=["friday"])
    ok &= expect(s == 201, f"M3 write-time SHARED 201 (got {s})")
    m3_id = w.get("id") if isinstance(w, dict) else None
    if not m3_id:
        log(f"FAIL no memory id in M3 write: {json.dumps(w)[:400]}")
        return 1
    ids["m3"] = m3_id
    log(f"M3 memory id: {m3_id}")
    s, r, _ = call("friday", "GET", f"/v1/memories/{m3_id}")
    ok &= expect(s == 200 and r.get("scope") == "SHARED",
                 f"M3 recipient read 200 SHARED (got {s})")
    s, r, _ = call("intelx", "GET", f"/v1/memories/{m3_id}")
    ok &= expect(s == 404, f"M3 non-recipient read 404 (got {s})")
    m4 = (
        f"{PREFIX} — M4 direct UNIVERSAL write (synthetic test record, "
        f"expect 403): an agent must not author UNIVERSAL directly."
    )
    s, w, _ = write_memory("sentinel", m4, "UNIVERSAL")
    ok &= expect(s == 403, f"M4 direct UNIVERSAL write 403 (got {s})")

    # ---- Audit: promotion rows present -----------------------------------
    s, a, _ = call("memora", "GET",
                   "/audit?action=MEMORY_SCOPE_PROMOTED&limit=20")
    rows = audit_rows(a)
    mine = [x for x in rows if isinstance(x, dict)
            and x.get("memory_id") in (m1_id, m1b_id, m1b2_id, m2_id)]
    ok &= expect(len(mine) >= 4,
                 f"audit has promotion rows for M1/M1b/M1b2/M2 (got {len(mine)})")
    for x in mine:
        d = x.get("details", {}) if isinstance(x.get("details"), dict) else {}
        log(f"audit row: {x.get('memory_id', '')[:8]} "
            f"{d.get('from_scope')}->{d.get('to_scope')} "
            f"path={d.get('path')}")

    with open(os.path.join(OUTDIR, "SUMMARY.json"), "w") as f:
        json.dump({"memory_ids": ids,
                   "phrases": {"m1": PHRASE_M1, "m1b": PHRASE_M1B,
                               "m2": PHRASE_M2, "m3": PHRASE_M3},
                   "all_pass": bool(ok)}, f, indent=2)
    log(f"SUMMARY: {'ALL PASS' if ok else 'FAILURES PRESENT'} ids={json.dumps(ids)}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
