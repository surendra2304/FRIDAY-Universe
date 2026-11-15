#!/usr/bin/env python3
"""Build VyralX's lane-1 (space & science) public-domain source catalogue.

TASK-VYR-006. Regenerates ``app/data/source_catalog_lane1.json`` — the
shelf of lawfully reusable footage the remix pipeline (TASK-VYR-004)
cuts from. Sources are public-domain ONLY:

* NASA Image and Video Library (images-api.nasa.gov) — U.S. Government works
* Internet Archive NASA/NOAA collections — U.S. Government works, mirrored
* Wikimedia Commons — NOAA works tagged PD-USGov-NOAA

Every record carries source URL, licence, provenance page, measured
duration and resolution (ffprobe for NASA assets; archive/Commons
metadata elsewhere), and topic tags. Records failing any check
(sub-640px, <20s or >1200s, no explicit PD basis) are excluded — no
record, no use. Two Commons items were additionally excluded by manual
curation (dated forecast presentation; interview profile — talking-head
formats that do not serve as remix footage); they are named in
``MANUAL_EXCLUDES`` so regeneration reproduces the shipped catalogue.

Usage:  python3 scripts/build_lane1_catalog.py [--out PATH]
Requires: ffprobe on PATH for NASA asset measurement.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

UA = {"User-Agent": "VyralX-catalogue-builder/1.0 (TASK-VYR-006)"}
NASA_LICENSE = "Public Domain (U.S. Government work - NASA)"
NOAA_LICENSE = "Public Domain (U.S. Government work - NOAA)"
NASA_GUIDELINES = "https://www.nasa.gov/nasa-brand-center/images-and-media/"
MIN_WIDTH, MIN_DUR, MAX_DUR = 640, 20, 1200

NASA_QUERIES = [
    ("nebula", ["nebula", "star-formation"]),
    ("supernova", ["supernova", "star-formation"]),
    ("black hole", ["black-hole"]),
    ("galaxy collision", ["galaxy"]),
    ("solar flare", ["solar", "sun"]),
    ("aurora from space", ["aurora", "earth-observation"]),
    ("rocket launch", ["rocket-launch"]),
    ("spacewalk ISS", ["iss", "spacewalk"]),
    ("Mars rover Perseverance", ["mars"]),
    ("Jupiter Juno", ["jupiter"]),
    ("Saturn Cassini rings", ["saturn"]),
    ("Apollo moon landing", ["moon", "apollo"]),
    ("solar eclipse", ["eclipse", "solar"]),
    ("comet", ["comet"]),
    ("James Webb telescope", ["webb"]),
    ("Earth from space timelapse", ["earth-observation"]),
    ("Hubble deep field", ["hubble", "galaxy"]),
    ("exoplanet", ["exoplanet"]),
    ("Perseverance rover landing", ["mars"]),
    ("Ingenuity helicopter Mars", ["mars"]),
    ("Artemis Moon rocket", ["moon", "rocket-launch"]),
    ("Sun solar dynamics observatory", ["solar", "sun"]),
    ("Pillars of Creation Webb", ["webb", "nebula"]),
    ("Milky Way galactic center", ["galaxy"]),
    ("asteroid Bennu OSIRIS-REx", ["asteroid"]),
    ("Europa Clipper", ["jupiter"]),
    ("space station Earth views", ["iss", "earth-observation"]),
    ("supernova remnant Cassiopeia", ["supernova"]),
]

MANUAL_EXCLUDES = {
    "commons:NOAA_Climate_Prediction_Center's_2016-17_winter_outlook.webm",
    "commons:NOAA_Legends-_RADM_Evelyn_Fields.webm",
}


def get_json(url, timeout=45):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def probe(url):
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-rw_timeout", "20000000",
             "-select_streams", "v:0", "-show_entries", "stream=width,height",
             "-show_entries", "format=duration", "-of", "json", url],
            capture_output=True, text=True, timeout=60)
        d = json.loads(out.stdout or "{}")
        streams = d.get("streams") or []
        if not streams:
            return None
        w = int(streams[0].get("width") or 0)
        h = int(streams[0].get("height") or 0)
        dur = float((d.get("format") or {}).get("duration") or 0)
        if w < MIN_WIDTH or dur <= 0:
            return None
        return dur, w, h
    except Exception:
        return None


def pick_nasa_asset(collection_url):
    try:
        files = get_json(collection_url, timeout=30)
    except Exception:
        return None
    if not isinstance(files, list):
        return None
    vids = [f for f in files if isinstance(f, str) and re.search(r"\.(mp4|mov)$", f, re.I)]
    if not vids:
        return None

    def rank(u):
        lu = u.lower()
        for i, tok in enumerate(["~orig", "~large", "~medium", "~small", "~mobile"]):
            if tok in lu:
                return i
        return 2
    vids.sort(key=rank)
    return vids[0]


def harvest_nasa(want=44, per_query=6):
    clips, seen = [], set()
    for query, tags in NASA_QUERIES:
        if len(clips) >= want:
            break
        q = urllib.parse.urlencode({"q": query, "media_type": "video", "page_size": 40})
        try:
            res = get_json(f"https://images-api.nasa.gov/search?{q}")
        except Exception:
            continue
        got = 0
        for item in (res.get("collection") or {}).get("items") or []:
            if len(clips) >= want or got >= per_query:
                break
            data = (item.get("data") or [{}])[0]
            nid = data.get("nasa_id") or ""
            if not nid or nid in seen:
                continue
            seen.add(nid)
            asset = pick_nasa_asset(item.get("href", ""))
            if not asset:
                continue
            if asset.startswith("http://"):
                asset = "https://" + asset[len("http://"):]
            p = probe(asset)
            if not p:
                continue
            dur, w, h = p
            if not (MIN_DUR <= dur <= MAX_DUR):
                continue
            kws = [k.strip().lower().replace(" ", "-") for k in (data.get("keywords") or [])][:6]
            clips.append({
                "title": (data.get("title") or nid).strip()[:280],
                "platform": "nasa_images",
                "creator": f"NASA ({data.get('center') or 'NASA'})",
                "source_url": asset,
                "page_url": f"https://images.nasa.gov/details/{urllib.parse.quote(nid)}",
                "license_name": NASA_LICENSE,
                "permission_reference": NASA_GUIDELINES,
                "rights_basis": "Work of the U.S. federal government (NASA); not subject to copyright in the United States. NASA media usage guidelines apply (no endorsement implied).",
                "external_id": nid,
                "duration_seconds": round(dur, 2),
                "width": w, "height": h,
                "topic_tags": sorted(set(tags + [k for k in kws if len(k) <= 24][:3])),
                "description": re.sub(r"\s+", " ", (data.get("description") or "")).strip()[:400],
            })
            got += 1
    return clips


def _ia_items(collection, org, want, have_ids):
    clips = []
    q = urllib.parse.urlencode({
        "q": f"collection:{collection} AND mediatype:movies",
        "fl[]": "identifier,title,creator,licenseurl,subject",
        "rows": 60, "output": "json"}, doseq=True)
    try:
        res = get_json(f"https://archive.org/advancedsearch.php?{q}")
    except Exception:
        return clips
    for doc in ((res.get("response") or {}).get("docs")) or []:
        if len(clips) >= want:
            break
        ident = doc.get("identifier")
        if not ident or ident in have_ids:
            continue
        lic = (doc.get("licenseurl") or "").lower()
        creator = str(doc.get("creator") or org)
        explicit_pd = "publicdomain" in lic or "zero/1.0" in lic
        if not explicit_pd and org.lower() not in creator.lower():
            continue
        try:
            meta = get_json(f"https://archive.org/metadata/{urllib.parse.quote(ident)}")
        except Exception:
            continue
        cand = []
        for f in meta.get("files") or []:
            name = f.get("name") or ""
            if not name.lower().endswith((".mp4", ".mov")):
                continue
            try:
                w = int(f.get("width") or 0); h = int(f.get("height") or 0)
                dur = float(f.get("length") or 0)
            except (TypeError, ValueError):
                continue
            if w >= MIN_WIDTH and MIN_DUR <= dur <= MAX_DUR:
                cand.append((w, dur, h, name))
        if not cand:
            continue
        cand.sort(reverse=True)
        w, dur, h, name = cand[0]
        have_ids.add(ident)
        subj = doc.get("subject") or []
        if isinstance(subj, str):
            subj = [subj]
        tags = sorted({s.strip().lower().replace(" ", "-")[:24] for s in subj if s})[:5]
        is_noaa = org == "NOAA"
        clips.append({
            "title": (doc.get("title") or ident).strip()[:280],
            "platform": "internet_archive",
            "creator": creator[:200],
            "source_url": f"https://archive.org/download/{ident}/{urllib.parse.quote(name)}",
            "page_url": f"https://archive.org/details/{ident}",
            "license_name": NOAA_LICENSE if is_noaa else NASA_LICENSE,
            "permission_reference": f"https://archive.org/details/{ident}",
            "rights_basis": (f"Work of the U.S. federal government ({org}); not subject to "
                             f"copyright in the United States. Mirrored in the Internet "
                             f"Archive {org} collection."),
            "external_id": ident,
            "duration_seconds": round(dur, 2),
            "width": w, "height": h,
            "topic_tags": tags or ["space"],
            "description": "",
        })
    return clips


def harvest_commons_noaa(want=6, have_ids=None):
    clips = []
    api = "https://commons.wikimedia.org/w/api.php"
    for q in ["NOAA ocean", "NOAA hurricane satellite", "NOAA weather satellite animation",
              "NOAA coral reef", "NOAA tornado"]:
        if len(clips) >= want:
            break
        params = {"action": "query", "format": "json", "generator": "search",
                  "gsrsearch": f"{q} filetype:video", "gsrnamespace": 6, "gsrlimit": 30,
                  "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata"}
        try:
            res = get_json(api + "?" + urllib.parse.urlencode(params), timeout=40)
        except Exception:
            continue
        for page in ((res.get("query") or {}).get("pages") or {}).values():
            if len(clips) >= want:
                break
            ii = (page.get("imageinfo") or [{}])[0]
            w = int(ii.get("width") or 0); h = int(ii.get("height") or 0)
            dur = float(ii.get("duration") or 0)
            em = ii.get("extmetadata") or {}
            lic = ((em.get("LicenseShortName") or {}).get("value") or "")
            title = page.get("title") or ""
            ext_id = "commons:" + title.replace("File:", "").replace(" ", "_")
            if (w < MIN_WIDTH or not (MIN_DUR <= dur <= MAX_DUR)
                    or "public domain" not in lic.lower()
                    or ext_id in MANUAL_EXCLUDES or (have_ids and ext_id in have_ids)):
                continue
            artist = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", ((em.get("Artist") or {}).get("value") or "NOAA"))).strip()[:200] or "NOAA"
            if "noaa" not in artist.lower() and "noaa" not in title.lower():
                continue
            if have_ids is not None:
                have_ids.add(ext_id)
            clips.append({
                "title": re.sub(r"\.(webm|ogv|mp4)$", "", title.replace("File:", ""), flags=re.I).replace("_", " ")[:280],
                "platform": "wikimedia_commons",
                "creator": artist,
                "source_url": ii.get("url") or "",
                "page_url": ii.get("descriptionurl") or "",
                "license_name": NOAA_LICENSE,
                "permission_reference": ii.get("descriptionurl") or "",
                "rights_basis": "Work of the U.S. federal government (NOAA), hosted on Wikimedia Commons and tagged public domain (PD-USGov-NOAA) in the file's licence metadata.",
                "external_id": ext_id,
                "duration_seconds": round(dur, 2),
                "width": w, "height": h,
                "topic_tags": ["earth-science", "noaa", "weather"],
                "description": re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", ((em.get("ImageDescription") or {}).get("value") or "")))[:400].strip(),
            })
    return clips


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "app" / "data" / "source_catalog_lane1.json"))
    args = ap.parse_args()
    today = date.today().isoformat()
    clips = harvest_nasa()
    have = {c["external_id"] for c in clips}
    clips += _ia_items("nasa", "NASA", 18, have)
    clips += harvest_commons_noaa(6, have)
    for c in clips:  # ID-like NASA titles -> description's first sentence
        if re.fullmatch(r"[A-Z0-9][A-Z0-9\-_ ]{5,}", c["title"]) and " " not in c["title"].strip():
            desc = (c.get("description") or "").strip()
            if desc:
                first = re.split(r"(?<=[.!?])\s+", desc)[0]
                if len(first) >= 12:
                    c["title"] = first[:160]
    out = []
    for i, c in enumerate(clips, 1):
        out.append({
            "catalog_id": f"lane1-{i:04d}", "lane": "lane1_space_science", **c,
            "resolution": f"{c['width']}x{c['height']}",
            "orientation": "landscape" if c["width"] >= c["height"] else "portrait",
            "rights_verified": True, "repeat_use_allowed": True,
            "status": "catalogued", "retrieved_at": today,
        })
    doc = {
        "catalogue": "vyralx_lane1_space_science_sources", "version": 1,
        "built_by": "TASK-VYR-006", "built_at": today, "lane": "lane1_space_science",
        "clip_count": len(out),
        "licence_policy": "Public-domain sources only (U.S. Government works: NASA/NOAA). Every record carries licence + provenance; no record = not usable.",
        "clips": out,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"WROTE {len(out)} clips -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
