#!/usr/bin/env python3
"""TASK-INF-005 scorer: deterministic checkers over results_raw.jsonl.

Scores each recorded completion 0..1 by item kind:
- facts (summarise): fraction of fact groups found (any synonym in a
  group), halved if the reply breaks the sentence/word cap.
- exact_number / contains / starts_with / one_word (reason, chat).
- json_fields (extract): fraction of fields whose value matches any
  accepted value (case-insensitive string compare; numbers compared
  numerically when both parse).
- code: extract the python block, run the declared unit tests in a
  subprocess (timeout 10s, no network), score = tests passed fraction.
Attribution: a run is scored under the model that SERVED it (response
`model` field); runs where served != requested are also counted in the
requested model's substitution tally. Failed HTTP calls score 0 under
the requested model (nothing served them).
Output: scores.json (full detail) + a markdown table on stdout.
"""
import json, re, subprocess, sys, tempfile, os
from statistics import mean, median

ROOT = "/home/hatch/workspace/inf-005"


def norm(s):
    return re.sub(r"\s+", " ", str(s).lower()).strip()


def score_facts(content, check):
    text = norm(content)
    groups = check["facts"]
    found = sum(1 for g in groups if any(norm(syn) in text for syn in g))
    score = found / len(groups)
    sentences = [s for s in re.split(r"[.!?]+", content) if s.strip()]
    words = len(content.split())
    if len(sentences) > check["max_sentences"] or words > check["max_words"]:
        score *= 0.5
    return score


def score_exact_number(content, check):
    nums = re.findall(r"-?\d+(?:\.\d+)?", content.replace(",", ""))
    expected = check["expected"]
    forbidden = set(check.get("forbidden", []))
    if expected in nums and not (forbidden & set(nums)):
        return 1.0
    return 0.0


def score_contains(content, check):
    text = norm(content)
    if check["expected"] in text and not any(
            f in text for f in check.get("forbidden", [])):
        return 1.0
    return 0.0


def score_starts_with(content, check):
    text = norm(content)
    return 1.0 if text.startswith(check["expected"]) else 0.0


def score_one_word(content, check):
    text = norm(content).strip(" .!\"'`")
    return 1.0 if text == check["expected"] else 0.0


def _num(x):
    try:
        return float(str(x).replace(",", "").replace("$", "").strip())
    except (TypeError, ValueError):
        return None


def score_json_fields(content, check):
    m = re.search(r"\{.*\}", content, re.S)
    if not m:
        return 0.0
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        return 0.0
    fields = check["fields"]
    got = 0
    for key, accepted in fields.items():
        if key not in obj:
            continue
        val = obj[key]
        for acc in accepted:
            na, nv = _num(acc), _num(val)
            if na is not None and nv is not None:
                if abs(na - nv) < 1e-9:
                    got += 1
                    break
            elif norm(acc) == norm(val) or norm(acc) in norm(val):
                got += 1
                break
    return got / len(fields)


def extract_code(content):
    m = re.search(r"```(?:python)?\s*\n(.*?)```", content, re.S)
    return m.group(1) if m else content


def score_code(content, check):
    code = extract_code(content)
    tests = check["tests"]
    func = check["func"]
    harness = code + "\n\nimport json as _j\n_results=[]\n"
    for arg, expected in tests:
        harness += (f"try:\n    _results.append({func}({arg!r}) == {expected!r})\n"
                    "except Exception:\n    _results.append(False)\n")
    harness += "print(_j.dumps(_results))\n"
    try:
        p = subprocess.run([sys.executable, "-c", harness],
                           capture_output=True, text=True, timeout=15)
        results = json.loads(p.stdout.strip().splitlines()[-1])
        return sum(1 for r in results if r) / len(tests)
    except Exception:
        return 0.0


CHECKERS = {
    "facts": score_facts,
    "exact_number": score_exact_number,
    "contains": score_contains,
    "starts_with": score_starts_with,
    "one_word": score_one_word,
    "json_fields": score_json_fields,
    "code": score_code,
}


def main():
    testset = json.load(open(f"{ROOT}/testset.json"))
    items = {it["id"]: it for it in testset["items"]}
    records = [json.loads(l) for l in open(f"{ROOT}/results_raw.jsonl")
               if l.strip()]
    detail = []
    for r in records:
        item = items[r["item"]]
        served = r.get("served_model") or r["requested_model"]
        ok_http = r.get("http") == 200 and bool(r.get("content"))
        score = CHECKERS[item["check"]["kind"]](r.get("content", ""),
                                                item["check"]) if ok_http else 0.0
        detail.append({
            "item": r["item"], "task_type": item["type"],
            "requested_model": r["requested_model"], "served_model": served,
            "substituted": served != r["requested_model"],
            "http": r.get("http"), "latency_s": r.get("latency_s"),
            # Proven L1-cache signature: the gateway's cache replay
            # reports prompt_tokens=0 AND completion_tokens=0 (a live
            # call always consumes prompt tokens). Sub-second latency
            # alone is NOT used: Groq genuinely answers in <1s.
            "cache_suspect": bool(
                isinstance(r.get("usage"), dict)
                and r["usage"].get("prompt_tokens") == 0
                and r["usage"].get("completion_tokens") == 0),
            "usage": r.get("usage"), "score": round(score, 3),
            "content_excerpt": (r.get("content", "") or "")[:160],
        })

    models = sorted({d["requested_model"] for d in detail} |
                    {d["served_model"] for d in detail})
    types = ["summarise", "reason", "code", "extract", "chat"]
    print("| model (as served) | " + " | ".join(types) +
          " | overall | median latency s | mean latency s | calls | ok | subst-in | tokens (in/out) |")
    print("|" + "---|" * 12)
    summary = {}
    for m in models:
        rows = [d for d in detail if d["served_model"] == m]
        per = {}
        for t in types:
            rs = [d["score"] for d in rows if d["task_type"] == t]
            per[t] = round(mean(rs), 3) if rs else None
        allscores = [d["score"] for d in rows]
        lats = [d["latency_s"] for d in rows if d["latency_s"] is not None]
        live_lats = [d["latency_s"] for d in rows
                     if d["latency_s"] is not None and not d["cache_suspect"]]
        tok_in = sum((d["usage"] or {}).get("prompt_tokens", 0) for d in rows)
        tok_out = sum((d["usage"] or {}).get("completion_tokens", 0) for d in rows)
        summary[m] = {"per_type": per,
                      "overall": round(mean(allscores), 3) if allscores else None,
                      "median_latency_s": round(median(lats), 3) if lats else None,
                      "mean_latency_s": round(mean(lats), 3) if lats else None,
                      "median_live_latency_s": round(median(live_lats), 3) if live_lats else None,
                      "cache_suspect_calls": sum(1 for d in rows if d["cache_suspect"]),
                      "calls": len(rows), "ok": sum(1 for d in rows if d["http"] == 200),
                      "substituted_in": sum(1 for d in rows if d["substituted"]),
                      "tokens_in": tok_in, "tokens_out": tok_out}
        print(f"| {m} | " + " | ".join(
            "-" if per[t] is None else f"{per[t]:.2f}" for t in types) +
            f" | {summary[m]['overall']} | {summary[m]['median_latency_s']} | "
            f"{summary[m]['mean_latency_s']} | {len(rows)} | {summary[m]['ok']} | "
            f"{summary[m]['substituted_in']} | {tok_in}/{tok_out} |")
    # As-requested view: what a caller naming model X actually received.
    print("\nAS-REQUESTED (per requested model):")
    for m in sorted({d["requested_model"] for d in detail}):
        rows = [d for d in detail if d["requested_model"] == m]
        own = sum(1 for d in rows if not d["substituted"])
        print(f"  {m}: calls={len(rows)} ok={sum(1 for d in rows if d['http'] == 200)} "
              f"served_as_requested={own}/{len(rows)} "
              f"mean_score_of_answers={round(mean([d['score'] for d in rows]), 3)} "
              f"median_latency_s={round(median([d['latency_s'] for d in rows if d['latency_s'] is not None]), 3)}")
    if "--print" in sys.argv:
        what = sys.argv[sys.argv.index("--print") + 1]
        if what == "summary":
            print("JSON_BEGIN")
            print(json.dumps(summary, indent=1))
            print("JSON_END")
        elif what.startswith("scores"):
            a, b = (int(x) for x in what[6:].split("-"))
            print("JSON_BEGIN")
            print(json.dumps(detail[a:b], indent=1))
            print("JSON_END")
        return
    json.dump(detail, open(f"{ROOT}/scores.json", "w"), indent=1)
    json.dump(summary, open(f"{ROOT}/summary.json", "w"), indent=1)


if __name__ == "__main__":
    main()
