"""VyralX remix content flow (TASK-VYR-004).

The channel's sanctioned way to build shorts out of other people's videos,
per the owner's 2026-11-15 direction: use existing footage, add the
channel's own commentary, keep the editing light — and only ever touch
material the channel may lawfully and safely reuse.

Flow: discovery -> provenance -> download -> remix -> render -> review queue.

* Discovery is restricted to Creative Commons-licensed video, public-domain
  material, and the owner's own uploads. Until the owner supplies a valid
  YouTube Data API key (the deployed key is invalid and CREDENTIALS.md holds
  none — TASK-VYR-003), discovery runs on keyless sources only: Wikimedia
  Commons, the Internet Archive, and NASA's public-domain library.
* Every evaluated source gets a provenance record (source URL, author,
  licence, retrieval date) in an append-only registry. No provenance record
  — or a licence that forbids derivatives or commercial use (NC / ND) —
  means the source is NOT a candidate, and the produce step refuses it.
* The remix itself is the TASK-VYR-003 fixed path in
  :mod:`app.services.viral_remix`: per-beat original voice-over with measured
  durations, visual segments retimed to the beat audio, captions aligned to
  the finished narration with Whisper word timestamps.
* Nothing in this flow uploads. Renders land in a review queue
  (``pending_review`` in the queue registry, ``pending_approval`` when a DB
  publish job is created) for the owner to approve.

The governing policy document is ``VyralX/docs/REMIX_POLICY.md`` — the
transformative edit spec and the per-video compliance checklist live there
and are mirrored by :func:`compliance_checklist`. Since TASK-VYR-009 the
checklist is also enforced by the automated gate in
:mod:`app.services.compliance_gate`: :func:`produce_remix_short` evaluates
it on the finished render's measured production record, and a failing
render is queued as ``blocked_compliance`` with no publish job — it can
never be marked ready to upload.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import httpx

from app.config import get_settings
from app.services import compliance_gate

log = logging.getLogger("vyralx.remix_flow")

USER_AGENT = "VyralX-RemixFlow/1.0 (FRIDAY Universe; CC/PD source discovery)"

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
ARCHIVE_SEARCH = "https://archive.org/advancedsearch.php"
ARCHIVE_METADATA = "https://archive.org/metadata"
ARCHIVE_DOWNLOAD = "https://archive.org/download"
NASA_SEARCH = "https://images-api.nasa.gov/search"
NASA_MEDIA_GUIDELINES = "https://www.nasa.gov/nasa-brand-center/images-and-media/"

#: Licence classes a monetised channel may build derivatives on.
ALLOWED_LICENSE_CLASSES = {"cc0", "public_domain", "cc_by", "cc_by_sa", "owner"}

#: Content lanes that must never be sourced (YouTube reused-content policy +
#: Content ID reality; see docs/REMIX_POLICY.md). Anime compilations are
#: named in the reused-content policy as monetisation-ineligible, and raw
#: gameplay re-uploads are the same category. Compilation lanes for sports,
#: Bollywood and movies carry the same claim/strike profile. Financial
#: ADVICE is excluded as a lane of its own: YouTube policy makes AI-persona
#: financial guidance non-monetisable (money content is stories only).
EXCLUDED_LANES = {
    "anime_compilation",
    "gameplay_reupload",
    "sports_compilation",
    "bollywood_compilation",
    "movie_compilation",
    "compilation",
    "reupload",
    "finance_advice",
}

#: Declared content lanes, in the researched priority order (2026-11-15):
#: space & science over PD footage first, history facts second, tech
#: explainers third, money STORIES (never advice) fourth.
CONTENT_LANES = ("space_science", "history_facts", "tech_explainer", "money_story")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", str(text or ""))
    return " ".join(text.split())


# --------------------------------------------------------------------------- #
# Licence gate
# --------------------------------------------------------------------------- #
def classify_license(
    license_name: str = "", license_url: str = "", platform: str = ""
) -> tuple[str, bool, str]:
    """Classify a licence into (class, allowed, reason).

    A remix is a derivative work on a monetised channel, so the licence must
    permit BOTH derivatives and commercial use: CC0 / public domain, CC BY
    and CC BY-SA pass; any NC (non-commercial) or ND (no-derivatives)
    variant fails, as does anything unrecognised.
    """
    name = str(license_name or "").casefold()
    url = str(license_url or "").casefold()
    text = f"{name} {url}"
    if platform == "owner_upload":
        return "owner", True, "the channel owner's own upload"
    if (
        "cc0" in text
        or "publicdomain/zero" in url
        or "public domain" in name
        or "publicdomain" in url
        or name.strip() in {"pdm", "cc-pdm"}
    ):
        return "public_domain", True, "public domain / CC0 — no rights reserved"
    if platform == "nasa" or "nasa" in name or "u.s. government" in name:
        return "public_domain", True, "U.S. Government work (NASA) is public domain"
    match = re.search(r"licenses/(by(?:-[a-z]+)*)/", url) or re.search(
        r"\bcc\s+(by(?:-[a-z]+)*)\b", name
    )
    if match:
        parts = match.group(1).split("-")
        if "nc" in parts:
            return (
                "cc_noncommercial",
                False,
                "NonCommercial licence forbids use on a monetised channel",
            )
        if "nd" in parts:
            return (
                "cc_noderivatives",
                False,
                "NoDerivatives licence forbids remixes (derivative works)",
            )
        if "sa" in parts:
            return (
                "cc_by_sa",
                True,
                "CC BY-SA — reuse allowed with attribution; share-alike noted",
            )
        return "cc_by", True, "CC BY — reuse allowed with attribution"
    if "creative commons" in name:
        return (
            "unknown",
            False,
            "Creative Commons variant not identified — NC/ND cannot be excluded",
        )
    return "unknown", False, "no recognised reuse licence in the source metadata"


# --------------------------------------------------------------------------- #
# Provenance
# --------------------------------------------------------------------------- #
@dataclass
class ProvenanceRecord:
    """One evaluated source, with everything needed to prove reuse rights."""

    platform: str
    title: str
    author: str
    source_page_url: str
    media_url: str
    license_name: str
    license_url: str = ""
    retrieved_at: str = ""
    duration_seconds: float | None = None
    width: int | None = None
    height: int | None = None
    license_class: str = "unknown"
    allowed: bool = False
    decision_reason: str = ""

    @property
    def record_id(self) -> str:
        digest = hashlib.sha1(
            f"{self.platform}|{self.source_page_url}".encode("utf-8")
        ).hexdigest()
        return digest[:12]

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "platform": self.platform,
            "title": self.title,
            "author": self.author,
            "source_page_url": self.source_page_url,
            "media_url": self.media_url,
            "license_name": self.license_name,
            "license_url": self.license_url,
            "retrieved_at": self.retrieved_at,
            "duration_seconds": self.duration_seconds,
            "width": self.width,
            "height": self.height,
            "license_class": self.license_class,
            "allowed": self.allowed,
            "decision_reason": self.decision_reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProvenanceRecord":
        keys = {
            "platform", "title", "author", "source_page_url", "media_url",
            "license_name", "license_url", "retrieved_at", "duration_seconds",
            "width", "height", "license_class", "allowed", "decision_reason",
        }
        return cls(**{k: data.get(k) for k in keys if k in data})

    def require_candidate(self) -> None:
        """The gate: no provenance, or a failing licence, is not a candidate."""
        missing = [
            name
            for name in ("source_page_url", "author", "license_name", "retrieved_at")
            if not str(getattr(self, name) or "").strip()
        ]
        if missing:
            raise ValueError(
                f"provenance incomplete for {self.source_page_url!r}: missing {missing}"
            )
        if not self.allowed or self.license_class not in ALLOWED_LICENSE_CLASSES:
            raise ValueError(
                f"source is not a reuse candidate: {self.decision_reason}"
            )


def default_registry_path() -> Path:
    return get_settings().data_dir / "remix_provenance.jsonl"


def record_provenance(
    records: Iterable[ProvenanceRecord], registry_path: Path | None = None
) -> Path:
    """Append records to the provenance registry (append-only JSONL)."""
    path = Path(registry_path) if registry_path else default_registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
    return path


def load_provenance(registry_path: Path | None = None) -> list[ProvenanceRecord]:
    path = Path(registry_path) if registry_path else default_registry_path()
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(ProvenanceRecord.from_dict(json.loads(line)))
    return records


# --------------------------------------------------------------------------- #
# Keyless discovery adapters
# --------------------------------------------------------------------------- #
def _http_get_json(url: str, params: dict[str, Any] | None = None) -> Any:
    with httpx.Client(
        timeout=30.0, headers={"User-Agent": USER_AGENT}, follow_redirects=True
    ) as client:
        response = client.get(url, params=params)
        response.raise_for_status()
        return response.json()


def _make_record(**kwargs: Any) -> ProvenanceRecord:
    license_class, allowed, reason = classify_license(
        kwargs.get("license_name", ""),
        kwargs.get("license_url", ""),
        kwargs.get("platform", ""),
    )
    return ProvenanceRecord(
        license_class=license_class,
        allowed=allowed,
        decision_reason=reason,
        **kwargs,
    )


def parse_commons(payload: dict[str, Any]) -> list[ProvenanceRecord]:
    """Parse a Wikimedia Commons videoinfo search payload."""
    records = []
    pages = ((payload or {}).get("query") or {}).get("pages") or []
    for page in pages:
        info = (page.get("videoinfo") or [{}])[0]
        if not info.get("url"):
            continue
        meta = info.get("extmetadata") or {}

        def meta_value(key: str) -> str:
            return str((meta.get(key) or {}).get("value") or "")

        title = str(page.get("title") or "").removeprefix("File:").rsplit(".", 1)[0]
        records.append(
            _make_record(
                platform="wikimedia_commons",
                title=title or "Untitled (Wikimedia Commons)",
                author=_strip_html(meta_value("Artist")) or "Unknown (Wikimedia Commons)",
                source_page_url=page.get("canonicalurl")
                or f"https://commons.wikimedia.org/wiki/{page.get('title', '').replace(' ', '_')}",
                media_url=str(info["url"]),
                license_name=meta_value("LicenseShortName"),
                license_url=meta_value("LicenseUrl"),
                duration_seconds=float(info["duration"]) if info.get("duration") else None,
                width=int(info["width"]) if info.get("width") else None,
                height=int(info["height"]) if info.get("height") else None,
            )
        )
    return records


def _commons_search(query: str, limit: int) -> list[ProvenanceRecord]:
    payload = _http_get_json(
        COMMONS_API,
        params={
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "generator": "search",
            "gsrsearch": f"{query} filetype:video",
            "gsrnamespace": "6",
            "gsrlimit": str(limit),
            "prop": "videoinfo|info",
            "inprop": "url",
            "viprop": "url|size|duration|extmetadata",
        },
    )
    return parse_commons(payload)


def parse_archive_search(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse an Internet Archive advancedsearch payload into raw hit dicts."""
    docs = ((payload or {}).get("response") or {}).get("docs") or []
    hits = []
    for doc in docs:
        creator = doc.get("creator") or ""
        if isinstance(creator, list):
            creator = ", ".join(str(c) for c in creator)
        hits.append(
            {
                "identifier": str(doc.get("identifier") or ""),
                "title": str(doc.get("title") or ""),
                "author": str(creator),
                "license_url": str(doc.get("licenseurl") or ""),
            }
        )
    return hits


def pick_archive_file(files: list[dict[str, Any]]) -> str | None:
    """Pick the best downloadable video file from an Archive metadata listing."""
    videos = [
        f
        for f in files or []
        if str(f.get("name") or "").casefold().endswith((".mp4", ".webm", ".mov"))
    ]
    if not videos:
        return None

    def rank(f: dict[str, Any]) -> tuple[int, int]:
        name = str(f.get("name") or "").casefold()
        fmt = str(f.get("format") or "").casefold()
        mp4 = 0 if (name.endswith(".mp4") or "mp4" in fmt) else 1
        size = int(f.get("size") or 0)
        return (mp4, -size)

    return str(sorted(videos, key=rank)[0]["name"])


def _archive_search(query: str, limit: int) -> list[ProvenanceRecord]:
    payload = _http_get_json(
        ARCHIVE_SEARCH,
        params={
            "q": f"({query}) AND mediatype:movies",
            "fl[]": ["identifier", "title", "creator", "licenseurl"],
            "rows": str(limit * 3),
            "page": "1",
            "output": "json",
        },
    )
    records = []
    for hit in parse_archive_search(payload):
        if len(records) >= limit:
            break
        if not hit["identifier"] or not hit["license_url"]:
            continue
        try:
            metadata = _http_get_json(f"{ARCHIVE_METADATA}/{hit['identifier']}")
        except Exception as exc:  # one bad item must not sink the search
            log.warning("Archive metadata failed for %s: %s", hit["identifier"], exc)
            continue
        file_name = pick_archive_file(metadata.get("files") or [])
        if not file_name:
            continue
        license_class, _, _ = classify_license("", hit["license_url"], "internet_archive")
        license_name = (
            "Creative Commons / public domain (see licence URL)"
            if license_class != "unknown"
            else ""
        )
        records.append(
            _make_record(
                platform="internet_archive",
                title=hit["title"] or hit["identifier"],
                author=hit["author"] or "Unknown (Internet Archive)",
                source_page_url=f"https://archive.org/details/{hit['identifier']}",
                media_url=f"{ARCHIVE_DOWNLOAD}/{hit['identifier']}/{file_name}",
                license_name=license_name,
                license_url=hit["license_url"],
            )
        )
    return records


def parse_nasa_search(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse a NASA image/video library search payload into raw hit dicts."""
    items = ((payload or {}).get("collection") or {}).get("items") or []
    hits = []
    for item in items:
        data = (item.get("data") or [{}])[0]
        hits.append(
            {
                "nasa_id": str(data.get("nasa_id") or ""),
                "title": str(data.get("title") or ""),
                "collection_url": str(item.get("href") or ""),
            }
        )
    return hits


def pick_nasa_file(urls: list[str]) -> str | None:
    """Pick a video file from a NASA asset collection listing."""
    mp4s = [u for u in urls or [] if str(u).casefold().endswith(".mp4")]
    if not mp4s:
        return None
    for marker in ("~small", "~mobile", "~medium"):
        for url in mp4s:
            if marker in url.casefold():
                return url
    return mp4s[0]


def _nasa_search(query: str, limit: int) -> list[ProvenanceRecord]:
    payload = _http_get_json(NASA_SEARCH, params={"q": query, "media_type": "video"})
    records = []
    for hit in parse_nasa_search(payload):
        if len(records) >= limit:
            break
        if not hit["collection_url"]:
            continue
        try:
            urls = _http_get_json(hit["collection_url"])
        except Exception as exc:
            log.warning("NASA collection failed for %s: %s", hit["nasa_id"], exc)
            continue
        media_url = pick_nasa_file(urls if isinstance(urls, list) else [])
        if not media_url:
            continue
        records.append(
            _make_record(
                platform="nasa",
                title=hit["title"] or hit["nasa_id"],
                author="NASA",
                source_page_url=f"https://images.nasa.gov/details/{hit['nasa_id']}",
                media_url=media_url,
                license_name="Public Domain — NASA (U.S. Government work)",
                license_url=NASA_MEDIA_GUIDELINES,
            )
        )
    return records


_ADAPTERS = {
    "wikimedia_commons": _commons_search,
    "internet_archive": _archive_search,
    "nasa": _nasa_search,
}


def discover_candidates(
    query: str,
    *,
    limit_per_source: int = 5,
    sources: Iterable[str] = ("wikimedia_commons", "internet_archive", "nasa"),
    registry_path: Path | None = None,
    record: bool = True,
) -> list[ProvenanceRecord]:
    """Discover reusable sources; record ALL evaluated; return candidates only.

    A source becomes a candidate only with a complete provenance record and
    a licence class in :data:`ALLOWED_LICENSE_CLASSES`.
    """
    evaluated: list[ProvenanceRecord] = []
    for name in sources:
        adapter = _ADAPTERS.get(name)
        if adapter is None:
            log.warning("unknown discovery source %r skipped", name)
            continue
        try:
            evaluated.extend(adapter(query, limit_per_source))
        except Exception as exc:  # a dead source must not sink discovery
            log.warning("discovery via %s failed: %s", name, exc)
    stamp = _now_iso()
    seen: set[str] = set()
    unique: list[ProvenanceRecord] = []
    for rec in evaluated:
        rec.retrieved_at = rec.retrieved_at or stamp
        if rec.source_page_url in seen:
            continue
        seen.add(rec.source_page_url)
        unique.append(rec)
    if record and unique:
        record_provenance(unique, registry_path)
    return [rec for rec in unique if rec.allowed]


# --------------------------------------------------------------------------- #
# Download + metadata
# --------------------------------------------------------------------------- #
def download_media(record: ProvenanceRecord, dest_dir: Path) -> Path:
    """Download a candidate's media file (provenance gate enforced)."""
    record.require_candidate()
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(record.media_url.split("?")[0]).suffix or ".mp4"
    destination = dest_dir / f"{record.record_id}{suffix}"
    if destination.exists() and destination.stat().st_size > 0:
        return destination
    with httpx.Client(
        timeout=600.0, headers={"User-Agent": USER_AGENT}, follow_redirects=True
    ) as client:
        with client.stream("GET", record.media_url) as response:
            response.raise_for_status()
            with destination.open("wb") as fh:
                for chunk in response.iter_bytes(1 << 20):
                    fh.write(chunk)
    return destination


def build_remix_metadata(
    record: ProvenanceRecord, *, title: str, hook: str = ""
) -> dict[str, Any]:
    """Upload metadata whose description carries the full attribution block."""
    description_lines = [
        hook or title,
        "",
        "Original commentary, editing and captions by VyralX over credited "
        "source footage — the borrowed video is the evidence, the commentary "
        "is the product.",
        "",
        f'Source footage: "{record.title}" by {record.author}',
        f"Licence: {record.license_name}"
        + (f" ({record.license_url})" if record.license_url else ""),
        f"Source: {record.source_page_url}",
        "Provenance recorded by VyralX remix flow "
        f"(record {record.record_id}, retrieved {record.retrieved_at}).",
    ]
    return {
        "title": title,
        "description": "\n".join(description_lines),
        "tags": ["shorts", "vyralx", "remix", "commentary"],
        "attribution": (
            f'"{record.title}" by {record.author}, licensed '
            f"{record.license_name} — {record.source_page_url}"
        ),
    }


# --------------------------------------------------------------------------- #
# Compliance checklist (mirrors docs/REMIX_POLICY.md)
# --------------------------------------------------------------------------- #
def compliance_checklist(
    record: ProvenanceRecord,
    *,
    lane: str,
    source_has_speech: bool,
    attribution_included: bool = True,
    render_seconds: float | None = None,
    language: str = "en",
    format_name: str = "",
) -> list[dict[str, Any]]:
    """The per-video compliance checklist for one remix, evaluated."""
    items: list[dict[str, Any]] = []

    def add(item: str, ok: bool, detail: str) -> None:
        items.append({"item": item, "status": "pass" if ok else "FAIL", "detail": detail})

    add(
        "Source is CC / public-domain / owner-owned, with a provenance record on file",
        record.allowed and bool(record.retrieved_at),
        f"record {record.record_id}: {record.license_name} ({record.decision_reason})",
    )
    add(
        "Licence permits derivatives and commercial use (no NC, no ND)",
        record.license_class in ALLOWED_LICENSE_CLASSES,
        f"licence class {record.license_class}",
    )
    add(
        "Original script + original voice-over commentary is the primary audio",
        not source_has_speech,
        "source audition: "
        + ("speech found — two voices would overlap" if source_has_speech else "no source narration; channel voice-over carries the video"),
    )
    add(
        "Source re-cut into scene beats retimed to the commentary (not a straight re-upload)",
        True,
        "TASK-VYR-003 scene-timed assembly (viral_remix.render_scene_timed)",
    )
    add(
        "Captions aligned to the finished audio (Whisper word timestamps)",
        True,
        "TASK-VYR-003 caption path (viral_remix.build_commentary_cues)",
    )
    add(
        "Runtime under 60 seconds (a claimed Short over 1 minute is BLOCKED, not just claimed)",
        render_seconds is not None and render_seconds < 60.0,
        f"render {render_seconds}s" if render_seconds is not None else "runtime not measured",
    )
    add(
        "Attribution in the description: author, licence, source URL",
        attribution_included,
        "build_remix_metadata attribution block",
    )
    add(
        "Format is not an excluded lane (no anime/gameplay/sports/Bollywood/movie compilations, no finance advice, no straight re-uploads)",
        lane not in EXCLUDED_LANES,
        f"lane {lane!r}"
        + (" is EXCLUDED — reused-content policy / Content ID" if lane in EXCLUDED_LANES else ""),
    )
    add(
        "Language and targeting: English, global audience",
        language == "en",
        "English script; publish targeting is global (India-only Shorts traffic "
        "pays ~41x less per AIR 2025 data) — set at upload, an owner step",
    )
    add(
        "Declared format recorded (structure varies across formats — no template-identical mass volume)",
        bool(format_name),
        f"format {format_name!r}; template-identical volume risks "
        "'inauthentic content' demonetisation",
    )
    add(
        "Held for owner review — this flow never uploads",
        True,
        "review queue status pending_review / publish job pending_approval",
    )
    return items


def checklist_passed(checklist: list[dict[str, Any]]) -> bool:
    return all(item["status"] == "pass" for item in checklist)


# --------------------------------------------------------------------------- #
# Review queue
# --------------------------------------------------------------------------- #
def default_queue_path() -> Path:
    return get_settings().data_dir / "remix_review_queue.jsonl"


def enqueue_review(entry: dict[str, Any], queue_path: Path | None = None) -> Path:
    path = Path(queue_path) if queue_path else default_queue_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return path


def list_review_queue(queue_path: Path | None = None) -> list[dict[str, Any]]:
    path = Path(queue_path) if queue_path else default_queue_path()
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


# --------------------------------------------------------------------------- #
# Produce: provenance-gated remix through the TASK-VYR-003 path
# --------------------------------------------------------------------------- #
def _gate_input_for_render(
    record: ProvenanceRecord,
    *,
    script: str,
    lane: str,
    format_name: str,
    tracks: dict[str, Any],
    cues: list[dict[str, Any]],
    render_path: Path,
) -> compliance_gate.GateInput:
    """Assemble the compliance gate's measured production record.

    Sync is measured from the finished render's own artifacts — the same
    recipe TASK-VYR-003 used for its production proof: per-beat rendered
    segment vs measured beat audio (via segment_timing), and the burned
    caption cues vs a Whisper transcript of the finished narration.
    Anything that cannot be measured stays None, and the gate fails that
    check — sync is proven from measurements, never asserted (TASK-VYR-009).
    """
    from app.services import viral_remix as vr
    from app.services.source_analysis import probe_media

    render_seconds: float | None = None
    try:
        probed = probe_media(render_path)
        render_seconds = float(probed.duration) if probed and probed.duration else None
    except Exception as exc:  # a probe failure must not crash the produce step
        log.warning(
            "Compliance gate: render probe failed (%s: %s)",
            type(exc).__name__, str(exc)[:120],
        )
    heard: list[dict[str, Any]] = []
    try:
        heard = vr._whisper_words(tracks["narration_path"])
    except Exception as exc:  # unmeasured captions fail the gate, not the render
        log.warning(
            "Compliance gate: caption measurement unavailable (%s: %s)",
            type(exc).__name__, str(exc)[:120],
        )
    match_rate, offset_max = compliance_gate.caption_sync_metrics(cues, heard)
    sync = compliance_gate.SyncMeasurements(
        beat_deviations_seconds=compliance_gate.beat_deviations_from_tracks(tracks),
        caption_offset_max_abs_seconds=offset_max,
        caption_match_rate=match_rate,
        narration_seconds=float(tracks["total_seconds"]),
        render_seconds=render_seconds,
    )
    return compliance_gate.GateInput(
        provenance=record,
        lane=lane,
        format_name=format_name,
        script=script,
        # The audition above already skipped narrated sources, and a source
        # with no audio track has no narration either.
        source_has_speech=False,
        # build_remix_metadata always emits the attribution block.
        attribution_included=True,
        language="en",
        sync=sync,
    )


def produce_remix_short(
    record: ProvenanceRecord,
    script: str,
    *,
    title: str,
    hook: str = "",
    lane: str = "space_science",
    format_name: str = "one_fact_escalation",
    category: str = "VIRAL",
    db: Any = None,
    queue_path: Path | None = None,
) -> dict[str, Any]:
    """Download -> audition -> scene-timed remix -> render -> review queue.

    ``script`` is the ORIGINAL commentary written for this video (the
    transformative element); ``lane`` is the content lane for the compliance
    checklist. Nothing is uploaded: the result is a review-queue entry.

    After the render, the TASK-VYR-009 compliance gate
    (:mod:`app.services.compliance_gate`) evaluates the render's measured
    production record. A passing render is queued ``pending_review`` (and
    gets its ``pending_approval`` publish job when ``db`` is given); a
    failing render is queued ``blocked_compliance`` and NO publish job is
    created — it cannot be marked ready to upload.
    """
    # Gates first, before any heavy import or network: a source without
    # provenance (or with a failing licence) never reaches the pipeline.
    record.require_candidate()
    if lane in EXCLUDED_LANES:
        raise ValueError(f"lane {lane!r} is excluded by the remix policy")

    from app.services import viral_remix as vr
    from app.services.source_analysis import detect_speech, probe_media
    settings = get_settings()
    settings.prepare_directories()
    settings.render_dir.mkdir(parents=True, exist_ok=True)
    settings.media_dir.mkdir(parents=True, exist_ok=True)

    project_key = f"remix-{record.record_id}-{uuid.uuid4().hex[:6]}"
    source_path = download_media(record, settings.media_dir / "remix_sources")
    probe = probe_media(source_path)
    duration = max(6.0, probe.duration or record.duration_seconds or 20.0)

    # Audition: a narrated source would put two voices on top of each other.
    speech = None
    if probe.has_audio:
        wav_path = vr._decode_to_wav(
            source_path, settings.media_dir / "remix_sources" / f"{project_key}-probe.wav"
        )
        speech = detect_speech(wav_path)
        if speech.has_speech:
            return {
                "status": "SKIPPED",
                "reason": "source_has_narration",
                "record_id": record.record_id,
                "speech_seconds": speech.speech_seconds,
            }

    voice = vr.VOICE_BY_CATEGORY.get(category.upper(), vr.DEFAULT_VOICE)
    tracks = vr.build_scene_tracks(
        script, voice, settings.media_dir / "voiceovers", project_key, duration
    )
    cues = vr.build_commentary_cues(tracks, script)
    if not cues:
        raise RuntimeError("caption generation produced no cues")
    render_path = settings.render_dir / f"{project_key}.mp4"
    vr.render_scene_timed(
        source_path, render_path, tracks, cues, category.upper(), probe.has_audio
    )

    meta = build_remix_metadata(record, title=title, hook=hook)
    checklist = compliance_checklist(
        record,
        lane=lane,
        source_has_speech=False,
        attribution_included=True,
        render_seconds=tracks["total_seconds"],
        format_name=format_name,
    )
    # TASK-VYR-009: the checklist is advisory; the compliance GATE decides.
    # It evaluates the finished render's measured production record, and a
    # failing render never reaches a publish job (see below).
    gate_verdict = compliance_gate.evaluate_compliance_gate(
        _gate_input_for_render(
            record,
            script=script,
            lane=lane,
            format_name=format_name,
            tracks=tracks,
            cues=cues,
            render_path=render_path,
        )
    )
    beats = [
        {
            "index": beat["index"],
            "segment_seconds": beat["segment_seconds"],
            "audio_seconds": beat["audio_seconds"],
            "factor": beat["timing"]["factor"],
        }
        for beat in tracks["beats"]
    ]
    result: dict[str, Any] = {
        "status": "PENDING_REVIEW" if gate_verdict.passed else "BLOCKED_COMPLIANCE",
        "project_key": project_key,
        "record_id": record.record_id,
        "title": title,
        "lane": lane,
        "format": format_name,
        "render": str(render_path),
        "ass": str(render_path.with_suffix(".ass")),
        "narration_seconds": tracks["total_seconds"],
        "source_duration": round(duration, 2),
        "beats": beats,
        "checklist_passed": checklist_passed(checklist),
        "compliance_gate": gate_verdict.to_dict(),
        "metadata": meta,
    }
    entry = {
        "queue_id": project_key,
        "created_at": _now_iso(),
        "status": "pending_review",
        "provenance": record.to_dict(),
        "compliance_checklist": checklist,
        **result,
    }
    if not gate_verdict.passed:
        entry["status"] = "blocked_compliance"
    enqueue_review(entry, queue_path)

    if not gate_verdict.passed:
        # The gate is a hard precondition for ready-to-upload: a blocked
        # render is queued for the record, but NO publish job is created,
        # so nothing downstream can approve or upload it.
        log.warning(
            "Remix short BLOCKED by the compliance gate: %s — failed checks: %s",
            project_key, ", ".join(gate_verdict.blocking_failures),
        )
        return result

    if db is not None:
        result["publish_job_id"] = _persist_review_job(
            db, record, source_path, probe, render_path, tracks, meta, project_key, title
        )
    log.info("Remix short ready for review: %s", result)
    return result


def _persist_review_job(
    db: Any,
    record: ProvenanceRecord,
    source_path: Path,
    probe: Any,
    render_path: Path,
    tracks: dict[str, Any],
    meta: dict[str, Any],
    project_key: str,
    title: str,
) -> int:
    """Persist rights + render rows and a PENDING_APPROVAL publish job.

    Mirrors viral_remix.produce_viral_short's persistence, except the rights
    record comes from the real provenance record (not an operator policy
    attestation) and the publish job waits for owner approval instead of
    being queued for upload.
    """
    from app.models import Asset, PublishJob, RenderJob, Source, VideoProject, utcnow

    settings = get_settings()
    source = Source(
        title=f"Source: {record.title[:240]}",
        source_url=record.source_page_url,
        platform=record.platform,
        creator=record.author[:280],
        license_name=record.license_name[:190],
        permission_reference=(record.license_url or record.source_page_url)[:2000],
        repeat_use_allowed=True,
        repeat_use_reviewed_at=utcnow(),
        repeat_use_review_notes=(
            f"Provenance record {record.record_id} retrieved {record.retrieved_at}; "
            f"licence class {record.license_class}."
        ),
        rights_verified=True,
        status="approved",
        notes=f"Remix flow provenance {record.record_id}: {record.decision_reason}",
    )
    db.add(source)
    db.flush()
    asset = Asset(
        source_id=source.id,
        title=record.title[:280],
        file_path=str(source_path),
        duration_seconds=float(probe.duration or record.duration_seconds or 0.0),
        width=probe.width,
        height=probe.height,
        rights_verified=True,
    )
    db.add(asset)
    db.flush()
    project = VideoProject(
        project_key=project_key,
        topic=f"Remix: {title[:120]}",
        video_format="shorts",
        target_seconds=int(round(tracks["total_seconds"])),
        audience="viral shorts audience",
        tone="original commentary over credited source footage",
        scene_count=1,
        confirm_pexels_license=False,
        confirm_pexels_repeat_use=False,
        use_voiceover=True,
        status="completed",
        primary_asset_id=asset.id,
        asset_ids_json=json.dumps([asset.id]),
        thumbnail_path="",
        completed_at=utcnow(),
        attempts=1,
    )
    db.add(project)
    db.flush()
    render_job = RenderJob(
        asset_id=asset.id,
        preset="shorts",
        status="completed",
        output_path=str(render_path),
        attempts=1,
        project_id=None,
        options_json=json.dumps({
            "montage_asset_ids": [asset.id],
            "provenance_record_id": record.record_id,
            "source_page_url": record.source_page_url,
            "edit_mode": "remix_commentary",
        }),
        completed_at=utcnow(),
    )
    db.add(render_job)
    db.flush()
    project.render_job_id = render_job.id
    publish_job = PublishJob(
        asset_id=asset.id,
        render_job_id=render_job.id,
        title=meta["title"][:100],
        description=meta["description"],
        tags_json=json.dumps(meta["tags"]),
        privacy_status=str(getattr(settings, "autonomous_publish_privacy", "unlisted")),
        status="pending_approval",
        approved_at=None,
    )
    db.add(publish_job)
    db.commit()
    return int(publish_job.id)
