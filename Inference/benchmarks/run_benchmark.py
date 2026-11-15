#!/usr/bin/env python3
"""TASK-INF-005 detached benchmark runner (runs ON Server 1).

Reads /tmp/inf005/job_all.json {models, items, system}; for every
(model, item) pair POSTs to the local Inference gateway and appends
one JSON record per line to /tmp/inf005/results.jsonl. Writes
/tmp/inf005/DONE when finished. Designed to be started with nohup so
bridge round-trips stay short; progress = line count of results.jsonl.
Auth: the gateway API key is read from the service env files on this
host and used only as a localhost request header (never printed).
"""
import glob, json, os, time, urllib.request, urllib.error

BASE = "/tmp/inf005"
URL = "http://127.0.0.1:8001/v1/chat/completions"


def find_api_key():
    for path in ["/opt/friday_universe/Inference/.env",
                 "/opt/friday_universe/FRIDAY/.env"] + \
            sorted(glob.glob("/etc/friday-universe/*.env")):
        try:
            lines = open(path).read().splitlines()
        except OSError:
            continue
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _, value = line.partition("=")
            name = name.strip()
            value = value.strip().strip('"').strip("'")
            if name in ("INFERENCE_API_KEY", "INFERENCE_KEY") and value:
                return value, f"{name}@{os.path.basename(path)}"
    return None, None


API_KEY, AUTH_SOURCE = find_api_key()


def one(model, item, system):
    body = {"model": model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": item["prompt"]}],
            "temperature": 0,
            "max_tokens": item.get("max_tokens", 500),
            "stream": False}
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["X-INFERENCE-API-KEY"] = API_KEY
    req = urllib.request.Request(URL, data=json.dumps(body).encode(),
                                 headers=headers, method="POST")
    rec = {"item": item["id"], "task_type": item["type"],
           "requested_model": model, "auth_source": AUTH_SOURCE}
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=150) as r:
            rec["latency_s"] = round(time.time() - t0, 3)
            rec["http"] = r.status
            payload = json.loads(r.read())
        rec["served_model"] = payload.get("model")
        rec["usage"] = payload.get("usage")
        if "provenance" in payload:
            rec["provenance"] = payload["provenance"]
        choices = payload.get("choices") or []
        rec["content"] = (choices[0].get("message") or {}).get("content", "") \
            if choices else ""
        rec["finish_reason"] = choices[0].get("finish_reason") if choices else None
    except urllib.error.HTTPError as e:
        rec["latency_s"] = round(time.time() - t0, 3)
        rec["http"] = e.code
        try:
            rec["error_body"] = e.read().decode()[:400]
        except Exception:
            rec["error_body"] = ""
        rec["content"] = ""
    except Exception as e:
        rec["latency_s"] = round(time.time() - t0, 3)
        rec["http"] = 0
        rec["error_body"] = f"{type(e).__name__}: {e}"[:400]
        rec["content"] = ""
    return rec


def main():
    job = json.load(open(f"{BASE}/job_all.json"))
    out = open(f"{BASE}/results.jsonl", "a", buffering=1)
    for model in job["models"]:
        for item in job["items"]:
            rec = one(model, item, job["system"])
            out.write(json.dumps(rec) + "\n")
            time.sleep(1.0)
    open(f"{BASE}/DONE", "w").write("done\n")


if __name__ == "__main__":
    main()
