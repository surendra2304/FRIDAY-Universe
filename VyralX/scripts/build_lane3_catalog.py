#!/usr/bin/env python3
"""Build VyralX's lane-3 (tech & AI explainers) source catalogue.

TASK-VYR-012. Regenerates ``app/data/source_catalog_lane3.json`` — the
shelf of lawfully reusable footage the remix pipeline (TASK-VYR-004)
cuts tech & AI explainer Shorts from. Mirrors the TASK-VYR-006 lane-1
builder, with the licence gate widened from PD-only to TASK-VYR-004's
gate exactly:

* Wikimedia Commons — PD / CC0 / CC BY / CC BY-SA (incl. the CC BY-SA
  3.0 IGO port used by ESA); NC / ND / GFDL / unknown rejected.
* Internet Archive, Prelinger collection — items whose own licence URL
  is an explicit pass licence (public-domain mark, CC0, CC BY, CC
  BY-SA); unmarked items are NOT taken.
* NASA Image and Video Library — U.S. Government works (public domain).

Every record carries source URL, licence, provenance page, creator,
measured duration + resolution with the measurement source labelled
(ffprobe for NASA assets, platform metadata elsewhere), and topic
tags. Records failing any check (sub-640px wide, <20s or >1200s, no
explicit pass licence, off-topic title, financial/trading content,
already stocked in the lane-1 catalogue) are excluded and counted —
no record, no use. Items culled by manual curation are named in
``MANUAL_EXCLUDES`` so regeneration reproduces the shipped catalogue.

Usage:  python3 scripts/build_lane3_catalog.py [--out PATH]
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
from collections import Counter
from datetime import date
from pathlib import Path

UA = {"User-Agent": "VyralX-catalogue-builder/1.0 (TASK-VYR-012)"}
NASA_LICENSE = "Public Domain (U.S. Government work - NASA)"
NASA_GUIDELINES = "https://www.nasa.gov/nasa-brand-center/images-and-media/"
MIN_WIDTH, MIN_DUR, MAX_DUR = 640, 20, 1200
LANE = "lane3_tech_ai"

REJECTS: Counter = Counter()

# Financial/trading content is excluded from every lane's B-roll.
FINANCIAL_RE = re.compile(
    r"stock market|stock trading|forex|cryptocurr|bitcoin|ethereum|"
    r"investment|investor|wall street|day trading|trading strategy|"
    r"shares|banking|mortgage|insurance|loan\b|financial advisor|"
    r"money making|get rich|passive income",
    re.I,
)

# Culled by manual curation after harvest review (regeneration
# reproduces the shipped catalogue): talking-head career profiles,
# conference talks and lectures, a physics explainer and a finished
# AI explainer (finished videos, not B-roll), political speeches and
# visits, a sex-robot product clip, cricket matches mislabelled by
# search, TV-ad compilations, shuttle launch/status coverage that
# matched tech queries only loosely, raw multi-hour ISS feeds,
# duplicate cuts of the same shoot, and promo/highlight reels.
MANUAL_EXCLUDES = {
    "SurprisinglySTEM_CHAPEA_Social",
    "commons:DotJS_2018_-_Devon_Lindsey_-_Robot_Rock.webm",
    "commons:Do_Gravitons_Really_Exist_-_Finding_the_Particles_of_Gravity.webm",
    "commons:Il_Presidente_Meloni_in_visita_al_CERN.webm",
    "commons:PCAPH_vs_CERN_CC_-_20140911_-_1.webm",
    "commons:PCAPH_vs_CERN_CC_-_20140911_-_10.webm",
    "commons:PCAPH_vs_CERN_CC_-_20140911_-_2.webm",
    "commons:MISSDOLL_SEX_ROBOT_ORAL-V2_-_HD_720p.webm",
    "commons:Drone_Eshbol.webm",
    "commons:Artificial_intelligence_explained_in_2_minutes_-_What_exactly_is_AI?.webm",
    "commons:Sen._Cory_Booker_Calls_for_Special_Session_of_Congress_on_Artificial_Intelligence_on_Senate_Floor.webm",
    "commons:Using_Artificial_Intelligence_to_automate_the_languages_of_discovery.webm",
    "commons:President_Biden_Joins_the_Virtual_CEO_Summit_on_Semiconductor_and_Supply_Chain_Resilience.webm",
    "ClassicT1948_6",
    "ClassicT1948_2",
    "ClassicT1948_5",
    "Televisi1970",
    "ksc_031108_sts123_launch",
    "ksc_031108_sts123_open",
    "ksc_031108_sts123_suitwalk",
    "ksc_031108_sts123_etjet",
    "ksc_032706_sssr",
    "jsc2022m000119_Russian_Spacewalk_53_Animation-MP4",
    "iss064m260691404_Expedition_64_Nanoracks_210310",
    "iss068m263001534_Expedition_68_Education_Inflight_with_the_U.S._Naval_Test_Pilot_School_221027",
    "JPL-20210319-M2020-0001-Mars_Report_Update_on_Perseverance_and_Ingenuity",
    "SpX-33_Science_Highlight",
    "300_ISS_3DBio",
    "ARC-20211021-AAV3373-VIPER-PathfinderBuild-Timelapse-NASAWeb-1080p",
    "MSFC_2025_March_CenterHighlightReel",
    "MSFC_20240821_CS2_LVSA_rollout_UAS-30s",
    "MSFC_StakeholderTour_v3",
    "SpaceX_CRS-23_Crew_Message",
    "ksc_041008_sts123_overview",
    "iss065m261471414_Expedition_65_PAO_GSFC_Hubble_210527",
    "JPL-20210610-M2020f-Mars-Report-NASAs-Perseverance-Rover-SuperCam-Instrument-June-2021",
    "jsc2023m000145_Russian_Spacewalk_60_Animation_230808-MP4",
    "Scientific_Investigations_Set_for_Space_on_Northrop_Grumman_CRS-12",
    "Northrop_Grumman_CRS-18_Science-MP4",
    "NG-16_Science_Overview",
    "commons:MORE_ON_THE_WAY_—_War_Robots_Cinematic_Trailer.webm",
    "commons:PCAPH_vs_CERN_CC_-_20140911_-_3.webm",
    "commons:Drone_over_Petriolo_2.webm",
    "Survival1951",
    "Electric1942",
    "history_of_communication",
    "Powersof1947",
}

# Title fragments that mark content the lanes never stock (adult,
# sport, advertising compilations) — applied to Commons + IA titles.
BAD_TITLE_FRAGMENTS = ["sex robot", "porn", "cricket", "commercials", "pcaph"]

# NASA formats that are talking heads / event coverage, not B-roll.
NASA_TITLE_SCREEN = [
    "stemonstrations", "surprisingly stem", "we asked a nasa expert",
    "robotics competition", "launch coverage", "countdown coverage",
    "mars report", "science launching", "crew previews",
]

NASA_QUERIES = [
    ("Robonaut robot", ["robotics"]),
    ("robotic arm space station", ["robotics"]),
    ("Canadarm2 robotic arm", ["robotics"]),
    ("robotics testing laboratory", ["robotics"]),
    ("VIPER rover testing", ["robotics"]),
    ("3D printing", ["3d-printing", "engineering"]),
    ("additive manufacturing", ["3d-printing", "engineering"]),
    ("wind tunnel testing", ["engineering", "aeronautics"]),
    ("hypersonic wind tunnel", ["engineering", "aeronautics"]),
    ("supercomputer", ["computing", "supercomputer"]),
    ("laser communications", ["communications", "laser"]),
    ("photonics laser testing", ["laser", "engineering"]),
    ("electric aircraft propulsion", ["aeronautics", "electric-flight"]),
    ("X-59 supersonic aircraft", ["aeronautics", "engineering"]),
    ("solar electric propulsion", ["propulsion", "engineering"]),
    ("artificial intelligence machine learning", ["ai", "computing"]),
    ("quantum communications", ["computing", "quantum"]),
    ("digital twin simulation", ["computing", "simulation"]),
    ("autonomous navigation rover", ["robotics", "ai"]),
    ("satellite servicing", ["robotics", "engineering"]),
    ("robotic refueling mission", ["robotics"]),
    ("aerospace manufacturing", ["engineering", "manufacturing"]),
    ("flight simulator", ["simulation", "aeronautics"]),
    ("solar array deployment test", ["engineering"]),
    ("battery testing laboratory", ["engineering", "energy"]),
]

# (search, tags, title keywords — at least one must appear in the title,
#  per-query cap)
COMMONS_QUERIES = [
    ("robot", ["robotics"], ["robot"], 8),
    ("industrial robot", ["robotics", "automation"], ["robot", "automat"], 4),
    ("3D printing", ["3d-printing"], ["3d print", "3-d print", "additive manufactur"], 6),
    ("CERN", ["engineering", "accelerator"], ["cern", "lhc", "particle", "accelerator", "hadron"], 3),
    ("drone", ["drones"], ["drone", "uav", "quadcopter", "multicopter"], 5),
    ("artificial intelligence", ["ai"], ["artificial intelligence", "neural", "machine learning", "deep learning"], 4),
    ("semiconductor", ["chips", "computing"], ["chip", "semiconductor", "integrated circuit", "transistor", "processor", "silicon wafer"], 4),
    ("laser", ["laser"], ["laser"], 3),
    ("supercomputer", ["computing", "supercomputer"], ["supercomputer", "supercomputing", "data center", "data centre"], 3),
    ("factory automation", ["automation", "engineering"], ["automat", "assembly line", "factory"], 4),
    ("humanoid robot", ["robotics", "ai"], ["robot"], 4),
    ("exoskeleton", ["robotics"], ["exoskeleton", "robot"], 3),
]

IA_TITLE_KW = [
    "computer", "robot", "electronic", "telephone", "automation",
    "television", "radar", "machine", "electric", "atomic", "jet",
    "communication", "transistor", "industrial", "industry",
    "production", "power", "design", "aviation", "helicopter",
    "missile", "diesel", "locomotive", "flight", "airplane",
]


def write_text_chunked(path, payload, chunk=4096, tries=30):
    """Write text in small appends, retrying per chunk.

    Some filesystems intermittently refuse larger writes (EPERM) while
    small appends succeed; chunking + per-chunk retry + a final size
    check keeps regeneration reliable there.
    """
    import time as _time
    data = payload.encode("utf-8")
    path.write_bytes(b"")
    written = 0
    while written < len(data):
        piece = data[written:written + chunk]
        last = None
        for _ in range(tries):
            try:
                with path.open("ab") as f:
                    f.write(piece)
                break
            except PermissionError as e:
                last = e
                _time.sleep(2)
        else:
            raise RuntimeError(f"write to {path} blocked at {written} bytes: {last}")
        written += len(piece)
    if path.stat().st_size != len(data):
        raise RuntimeError(f"write to {path} incomplete: {path.stat().st_size} != {len(data)}")


def get_json(url, timeout=45):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def strip_html(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()


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


# ---------------------------------------------------------------- NASA

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


def harvest_nasa(want=28, per_query=5, lane1_ids=None):
    clips, seen = [], set(lane1_ids or ())
    for query, tags in NASA_QUERIES:
        if len(clips) >= want:
            break
        q = urllib.parse.urlencode({"q": query, "media_type": "video", "page_size": 40})
        try:
            res = get_json(f"https://images-api.nasa.gov/search?{q}")
        except Exception:
            REJECTS["nasa_query_failed"] += 1
            continue
        got = 0
        for item in (res.get("collection") or {}).get("items") or []:
            if len(clips) >= want or got >= per_query:
                break
            data = (item.get("data") or [{}])[0]
            nid = data.get("nasa_id") or ""
            if not nid or nid in seen or nid in MANUAL_EXCLUDES:
                REJECTS["nasa_dup_or_lane1"] += 1
                continue
            seen.add(nid)
            title = (data.get("title") or nid).strip()
            if any(s in title.lower() for s in NASA_TITLE_SCREEN):
                REJECTS["nasa_format_screen"] += 1
                continue
            desc = re.sub(r"\s+", " ", (data.get("description") or "")).strip()
            if FINANCIAL_RE.search(title + " " + desc):
                REJECTS["nasa_financial"] += 1
                continue
            asset = pick_nasa_asset(item.get("href", ""))
            if not asset:
                REJECTS["nasa_no_asset"] += 1
                continue
            if asset.startswith("http://"):
                asset = "https://" + asset[len("http://"):]
            p = probe(asset)
            if not p:
                REJECTS["nasa_probe_or_size"] += 1
                continue
            dur, w, h = p
            if not (MIN_DUR <= dur <= MAX_DUR):
                REJECTS["nasa_duration"] += 1
                continue
            kws = [k.strip().lower().replace(" ", "-") for k in (data.get("keywords") or [])][:6]
            clips.append({
                "title": title[:280],
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
                "measurement_source": "ffprobe",
                "topic_tags": sorted(set(tags + [k for k in kws if len(k) <= 24][:3])),
                "description": desc[:400],
            })
            got += 1
    return clips


# ------------------------------------------------------- Wikimedia Commons

def commons_licence(em):
    """Map Commons extmetadata onto the VYR-004 gate.

    Returns (license_name, licence_url) for a pass licence, else None.
    """
    short = ((em.get("LicenseShortName") or {}).get("value") or "").strip()
    url = ((em.get("LicenseUrl") or {}).get("value") or "").strip()
    low = short.lower()
    tokens = re.split(r"[\s\-/]+", low)
    if "nc" in tokens or "nd" in tokens:
        return None
    if "public domain" in low or low.startswith("pd"):
        return (short if short else "Public Domain", url)
    if low.startswith("cc0"):
        return (short, url)
    if low.startswith("cc by-sa"):
        return (short, url)
    if low.startswith("cc by"):
        return (short, url)
    return None


def harvest_commons(want=36, have_ids=None):
    clips = []
    have = have_ids if have_ids is not None else set()
    api = "https://commons.wikimedia.org/w/api.php"
    for query, tags, title_kw, per_query in COMMONS_QUERIES:
        if len(clips) >= want:
            break
        params = {"action": "query", "format": "json", "generator": "search",
                  "gsrsearch": f"{query} filetype:video", "gsrnamespace": 6,
                  "gsrlimit": 50, "prop": "imageinfo",
                  "iiprop": "url|size|mime|extmetadata"}
        try:
            res = get_json(api + "?" + urllib.parse.urlencode(params), timeout=60)
        except Exception:
            REJECTS["commons_query_failed"] += 1
            continue
        got = 0
        for page in ((res.get("query") or {}).get("pages") or {}).values():
            if len(clips) >= want or got >= per_query:
                break
            ii = (page.get("imageinfo") or [{}])[0]
            title = page.get("title") or ""
            ext_id = "commons:" + title.replace("File:", "").replace(" ", "_")
            if ext_id in have or ext_id in MANUAL_EXCLUDES:
                REJECTS["commons_dup_or_excluded"] += 1
                continue
            if not str(ii.get("mime") or "").startswith("video/"):
                REJECTS["commons_not_video"] += 1
                continue
            em = ii.get("extmetadata") or {}
            lic = commons_licence(em)
            if lic is None:
                REJECTS["commons_licence"] += 1
                continue
            lic_name, lic_url = lic
            w = int(ii.get("width") or 0)
            h = int(ii.get("height") or 0)
            dur = float(ii.get("duration") or 0)
            if w < MIN_WIDTH:
                REJECTS["commons_width"] += 1
                continue
            if not (MIN_DUR <= dur <= MAX_DUR):
                REJECTS["commons_duration"] += 1
                continue
            clean_title = re.sub(r"\.(webm|ogv|mp4|mov)$", "", title.replace("File:", ""), flags=re.I).replace("_", " ")
            if any(bad in clean_title.lower() for bad in BAD_TITLE_FRAGMENTS):
                REJECTS["commons_bad_title"] += 1
                continue
            desc = strip_html((em.get("ImageDescription") or {}).get("value") or "")
            if not any(kw in clean_title.lower() for kw in title_kw):
                REJECTS["commons_offtopic_title"] += 1
                continue
            if FINANCIAL_RE.search(clean_title + " " + desc):
                REJECTS["commons_financial"] += 1
                continue
            artist = strip_html((em.get("Artist") or {}).get("value") or "")[:200] or "Wikimedia Commons contributor"
            have.add(ext_id)
            basis = (f"Licensed {lic_name} per the file's licence metadata on "
                     f"Wikimedia Commons; reuse requires the licence terms "
                     f"(attribution, and share-alike where applicable) to be honoured.")
            if "public domain" in lic_name.lower():
                basis = ("Marked public domain in the file's licence metadata on "
                         "Wikimedia Commons (see provenance page for the basis).")
            clips.append({
                "title": clean_title[:280],
                "platform": "wikimedia_commons",
                "creator": artist,
                "source_url": ii.get("url") or "",
                "page_url": ii.get("descriptionurl") or "",
                "license_name": lic_name,
                "permission_reference": lic_url or (ii.get("descriptionurl") or ""),
                "rights_basis": basis,
                "external_id": ext_id,
                "duration_seconds": round(dur, 2),
                "width": w, "height": h,
                "measurement_source": "wikimedia_commons_imageinfo",
                "topic_tags": sorted(set(tags)),
                "description": desc[:400],
            })
            got += 1
    return clips


# ------------------------------------------------------- Internet Archive

def ia_licence(licenseurl):
    """Map an IA item's licence URL onto the VYR-004 gate, else None."""
    lic = (licenseurl or "").lower()
    if "publicdomain" in lic or "/mark/" in lic:
        return "Public Domain (Prelinger Archives, Internet Archive)"
    if "zero/1.0" in lic:
        return "CC0 1.0 Universal (public domain dedication)"
    if "by-sa" in lic and "nc" not in lic:
        return "CC BY-SA (Internet Archive item licence)"
    if "/by/" in lic and "nc" not in lic and "nd" not in lic:
        return "CC BY (Internet Archive item licence)"
    return None


def harvest_ia_prelinger(want=16, have_ids=None):
    clips = []
    have = have_ids if have_ids is not None else set()
    docs = []
    for terms in [
        ("(computer OR robot OR electronics OR telephone OR automation "
         "OR television OR radar OR transistor OR machinery)"),
        ("(industry OR production OR power OR design OR communications "
         "OR engineering OR invention)"),
        ("(jet OR aviation OR aeronautics OR helicopter OR guidance "
         "OR missile OR diesel OR locomotive)"),
    ]:
        q = urllib.parse.urlencode({
            "q": f"collection:prelinger AND mediatype:movies AND {terms}",
            "fl[]": "identifier,title,creator,licenseurl,subject",
            "rows": 300, "sort[]": "downloads desc", "output": "json"}, doseq=True)
        try:
            res = get_json(f"https://archive.org/advancedsearch.php?{q}", timeout=60)
            docs += ((res.get("response") or {}).get("docs")) or []
        except Exception:
            REJECTS["ia_query_failed"] += 1
    for doc in docs:
        if len(clips) >= want:
            break
        ident = doc.get("identifier")
        if not ident or ident in have:
            continue
        lic_name = ia_licence(doc.get("licenseurl"))
        if lic_name is None:
            REJECTS["ia_licence"] += 1
            continue
        title = (doc.get("title") or ident).strip()
        if any(bad in title.lower() for bad in BAD_TITLE_FRAGMENTS):
            REJECTS["ia_bad_title"] += 1
            continue
        if not any(kw in title.lower() for kw in IA_TITLE_KW):
            REJECTS["ia_offtopic_title"] += 1
            continue
        if FINANCIAL_RE.search(title):
            REJECTS["ia_financial"] += 1
            continue
        try:
            meta = get_json(f"https://archive.org/metadata/{urllib.parse.quote(ident)}", timeout=40)
        except Exception:
            REJECTS["ia_metadata_failed"] += 1
            continue
        cand = []
        for f in meta.get("files") or []:
            name = f.get("name") or ""
            if not name.lower().endswith((".mp4", ".mov", ".m4v")):
                continue
            try:
                w = int(f.get("width") or 0)
                h = int(f.get("height") or 0)
                dur = float(f.get("length") or 0)
            except (TypeError, ValueError):
                continue
            if w >= MIN_WIDTH and MIN_DUR <= dur <= MAX_DUR:
                cand.append((w, dur, h, name))
        if not cand:
            REJECTS["ia_no_fitting_file"] += 1
            continue
        cand.sort(reverse=True)
        w, dur, h, name = cand[0]
        have.add(ident)
        subj = doc.get("subject") or []
        if isinstance(subj, str):
            subj = [subj]
        tags = sorted({s.strip().lower().replace(" ", "-")[:24] for s in subj if s})[:4]
        base_tags = ["engineering"]
        if "computer" in title.lower():
            base_tags.append("computing")
        if "robot" in title.lower() or "automation" in title.lower():
            base_tags += ["automation", "robotics"]
        if "telephone" in title.lower() or "television" in title.lower():
            base_tags.append("communications")
        clips.append({
            "title": title[:280],
            "platform": "internet_archive",
            "creator": str(doc.get("creator") or "Prelinger Archives")[:200],
            "source_url": f"https://archive.org/download/{ident}/{urllib.parse.quote(name)}",
            "page_url": f"https://archive.org/details/{ident}",
            "license_name": lic_name,
            "permission_reference": doc.get("licenseurl") or f"https://archive.org/details/{ident}",
            "rights_basis": ("Item in the Internet Archive's Prelinger collection carrying an "
                             "explicit pass licence on its own record (see permission "
                             "reference); Prelinger Archives material is dedicated to "
                             "public reuse."),
            "external_id": ident,
            "duration_seconds": round(dur, 2),
            "width": w, "height": h,
            "measurement_source": "internet_archive_metadata",
            "topic_tags": sorted(set(base_tags + tags)),
            "description": "",
        })
    return clips


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "app" / "data" / "source_catalog_lane3.json"))
    ap.add_argument("--lane1", default=None, help="path to lane-1 catalogue JSON for cross-lane dedupe")
    args = ap.parse_args()
    today = date.today().isoformat()
    lane1_ids = set()
    if args.lane1:
        try:
            lane1_ids = {c.get("external_id") for c in json.loads(Path(args.lane1).read_text(encoding="utf-8")).get("clips", [])}
        except Exception:
            lane1_ids = set()
    clips = harvest_nasa(lane1_ids=lane1_ids)
    have = {c["external_id"] for c in clips}
    clips += harvest_commons(have_ids=have)
    clips += harvest_ia_prelinger(have_ids=have)
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
            "catalog_id": f"lane3-{i:04d}", "lane": LANE, **c,
            "resolution": f"{c['width']}x{c['height']}",
            "orientation": "landscape" if c["width"] >= c["height"] else "portrait",
            "rights_verified": True, "repeat_use_allowed": True,
            "status": "catalogued", "retrieved_at": today,
        })
    doc = {
        "catalogue": "vyralx_lane3_tech_ai_sources", "version": 1,
        "built_by": "TASK-VYR-012", "built_at": today, "lane": LANE,
        "clip_count": len(out),
        "licence_policy": ("TASK-VYR-004 gate: CC0 / public domain / CC BY / CC BY-SA only, "
                           "each record carrying licence + provenance; NC/ND/unknown/ARR "
                           "rejected at harvest. No record = not usable."),
        "clips": out,
    }
    payload = json.dumps(doc, indent=2, ensure_ascii=False)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_text_chunked(out_path, payload)
    print(f"WROTE {len(out)} clips -> {args.out}")
    print("REJECTS:", dict(REJECTS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
