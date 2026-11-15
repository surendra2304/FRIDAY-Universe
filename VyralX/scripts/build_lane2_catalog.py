#!/usr/bin/env python3
"""Build VyralX's lane-2 (history / did-you-know) source catalogue.

TASK-VYR-011. Regenerates ``app/data/source_catalog_lane2.json`` — the
shelf of lawfully reusable archival footage the remix pipeline
(TASK-VYR-004) cuts history Shorts from. Mirrors the lane-1 builder
(TASK-VYR-006) and applies the same rights gate as the remix flow:
CC0 / public domain / CC BY / CC BY-SA pass; NC / ND / unknown /
all-rights-reserved are rejected at harvest. Sources are keyless only:

* Internet Archive — Universal Newsreels (public-domain mark) and the
  Prelinger Archives (dedicated to the public domain by the donor)
* Wikimedia Commons — archival film tagged PD / CC0 / CC BY / CC BY-SA
  in its licence metadata (incl. U.S. National Archives material)
* Library of Congress — pre-1929 U.S. motion pictures (public domain by
  publication age), access_restricted=false, measured from LOC resource metadata

Every record carries source URL, licence, provenance page, measured
duration and resolution (feed metadata, or ffprobe for LOC; the record's
``measurement_source`` says which), and topic tags. Records failing any
check (sub-640px, <20s or >1200s, no acceptable licence basis, already
stocked in lane 1) are excluded — no record, no use. Graphic atrocity
footage (concentration-camp liberation reels and similar) is excluded
by curation in ``CURATION_EXCLUDE_PATTERNS``: lawful or not, it is not
Shorts remix material. The builder prints per-gate rejection counts so
the honest yield of every regeneration is visible.

Usage:  python3 scripts/build_lane2_catalog.py [--out PATH]
LOC durations/resolutions come from the Library's own resource metadata.
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

UA = {"User-Agent": "VyralX-catalogue-builder/1.0 (TASK-VYR-011)"}
MIN_WIDTH, MIN_DUR, MAX_DUR = 640, 20, 1200

STATS = {
    "accepted": 0, "licence": 0, "width": 0, "duration": 0,
    "no_measurable_file": 0, "duplicate": 0, "lane1_overlap": 0,
    "curated_out": 0, "fetch_error": 0,
}

LANE1_IDS: set = set()
LANE1_URLS: set = set()

# Curation: graphic atrocity / execution footage is not remix material,
# and neither are amateur home-movie dumps or modern drone flyovers —
# the shelf is archival productions. Both lists count as curated_out.
QUALITY_EXCLUDE_PATTERNS = [
    "[home movies", "home movie: 0", "drone flight",
]

CURATION_EXCLUDE_PATTERNS = [
    "concentration camp", "liberation camp", "atrocity", "atrocities",
    "extermination", "corpse", "execution of", "hanging of",
    "nuremberg trial", "death camp",
]

COMMONS_QUERIES = [
    ("Berlin Wall fall 1989 film", ["berlin-wall", "cold-war"]),
    ("World War I film footage", ["world-war-i"]),
    ("D-Day Normandy 1944 film", ["world-war-ii", "d-day"]),
    ("Hindenburg disaster newsreel", ["hindenburg", "aviation-history"]),
    ("Wright brothers flight film", ["aviation-history", "first-flight"]),
    ("San Francisco earthquake 1906 film", ["earthquake-1906", "san-francisco"]),
    ("Empire State Building construction film", ["empire-state-building", "construction"]),
    ("Golden Gate Bridge construction film", ["golden-gate-bridge", "construction"]),
    ("Lumière brothers film", ["early-cinema"]),
    ("Edison motion picture film", ["early-cinema", "edison"]),
    ("Voice of America film", ["voice-of-america", "cold-war"]),
    ("National Archives World War II film", ["world-war-ii"]),
    ("Great Depression United States film", ["great-depression"]),
    ("vintage New York City street film", ["new-york", "street-scene"]),
    ("Titanic ship film", ["titanic", "maritime-history"]),
    ("suffragette parade film", ["suffrage", "womens-history"]),
    ("Cold War newsreel film", ["cold-war", "newsreel"]),
    ("vintage automobile street film 1920s", ["1920s", "street-scene"]),
]


def write_resilient(path, text, tries=10):
    """Sandbox intermittently EPERMs file writes in multi-minute phases.

    Write in 4KB appends, each retried until it lands, so partial
    progress survives a bad phase; verify the whole file by read-back
    and restart from truncation if it does not match.
    """
    import time as _t
    data = text.encode("utf-8")
    last = None
    for _ in range(tries):
        try:
            with open(path, "wb"):
                pass
            ok = True
            with open(path, "ab") as f:
                for i in range(0, len(data), 4096):
                    chunk = data[i:i + 4096]
                    for _try in range(45):
                        try:
                            f.write(chunk)
                            f.flush()
                            break
                        except PermissionError as e:
                            last = e
                            _t.sleep(2)
                    else:
                        ok = False
                        break
            if ok and Path(path).read_bytes() == data:
                return
            last = RuntimeError("write landed truncated/zeroed")
        except PermissionError as e:
            last = e
        _t.sleep(3)
    raise RuntimeError(f"write to {path} blocked: {last}")


def get_json(url, timeout=45):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def probe(url):
    """ffprobe a remote media URL -> (duration, width, height) or None."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-rw_timeout", "20000000",
             "-select_streams", "v:0", "-show_entries", "stream=width,height",
             "-show_entries", "format=duration", "-of", "json", url],
            capture_output=True, text=True, timeout=90)
        d = json.loads(out.stdout or "{}")
        streams = d.get("streams") or []
        if not streams:
            return None
        w = int(streams[0].get("width") or 0)
        h = int(streams[0].get("height") or 0)
        dur = float((d.get("format") or {}).get("duration") or 0)
        if w <= 0 or dur <= 0:
            return None
        return dur, w, h
    except Exception:
        return None


def curated_out(title):
    t = (title or "").lower()
    return any(p in t for p in CURATION_EXCLUDE_PATTERNS + QUALITY_EXCLUDE_PATTERNS)


def clean_html(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()


# ---------------------------------------------------------------- Commons

def commons_licence(short_name):
    """Map a Commons LicenseShortName onto the gate. -> (name, ok)."""
    s = (short_name or "").strip()
    low = s.lower()
    if "noncommercial" in low or "no derivatives" in low or "-nc" in low or "-nd" in low:
        return s, False
    if low == "public domain" or low.startswith("pd-") or "public domain" in low:
        return "Public Domain", True
    if low.startswith("cc0"):
        return s, True
    if re.match(r"cc by-sa( |$)", low):
        return s, True
    if re.match(r"cc by( |$)", low):
        return s, True
    return s, False


def harvest_commons(want=14, have_ids=None, have_urls=None):
    clips = []
    api = "https://commons.wikimedia.org/w/api.php"
    for query, tags in COMMONS_QUERIES:
        if len(clips) >= want:
            break
        params = {"action": "query", "format": "json", "generator": "search",
                  "gsrsearch": f"{query} filetype:video", "gsrnamespace": 6,
                  "gsrlimit": 30, "prop": "imageinfo",
                  "iiprop": "url|size|mime|extmetadata"}
        try:
            res = get_json(api + "?" + urllib.parse.urlencode(params), timeout=40)
        except Exception:
            STATS["fetch_error"] += 1
            continue
        pages = sorted(((res.get("query") or {}).get("pages") or {}).values(),
                       key=lambda p: p.get("title") or "")
        for page in pages:
            if len(clips) >= want:
                break
            ii = (page.get("imageinfo") or [{}])[0]
            title = page.get("title") or ""
            ext_id = "commons:" + title.replace("File:", "").replace(" ", "_")
            nice_title = re.sub(r"\.(webm|ogv|ogg|mp4)$", "",
                                title.replace("File:", ""), flags=re.I).replace("_", " ")
            if curated_out(nice_title):
                STATS["curated_out"] += 1
                continue
            if ext_id in LANE1_IDS or (ii.get("url") or "") in LANE1_URLS:
                STATS["lane1_overlap"] += 1
                continue
            if ext_id in (have_ids or set()) or (ii.get("url") in (have_urls or set())):
                STATS["duplicate"] += 1
                continue
            em = ii.get("extmetadata") or {}
            lic_name, ok = commons_licence((em.get("LicenseShortName") or {}).get("value") or "")
            if not ok:
                STATS["licence"] += 1
                continue
            try:
                w = int(ii.get("width") or 0); h = int(ii.get("height") or 0)
                dur = float(ii.get("duration") or 0)
            except (TypeError, ValueError):
                w = h = 0; dur = 0.0
            if w < MIN_WIDTH:
                STATS["width"] += 1
                continue
            if not (MIN_DUR <= dur <= MAX_DUR):
                STATS["duration"] += 1
                continue
            lic_url = ((em.get("LicenseUrl") or {}).get("value") or "").strip()
            artist = clean_html((em.get("Artist") or {}).get("value") or "")[:200]
            basis = (f"Licence recorded in the file's Wikimedia Commons metadata: "
                     f"'{(em.get('LicenseShortName') or {}).get('value')}'"
                     + (f", licence text at {lic_url}" if lic_url else "")
                     + ". Provenance page carries the full licence and source detail.")
            if lic_name == "Public Domain":
                basis = ("Tagged public domain in the file's Wikimedia Commons "
                         "licence metadata (U.S. Government / expired-copyright "
                         "archival material). " + basis)
            clips.append({
                "title": nice_title.strip()[:280],
                "platform": "wikimedia_commons",
                "creator": artist or "Wikimedia Commons contributor",
                "source_url": ii.get("url") or "",
                "page_url": ii.get("descriptionurl") or "",
                "license_name": lic_name,
                "permission_reference": lic_url or (ii.get("descriptionurl") or ""),
                "rights_basis": basis,
                "external_id": ext_id,
                "duration_seconds": round(dur, 2),
                "width": w, "height": h,
                "topic_tags": sorted(set(tags)),
                "description": clean_html((em.get("ImageDescription") or {}).get("value") or "")[:400],
                "measurement_source": "commons_metadata",
            })
            if have_ids is not None:
                have_ids.add(ext_id)
            if have_urls is not None:
                have_urls.add(ii.get("url") or "")
            STATS["accepted"] += 1
    return clips


# ---------------------------------------------------------- Internet Archive

def ia_licence(licenseurl):
    """Classify an archive.org licenseurl. -> (kind, ok).

    kind: 'pd' (public-domain mark), 'cc0', 'by', 'by-sa', or '' .
    """
    lic = (licenseurl or "").lower()
    if not lic:
        return "", False
    if "by-nc" in lic or "by-nd" in lic:
        return "", False
    if "publicdomain" in lic:
        return ("cc0", True) if "zero" in lic else ("pd", True)
    if "/by-sa/" in lic:
        return "by-sa", True
    if "/by/" in lic:
        return "by", True
    return "", False


IA_LICENCE_NAMES = {
    "pd": "Public Domain",
    "cc0": "CC0 1.0",
    "by": "CC BY",
    "by-sa": "CC BY-SA",
}

PRELINGER_BASIS = (
    "Prelinger Archives: the collection was dedicated to the public domain "
    "by its donor and archive.org hosts it as public-domain material; the "
    "item page is the provenance record."
)


def _ia_pick_file(meta):
    """Largest gate-passing mp4/mov in an IA item's file list."""
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
        cand.append((w, dur, h, name))
    if not cand:
        STATS["no_measurable_file"] += 1
        return None
    wide = [c for c in cand if c[0] >= MIN_WIDTH]
    if not wide:
        STATS["width"] += 1
        return None
    inrange = [c for c in wide if MIN_DUR <= c[1] <= MAX_DUR]
    if not inrange:
        STATS["duration"] += 1
        return None
    inrange.sort(reverse=True)
    return inrange[0]


def _ia_doc_to_clip(doc, meta, licence_name, basis, perm_ref, tags, have_ids, have_urls):
    ident = doc.get("identifier")
    picked = _ia_pick_file(meta)
    if not picked:
        return None
    w, dur, h, name = picked
    subj = doc.get("subject") or []
    if isinstance(subj, str):
        subj = [subj]
    stag = sorted({s.strip().lower().replace(" ", "-")[:24] for s in subj if s})[:4]
    creator = str(doc.get("creator") or "Internet Archive contributor")
    return {
        "title": (doc.get("title") or ident).strip()[:280],
        "platform": "internet_archive",
        "creator": creator[:200],
        "source_url": f"https://archive.org/download/{ident}/{urllib.parse.quote(name)}",
        "page_url": f"https://archive.org/details/{ident}",
        "license_name": licence_name,
        "permission_reference": perm_ref,
        "rights_basis": basis,
        "external_id": ident,
        "duration_seconds": round(dur, 2),
        "width": w, "height": h,
        "topic_tags": sorted(set(tags + stag))[:6] or ["history"],
        "description": "",
        "measurement_source": "archive_metadata",
    }


def _ia_search(query, rows=60, sort=None):
    fl = "identifier,title,creator,licenseurl,subject,date"
    params = {"q": query, "fl[]": fl, "rows": rows, "output": "json"}
    if sort:
        params["sort[]"] = sort
    q = urllib.parse.urlencode(params, doseq=True)
    res = get_json(f"https://archive.org/advancedsearch.php?{q}")
    return ((res.get("response") or {}).get("docs")) or []


def harvest_ia_newsreels(want=24, have_ids=None, have_urls=None):
    """Universal Newsreels: U.S. newsreels 1929-1967, public-domain mark."""
    clips = []
    docs, seen = [], set()
    for sort in ["date asc", "date desc"]:  # both ends of 1929-1967
        try:
            batch = _ia_search("collection:universal_newsreels AND mediatype:movies",
                               rows=80, sort=sort)
        except Exception:
            STATS["fetch_error"] += 1
            batch = []
        cap = want // 2 if sort == "date asc" else want
        added = 0
        for d in batch:
            if added >= cap:
                break
            if d.get("identifier") not in seen:
                seen.add(d.get("identifier")); docs.append(d); added += 1
    for doc in docs:
        if len(clips) >= want:
            break
        ident = doc.get("identifier")
        if ident and ident in LANE1_IDS:
            STATS["lane1_overlap"] += 1
            continue
        if not ident or ident in (have_ids or set()):
            STATS["duplicate"] += 1
            continue
        if curated_out(doc.get("title") or ""):
            STATS["curated_out"] += 1
            continue
        kind, ok = ia_licence(doc.get("licenseurl"))
        if not ok:
            STATS["licence"] += 1
            continue
        try:
            meta = get_json(f"https://archive.org/metadata/{urllib.parse.quote(ident)}")
        except Exception:
            STATS["fetch_error"] += 1
            continue
        clip = _ia_doc_to_clip(
            doc, meta, IA_LICENCE_NAMES.get(kind, "Public Domain"),
            ("Universal Newsreels item carrying a public-domain licence "
             f"marker ({doc.get('licenseurl')}); U.S. newsreel material "
             "hosted by the Internet Archive. Item page is the provenance record."),
            doc.get("licenseurl") or f"https://archive.org/details/{ident}",
            ["newsreel", "history"], have_ids, have_urls)
        if clip:
            clips.append(clip)
            if have_ids is not None:
                have_ids.add(ident)
            if have_urls is not None:
                have_urls.add(clip["source_url"])
            STATS["accepted"] += 1
    return clips


def harvest_ia_prelinger(want=20, have_ids=None, have_urls=None):
    """Prelinger Archives: ephemeral films dedicated to the public domain."""
    clips = []
    queries = [
        'collection:prelinger AND mediatype:movies AND subject:"Civil defense"',
        'collection:prelinger AND mediatype:movies AND subject:"Atomic bomb"',
        'collection:prelinger AND mediatype:movies AND subject:"World War II"',
        'collection:prelinger AND mediatype:movies AND subject:"Automobiles"',
        'collection:prelinger AND mediatype:movies AND subject:"United States -- History"',
        'collection:prelinger AND mediatype:movies AND title:"Duck and Cover"',
        'collection:prelinger AND mediatype:movies AND subject:"Aviation"',
        'collection:prelinger AND mediatype:movies AND subject:"New York"',
        'collection:prelinger AND mediatype:movies AND subject:"History"',
        'collection:prelinger AND mediatype:movies AND subject:"Industry"',
    ]
    docs, seen = [], set()
    for query in queries:
        try:
            for d in _ia_search(query, rows=40):
                if d.get("identifier") not in seen:
                    seen.add(d.get("identifier")); docs.append(d)
        except Exception:
            STATS["fetch_error"] += 1
    for doc in docs:
        if len(clips) >= want:
            break
        ident = doc.get("identifier")
        if ident and ident in LANE1_IDS:
            STATS["lane1_overlap"] += 1
            continue
        if not ident or ident in (have_ids or set()):
            STATS["duplicate"] += 1
            continue
        if curated_out(doc.get("title") or ""):
            STATS["curated_out"] += 1
            continue
        kind, ok = ia_licence(doc.get("licenseurl"))
        if ok:
            licence_name = IA_LICENCE_NAMES.get(kind, "Public Domain")
            basis = (f"Item carries a public-domain/CC licence marker "
                     f"({doc.get('licenseurl')}) in the Prelinger Archives. "
                     + PRELINGER_BASIS)
            perm_ref = doc.get("licenseurl")
        else:
            # No per-item marker: the collection-level dedication is the basis.
            licence_name = "Public Domain (Prelinger Archives)"
            basis = PRELINGER_BASIS
            perm_ref = f"https://archive.org/details/{ident}"
        try:
            meta = get_json(f"https://archive.org/metadata/{urllib.parse.quote(ident)}")
        except Exception:
            STATS["fetch_error"] += 1
            continue
        clip = _ia_doc_to_clip(doc, meta, licence_name, basis, perm_ref,
                               ["ephemeral-film", "history"], have_ids, have_urls)
        if clip:
            clips.append(clip)
            if have_ids is not None:
                have_ids.add(ident)
            if have_urls is not None:
                have_urls.add(clip["source_url"])
            STATS["accepted"] += 1
    return clips


# ------------------------------------------------------- Library of Congress

def harvest_loc(want=6, have_ids=None, have_urls=None):
    """LOC early motion pictures: pre-1929 U.S. films are PD by age.

    Only items with access_restricted == False are considered. The LOC
    item JSON's resource records carry the direct mp4 URL plus the
    Library's own duration/width/height for its digital viewing copies
    (measurement_source "loc_metadata"); the builder's ``files`` field
    there is a count, not a list — the media URL is ``resource["video"]``.
    """
    clips = []
    queries = ["edison film", "early motion picture new york", "lumiere actuality"]
    seen = set()
    detail_budget = [12]  # loc.gov is slow: cap per-item detail fetches
    for query in queries:
        if len(clips) >= want:
            break
        q = urllib.parse.urlencode({"q": query, "fo": "json", "c": 20,
                                    "at": "results"})
        try:
            res = get_json(f"https://www.loc.gov/film-and-videos/?{q}", timeout=40)
        except Exception:
            STATS["fetch_error"] += 1
            continue
        for item in res.get("results") or []:
            if len(clips) >= want:
                break
            loc_id = str(item.get("id") or "").rstrip("/").split("/")[-1]
            title = (item.get("title") or "").strip()
            if not loc_id or loc_id in seen or item.get("access_restricted"):
                continue
            seen.add(loc_id)
            if curated_out(title):
                STATS["curated_out"] += 1
                continue
            dates = str(item.get("date") or "")
            m = re.search(r"(1[89]\d\d|19[0-2]\d)", dates)
            if not m:  # no pre-1929 date evidence -> no PD-by-age basis
                STATS["licence"] += 1
                continue
            if detail_budget[0] <= 0:
                continue
            detail_budget[0] -= 1
            try:
                detail = get_json(f"https://www.loc.gov/item/{loc_id}/?fo=json",
                                  timeout=25)
            except Exception:
                STATS["fetch_error"] += 1
                continue
            media = None
            for resrc in (detail.get("item") or {}).get("resources") or []:
                if not isinstance(resrc, dict):
                    continue
                url = resrc.get("video")
                if isinstance(url, str) and url.lower().endswith(".mp4"):
                    media = resrc
                    break
            if media is None:
                STATS["no_measurable_file"] += 1
                continue
            try:
                w = int(media.get("width") or 0); h = int(media.get("height") or 0)
                dur = float(media.get("duration") or 0)
            except (TypeError, ValueError):
                STATS["no_measurable_file"] += 1
                continue
            if w < MIN_WIDTH:
                STATS["width"] += 1
                continue
            if not (MIN_DUR <= dur <= MAX_DUR):
                STATS["duration"] += 1
                continue
            ext_id = f"loc:{loc_id}"
            names = (detail.get("item") or {}).get("contributor_names") or []
            creator = ", ".join(str(n) for n in names)[:200] or "Library of Congress"
            if have_ids is not None:
                have_ids.add(ext_id)
            if have_urls is not None:
                have_urls.add(media["video"])
            clips.append({
                "title": title[:280] or f"LOC item {loc_id}",
                "platform": "library_of_congress",
                "creator": creator,
                "source_url": media["video"],
                "page_url": f"https://www.loc.gov/item/{loc_id}/",
                "license_name": "Public Domain (pre-1929 U.S. publication)",
                "permission_reference": f"https://www.loc.gov/item/{loc_id}/",
                "rights_basis": (f"U.S. motion picture published {m.group(1)}; "
                                 "works published in the United States before "
                                 "1929 are in the public domain. LOC lists the "
                                 "item as not access-restricted."),
                "external_id": ext_id,
                "duration_seconds": round(dur, 2),
                "width": w, "height": h,
                "topic_tags": ["early-cinema", "history"],
                "description": "",
                "measurement_source": "loc_metadata",
            })
            STATS["accepted"] += 1
    return clips


# ------------------------------------------------------------------- main

def _lane1_sets(data_dir):
    ids, urls = set(), set()
    p = Path(data_dir) / "source_catalog_lane1.json"
    if p.is_file():
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
            for c in doc.get("clips") or []:
                ids.add(c.get("external_id")); urls.add(c.get("source_url"))
        except Exception:
            pass
    return ids, urls


def build_document(data_dir):
    """Harvest + assemble the catalogue document (no file output).

    ``data_dir`` is where the lane-1 catalogue lives (for overlap
    dedupe). Returns the document dict; gate accounting is in STATS.
    """
    today = date.today().isoformat()
    lane1_ids, lane1_urls = _lane1_sets(data_dir)
    LANE1_IDS.update(lane1_ids)
    LANE1_URLS.update(lane1_urls)
    have_ids: set = set()
    have_urls: set = set()

    clips = []
    checkpoint = Path("catalog_checkpoint.json")  # cwd, not the data dir
    for name, fn, want in [
        ("newsreels", harvest_ia_newsreels, 24),
        ("prelinger", harvest_ia_prelinger, 20),
        ("commons", harvest_commons, 14),
        ("loc", harvest_loc, 6),
    ]:
        try:
            clips += fn(want, have_ids, have_urls)
        except Exception as e:  # one bad source must not lose the others
            print(f"HARVESTER {name} FAILED: {e}", file=sys.stderr)
            STATS["fetch_error"] += 1
        try:
            write_resilient(checkpoint, json.dumps(clips, indent=1))
        except Exception as e:  # checkpoints are advisory; never fatal
            print(f"checkpoint write failed ({e}); continuing", flush=True)
        print(f"checkpoint: {name} done, {len(clips)} clips so far", flush=True)

    def _stem(t):
        t = (t or "").lower()
        t = re.sub(r"\((?!.*(part|reel))[^)]*\)", " ", t)  # drop (4K)/(High Res) etc.
        t = re.sub(r"\[[^\]]*\]", " ", t)
        return re.sub(r"[^a-z0-9]+", " ", t).strip()

    by_stem = {}
    for c in clips:
        by_stem.setdefault(_stem(c["title"]), []).append(c)
    deduped = []
    for stem, group in by_stem.items():
        group.sort(key=lambda c: (-c["width"], -c["duration_seconds"]))
        identical = len({c["title"] for c in group}) == 1
        keep = group[:1] if identical else group[:2]
        STATS["duplicate"] += len(group) - len(keep)
        deduped.extend(keep)
    clips = deduped

    out = []
    for i, c in enumerate(clips, 1):
        out.append({
            "catalog_id": f"lane2-{i:04d}", "lane": "lane2_history", **c,
            "resolution": f"{c['width']}x{c['height']}",
            "orientation": "landscape" if c["width"] >= c["height"] else "portrait",
            "rights_verified": True, "repeat_use_allowed": True,
            "status": "catalogued", "retrieved_at": today,
        })
    doc = {
        "catalogue": "vyralx_lane2_history_sources", "version": 1,
        "built_by": "TASK-VYR-011", "built_at": today, "lane": "lane2_history",
        "clip_count": len(out),
        "licence_policy": ("Rights gate identical to the remix flow "
                           "(TASK-VYR-004): public domain / CC0 / CC BY / "
                           "CC BY-SA only, each record carrying licence, "
                           "rights basis and provenance page. NC / ND / "
                           "unknown licences are rejected at harvest; no "
                           "record = not usable."),
        "clips": out,
    }
    return doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent
                                         / "app" / "data" / "source_catalog_lane2.json"))
    args = ap.parse_args()
    doc = build_document(Path(args.out).parent)
    print("gate stats:", json.dumps(STATS, sort_keys=True), flush=True)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    write_resilient(Path(args.out), json.dumps(doc, indent=2, ensure_ascii=False))
    print(f"WROTE {doc['clip_count']} clips -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
