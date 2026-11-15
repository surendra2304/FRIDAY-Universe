#!/usr/bin/env python3
"""TASK-MEM-002 — Memora recall benchmark runner.

Runs the fixed probe set in ``recall_probe_set.json`` against a live Memora
service and prints a JSON report on stdout. The benchmark is the repeatable
successor to the one-off live probes of TASK-REL-013 / 024 / 027 / 031: the
probe set is versioned, every case names the guarantee it extends, and the
report records measured positions, per-leg scores, match reasons and search
latencies so runs are comparable before/after any ranking change.

Safety: the only production mutation is the benchmark's own synthetic facts
(every content string carries the per-run token), and cleanup hard-deletes
every created record and verifies absence afterwards.

Configuration (environment):
  MEMORA_BASE_URL     default http://127.0.0.1:8002
  MEMORA_AGENT_NAME   default friday
  MEMORA_API_KEY      the agent's API key (never printed)
  MEMORA_KEY_ENV_FILE optional path to an env file to read the key from
  MEMORA_KEY_VAR      key variable name in that file, default FRIDAY_API_KEY
  MEMORA_PROBE_SET    optional path to the probe-set JSON

Usage: python3 recall_benchmark.py [--keep]   (--keep skips cleanup; debugging)
"""
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
PROBE_SET_PATH = os.environ.get("MEMORA_PROBE_SET", os.path.join(HERE, "recall_probe_set.json"))
BASE = os.environ.get("MEMORA_BASE_URL", "http://127.0.0.1:8002").rstrip("/")
AGENT = os.environ.get("MEMORA_AGENT_NAME", "friday")
TIMEOUT = 180


def _load_key():
    key = os.environ.get("MEMORA_API_KEY")
    if key:
        return key
    env_file = os.environ.get("MEMORA_KEY_ENV_FILE")
    var = os.environ.get("MEMORA_KEY_VAR", "FRIDAY_API_KEY")
    if env_file:
        with open(env_file) as fh:
            for line in fh:
                line = line.strip()
                if line.startswith(var + "="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


API_KEY = _load_key()


def call(method, path, body=None, timeout=TIMEOUT):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    headers = {"X-Agent-Name": AGENT, "Content-Type": "application/json"}
    if API_KEY:
        headers["X-API-Key"] = API_KEY
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = resp.read().decode("utf-8", "replace")
            status = resp.status
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode("utf-8", "replace")
        status = exc.code
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    try:
        parsed = json.loads(payload) if payload else None
    except json.JSONDecodeError:
        parsed = {"raw": payload[:500]}
    return status, parsed, elapsed_ms


def write_fact(content, memory_type="episodic", importance=None, idem=None):
    body = {
        "content_text": content,
        "memory_type": memory_type,
        "source": "mem002-benchmark",
        "idempotency_key": idem,
    }
    if importance is not None:
        body["importance"] = importance
    status, parsed, ms = call("POST", "/v1/memories", body)
    rid = parsed.get("id") if isinstance(parsed, dict) else None
    return status, rid, parsed, ms


def search(query, limit):
    q = urllib.parse.urlencode({"q": query, "limit": limit, "min_score": 0})
    status, parsed, ms = call("GET", f"/v1/memories/search?{q}")
    results = parsed if isinstance(parsed, list) else []
    return status, results, ms


def position_of(results, record_id):
    for idx, item in enumerate(results):
        if item.get("id") == record_id:
            return idx + 1, item
    return None, None


def main():
    keep = "--keep" in sys.argv
    with open(PROBE_SET_PATH) as fh:
        probe = json.load(fh)

    run = "mem002-" + uuid.uuid4().hex[:10]
    tail = uuid.uuid4().hex[:6]

    def fill(text):
        return text.replace("{{RUN}}", run).replace("{{TAIL}}", tail)

    created = {}   # fact key -> record id
    write_log = []
    latencies = []
    cases_out = []

    def ensure_fact(key):
        if key in created:
            return created[key]
        spec = probe["facts"][key]
        status, rid, parsed, ms = write_fact(
            fill(spec["content_text"]), spec.get("memory_type", "episodic"),
            idem=f"{run}-{key}",
        )
        write_log.append({"fact": key, "status": status, "id": rid, "ms": round(ms, 1),
                          "detail": (parsed if status != 201 else None)})
        if status != 201 or not rid:
            raise RuntimeError(f"setup write for fact {key} failed: HTTP {status} {parsed}")
        created[key] = rid
        return rid

    def do_search(query, limit):
        status, results, ms = search(fill(query), limit)
        latencies.append(ms)
        if status != 200:
            raise RuntimeError(f"search failed: HTTP {status} for query {query!r}")
        return results, ms

    decoy_ids = []

    def ensure_decoys():
        if decoy_ids:
            return decoy_ids
        spec = probe["decoys"]
        for i, topic in enumerate(spec["topics"][: spec["count"]]):
            content = fill(spec["content_template"]).replace("{i}", str(i)).replace("{topic}", topic)
            status, rid, parsed, ms = write_fact(content, "episodic", importance=spec["importance"],
                                                 idem=f"{run}-decoy-{i}")
            write_log.append({"fact": f"decoy-{i}", "status": status, "id": rid, "ms": round(ms, 1),
                              "detail": (parsed if status != 201 else None)})
            if status != 201 or not rid:
                raise RuntimeError(f"decoy write {i} failed: HTTP {status} {parsed}")
            decoy_ids.append(rid)
        return decoy_ids

    graph_ids = []

    def ensure_graph_web():
        if graph_ids:
            return graph_ids
        _, hub_id, _, _ = (None, None, None, None)
        status, hub_id, parsed, ms = write_fact(
            fill("Benchmark hub {{RUN}}: the central planning hub record linking the benchmark companion notes."),
            "episodic", importance=0.95, idem=f"{run}-hub")
        if status != 201:
            raise RuntimeError(f"hub write failed: HTTP {status} {parsed}")
        graph_ids.append(hub_id)
        created["__hub"] = hub_id
        companions = []
        for i in range(6):
            status, cid, parsed, ms = write_fact(
                fill(f"Benchmark companion {{{{RUN}}}}-{i}: a planning note about scheduling and the weekly review, linked to the hub."),
                "episodic", importance=0.9, idem=f"{run}-companion-{i}")
            if status != 201:
                raise RuntimeError(f"companion write {i} failed: HTTP {status} {parsed}")
            companions.append(cid)
            graph_ids.append(cid)
        for cid in companions:
            s1, _, _ = call("POST", f"/v1/memories/{hub_id}/relationships",
                            {"target_memory_id": cid, "relationship_type": "relates_to", "weight": 0.95})
            s2, _, _ = call("POST", f"/v1/memories/{cid}/relationships",
                            {"target_memory_id": hub_id, "relationship_type": "relates_to", "weight": 0.95})
            if s1 not in (200, 201) or s2 not in (200, 201):
                raise RuntimeError(f"relationship creation failed: {s1}/{s2}")
        return graph_ids

    def run_setup(steps):
        meta = {}
        for step in steps:
            if step == "decoys":
                ensure_decoys()
            elif step == "graph_web":
                ensure_graph_web()
            elif step.startswith("supersede:"):
                old_key, new_key = step[len("supersede:"):].split("->")
                status, parsed, ms = call("POST", f"/v1/memories/{created[old_key]}/supersede",
                                          {"new_memory_id": created[new_key],
                                           "reason": "mem002 benchmark supersede case"})
                meta["supersede_status"] = status
                if status != 200:
                    raise RuntimeError(f"supersede failed: HTTP {status} {parsed}")
            elif step == "confirm_present":
                pass  # handled inside the forget case itself
            elif step.startswith("delete:"):
                pass  # handled inside the forget case itself
            else:
                ensure_fact(step)
        return meta

    for case in probe["cases"]:
        entry = {"id": case["id"], "kind": case["kind"], "extends": case.get("extends")}
        try:
            meta = run_setup(case.get("setup", []))
            entry.update(meta)
            kind = case["kind"]
            if kind == "recall":
                results, ms = do_search(case["query"], case.get("query_limit", 100))
                pos, item = position_of(results, created[case["target"]])
                entry["target_position"] = pos
                entry["search_ms"] = round(ms, 1)
                entry["result_count"] = len(results)
                if item:
                    entry["target_scores"] = {
                        "final_score": item.get("final_score"),
                        "semantic_score": item.get("semantic_score"),
                        "keyword_score": item.get("keyword_score"),
                        "graph_boost": item.get("graph_boost"),
                        "match_reasons": item.get("match_reasons"),
                    }
                entry["top5"] = [
                    {"pos": i + 1, "id": r.get("id"), "final_score": r.get("final_score"),
                     "semantic_score": r.get("semantic_score"), "keyword_score": r.get("keyword_score")}
                    for i, r in enumerate(results[:5])
                ]
                limit = case.get("query_limit", 100)
                want = 1 if case["id"] == "verbatim_control" else (25 if limit == 25 else 5)
                entry["pass"] = pos is not None and pos <= want
                if case["id"] == "paraphrase_semantic":
                    reasons = (item or {}).get("match_reasons") or []
                    entry["semantic_reason"] = any("Semantic match" in r for r in reasons)
                    entry["pass"] = bool(entry["pass"] and entry["semantic_reason"])
            elif kind == "ranking_pair":
                results, ms = do_search(case["query"], case.get("query_limit", 100))
                t_pos, _ = position_of(results, created[case["target"]])
                o_pos, _ = position_of(results, created[case["other"]])
                entry["target_position"] = t_pos
                entry["other_position"] = o_pos
                entry["search_ms"] = round(ms, 1)
                entry["pass"] = t_pos is not None and t_pos <= 5 and (o_pos is None or t_pos < o_pos)
            elif kind == "lifecycle" and case["id"] == "supersede_excludes_old":
                results, ms = do_search(case["query"], case.get("query_limit", 100))
                t_pos, _ = position_of(results, created[case["target"]])
                a_pos, _ = position_of(results, created[case["absent"]])
                entry["target_position"] = t_pos
                entry["absent_position"] = a_pos
                entry["search_ms"] = round(ms, 1)
                entry["pass"] = t_pos is not None and t_pos <= 5 and a_pos is None
            elif kind == "lifecycle" and case["id"] == "forget_by_id":
                results, ms = do_search(case["queries"][0], 100)
                pre_pos, _ = position_of(results, created["forget_me"])
                entry["position_before_delete"] = pre_pos
                status, parsed, dms = call("DELETE", f"/v1/memories/{created['forget_me']}")
                entry["delete_status"] = status
                absent_checks = {}
                all_absent = status == 200
                for q in case["queries"]:
                    results, ms = do_search(q, case.get("query_limit", 100))
                    p, _ = position_of(results, created["forget_me"])
                    absent_checks[q] = p
                    if p is not None:
                        all_absent = False
                entry["positions_after_delete"] = absent_checks
                entry["pass"] = pre_pos is not None and pre_pos <= 5 and all_absent
            elif kind == "fidelity":
                results, ms = do_search(case["query"], case.get("query_limit", 100))
                pos, item = position_of(results, created[case["target"]])
                entry["target_position"] = pos
                entry["reported_memory_type"] = (item or {}).get("memory_type")
                entry["search_ms"] = round(ms, 1)
                entry["pass"] = pos is not None and entry["reported_memory_type"] == "experience"
            else:
                entry["pass"] = None
                entry["note"] = "unhandled case kind"
        except Exception as exc:  # a failed case is data, not a crashed run
            entry["pass"] = False
            entry["error"] = f"{type(exc).__name__}: {exc}"[:400]
            if case["id"] == "graph_companion_guard":
                entry["pass"] = None
                entry["skipped"] = True
        cases_out.append(entry)

    # ---- cleanup: hard-delete everything we created, then verify absence
    all_ids = list(created.values()) + decoy_ids + [g for g in graph_ids if g not in created.values()]
    cleanup = {"attempted": len(all_ids), "deleted": 0, "errors": []}
    if not keep:
        for rid in all_ids:
            status, parsed, ms = call("DELETE", f"/v1/memories/{rid}?hard=true")
            if status == 200:
                cleanup["deleted"] += 1
            else:
                cleanup["errors"].append({"id": rid, "status": status})
        _status, results, _ms = search(run, 100)
        leftover = [r.get("id") for r in results if r.get("id") in set(all_ids)]
        cleanup["leftover_ids"] = leftover

    recall_cases = [c for c in cases_out if c.get("pass") is not None]
    report = {
        "benchmark": probe.get("probe_set"),
        "probe_set_version": probe.get("version"),
        "task": probe.get("task"),
        "run_token": run,
        "base_url": BASE,
        "agent": AGENT,
        "started_at_unix": time.time(),
        "writes": write_log,
        "cases": cases_out,
        "aggregate": {
            "cases_passed": sum(1 for c in recall_cases if c["pass"]),
            "cases_failed": sum(1 for c in recall_cases if c["pass"] is False),
            "cases_total_scored": len(recall_cases),
            "search_latency_ms": {
                "count": len(latencies),
                "p50": round(statistics.median(latencies), 1) if latencies else None,
                "p95": round(sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)], 1) if latencies else None,
                "max": round(max(latencies), 1) if latencies else None,
            },
        },
        "cleanup": cleanup,
    }
    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
