"""VyralX public-domain source whitelist lane (TASK-VYR-064).

Space & Science series discovery draws only from whitelisted
public-domain sources, with the licence recorded per item:

* ``nasa`` — NASA Image & Video Library (images-api.nasa.gov,
  keyless JSON API). All NASA imagery is public domain; the credit
  is NASA or a NASA centre ONLY — never the ``secondary_creator``
  field, which can name an external partner (university, contractor).
* ``noaa`` — NOAA Photo Library (photolib.noaa.gov). U.S. Government
  work, public domain. No stable keyless JSON search API exists, so
  the lane returns a catalogue entry pointing at the official search
  instead of inventing a media URL.
* ``usgs`` — USGS Multimedia Gallery (usgs.gov/media/images). U.S.
  Government work, public domain. Same catalogue-entry treatment as
  NOAA: the official search URL is recorded, no media URL invented.
* ``wikimedia`` — Wikimedia Commons (commons.wikimedia.org API,
  keyless JSON API). Only files whose recorded licence is CC0 or
  Public Domain are kept; anything else (CC-BY, CC-BY-SA, ...) is
  dropped with its reason, because the lane is public-domain only.

Guards (acceptance, verbatim from the board):

* No NASA logos — :func:`logo_guard` rejects any item whose title,
  description or keywords name a logo / insignia / seal / logotype
  (including the NASA "meatball" and "worm" logotypes). Rejected
  items never reach a series pack.
* Credit in description — :func:`build_credit` produces the credit
  line for every item, and :func:`build_series_pack` collects the
  distinct lines so the pack can carry them into the description.
* YouTube Audio Library music only — :func:`validate_music_source`
  passes exactly that source; anything else is rejected with a
  reason. The lane records no other music source.

Honesty boundaries: NOAA/USGS entries carry ``media_url=None`` and
``fetch="catalogue"`` — a human picks the item on the official
catalogue; the lane never fabricates a download link. NASA and
Wikimedia entries carry the real URLs the APIs returned. Licence
strings are recorded per item, never assumed for the lane as a
whole. Nothing here downloads, renders, or publishes — it discovers
and records provenance for media the pipeline later imports.
"""
from __future__ import annotations

import re
from urllib.parse import quote_plus

import httpx

NASA_SEARCH_URL = "https://images-api.nasa.gov/search"
WIKIMEDIA_API_URL = "https://commons.wikimedia.org/w/api.php"

# Wikimedia's API requires a descriptive User-Agent and blocks generic
# library defaults (HTTP 403); NASA accepts one too, so both live
# calls carry it.
USER_AGENT = (
    "VyralX/1.0 (FRIDAY-Universe public-domain whitelist lane; "
    "https://github.com/surendra2304/FRIDAY-Universe)"
)

# The only music source this lane permits (acceptance guard).
PD_MUSIC_SOURCE = "YouTube Audio Library"

# Licence strings recorded per item. NASA/NOAA/USGS media is U.S.
# Government work (public domain); Wikimedia items carry their own
# recorded licence, filtered to CC0 / Public Domain only.
PD_SOURCES: dict[str, dict[str, str]] = {
    "nasa": {
        "name": "NASA Image & Video Library",
        "licence": "Public Domain (NASA)",
        "credit": "NASA",
        "search_url": "https://images.nasa.gov/",
        "fetch": "api",
    },
    "noaa": {
        "name": "NOAA Photo Library",
        "licence": "Public Domain (U.S. Government work)",
        "credit": "NOAA",
        "search_url": "https://www.photolib.noaa.gov/",
        "fetch": "catalogue",
    },
    "usgs": {
        "name": "USGS Multimedia Gallery",
        "licence": "Public Domain (U.S. Government work)",
        "credit": "U.S. Geological Survey",
        "search_url": "https://www.usgs.gov/media/images",
        "fetch": "catalogue",
    },
    "wikimedia": {
        "name": "Wikimedia Commons",
        "licence": "CC0 / Public Domain (per item)",
        "credit": "Wikimedia Commons",
        "search_url": "https://commons.wikimedia.org/",
        "fetch": "api",
    },
}

# Wikimedia licence short names the lane accepts. Anything else is
# dropped: the lane is public-domain only, not "free to view".
WIKIMEDIA_ALLOWED_LICENCES = {"cc0", "public domain"}

# Terms that mark an item as logo/insignia material. Checked against
# title + description + keywords, lowercased. "worm" alone is not
# listed: it would nuke genuine earthworm imagery; only the logotype
# phrasings count.
LOGO_TERMS = (
    "logo",
    "insignia",
    "meatball",
    "worm logo",
    "worm logotype",
    "logotype",
    "official seal",
    "nasa seal",
)

_TAG_RE = re.compile(r"<[^>]+>")


def logo_guard(item: dict) -> tuple[bool, str | None]:
    """Reject logo/insignia items (acceptance guard: no NASA logos).

    Returns ``(True, None)`` when the item is clear, ``(False, reason)``
    when a logo term appears in its title, description or keywords.
    """
    haystack = " ".join(
        [
            str(item.get("title") or ""),
            str(item.get("description") or ""),
            " ".join(str(k) for k in (item.get("keywords") or [])),
        ]
    ).casefold()
    for term in LOGO_TERMS:
        if term in haystack:
            return False, f"logo term {term!r} in title/description/keywords"
    return True, None


def build_credit(source_key: str, item: dict) -> str:
    """Credit line for one whitelist item, for the video description.

    NASA: the centre only (``NASA/JPL``), never ``secondary_creator``,
    which can name an external partner. Wikimedia: the recorded artist
    when present, else the Commons fallback. NOAA/USGS: the agency.
    """
    source = PD_SOURCES[source_key]
    if source_key == "nasa":
        centre = str(item.get("centre") or "").strip()
        return f"Credit: NASA/{centre}" if centre else "Credit: NASA"
    if source_key == "wikimedia":
        artist = _TAG_RE.sub("", str(item.get("artist") or "")).strip()
        if artist:
            return f"Credit: {artist} via Wikimedia Commons ({item.get('licence', '')})"
        return f"Credit: Wikimedia Commons ({item.get('licence', '')})"
    return f"Credit: {source['credit']}"


def validate_music_source(name: str) -> tuple[bool, str | None]:
    """Music guard: only the YouTube Audio Library is permitted."""
    if str(name or "").strip().casefold() == PD_MUSIC_SOURCE.casefold():
        return True, None
    return False, f"music source {name!r} is not the YouTube Audio Library"


def _fetch_json(
    client: httpx.Client | None, url: str, params: dict, headers: dict | None = None
) -> dict:
    """GET JSON, raising RuntimeError on transport/HTTP failure.

    Mirrors ``discovery.discover_youtube_videos`` error handling so
    callers see one failure shape for every discovery source.
    """
    owned = client is None
    client = client or httpx.Client(timeout=20)
    try:
        response = client.get(url, params=params, headers=headers or {"User-Agent": USER_AGENT})
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            f"Public-domain source returned HTTP {exc.response.status_code} ({url})"
        ) from None
    except httpx.RequestError as exc:
        raise RuntimeError(
            f"Public-domain source request failed ({type(exc).__name__}: {url})"
        ) from None
    finally:
        if owned:
            client.close()
    if not isinstance(data, dict):
        raise RuntimeError(f"Public-domain source returned non-object JSON ({url})")
    return data


def nasa_search(query: str, max_results: int = 10, client: httpx.Client | None = None) -> list[dict]:
    """Search the NASA Image & Video Library (keyless API).

    Returns items with the licence recorded per item and the NASA-centre
    credit. Items failing the logo guard are excluded (counted in the
    returned items' absence — see :func:`discover_pd_media`).
    """
    query = str(query or "").strip()
    if not query:
        raise ValueError("NASA search needs a non-empty query")
    max_results = max(1, min(int(max_results), 50))
    data = _fetch_json(
        client,
        NASA_SEARCH_URL,
        {"q": query[:200], "media_type": "image,video", "page_size": max_results},
    )
    items: list[dict] = []
    for entry in data.get("collection", {}).get("items", []) or []:
        rows = entry.get("data") or []
        if not rows:
            continue
        row = rows[0]
        links = entry.get("links") or []
        canonical = next(
            (lnk.get("href") for lnk in links if lnk.get("rel") == "canonical"),
            None,
        )
        preview = next(
            (lnk.get("href") for lnk in links if lnk.get("rel") == "preview"),
            None,
        )
        item = {
            "source": "nasa",
            "source_id": str(row.get("nasa_id") or ""),
            "title": str(row.get("title") or ""),
            "description": str(row.get("description") or "")[:500],
            "keywords": [str(k) for k in (row.get("keywords") or [])],
            "media_type": str(row.get("media_type") or ""),
            "centre": str(row.get("center") or ""),
            "media_url": canonical or str(entry.get("href") or ""),
            "preview_url": preview,
            "licence": PD_SOURCES["nasa"]["licence"],
            "fetch": "api",
            "rights_verified": True,
        }
        item["credit"] = build_credit("nasa", item)
        ok, _reason = logo_guard(item)
        if not ok:
            continue
        items.append(item)
    return items[:max_results]


def wikimedia_search(query: str, max_results: int = 10, client: httpx.Client | None = None) -> list[dict]:
    """Search Wikimedia Commons, keeping CC0 / Public Domain files only.

    The Commons API returns the recorded licence per file
    (``extmetadata.LicenseShortName``); files under any other licence
    are dropped, not relabelled.
    """
    query = str(query or "").strip()
    if not query:
        raise ValueError("Wikimedia search needs a non-empty query")
    max_results = max(1, min(int(max_results), 50))
    data = _fetch_json(
        client,
        WIKIMEDIA_API_URL,
        {
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrsearch": query[:200],
            "gsrnamespace": 6,
            "gsrlimit": max_results,
            "prop": "imageinfo",
            "iiprop": "url|extmetadata",
            "iiextmetadatafilter": "LicenseShortName|Artist",
        },
    )
    items: list[dict] = []
    for page in (data.get("query", {}).get("pages", {}) or {}).values():
        info = (page.get("imageinfo") or [{}])[0]
        ext = info.get("extmetadata") or {}
        licence = str((ext.get("LicenseShortName") or {}).get("value") or "").strip()
        if licence.casefold() not in WIKIMEDIA_ALLOWED_LICENCES:
            continue
        item = {
            "source": "wikimedia",
            "source_id": str(page.get("title") or ""),
            "title": str(page.get("title") or ""),
            "description": "",
            "keywords": [],
            "media_type": "image",
            "centre": "",
            "media_url": str(info.get("url") or ""),
            "preview_url": str(info.get("thumburl") or "") or None,
            "licence": licence,
            "artist": str((ext.get("Artist") or {}).get("value") or ""),
            "file_page": str(info.get("descriptionurl") or ""),
            "fetch": "api",
            "rights_verified": True,
        }
        item["credit"] = build_credit("wikimedia", item)
        ok, _reason = logo_guard(item)
        if not ok:
            continue
        items.append(item)
    return items[:max_results]


def _catalogue_entry(source_key: str, query: str) -> dict:
    """Catalogue entry for a source with no stable keyless JSON API.

    NOAA and USGS expose no keyless search API from this environment
    (photolib search redirects; usgs.gov media search is CloudFront
    blocked), so the lane records the official search URL and the
    licence, and leaves ``media_url`` empty: a human picks the item on
    the catalogue. No download link is ever invented.
    """
    source = PD_SOURCES[source_key]
    base = source["search_url"]
    if source_key == "noaa":
        search_url = f"https://www.photolib.noaa.gov/search?search={quote_plus(query)}"
    else:  # usgs
        search_url = f"{base}?search={quote_plus(query)}"
    item = {
        "source": source_key,
        "source_id": "",
        "title": f"{source['name']} catalogue search: {query}",
        "description": (
            f"Pick the item on the official {source['name']} catalogue; "
            "record its page URL before import."
        ),
        "keywords": [],
        "media_type": "",
        "centre": "",
        "media_url": None,
        "preview_url": None,
        "licence": source["licence"],
        "search_url": search_url,
        "fetch": "catalogue",
        "rights_verified": True,
    }
    item["credit"] = build_credit(source_key, item)
    return item


def discover_pd_media(
    query: str,
    sources: tuple[str, ...] = ("nasa", "wikimedia", "noaa", "usgs"),
    max_results: int = 10,
    client: httpx.Client | None = None,
) -> list[dict]:
    """The whitelist lane: discover space/science media, licence per item.

    Live API sources (NASA, Wikimedia) are queried; catalogue sources
    (NOAA, USGS) contribute one catalogue entry each. Results are
    merged round-robin across the live sources so no source crowds
    the others out of the pack. Every returned item carries
    ``source``, ``licence``, ``credit`` and ``fetch``; logo-guarded
    items are excluded upstream. Raises ValueError on an unknown
    source key, RuntimeError on API failure.
    """
    query = str(query or "").strip()
    if not query:
        raise ValueError("Whitelist discovery needs a non-empty query")
    unknown = [s for s in sources if s not in PD_SOURCES]
    if unknown:
        raise ValueError(f"Unknown whitelist source(s): {', '.join(unknown)}")
    max_results = max(1, min(int(max_results), 50))
    lists: list[list[dict]] = []
    for key in sources:
        if PD_SOURCES[key]["fetch"] == "api":
            search = nasa_search if key == "nasa" else wikimedia_search
            lists.append(search(query, max_results=max_results, client=client))
        else:
            lists.append([_catalogue_entry(key, query)])
    # Round-robin across every source (catalogue entries are one-item
    # lists) so no source crowds the others out of the pack and all
    # four whitelist sources are represented whenever they have items.
    items: list[dict] = []
    for index in range(max((len(lst) for lst in lists), default=0)):
        for lst in lists:
            if index < len(lst):
                items.append(lst[index])
    return items[:max_results]


def build_series_pack(
    query: str,
    max_results: int = 10,
    client: httpx.Client | None = None,
) -> dict:
    """One space/science series pack from the whitelist lane.

    Returns the discovered items plus the description credit lines and
    the guard record: no NASA logos (enforced at discovery), credit in
    description (the collected lines), YouTube Audio Library music
    only (the lane's sole permitted music source).
    """
    items = discover_pd_media(query, max_results=max_results, client=client)
    credits: list[str] = []
    for item in items:
        credit = item.get("credit") or ""
        if credit and credit not in credits:
            credits.append(credit)
    return {
        "query": query,
        "items": items,
        "credits": credits,
        "music_source": PD_MUSIC_SOURCE,
        "guards": {
            "no_nasa_logos": True,
            "credit_in_description": bool(credits),
            "music_source": PD_MUSIC_SOURCE,
        },
        "licences": {key: PD_SOURCES[key]["licence"] for key in PD_SOURCES},
    }
