"""Automated per-video compliance gate (TASK-VYR-009).

The remix policy (``VyralX/docs/REMIX_POLICY.md`` §5) defines a per-video
compliance checklist, and TASK-VYR-004 implemented it as
:func:`app.services.remix_flow.compliance_checklist` — an advisory list that
was *stored* on the review-queue entry while the render was queued for
approval regardless of the outcome. Two of its items were also asserted by
construction ("the TASK-VYR-003 path was used, therefore sync passes") —
exactly the failure mode TASK-VYR-003 had just fixed in production, where
sync was assumed for months while the shipped shorts were measurably out
of sync.

This module is the enforcement layer. It evaluates the same checklist as a
**gate** over the finished render's *measured production record*:

* a provenance record must be present, complete, and licence-allowed;
* the original commentary must be the main content — an original script,
  no narration in the source, and the narration track covering the
  majority of the render's runtime;
* sync must be *measured*, never asserted: per-beat
  |rendered segment − voice-over| deviations, caption-vs-audio offsets and
  the caption word-match rate must all be present and inside the
  TASK-VYR-003 production-verified thresholds. **Unmeasured sync fails
  the gate** — a render whose sync was never measured cannot be marked
  ready to upload;
* a render containing possibly-claimed (borrowed) material must be under
  60 seconds — a claimed Short over 1 minute is BLOCKED by YouTube, not
  just claimed;
* the declared lane/format must not be an excluded category (anime /
  gameplay / sports / Bollywood / movie compilations, straight
  re-uploads);
* the script must contain no financial advice (prescriptive markers are
  scanned, not just the lane label — money content is stories only);
* attribution must be present, the language English, the format declared.

:func:`app.services.remix_flow.produce_remix_short` runs this gate on
every render: a failing render is queued as ``blocked_compliance`` and no
publish job is created, so it can never be marked ready to upload.
:func:`assert_ready_to_upload` is the same verdict as an exception, for
any other caller that marks a video ready.
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

# --------------------------------------------------------------------------- #
# Thresholds — the TASK-VYR-003 production-verified numbers.
# The proof render (vyr003-proof) measured: per-beat deviations 0.00s,
# caption offset mean -0.025s / max |offset| 0.413s, 83/90 words matched.
# The broken pre-fix render measured: caption offsets +0.725s mean / 1.5s
# max, narration covering only 73.6% of the runtime.
# --------------------------------------------------------------------------- #
#: Max per-beat |rendered segment − voice-over| deviation, seconds.
MAX_BEAT_DEVIATION_SECONDS = 0.50
#: Max caption-vs-audio word offset, seconds (absolute).
MAX_CAPTION_OFFSET_SECONDS = 0.50
#: Min fraction of caption words matched to the finished audio (the
#: TASK-VYR-003 alignment floor in viral_remix.align_script_words).
MIN_CAPTION_MATCH_RATE = 0.70
#: Min narration/runtime ratio for the commentary to be the main content.
MIN_COMMENTARY_COVERAGE = 0.60
#: A Short containing possibly-claimed material must stay under this.
CLAIMED_SHORT_LIMIT_SECONDS = 60.0

# Lane / licence sets mirror app.services.remix_flow (the VYR-004 flow owns
# them; they are duplicated here so this module never imports remix_flow —
# remix_flow imports this module, and the gate must stay importable on its
# own). test_vyr009_compliance_gate pins the two copies to each other.
ALLOWED_LICENSE_CLASSES = {"cc0", "public_domain", "cc_by", "cc_by_sa", "owner"}
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
CONTENT_LANES = ("space_science", "history_facts", "tech_explainer", "money_story")

#: Tokens that mark an excluded category in a declared lane/format string.
EXCLUDED_TOKENS = (
    "anime",
    "gameplay",
    "sports",
    "bollywood",
    "movie",
    "compilation",
    "reupload",
    "re-upload",
)

#: Provenance fields that must all be present and non-empty. Mirrors
#: ProvenanceRecord.require_candidate, plus media_url (a record that does
#: not identify the media it covers is not a record of anything).
PROVENANCE_REQUIRED_FIELDS = (
    "source_page_url",
    "author",
    "license_name",
    "retrieved_at",
    "media_url",
)

#: Prescriptive financial-advice markers (imperative / promissory only —
#: narrative past tense in a money STORY does not match these). This is a
#: floor, not a ceiling: a hit blocks the video and is reported verbatim so
#: a human can judge borderline cases. See REMIX_POLICY.md §2/§3 lane 4.
FINANCE_ADVICE_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\byou should (buy|sell|invest|trade|short)\b", "direct recommendation to the viewer"),
    (r"\b(buy|sell) (it |this |that )?(now|today)\b", "timed buy/sell call"),
    (r"\bguaranteed (returns?|profits?|income)\b", "promised returns"),
    (r"\b(double|triple) your money\b", "promised multiplication of money"),
    (r"\bwill make you rich\b", "wealth promise"),
    (r"\bget rich (quick|fast)\b", "get-rich-quick promise"),
    (r"\buse \d+(\.\d+)?x leverage\b", "prescriptive leverage instruction"),
    (r"\bkeep your leverage (low|under|below)\b", "prescriptive leverage instruction"),
    (r"\bpracti[cs]e on (a )?demo first\b", "prescriptive trading instruction"),
    (r"\bset (a |your )?stop[- ]loss\b", "prescriptive risk instruction"),
)


class ComplianceGateError(ValueError):
    """Raised when a video that failed the gate is marked ready to upload."""


@dataclass
class SyncMeasurements:
    """Measured sync/production numbers for one finished render.

    Every field is optional at the type level because a producer may fail
    to measure; the gate treats a missing measurement as a FAILURE, never
    as a pass (see module docstring).
    """

    beat_deviations_seconds: list[float] | None = None
    caption_offset_max_abs_seconds: float | None = None
    caption_match_rate: float | None = None
    narration_seconds: float | None = None
    render_seconds: float | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "SyncMeasurements":
        if not data:
            return cls()
        return cls(
            beat_deviations_seconds=data.get("beat_deviations_seconds"),
            caption_offset_max_abs_seconds=data.get("caption_offset_max_abs_seconds"),
            caption_match_rate=data.get("caption_match_rate"),
            narration_seconds=data.get("narration_seconds"),
            render_seconds=data.get("render_seconds"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "beat_deviations_seconds": self.beat_deviations_seconds,
            "caption_offset_max_abs_seconds": self.caption_offset_max_abs_seconds,
            "caption_match_rate": self.caption_match_rate,
            "narration_seconds": self.narration_seconds,
            "render_seconds": self.render_seconds,
        }


@dataclass
class GateInput:
    """Everything the gate needs to judge one candidate video."""

    provenance: Any = None  # ProvenanceRecord, its to_dict(), or None
    lane: str = ""
    format_name: str = ""
    category: str = ""  # optional declared content category ("" = undeclared)
    script: str = ""
    source_has_speech: bool | None = None
    attribution_included: bool = False
    language: str = "en"
    sync: SyncMeasurements | None = None
    possibly_claimed: bool | None = None  # None = derive from provenance

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GateInput":
        sync = data.get("sync")
        return cls(
            provenance=data.get("provenance"),
            lane=str(data.get("lane") or ""),
            format_name=str(data.get("format_name") or ""),
            category=str(data.get("category") or ""),
            script=str(data.get("script") or ""),
            source_has_speech=data.get("source_has_speech"),
            attribution_included=bool(data.get("attribution_included")),
            language=str(data.get("language") or "en"),
            sync=sync if isinstance(sync, SyncMeasurements) else SyncMeasurements.from_dict(sync),
            possibly_claimed=data.get("possibly_claimed"),
        )


@dataclass
class GateVerdict:
    passed: bool
    checks: list[dict[str, Any]] = field(default_factory=list)
    blocking_failures: list[str] = field(default_factory=list)
    evaluated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "checks": self.checks,
            "blocking_failures": self.blocking_failures,
            "evaluated_at": self.evaluated_at,
        }


def _provenance_dict(provenance: Any) -> dict[str, Any] | None:
    if provenance is None:
        return None
    if isinstance(provenance, dict):
        return provenance
    to_dict = getattr(provenance, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    return None


def _norm_word(word: str) -> str:
    return re.sub(r"[^a-z0-9']", "", str(word).lower())


def find_finance_advice(script: str) -> list[dict[str, str]]:
    """Prescriptive financial-advice markers found in a script."""
    hits = []
    text = str(script or "")
    for pattern, label in FINANCE_ADVICE_PATTERNS:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            hits.append({"pattern": label, "matched_text": match.group(0)})
    return hits


# --------------------------------------------------------------------------- #
# Measurement helpers — turn pipeline artifacts into SyncMeasurements.
# --------------------------------------------------------------------------- #
def beat_deviations_from_tracks(tracks: dict[str, Any] | None) -> list[float] | None:
    """Per-beat |rendered segment − voice-over| deviations from scene tracks.

    Mirrors the TASK-VYR-003 proof measurement (proof_measure.py): a beat's
    rendered segment length is ``segment x factor + pad − trims`` from its
    segment_timing, compared against the beat's measured audio length.
    Returns None when the tracks do not carry the timing data (unmeasured).
    """
    beats = (tracks or {}).get("beats") or []
    if not beats:
        return None
    deviations: list[float] = []
    for beat in beats:
        timing = beat.get("timing") or {}
        try:
            segment = float(beat["segment_seconds"])
            audio = float(beat["audio_seconds"])
            landed = (
                segment * float(timing.get("factor", 1.0))
                + float(timing.get("pad_seconds", 0.0))
                - float(timing.get("trim_head_seconds", 0.0))
                - float(timing.get("trim_tail_seconds", 0.0))
            )
        except (KeyError, TypeError, ValueError):
            return None
        deviations.append(round(abs(landed - audio), 3))
    return deviations


def caption_sync_metrics(
    cues: list[dict[str, Any]] | None,
    heard_words: list[dict[str, Any]] | None,
) -> tuple[float | None, float | None]:
    """(caption word-match rate, max |caption − audio| offset) for a render.

    ``cues`` are the burned caption cues (start/end/text); ``heard_words``
    are Whisper word timestamps from the render's own audio. Words are
    matched by sequence (difflib, as in viral_remix.align_script_words);
    a matched word's offset is its caption time (proportional inside its
    cue) minus its heard start time. Returns (None, None) when either side
    is missing — the caller records that as *unmeasured*, and the gate
    fails unmeasured sync.
    """
    cue_words: list[tuple[str, float]] = []
    for cue in cues or []:
        words = str(cue.get("text") or "").split()
        if not words:
            continue
        start = float(cue.get("start") or 0.0)
        end = float(cue.get("end") or start)
        span = max(0.0, end - start)
        for index, word in enumerate(words):
            cue_words.append((_norm_word(word), start + span * (index / len(words))))
    heard = [
        (_norm_word(word.get("text", "")), float(word.get("start") or 0.0))
        for word in (heard_words or [])
    ]
    heard = [(text, start) for text, start in heard if text]
    if not cue_words or not heard:
        return None, None
    matcher = difflib.SequenceMatcher(
        a=[text for text, _ in cue_words],
        b=[text for text, _ in heard],
        autojunk=False,
    )
    offsets: list[float] = []
    matched = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                offsets.append(cue_words[i1 + k][1] - heard[j1 + k][1])
                matched += 1
    if not matched:
        return 0.0, None
    return matched / len(cue_words), max(abs(offset) for offset in offsets)


# --------------------------------------------------------------------------- #
# The gate
# --------------------------------------------------------------------------- #
def evaluate_compliance_gate(candidate: GateInput | dict[str, Any]) -> GateVerdict:
    """Evaluate every compliance check for one candidate video.

    Fail-closed throughout: anything missing or unmeasured FAILS its check.
    The verdict's ``blocking_failures`` names every failed check.
    """
    inp = candidate if isinstance(candidate, GateInput) else GateInput.from_dict(candidate)
    sync = inp.sync or SyncMeasurements()
    record = _provenance_dict(inp.provenance)
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "status": "pass" if ok else "FAIL", "detail": detail})

    # 1 — Provenance record present, complete, licence-allowed.
    if record is None:
        add("provenance_record", False, "no provenance record — a source without a record is not a candidate")
    else:
        missing = [
            name for name in PROVENANCE_REQUIRED_FIELDS
            if not str(record.get(name) or "").strip()
        ]
        license_class = str(record.get("license_class") or "")
        if missing:
            add("provenance_record", False, f"provenance record incomplete: missing {missing}")
        elif not record.get("allowed") or license_class not in ALLOWED_LICENSE_CLASSES:
            add(
                "provenance_record", False,
                f"licence class {license_class!r} is not reuse-allowed "
                f"({record.get('decision_reason') or 'not allowed'})",
            )
        else:
            add(
                "provenance_record", True,
                f"record {record.get('record_id', '?')}: {record.get('license_name')} "
                f"({license_class}), retrieved {record.get('retrieved_at')}",
            )

    # 2 — Original commentary is the main content.
    coverage = None
    if sync.narration_seconds is not None and sync.render_seconds:
        coverage = sync.narration_seconds / sync.render_seconds
    if not str(inp.script or "").strip():
        add("commentary_main_content", False, "no original script recorded for this video")
    elif inp.source_has_speech is not False:
        add(
            "commentary_main_content", False,
            "source narration present or audition not recorded — the channel "
            "commentary is not the sole/main voice",
        )
    elif coverage is None:
        add("commentary_main_content", False, "narration/render durations not measured — commentary share unverifiable")
    elif coverage < MIN_COMMENTARY_COVERAGE:
        add(
            "commentary_main_content", False,
            f"narration covers {coverage:.1%} of the render (< {MIN_COMMENTARY_COVERAGE:.0%}) — "
            "borrowed footage, not commentary, is the main content",
        )
    else:
        add(
            "commentary_main_content", True,
            f"original script; no source narration; narration covers {coverage:.1%} of the render",
        )

    # 3 — Sync measurements present and inside the VYR-003 thresholds.
    sync_problems: list[str] = []
    deviations = sync.beat_deviations_seconds
    if not deviations:
        sync_problems.append("per-beat segment/voice-over deviations not measured")
    elif max(deviations) > MAX_BEAT_DEVIATION_SECONDS:
        sync_problems.append(
            f"worst per-beat deviation {max(deviations):.2f}s > {MAX_BEAT_DEVIATION_SECONDS:.2f}s"
        )
    if sync.caption_match_rate is None:
        sync_problems.append("caption word-match rate not measured")
    elif sync.caption_match_rate < MIN_CAPTION_MATCH_RATE:
        sync_problems.append(
            f"caption word-match rate {sync.caption_match_rate:.2f} < {MIN_CAPTION_MATCH_RATE:.2f}"
        )
    if sync.caption_offset_max_abs_seconds is None:
        sync_problems.append("caption-vs-audio offsets not measured")
    elif sync.caption_offset_max_abs_seconds > MAX_CAPTION_OFFSET_SECONDS:
        sync_problems.append(
            f"max caption offset {sync.caption_offset_max_abs_seconds:.2f}s > {MAX_CAPTION_OFFSET_SECONDS:.2f}s"
        )
    if sync_problems:
        add("sync_measurements", False, "; ".join(sync_problems))
    else:
        add(
            "sync_measurements", True,
            f"beats max deviation {max(deviations):.2f}s; caption match "
            f"{sync.caption_match_rate:.2f}; max caption offset "
            f"{sync.caption_offset_max_abs_seconds:.2f}s",
        )

    # 4 — Possibly-claimed material must stay under 60 seconds.
    if inp.possibly_claimed is not None:
        possibly_claimed = bool(inp.possibly_claimed)
        claimed_basis = "declared by the producer"
    elif record is None:
        possibly_claimed = True
        claimed_basis = "no provenance record — material treated as borrowed"
    else:
        possibly_claimed = str(record.get("license_class") or "") != "owner"
        claimed_basis = f"licence class {record.get('license_class')!r}"
    if not possibly_claimed:
        add("claimed_short_duration", True, f"no borrowed material ({claimed_basis}) — the claimed-Short limit does not apply")
    elif sync.render_seconds is None:
        add("claimed_short_duration", False, f"render duration not measured ({claimed_basis}) — the <60s claimed-Short rule is unverifiable")
    elif sync.render_seconds >= CLAIMED_SHORT_LIMIT_SECONDS:
        add(
            "claimed_short_duration", False,
            f"render {sync.render_seconds:.2f}s >= {CLAIMED_SHORT_LIMIT_SECONDS:.0f}s with possibly-claimed "
            "material — a claimed Short over 1 minute is BLOCKED, not just claimed",
        )
    else:
        add("claimed_short_duration", True, f"render {sync.render_seconds:.2f}s < 60s ({claimed_basis})")

    # 5 — No excluded categories (the checklist item). Lane *discipline* —
    # which of the declared lanes to produce — is the producing flow's
    # policy, not a compliance block, so an undeclared lane is noted, not
    # failed; an excluded one always fails.
    declared = " ".join(
        part for part in (inp.lane, inp.format_name, inp.category) if part
    ).casefold()
    token_hits = [token for token in EXCLUDED_TOKENS if token in declared]
    if inp.lane in EXCLUDED_LANES:
        add("excluded_categories", False, f"lane {inp.lane!r} is an excluded category (reused-content policy / Content ID)")
    elif token_hits:
        add("excluded_categories", False, f"declared lane/format/category {declared!r} contains excluded token(s) {token_hits}")
    elif inp.lane in CONTENT_LANES:
        add("excluded_categories", True, f"lane {inp.lane!r}; no excluded category tokens in the declared format")
    else:
        add(
            "excluded_categories", True,
            f"lane {inp.lane!r} is not an excluded category (outside the declared "
            "content lanes — lane discipline is the producing flow's responsibility)",
        )

    # 6 — No financial advice (lane label AND script content).
    advice_hits = find_finance_advice(inp.script)
    if inp.lane == "finance_advice":
        add("finance_advice", False, "lane 'finance_advice' — financial advice is not a permitted lane (money content is stories only)")
    elif advice_hits:
        add(
            "finance_advice", False,
            "prescriptive advice markers in the script: "
            + "; ".join(f"{hit['pattern']} ({hit['matched_text']!r})" for hit in advice_hits),
        )
    else:
        add("finance_advice", True, "no prescriptive advice markers in the script")

    # 7 — Attribution present in the upload metadata.
    add(
        "attribution_present",
        bool(inp.attribution_included),
        "attribution block (author, licence, source URL) in the description"
        if inp.attribution_included
        else "no attribution block recorded for the upload metadata",
    )

    # 8 — Language / targeting.
    add(
        "language_targeting",
        inp.language == "en",
        "English, global audience" if inp.language == "en"
        else f"language {inp.language!r} — the channel publishes in English for a global audience",
    )

    # 9 — Declared format recorded (no template-identical mass volume).
    add(
        "declared_format",
        bool(str(inp.format_name or "").strip()),
        f"format {inp.format_name!r}" if inp.format_name
        else "no declared format — template-identical volume risks 'inauthentic content' demonetisation",
    )

    blocking = [check["check"] for check in checks if check["status"] != "pass"]
    return GateVerdict(
        passed=not blocking,
        checks=checks,
        blocking_failures=blocking,
        evaluated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def assert_ready_to_upload(verdict: GateVerdict) -> None:
    """The gate as a hard precondition: raise unless the verdict passed."""
    if not verdict.passed:
        details = "; ".join(
            f"{check['check']}: {check['detail']}"
            for check in verdict.checks
            if check["status"] != "pass"
        )
        raise ComplianceGateError(
            f"compliance gate blocks ready-to-upload — failed checks: {details}"
        )
