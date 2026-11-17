"""Fail-closed quality gates for the viral autopilot path (TASK-VYR-014).

Why this module exists — the owner's full-watch of the channel's output
(2026-11-17) graded six uploads BROKEN/WEAK with zero GOOD, all from one
family of causes: the package (title, narration, captions, description) was
generated from the source's title and a best-effort free-text scene note, and
nothing ever checked the words against the footage. The shipped defects:

* job 741: narration calls a light-skinned, light-brown-haired woman
  "a black woman" and says the man's eyes are closed while they are open;
* job 761: "pink-haired woman" (a pink SHIRT), a "nighttime panic" title over
  a daylight scene of a smiling, standing man the narration says "sits";
* job 683: narration ends mid-sentence ("Now again, about") over footage it
  does not describe;
* job 721: the title promises a "Switch Shock" that never happens and the
  narration describes the same action twice;
* job 701: two static shots, nothing happens, and the description asks
  viewers to "Drop your answer below!" to a question nobody asked.

The gates here are deterministic and footage-first. They consume the
structured vision record produced by
:func:`app.services.scene_analysis.analyze_scene` — per-beat setting,
time of day, subjects (hair, clothing, posture, action, emotion, eyes),
objects and summaries — and reject any package whose checkable claims are
not in that record. Race/skin identity is never in the record by design, so
any identity claim in the copy is unverifiable and rejected outright.

Every gate returns a list of :class:`Violation`; an empty list is a pass.
``produce_viral_short`` retries the editorial once with the violations as
feedback and then skips the candidate — a bad video is never shipped to
make a quota.
"""
from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger("vyralx.viral_quality")


# --------------------------------------------------------------------------- #
# violations
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Violation:
    kind: str
    field: str
    detail: str

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.field}:{self.kind}: {self.detail}"


# --------------------------------------------------------------------------- #
# lexicons
# --------------------------------------------------------------------------- #
_COLOUR_ALIASES = {
    "gray": "grey", "golden": "gold", "brunette": "brown", "auburn": "brown",
    "ginger": "red", "blond": "blonde", "silver": "grey", "maroon": "red",
    "crimson": "red", "scarlet": "red", "navy": "blue", "turquoise": "teal",
    "violet": "purple", "magenta": "pink", "cyan": "blue", "beige": "brown",
    "khaki": "brown", "olive": "green", "coral": "orange", "lavender": "purple",
    "burgundy": "red", "amber": "orange", "emerald": "green", "ruby": "red",
    "sapphire": "blue", "charcoal": "grey", "ivory": "white", "lilac": "purple",
    "peach": "orange", "mint": "green", "rust": "orange",
}
COLOURS = {
    "black", "white", "red", "pink", "blue", "green", "yellow", "orange",
    "purple", "brown", "grey", "gold", "teal", "blonde",
} | set(_COLOUR_ALIASES)

# Colours that describe a PERSON when placed next to a person noun are read
# as skin/identity claims. The vision record never records identity, so the
# claim can never be verified — reject it and let the retry describe the
# person's hair or clothing instead (both are recorded and checkable).
_IDENTITY_COLOURS = {"black", "white", "brown"}
_IDENTITY_WORDS = {
    "asian", "african", "european", "latino", "latina", "hispanic", "arab",
    "indian", "chinese", "japanese", "korean", "american", "british",
    "dark-skinned", "light-skinned", "fair-skinned", "dark", "fair",
}
_PERSON_NOUNS = {
    "woman", "man", "girl", "boy", "lady", "guy", "person", "people",
    "women", "men", "girls", "boys", "ladies", "guys", "persons",
}
_HAIR_WORDS = {"blonde", "brunette", "ginger", "auburn", "redhead", "blond"}

_GARMENTS = {
    "shirt", "t-shirt", "tee", "top", "dress", "skirt", "pants", "trousers",
    "shorts", "jeans", "jacket", "coat", "sweater", "hoodie", "hat", "cap",
    "gloves", "glove", "robe", "kimono", "uniform", "suit", "blouse",
    "sari", "scarf", "shoes", "sneakers", "boots", "apron", "jersey",
    "gown", "vest", "tie", "swimsuit", "bikini", "leggings", "blazer",
    "cardigan", "overalls", "pajamas", "pyjamas", "socks", "heels", "crown",
}

_POSTURE_FORMS = {
    "sitting": {"sit", "sits", "sitting", "seated", "sat"},
    "standing": {"stand", "stands", "standing", "stood"},
    "lying": {"lie", "lies", "lying", "lay", "laid", "lying down"},
    "kneeling": {"kneel", "kneels", "kneeling", "knelt"},
    "crouching": {"crouch", "crouches", "crouching", "crouched"},
    "leaning": {"lean", "leans", "leaning", "leaned", "leant"},
}

_EMOTION_FORMS = {
    "laughing": {"laugh", "laughs", "laughing", "laughed", "giggling", "giggles", "chuckling"},
    "smiling": {"smile", "smiles", "smiling", "smiled", "grin", "grins", "grinning", "smirk"},
    "shocked": {"shock", "shocked", "stunned", "surprised", "surprise", "gasping", "gasp", "amazed", "astonished"},
    "scared": {"scared", "terrified", "frightened", "afraid", "panic", "panicking", "panicked", "fear"},
    "crying": {"cry", "cries", "crying", "cried", "tears", "sobbing", "weeping"},
    "angry": {"angry", "furious", "mad", "shouting", "yelling", "screaming", "scream"},
    "embarrassed": {"embarrassed", "embarrassing", "ashamed", "awkward"},
    "confused": {"confused", "confusing", "puzzled", "bewildered"},
    "calm": {"calm", "relaxed", "serious", "unimpressed", "deadpan", "bored"},
    "excited": {"excited", "thrilled", "celebrating", "cheering"},
    "happy": {"happy", "joyful", "cheerful", "delighted"},
    "sad": {"sad", "unhappy", "miserable", "disappointed"},
}
_EMOTION_CANON = {form: canon for canon, forms in _EMOTION_FORMS.items() for form in forms}
_POSTURE_CANON = {form: canon for canon, forms in _POSTURE_FORMS.items() for form in forms}

_NIGHT_WORDS = {"night", "nighttime", "midnight", "evening", "dusk", "sunset", "moonlight"}
_NIGHT_PHRASES = ("after dark", "in the dark")
_DAY_WORDS = {"daylight", "daytime", "morning", "sunrise", "sunny", "midday", "noon", "afternoon"}

_STOPWORDS = {
    "that", "this", "with", "from", "into", "over", "then", "they", "them",
    "their", "while", "when", "what", "have", "been", "were", "will", "your",
    "about", "after", "before", "because", "there", "here", "just", "like",
    "more", "most", "some", "very", "also", "onto", "than", "only", "even",
    "still", "much", "many", "such", "each", "other", "both", "same", "does",
    "doing", "make", "made", "gets", "goes", "going", "come", "comes", "says",
    "said", "looks", "looking", "shows", "showing", "starts", "started",
    "watch", "video", "clip", "moment", "second", "first", "final", "whole",
}

_FILLER_CLOSERS = (
    re.compile(r"\bis legendary\b", re.I),
    re.compile(r"\bleaving (viewers|you|us) wondering\b", re.I),
    re.compile(r"\bwhat (will )?happens next\b", re.I),
    re.compile(r"\bsays it all\b", re.I),
)


def _canon_colour(word: str) -> str:
    return _COLOUR_ALIASES.get(word, word)


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z]+(?:-[a-z]+)?", str(text or "").lower())


def content_words(text: str) -> set[str]:
    """Significant words (the repo's existing scene-match vocabulary rule)."""
    return {w for w in re.findall(r"[a-z]{4,}", str(text or "").lower())} - _STOPWORDS


def split_sentences(text: str) -> list[str]:
    cleaned = " ".join(str(text or "").split())
    if not cleaned:
        return []
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", cleaned) if part.strip()]


# --------------------------------------------------------------------------- #
# sanitizer — bracket tags like "[music]" must never reach the voice or the
# captions (job 761 shipped one baked into a mid-sentence caption).
# --------------------------------------------------------------------------- #
_BRACKET_TAG = re.compile(r"\[[^\]\[]{1,40}\]")
_ANGLE_TAG = re.compile(r"<[^>]{1,40}>")


def sanitize_spoken_text(text: str) -> str:
    cleaned = _BRACKET_TAG.sub(" ", str(text or ""))
    cleaned = _ANGLE_TAG.sub(" ", cleaned)
    return " ".join(cleaned.split())


# --------------------------------------------------------------------------- #
# vision-record vocabulary
# --------------------------------------------------------------------------- #
@dataclass
class RecordVocabulary:
    colours: set[str] = field(default_factory=set)
    hair_colours: set[str] = field(default_factory=set)
    garment_pairs: set[tuple[str, str]] = field(default_factory=set)
    postures: set[str] = field(default_factory=set)
    emotions: set[str] = field(default_factory=set)
    times_of_day: set[str] = field(default_factory=set)
    beat_times: list[str] = field(default_factory=list)
    eyes: set[str] = field(default_factory=set)
    nouns: dict[str, int] = field(default_factory=dict)
    beat_nouns: list[set[str]] = field(default_factory=list)
    object_nouns: set[str] = field(default_factory=set)


def _record_strings(record: dict[str, Any]) -> list[str]:
    texts: list[str] = [str(record.get("event_arc") or "")]
    for beat in record.get("beats") or []:
        if not isinstance(beat, dict):
            continue
        texts.append(str(beat.get("setting") or ""))
        texts.append(str(beat.get("summary") or ""))
        texts.extend(str(item) for item in beat.get("objects") or [])
        for subject in beat.get("subjects") or []:
            if isinstance(subject, dict):
                texts.extend(str(subject.get(key) or "") for key in
                             ("hair", "clothing", "posture", "action", "emotion"))
    return texts


def record_vocabulary(record: dict[str, Any]) -> RecordVocabulary:
    vocab = RecordVocabulary()
    beats = [b for b in (record.get("beats") or []) if isinstance(b, dict)]
    for beat in beats:
        beat_words: set[str] = set()
        time_value = str(beat.get("time_of_day") or "unknown").strip().lower()
        if time_value not in {"day", "night", "indoor", "unknown"}:
            time_value = "unknown"
        vocab.times_of_day.add(time_value)
        vocab.beat_times.append(time_value)
        for item in beat.get("objects") or []:
            vocab.object_nouns |= content_words(str(item))
        beat_texts = [
            str(beat.get("setting") or ""), str(beat.get("summary") or ""),
            *[str(item) for item in beat.get("objects") or []],
        ]
        for subject in beat.get("subjects") or []:
            if not isinstance(subject, dict):
                continue
            hair = str(subject.get("hair") or "")
            clothing = str(subject.get("clothing") or "")
            posture = str(subject.get("posture") or "")
            action = str(subject.get("action") or "")
            emotion = str(subject.get("emotion") or "")
            eyes = str(subject.get("eyes") or "unknown").strip().lower()
            if eyes in {"open", "closed"}:
                vocab.eyes.add(eyes)
            for token in _tokens(hair):
                canon = _canon_colour(token)
                if canon in COLOURS:
                    vocab.hair_colours.add(canon)
                if token in _HAIR_WORDS:
                    vocab.hair_colours.add(_canon_colour(token))
            clothing_tokens = _tokens(clothing)
            clothing_colours = {_canon_colour(t) for t in clothing_tokens} & COLOURS
            for token in clothing_tokens:
                if token in _GARMENTS:
                    for colour in clothing_colours:
                        vocab.garment_pairs.add((colour, token))
            for token in _tokens(f"{posture} {action}"):
                if token in _POSTURE_CANON:
                    vocab.postures.add(_POSTURE_CANON[token])
            for token in _tokens(f"{emotion} {action} {beat.get('summary') or ''}"):
                if token in _EMOTION_CANON:
                    vocab.emotions.add(_EMOTION_CANON[token])
            beat_texts.extend([hair, clothing, posture, action, emotion])
        for text in beat_texts:
            beat_words |= content_words(text)
        vocab.beat_nouns.append(beat_words)
    for text in _record_strings(record):
        for token in _tokens(text):
            canon = _canon_colour(token)
            if canon in COLOURS:
                vocab.colours.add(canon)
        for word in content_words(text):
            vocab.nouns[word] = vocab.nouns.get(word, 0) + 1
    return vocab


# --------------------------------------------------------------------------- #
# consistency — every checkable claim must be in the vision record
# --------------------------------------------------------------------------- #
def _check_claims(text: str, vocab: RecordVocabulary, field_name: str) -> list[Violation]:
    violations: list[Violation] = []
    lowered = f" {str(text or '').lower()} "
    tokens = _tokens(text)

    def add(kind: str, detail: str) -> None:
        violation = Violation(kind, field_name, detail)
        if violation not in violations:
            violations.append(violation)

    # Identity / race claims: never recorded, therefore never verifiable.
    for index, token in enumerate(tokens):
        following = tokens[index + 1:index + 3]
        if token in _IDENTITY_COLOURS and any(t in _PERSON_NOUNS for t in following):
            add("unverifiable_identity",
                f"'{token} {following[0]}' states a skin/identity fact the footage record never holds")
        if token in {"dark", "fair", "pale", "light"} and any(
            t in _PERSON_NOUNS for t in following
        ):
            add("unverifiable_identity",
                f"'{token} {following[0]}' reads as a skin-tone claim the footage record never holds")
        if token in _IDENTITY_WORDS and token not in {"dark", "fair"}:
            add("unverifiable_identity", f"'{token}' is an identity label the footage record never holds")
        if token in _HAIR_WORDS:
            if _canon_colour(token) not in vocab.hair_colours:
                add("unverified_hair", f"'{token}' describes hair the record does not show")

    # Hair colour pairings: "<colour> hair", "<colour>-haired".
    for match in re.finditer(r"([a-z]+)[ -]haired", lowered):
        colour = _canon_colour(match.group(1))
        if colour not in vocab.hair_colours:
            add("unverified_hair", f"'{match.group(0).strip()}' — recorded hair is {sorted(vocab.hair_colours) or 'not visible'}")
    for index, token in enumerate(tokens):
        if token == "hair" and index > 0:
            colour = _canon_colour(tokens[index - 1])
            if tokens[index - 1] in COLOURS and colour not in vocab.hair_colours:
                add("unverified_hair", f"'{tokens[index - 1]} hair' — recorded hair is {sorted(vocab.hair_colours) or 'not visible'}")

    # Garment colour pairings + unseen colours.
    for index, token in enumerate(tokens):
        canon = _canon_colour(token)
        if token not in COLOURS:
            continue
        window = tokens[index + 1:index + 3]
        garment = next((t for t in window if t in _GARMENTS), None)
        if garment and (canon, garment) not in vocab.garment_pairs:
            add("unverified_garment_colour",
                f"'{token} {garment}' is not in the record (recorded: "
                f"{sorted(f'{c} {g}' for c, g in vocab.garment_pairs) or 'none'})")
        if canon not in vocab.colours:
            add("unseen_colour", f"colour '{token}' appears nowhere in the footage record")

    # Posture and emotion claims must be recorded somewhere in the clip.
    for token in tokens:
        canon_posture = _POSTURE_CANON.get(token)
        if canon_posture and canon_posture not in vocab.postures:
            add("unverified_posture", f"'{token}' — recorded postures: {sorted(vocab.postures) or 'none'}")
        canon_emotion = _EMOTION_CANON.get(token)
        if canon_emotion and canon_emotion not in vocab.emotions:
            add("unverified_emotion", f"'{token}' — recorded emotions/actions: {sorted(vocab.emotions) or 'none'}")

    # Eye state: only claimable when the record actually resolved it.
    for state in ("closed", "open"):
        if re.search(rf"\beyes?\s+(are\s+)?{state}\b", lowered) or re.search(rf"\b{state}\s+eyes?\b", lowered):
            if state not in vocab.eyes:
                add("unverified_eyes", f"'eyes {state}' — the record resolved eyes as {sorted(vocab.eyes) or 'unknown'}")

    return violations


def _check_time_claims(
    text: str, times_of_day: set[str], field_name: str
) -> list[Violation]:
    """A time-of-day claim needs a confirming beat and no contradicting one."""
    violations: list[Violation] = []
    lowered = f" {str(text or '').lower()} "
    tokens = _tokens(text)
    claimed: set[str] = set()
    if any(word in tokens for word in _NIGHT_WORDS) or any(p in lowered for p in _NIGHT_PHRASES):
        claimed.add("night")
    if any(word in tokens for word in _DAY_WORDS):
        claimed.add("day")
    for family in claimed:
        opposite = "day" if family == "night" else "night"
        if opposite in times_of_day:
            violations.append(Violation(
                "time_of_day_contradiction", field_name,
                f"copy claims {family} but the footage there is recorded as {opposite}",
            ))
        elif family not in times_of_day:
            violations.append(Violation(
                "time_of_day_unverified", field_name,
                f"copy claims {family} but no beat is recorded as {family} "
                f"(beats: {sorted(times_of_day)})",
            ))
    return violations


def _sentence_beat_groups(sentences: list[str], beat_count: int) -> list[list[str]]:
    """Distribute sentences over beats exactly as the renderer times them."""
    groups: list[list[str]] = [[] for _ in range(max(1, beat_count))]
    if not sentences:
        return groups
    base, extra = divmod(len(sentences), len(groups))
    cursor = 0
    for index in range(len(groups)):
        take = base + (1 if index < extra else 0)
        groups[index] = sentences[cursor:cursor + take]
        cursor += take
    return groups


def check_consistency(
    *,
    commentary: str = "",
    title: str = "",
    description: str = "",
    record: dict[str, Any],
) -> list[Violation]:
    """Claim-check the whole package against the vision record.

    Time-of-day claims in the commentary are checked against the beat each
    sentence narrates (a day scene followed by a night scene may be
    described as both, in order); claims in the title and description must
    hold for the whole clip — job 761's title promised "Nighttime" over a
    video whose first half is bright daylight.
    """
    vocab = record_vocabulary(record)
    def per_beat_time(text: str, field_name: str) -> list[Violation]:
        found: list[Violation] = []
        groups = _sentence_beat_groups(
            split_sentences(text), len(vocab.beat_times) or 3
        )
        for index, group in enumerate(groups):
            if not group:
                continue
            beat_time = (
                vocab.beat_times[index]
                if index < len(vocab.beat_times)
                else "unknown"
            )
            found += _check_time_claims(" ".join(group), {beat_time}, field_name)
        return found

    violations: list[Violation] = []
    if commentary:
        violations += _check_claims(commentary, vocab, "commentary")
        violations += per_beat_time(commentary, "commentary")
    if title:
        violations += _check_claims(title, vocab, "title")
        violations += _check_time_claims(title, vocab.times_of_day, "title")
    if description:
        violations += _check_claims(description, vocab, "description")
        violations += per_beat_time(description, "description")
        violations += _check_description_question(description, vocab)
    return violations


def _check_description_question(description: str, vocab: RecordVocabulary) -> list[Violation]:
    violations: list[Violation] = []
    text = str(description or "")
    lowered = text.lower()
    has_question = "?" in text
    if "drop your answer" in lowered and not has_question:
        violations.append(Violation(
            "cta_without_question", "description",
            "'Drop your answer below!' appears with no question anywhere in the description",
        ))
    if has_question:
        question_text = " ".join(
            part for part in re.split(r"(?<=[.!?])\s+", text) if "?" in part
        )
        if question_text and not (content_words(question_text) & set(vocab.nouns)):
            violations.append(Violation(
                "question_ungrounded", "description",
                "the description's question names nothing that appears in the footage record",
            ))
    return violations


def repair_description_question(description: str, record: dict[str, Any]) -> str:
    """Deterministically repair a description whose only sin is its question.

    Ungrounded question sentences are dropped (they ask about things the
    footage never shows); if no grounded question survives, the record's own
    grounded question is appended; a bare "Drop your answer below!" CTA is
    dropped when no question remains to point at. Factual claims are NEVER
    touched — a description with claim violations must fail the gate, not be
    edited into compliance. Proven necessary by the TASK-VYR-014 staging
    self-test (2026-11-17): the model's second draft was fully grounded and
    failed only on an ungrounded description question plus a long hook —
    discarding grounded packages over packaging mechanics starves a channel
    whose candidate supply is already thin (11 of 12 discoveries carried
    narration). Returns the (possibly unchanged) description.
    """
    text = str(description or "")
    if "?" not in text and "drop your answer" not in text.lower():
        return text
    vocab = record_vocabulary(record)
    kept_lines: list[str] = []
    has_grounded_question = False
    for line in text.split("\n"):
        if not line.strip():
            kept_lines.append("")
            continue
        kept_chunks: list[str] = []
        dropped_question = False
        for chunk in re.split(r"(?<=[.!?])\s+", line):
            piece = chunk.strip()
            if not piece:
                continue
            if "?" in piece:
                if content_words(piece) & set(vocab.nouns):
                    has_grounded_question = True
                    dropped_question = False
                    kept_chunks.append(chunk)
                else:
                    # Ungrounded questions are dropped, never rewritten;
                    # their trailing CTA chunk goes with them.
                    dropped_question = True
                continue
            if dropped_question and "drop your answer" in piece.lower():
                dropped_question = False
                continue
            dropped_question = False
            kept_chunks.append(chunk)
        if kept_chunks:
            kept_lines.append(" ".join(kept_chunks))
    repaired = "\n".join(kept_lines).strip()
    if not has_grounded_question:
        question = grounded_question(record)
        if question:
            repaired = f"{repaired}\n\n{question}" if repaired else question
        else:
            repaired = re.sub(
                r"(?im)^.*drop your answer.*$", "", repaired
            ).strip()
    return repaired


# --------------------------------------------------------------------------- #
# structure — hook, build, payoff; nothing repeated; no filler closers
# --------------------------------------------------------------------------- #
def check_structure(*, commentary: str, record: dict[str, Any]) -> list[Violation]:
    violations: list[Violation] = []
    sentences = split_sentences(commentary)
    if len(sentences) < 3:
        violations.append(Violation(
            "too_few_sentences", "commentary",
            f"script has {len(sentences)} sentence(s); a hook/build/payoff arc needs at least 3",
        ))
        return violations
    if len(sentences) > 7:
        violations.append(Violation(
            "too_many_sentences", "commentary",
            f"script has {len(sentences)} sentences; a Short's narration must stay tight (max 7)",
        ))
    vocab = record_vocabulary(record)
    hook = sentences[0]
    # 18 words ≈ 7.3s at the production TTS rate — still inside beat 1
    # (a third of the clip), still one punchy sentence. Calibrated from 14
    # after the staging self-test (2026-11-17): two independent editorial
    # sessions produced fully grounded, claim-clean packages for a real
    # clip whose ONLY defect was a >14-word hook; a cap that discards
    # grounded packages over 15-18-word opening lines starves the channel
    # without making hooks punchier in any way the footage shows.
    if len(hook.split()) > 18:
        violations.append(Violation(
            "hook_too_long", "commentary",
            f"hook runs {len(hook.split())} words; the opening line must stay tight "
            "enough to land the hook immediately (max 18 words)",
        ))
    if not (content_words(hook) & set(vocab.nouns)):
        violations.append(Violation(
            "hook_ungrounded", "commentary",
            "the hook names nothing from the footage record — it could open any video",
        ))
    word_sets = [content_words(sentence) for sentence in sentences]
    for first in range(len(sentences)):
        for second in range(first + 1, len(sentences)):
            union = word_sets[first] | word_sets[second]
            if not union:
                continue
            shared = word_sets[first] & word_sets[second]
            jaccard = len(shared) / len(union)
            # Job 721's repetition is paraphrased ("reaches up to press the
            # wall switch" / "holds his arm toward the switch"), so plain
            # overlap misses it; two ADJACENT sentences circling the same
            # recorded object with shared wording are the same tell.
            paraphrased_repeat = (
                second == first + 1
                and len(shared & vocab.object_nouns) >= 1
                and len(shared) >= 2
            )
            if jaccard >= 0.55 or paraphrased_repeat:
                violations.append(Violation(
                    "repeated_action", "commentary",
                    f"sentences {first + 1} and {second + 1} describe the same action twice "
                    f"(overlap {jaccard:.2f}): '{sentences[second][:60]}'",
                ))
    payoff = sentences[-1]
    if vocab.beat_nouns:
        overlap = content_words(payoff) & vocab.beat_nouns[-1]
        if len(overlap) < 2:
            violations.append(Violation(
                "payoff_ungrounded", "commentary",
                "the closing line does not land on the final beat's recorded action/objects",
            ))
    for pattern in _FILLER_CLOSERS:
        if pattern.search(payoff):
            violations.append(Violation(
                "filler_closer", "commentary",
                f"closing line is empty filler ('{payoff[:60]}') instead of a payoff",
            ))
            break
    return violations


# --------------------------------------------------------------------------- #
# length fit — the script is sized BEFORE synthesis, and the measured
# narration is verified after it. Job 683 shipped a voice-over that ended
# mid-sentence; both gates together make that unshippable.
# --------------------------------------------------------------------------- #
# edge-tts en-US-GuyNeural at the channel's default rate speaks at roughly
# 150 words/minute; 2.45 words/second with a 0.94 fill factor leaves the
# payoff line room to land before the clip ends.
WORDS_PER_SECOND = 2.45
_FILL_MAX = 0.94
_FILL_MIN = 0.45


def word_budget(duration: float) -> int:
    """Maximum narration words that fit ``duration`` seconds of footage."""
    return max(12, int(max(0.0, float(duration or 0.0)) * WORDS_PER_SECOND * _FILL_MAX))


def check_script_length(*, commentary: str, duration: float) -> list[Violation]:
    violations: list[Violation] = []
    text = " ".join(str(commentary or "").split())
    words = len(text.split()) if text else 0
    budget = word_budget(duration)
    if words > budget:
        violations.append(Violation(
            "script_too_long", "commentary",
            f"script is {words} words; at {WORDS_PER_SECOND} words/sec only {budget} fit "
            f"{float(duration or 0.0):.1f}s — the ending would be cut off",
        ))
    minimum = int(max(0.0, float(duration or 0.0)) * WORDS_PER_SECOND * _FILL_MIN)
    if 0 < words < minimum:
        violations.append(Violation(
            "script_too_short", "commentary",
            f"script is {words} words for a {float(duration or 0.0):.1f}s clip "
            f"(minimum {minimum}); most of the video would play in silence",
        ))
    if text and text[-1] not in ".!?":
        violations.append(Violation(
            "unterminated_script", "commentary",
            "script does not end with sentence-final punctuation — it would be spoken mid-thought",
        ))
    return violations


def evaluate_narration_fit(
    *,
    commentary: str,
    narration_seconds: float,
    duration: float,
    last_sentence_coverage: float | None = None,
) -> list[Violation]:
    """Post-synthesis check on the MEASURED narration (fail closed)."""
    violations: list[Violation] = []
    clip = max(0.0, float(duration or 0.0))
    spoken = max(0.0, float(narration_seconds or 0.0))
    if clip > 0 and spoken > clip * 1.03 + 0.35:
        violations.append(Violation(
            "narration_overruns_clip", "narration",
            f"measured narration is {spoken:.1f}s over a {clip:.1f}s clip; "
            "the render would freeze/stretch footage to chase the voice",
        ))
    if clip > 0 and spoken < clip * 0.5:
        violations.append(Violation(
            "narration_underruns_clip", "narration",
            f"measured narration is {spoken:.1f}s over a {clip:.1f}s clip; "
            "half the video would play without commentary",
        ))
    if last_sentence_coverage is not None and last_sentence_coverage < 0.9:
        violations.append(Violation(
            "final_sentence_truncated", "narration",
            f"only {last_sentence_coverage:.0%} of the final sentence is present in the "
            "finished narration audio — the ending was cut off",
        ))
    return violations


def last_sentence_coverage(
    script: str,
    matched_indexes: set[int] | None,
) -> float | None:
    """Fraction of the final sentence's words actually heard in the audio.

    ``matched_indexes`` comes from the caller's script↔transcript alignment
    (viral_remix aligns Whisper words to the script); when it is unavailable
    the coverage is None and the duration window alone decides.
    """
    sentences = split_sentences(script)
    if not sentences or matched_indexes is None:
        return None
    words_before = sum(len(s.split()) for s in sentences[:-1])
    last_words = len(sentences[-1].split())
    if last_words == 0:
        return None
    heard = sum(1 for index in range(words_before, words_before + last_words)
                if index in matched_indexes)
    return heard / last_words


# --------------------------------------------------------------------------- #
# grounded fallback question — a real question about THIS clip, or no CTA
# --------------------------------------------------------------------------- #
_QUESTION_SKIP_NOUNS = _PERSON_NOUNS | {
    "video", "clip", "moment", "second", "thing", "things", "person",
    "people", "hand", "hands", "face", "head", "eyes", "eye",
}


def grounded_question(record: dict[str, Any]) -> str:
    """Build the description's question from the record's own objects.

    Returns "" when the record holds no concrete noun to ask about — in
    that case the description ships with no 'Drop your answer below!' CTA
    at all (job 701's defect was a CTA pointing at a question never asked).
    """
    vocab = record_vocabulary(record)
    candidates: list[tuple[int, str]] = []
    for beat in record.get("beats") or []:
        if not isinstance(beat, dict):
            continue
        for item in beat.get("objects") or []:
            for word in content_words(str(item)):
                if word not in _QUESTION_SKIP_NOUNS:
                    candidates.append((vocab.nouns.get(word, 0) + 2, word))
        for subject in beat.get("subjects") or []:
            if isinstance(subject, dict):
                for word in content_words(str(subject.get("clothing") or "")):
                    if word not in _QUESTION_SKIP_NOUNS:
                        candidates.append((vocab.nouns.get(word, 0), word))
    if not candidates:
        ranked = sorted(
            ((count, word) for word, count in vocab.nouns.items()
             if word not in _QUESTION_SKIP_NOUNS),
            reverse=True,
        )
        if not ranked:
            return ""
        candidates = ranked[:1]
    noun = max(candidates)[1]
    return f"Did you spot the {noun}?"


# --------------------------------------------------------------------------- #
# event arc — a clip where nothing happens is not a video (job 701).
# Measured with ffmpeg only: downscaled greyscale frames, mean absolute
# difference between consecutive samples. The metric core is pure so it is
# unit-testable without ffmpeg.
# --------------------------------------------------------------------------- #
_FRAME_WIDTH = 96
_FRAME_HEIGHT = 170
_STATIC_EPSILON = 0.004     # below this, two samples are the same picture
_STATIC_MAX_CHANGE = 0.02   # a real event moves the frame more than this
_STATIC_RATIO_LIMIT = 0.85


@dataclass(frozen=True)
class EventArc:
    samples: int
    mean_change: float
    max_change: float
    static_ratio: float
    peak_position: float  # 0..1 through the clip; >0.66 = the peak lands late
    changes: tuple[float, ...] = ()


def frame_change_metrics(frames: list[bytes]) -> EventArc:
    """Mean-absolute-difference arc over equal-sized greyscale frames."""
    usable = [frame for frame in frames if frame]
    if len(usable) < 2:
        return EventArc(len(usable), 0.0, 0.0, 1.0, 0.0, ())
    size = min(len(frame) for frame in usable)
    changes: list[float] = []
    for previous, current in zip(usable, usable[1:]):
        total = 0
        for index in range(size):
            total += abs(current[index] - previous[index])
        changes.append(total / (size * 255.0))
    peak_index = max(range(len(changes)), key=lambda i: changes[i])
    return EventArc(
        samples=len(usable),
        mean_change=round(sum(changes) / len(changes), 5),
        max_change=round(max(changes), 5),
        static_ratio=round(
            sum(1 for change in changes if change < _STATIC_EPSILON) / len(changes), 3
        ),
        peak_position=round((peak_index + 1) / len(changes), 3),
        changes=tuple(round(change, 5) for change in changes),
    )


def measure_event_arc(
    source_path: Path | str,
    duration: float,
    *,
    ffmpeg_bin: str = "ffmpeg",
    samples: int = 10,
) -> EventArc | None:
    """Sample frames across the clip and measure how much ever changes.

    Returns None when measurement itself is impossible (extraction failed);
    None is *not* evidence of a static clip, so the caller logs it and lets
    the vision gate decide.
    """
    source = Path(source_path)
    length = float(duration or 0.0)
    if not source.is_file() or length <= 0:
        return None
    frames: list[bytes] = []
    for index in range(samples):
        at = length * (index + 0.5) / samples
        cmd = [
            ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-nostdin",
            "-ss", f"{at:.2f}", "-i", str(source),
            "-frames:v", "1",
            "-vf", (f"scale={_FRAME_WIDTH}:{_FRAME_HEIGHT}:"
                    "force_original_aspect_ratio=increase,"
                    f"crop={_FRAME_WIDTH}:{_FRAME_HEIGHT},format=gray"),
            "-f", "rawvideo", "-",
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, timeout=60)
        except (subprocess.SubprocessError, OSError) as exc:
            log.warning("Event-arc frame extraction failed at %.1fs: %s", at, exc)
            return None
        if proc.returncode == 0 and len(proc.stdout) == _FRAME_WIDTH * _FRAME_HEIGHT:
            frames.append(proc.stdout)
    if len(frames) < 4:
        log.warning("Event-arc measurement got only %d usable frames", len(frames))
        return None
    return frame_change_metrics(frames)


def arc_gate(arc: EventArc | None) -> tuple[bool, str]:
    """(passes, reason) — static scenes are rejected, late peaks preferred."""
    if arc is None:
        return True, "arc_unmeasured"
    if arc.max_change < _STATIC_MAX_CHANGE:
        return False, "static_scene"
    if arc.static_ratio >= _STATIC_RATIO_LIMIT:
        return False, "static_scene"
    if arc.peak_position >= 0.66:
        return True, "late_peak"
    return True, "eventful"
