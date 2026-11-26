#!/usr/bin/env python3
"""Find viral Shorts candidates for the next supervised VyralX cycle,
flat-playlist edition (TASK-VYR-055).

Why flat: since 2026-11-24 the full (non-flat) yt-dlp search hangs and
per-video extraction fails on S2 — YouTube's n-challenge can no longer be
solved (deno 2.9.8 vs yt-dlp 2026.10.21 JS incompatibility) and the account
is in YouTube's SABR-only streaming experiment, so no formats are returned
("Only images are available for download"). ``--flat-playlist`` search
bypasses per-video extraction and works (rc 0): entries carry id, title,
duration, view_count, uploader and channel — everything discovery needs.
Media-level gates (caption track, BGM, watermark, loudness) still need a
download and stay BLOCKED until the download path is repaired; see
docs/collaboration/TASK-VYR-055-CANDIDATE-POOL.md.

Otherwise the same proven VYR-037 approach: venv yt-dlp resolution,
the pipeline's own cookie jar, ``ytsearch10`` with a Python-side 15-60s
filter (YouTube search surfaces long-form compilations), known-id
exclusions, most-popular ranking by view_count.

Read-only: --skip-download, no writes, no uploads. Loop stays OFF.
Usage: python3 find_viral_candidates_flat.py [--query-index N]
Prints one JSON object: {query, returned, shorts_len, excluded_known,
fresh: [{id, title, duration, views, uploader, channel, url}]}.
With --query-index, runs that query only; without it, runs all QUERIES.
"""

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

# TASK-VYR-065: hard niche avoid-list guardrail, shared with the app-level
# discovery service. Loaded by file path (this script runs standalone, no
# app imports) and cached; a missing guard file fails loudly — a guardrail
# that silently disappears defeats the purpose.
_GUARD_PATH = Path(__file__).resolve().parents[1] / "app" / "services" / "niche_guard.py"
_guard = None


def _load_guard():
    global _guard
    if _guard is not None:
        return _guard
    if not _GUARD_PATH.is_file():
        raise SystemExit(f"TASK-VYR-065 niche guard missing: {_GUARD_PATH}")
    spec = importlib.util.spec_from_file_location("vyr065_niche_guard", _GUARD_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _guard = module
    return _guard

QUERIES = [
    "most satisfying video ever short",
    "incredible street magic revealed short",
    "satisfying hydraulic press crushing short",
    "amazing domino art chain reaction short",
    "oddly satisfying soap carving short",
    "epic basketball trick shot short",
]

# VYR-037 pool candidate 2 — not present in the S2 exclusion files.
EXTRA_EXCLUDE = {"CpQGaTtppnU"}

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
    # Same 15-60s gate as find_viral_candidates.py; bool is not a duration.
    return (
        isinstance(duration, (int, float))
        and not isinstance(duration, bool)
        and 15 <= duration <= 60
    )


def parse_flat_entry(row: dict) -> dict | None:
    """Reduce one --flat-playlist --dump-json row to the pool record.

    Returns None when the row carries no usable id. Flat rows have no
    licence/subtitle fields — those gates need full extraction and are
    recorded as PENDING/BLOCKED downstream, never inferred here.
    """
    vid = row.get("id")
    if not vid or not isinstance(vid, str):
        return None
    return {
        "id": vid,
        "title": row.get("title"),
        "duration": row.get("duration"),
        "views": row.get("view_count"),
        "uploader": row.get("uploader"),
        "channel": row.get("channel"),
        "url": f"https://youtube.com/shorts/{vid}",
    }


def rank_fresh(entries, excluded: set) -> list:
    """Shorts-length filter + known-id exclusion + most-popular ranking.

    Keeps first-seen order for duplicates, drops excluded ids, and sorts
    by view_count descending (None counts as 0).
    """
    seen = set()
    fresh = []
    for entry in entries:
        if entry is None:
            continue
        if not is_shorts_length(entry.get("duration")):
            continue
        vid = entry.get("id")
        if not vid or vid in seen or vid in excluded:
            continue
        seen.add(vid)
        fresh.append(entry)
    fresh.sort(key=lambda d: -(d.get("views") or 0))
    return fresh


def load_exclusions(data_dir: Path, extra=None) -> set:
    """Known ids: rejected + published + held loop manifest (+ extra)."""
    ids = set(extra or set())

    def _load_json(path, keys):
        try:
            data = json.loads(Path(path).read_text())
        except Exception:
            return
        if isinstance(data, list):
            for item in data:
                if isinstance(item, str):
                    ids.add(item)
                elif isinstance(item, dict):
                    for k in keys:
                        if item.get(k):
                            ids.add(item[k])
        elif isinstance(data, dict):
            ids.update(str(k) for k in data.keys())

    _load_json(data_dir / "rejected_sources.json", [])
    _load_json(data_dir / "published_shorts_manifest.json", ["video_id", "yt_id"])
    try:
        for line in (data_dir / "viral_loop_manifest.jsonl").read_text().splitlines():
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get("video_id"):
                ids.add(d["video_id"])
    except Exception:
        pass
    return ids


def search_flat(query, ytdlp, cookies, timeout=180) -> list:
    """Run one flat ytsearch10 query; return parsed pool records."""
    cmd = [ytdlp, "--skip-download"]
    if cookies is not None:
        cmd += ["--cookies", str(cookies)]
    cmd += ["--flat-playlist", "--dump-json", f"ytsearch10:{query}"]
    p = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="ignore", timeout=timeout)
    results = []
    for line in p.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        entry = parse_flat_entry(row)
        if entry is not None:
            results.append(entry)
    return results


def run_query(query, ytdlp, cookies, excluded: set) -> dict:
    guard = _load_guard()
    # TASK-VYR-065: a query naming a banned niche is rejected outright —
    # no search is issued for it.
    allowed, reason = guard.check_query(query)
    if not allowed:
        return {
            "query": query,
            "returned": 0,
            "shorts_len": 0,
            "excluded_known": len(excluded),
            "fresh": [],
            "rejected_niche": 0,
            "rejected_niche_reasons": [],
            "rejected_query": reason,
        }
    entries = search_flat(query, ytdlp, cookies)
    fresh = rank_fresh(entries, excluded)
    # TASK-VYR-065: hard niche avoid-list — drop banned-niche candidates
    # before they can enter the pool. Rejections are logged with their
    # reason inside filter_candidates and recorded in the output.
    fresh, rejected = guard.filter_candidates(fresh)
    shorts = [e for e in entries if is_shorts_length(e.get("duration"))]
    return {
        "query": query,
        "returned": len(entries),
        "shorts_len": len(shorts),
        "excluded_known": len(excluded),
        "fresh": fresh,
        "rejected_niche": len(rejected),
        "rejected_niche_reasons": [
            {"id": r.get("id"), "rejection_reason": r.get("rejection_reason")}
            for r in rejected
        ],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query-index", type=int, default=None,
                        help="run one query by index into QUERIES (default: all)")
    args = parser.parse_args(argv)
    ytdlp = find_ytdlp()
    cookies = COOKIES if COOKIES.is_file() else None
    if cookies is None:
        print("WARNING: no cookie jar at VyralX/data/youtube_cookies.txt "
              "-- YouTube may bot-block search", file=sys.stderr)
    excluded = load_exclusions(ROOT / "data", EXTRA_EXCLUDE)
    queries = QUERIES
    if args.query_index is not None:
        queries = [QUERIES[args.query_index]]
    for q in queries:
        print(json.dumps(run_query(q, ytdlp, cookies, excluded), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
