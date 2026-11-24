#!/usr/bin/env python3
"""Find viral Shorts candidates for the next supervised VyralX cycle.

TASK-VYR-037 discovery. Fixes two defects found 2026-11-22 on U2:
1. The script called bare `yt-dlp`, which is not on PATH when run with the
   system python3 (FileNotFoundError) -- it lives in the repo venv.
2. It passed no --cookies, so YouTube bot-blocks the search and returns [].
   The pipeline's own cookie jar (VyralX/data/youtube_cookies.txt, see
   VyralX/app/services/ytdlp_support.py:cookies_file()) fixes it.
Also uses ytsearch10 with a Python-side 15-60s filter: ytsearch top results
are long-form compilations, so the old --match-filter dropped everything
before we ever saw it.

Read-only: --skip-download, no writes, no uploads. Loop stays OFF.
"""

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

# TASK-VYR-065: hard niche avoid-list guardrail, shared with the app-level
# discovery service and the flat script. Loaded by file path (this script
# runs standalone, no app imports); a missing guard file fails loudly.
_GUARD_PATH = Path(__file__).resolve().parents[1] / "app" / "services" / "niche_guard.py"


def _load_guard():
    if not _GUARD_PATH.is_file():
        raise SystemExit(f"TASK-VYR-065 niche guard missing: {_GUARD_PATH}")
    spec = importlib.util.spec_from_file_location("vyr065_niche_guard", _GUARD_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

QUERIES = [
    "oddly satisfying visual craft silent",
    "insane human precision trickshot silent",
    "mesmerizing soap cutting satisfying asmr",
    "satisfying industrial loop machine silent",
]

ROOT = Path(__file__).resolve().parents[1]  # VyralX/
COOKIES = ROOT / "data" / "youtube_cookies.txt"


def find_ytdlp() -> str:
    found = shutil.which("yt-dlp")
    if found:
        return found
    venv = ROOT.parent / "venv" / "bin" / "yt-dlp"
    if venv.is_file():
        return str(venv)
    raise SystemExit("yt-dlp not found on PATH or in <repo>/venv/bin -- cannot run discovery")


def is_shorts_length(duration) -> bool:
    return isinstance(duration, (int, float)) and 15 <= duration <= 60


def search(query, ytdlp, cookies):
    cmd = [ytdlp, "--skip-download"]
    if cookies is not None:
        cmd += ["--cookies", str(cookies)]
    cmd += ["--dump-json", f"ytsearch10:{query}"]
    p = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="ignore", timeout=120)
    results = []
    for line in p.stdout.strip().split("\n"):
        if not line:
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        results.append({
            "id": d.get("id"),
            "title": d.get("title"),
            "views": d.get("view_count"),
            "duration": d.get("duration"),
            "url": f"https://youtube.com/shorts/{d.get('id')}",
            "uploader": d.get("uploader"),
            "upload_date": d.get("upload_date"),
        })
    return results


def main():
    ytdlp = find_ytdlp()
    cookies = COOKIES if COOKIES.is_file() else None
    if cookies is None:
        print("WARNING: no cookie jar at VyralX/data/youtube_cookies.txt "
              "-- YouTube may bot-block search", file=sys.stderr)
    guard = _load_guard()
    seen = set()
    results = []
    for q in QUERIES:
        # TASK-VYR-065: a query naming a banned niche is rejected outright.
        allowed, reason = guard.check_query(q)
        if not allowed:
            print(f"WARNING: query rejected ({reason}): {q}", file=sys.stderr)
            continue
        for r in search(q, ytdlp, cookies):
            if not r["id"] or r["id"] in seen:
                continue
            seen.add(r["id"])
            if is_shorts_length(r["duration"]):
                results.append({**r, "query": q})
    # TASK-VYR-065: hard niche avoid-list — drop banned-niche candidates
    # before they can enter the pool (rejections logged with their reason).
    results, _rejected = guard.filter_candidates(results)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
