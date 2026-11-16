"""Spoken-English practice engine (TASK-IG2-VOI-01, IG cluster #111).

Pattern: the PeerUp-style reel (IG DeIyWtZs9uv, sweep crew-01) — the
learner says or types one sentence, and the tutor answers with the
corrected sentence, an error label ("Error: Sentence structure and
clarity." in the demo) and a short tip, then the conversation moves on.

This module is the deterministic core of FRIDAY's practice mode. It
runs fully offline on the fleet (no new service, no paid API): a set
of precise, high-confidence rules for the errors Indian-English
learners hit most — subject–verb agreement, past-tense after a past
time marker, a/an, double comparatives, redundant prepositions,
capitalisation and end punctuation. Every rule only fires on a shape
it can correct with certainty; anything else is reported as clean
rather than "corrected" into a guess. The chat/voice layer may enrich
a turn with the LLM, but this engine is the testable ground truth and
the offline fallback.

A session tracks attempts, clean sentences and per-label counts so
FRIDAY can say, honestly, what the learner keeps tripping on.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Error labels (PeerUp shows one headline label per sentence; a turn
# here can carry several corrections, each with its own label + tip).
LABEL_AGREEMENT = "Subject–verb agreement"
LABEL_TENSE = "Verb tense"
LABEL_ARTICLE = "Article (a/an)"
LABEL_COMPARATIVE = "Double comparative"
LABEL_PREPOSITION = "Unnecessary preposition"
LABEL_CAPITALISATION = "Capitalisation"
LABEL_PUNCTUATION = "End punctuation"
LABEL_STRUCTURE = "Sentence structure and clarity"


@dataclass
class Correction:
    """One applied fix inside a sentence."""

    label: str
    tip: str
    before: str
    after: str

    def to_dict(self) -> dict[str, str]:
        return {"label": self.label, "tip": self.tip, "before": self.before, "after": self.after}


@dataclass
class SentenceFeedback:
    """The per-sentence answer the practice mode returns."""

    original: str
    corrected: str
    corrections: list[Correction] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return not self.corrections

    @property
    def headline_label(self) -> str | None:
        """The first (headline) error label, PeerUp-style; None if clean."""
        return self.corrections[0].label if self.corrections else None

    def render(self) -> str:
        """Chat/voice-friendly rendering: correction, label, tip."""
        if self.is_clean:
            return f"✓ Correct: \"{self.corrected}\" — clean sentence, nicely said."
        lines = [f"Corrected: \"{self.corrected}\""]
        for fix in self.corrections:
            lines.append(f"Error: {fix.label}. {fix.tip} (\"{fix.before}\" → \"{fix.after}\")")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "original": self.original,
            "corrected": self.corrected,
            "is_clean": self.is_clean,
            "headline_label": self.headline_label,
            "corrections": [c.to_dict() for c in self.corrections],
        }


# --- Rule tables -----------------------------------------------------

_THIRD_PERSON = {"he", "she", "it"}
# subject -> (wrong present form, right present form) for "don't" class.
_AGREEMENT_DONT = {"he": "doesn't", "she": "doesn't", "it": "doesn't"}
_AGREEMENT_DO = {"i": "don't", "you": "don't", "we": "don't", "they": "don't"}

# Irregular past forms for the past-marker rule (yesterday, last night…).
_IRREGULAR_PAST = {
    "go": "went", "come": "came", "see": "saw", "buy": "bought",
    "eat": "ate", "drink": "drank", "meet": "met", "take": "took",
    "give": "gave", "make": "made", "say": "said", "tell": "told",
    "write": "wrote", "read": "read", "run": "ran", "bring": "brought",
    "teach": "taught", "think": "thought", "speak": "spoke", "drive": "drove",
    "forget": "forgot", "leave": "left", "find": "found", "get": "got",
    "do": "did", "have": "had", "pay": "paid", "send": "sent",
    "sleep": "slept", "win": "won", "lose": "lost", "begin": "began",
}
_PAST_MARKERS = (
    "yesterday", "last night", "last week", "last month", "last year",
    "last monday", "last tuesday", "last wednesday", "last thursday",
    "last friday", "last saturday", "last sunday",
)

_DOUBLE_COMPARATIVES = {
    "more better": "better", "more easier": "easier", "more faster": "faster",
    "more bigger": "bigger", "more happier": "happier", "more cheaper": "cheaper",
    "more simpler": "simpler", "more worse": "worse",
}

# verb + redundant preposition -> verb alone ("discuss about X").
_REDUNDANT_PREPOSITIONS = {
    "discuss about": "discuss", "describe about": "describe",
    "explain about": "explain", "mention about": "mention",
    "reach to": "reach", "enter into": "enter",
    "return back": "return", "repeat again": "repeat",
}

_VOWELS = set("aeiou")


def _apply(text: str, pattern: str, repl, label: str, tip: str,
           corrections: list[Correction], flags: int = re.IGNORECASE) -> str:
    """Apply one regex rule once, recording the fix it made."""
    match = re.search(pattern, text, flags)
    if not match:
        return text
    after = repl(match) if callable(repl) else match.expand(repl)
    new_text = text[: match.start()] + after + text[match.end():]
    if new_text != text:
        corrections.append(Correction(label=label, tip=tip,
                                      before=match.group(0), after=after))
        return new_text
    return text


def correct_sentence(sentence: str) -> SentenceFeedback:
    """Return per-sentence feedback: corrected text + labelled fixes.

    Rules fire only on shapes they can correct with certainty. A
    sentence no rule touches is reported clean — never rewritten.
    """
    original = (sentence or "").strip()
    corrections: list[Correction] = []
    if not original:
        return SentenceFeedback(original=original, corrected=original, corrections=[
            Correction(label=LABEL_STRUCTURE,
                       tip="Say or type one full sentence and I will check it.",
                       before="", after=""),
        ])

    text = original

    # Double comparatives: "more better" -> "better".
    for wrong, right in _DOUBLE_COMPARATIVES.items():
        pattern = rf"\b{re.escape(wrong)}\b"
        if re.search(pattern, text, re.IGNORECASE):
            text = _apply(text, pattern,
                          lambda m, r=right: r if m.group(0)[0].islower() else r.capitalize(),
                          LABEL_COMPARATIVE,
                          "Comparatives like 'better' already carry the comparison — 'more' is not needed.",
                          corrections)

    # Redundant prepositions: "discuss about the plan" -> "discuss the plan".
    for wrong, right in _REDUNDANT_PREPOSITIONS.items():
        pattern = rf"\b{re.escape(wrong)}\b"
        if re.search(pattern, text, re.IGNORECASE):
            text = _apply(text, pattern,
                          lambda m, r=right: r if m.group(0)[0].islower() else r.capitalize(),
                          LABEL_PREPOSITION,
                          f"'{right.capitalize()}' already includes that meaning — the extra word is dropped in natural English.",
                          corrections)

    # Subject–verb agreement: "He don't …" -> "He doesn't …";
    # "They doesn't …" -> "They don't …".
    def _dont_repl(match: re.Match) -> str:
        subject = match.group(1)
        fixed = _AGREEMENT_DONT[subject.lower()]
        return f"{subject} {fixed}"

    text = _apply(text, r"\b(he|she|it)\s+don't\b", _dont_repl,
                  LABEL_AGREEMENT,
                  "With he/she/it, 'don't' becomes 'doesn't'.",
                  corrections)

    def _do_repl(match: re.Match) -> str:
        subject = match.group(1)
        fixed = _AGREEMENT_DO[subject.lower()]
        return f"{subject} {fixed}"

    text = _apply(text, r"\b(i|you|we|they)\s+doesn't\b", _do_repl,
                  LABEL_AGREEMENT,
                  "With I/you/we/they, 'doesn't' becomes 'don't'.",
                  corrections)

    # "I am agree" -> "I agree" (agree is a verb, not an adjective).
    text = _apply(text, r"\b(i|you|we|they|he|she|it)\s+(?:am|are|is)\s+agree\b",
                  lambda m: f"{m.group(1)} agree",
                  LABEL_STRUCTURE,
                  "'Agree' is a verb, so it stands on its own: 'I agree', not 'I am agree'.",
                  corrections)

    # Past tense after a past time marker: "Yesterday I go …" -> "went".
    lowered = text.lower()
    if any(marker in lowered for marker in _PAST_MARKERS):
        for base, past in _IRREGULAR_PAST.items():
            pattern = rf"\b{base}\b"
            match = re.search(pattern, text, re.IGNORECASE)
            if match and match.group(0).lower() == base:
                replacement = past.capitalize() if match.group(0)[0].isupper() else past
                text = _apply(text, pattern, lambda m, r=replacement: r,
                              LABEL_TENSE,
                              f"A past time marker ('yesterday', 'last night'… ) needs the past form: '{base}' → '{past}'.",
                              corrections)
                break  # one tense fix per sentence keeps feedback focused

    # a/an: "a apple" -> "an apple"; "an university" stays (u = /juː/
    # consonant sound) — only the vowel-letter rule is applied, and
    # only before a vowel letter, where it is unambiguous.
    def _article_repl(match: re.Match) -> str:
        article, word = match.group(1), match.group(2)
        fixed = "an" if article.islower() else "An"
        return f"{fixed} {word}"

    # Guards: vowel-letter words with a consonant sound ("a university",
    # "a European") and silent-h words ("an hour", "an honest man")
    # are already correct and must never be "fixed".
    text = _apply(text, r"\b(a)\s+(?!(?:uni|use|usu|eur|one))([aeiouAEIOU]\w+)", _article_repl,
                  LABEL_ARTICLE,
                  "Use 'an' before a vowel sound: 'an apple', 'an hour'.",
                  corrections)
    text = _apply(text, r"\b(an)\s+(?!(?:hour|honest|honor|honour|heir))([bcdfghjklmnpqrstvwxyzBCDFGHJKLMNPQRSTVWXYZ]\w+)",
                  lambda m: f"{'a' if m.group(1).islower() else 'A'} {m.group(2)}",
                  LABEL_ARTICLE,
                  "Use 'a' before a consonant sound: 'a book', 'a car'.",
                  corrections)

    # Capitalisation: sentence-initial letter and standalone "i".
    if text and text[0].islower():
        fixed = text[0].upper() + text[1:]
        corrections.append(Correction(label=LABEL_CAPITALISATION,
                                      tip="Sentences start with a capital letter.",
                                      before=text[0], after=fixed[0]))
        text = fixed
    text = _apply(text, r"(?<!\w)i(?!\w)", lambda m: "I",
                  LABEL_CAPITALISATION,
                  "The pronoun 'I' is always capitalised.",
                  corrections, flags=0)

    # End punctuation: a spoken-style sentence still gets its full stop
    # in the written correction, so the learner sees the complete shape.
    if text and text[-1] not in ".!?":
        corrections.append(Correction(label=LABEL_PUNCTUATION,
                                      tip="Finish the sentence with a full stop, question mark or exclamation mark.",
                                      before=text[-1], after=text[-1] + "."))
        text = text + "."

    return SentenceFeedback(original=original, corrected=text, corrections=corrections)


# --- Session ---------------------------------------------------------

# Starter prompts FRIDAY can offer when the learner wants a sentence
# to try (kept small and everyday on purpose).
PRACTICE_PROMPTS = [
    "Tell me what you did yesterday.",
    "Describe your journey to work or college today.",
    "Tell me about your favourite food and why you like it.",
    "What are your plans for this weekend?",
    "Describe the last movie you watched.",
]


@dataclass
class EnglishPracticeSession:
    """One learner's practice run: turns, score and recurring labels."""

    attempts: int = 0
    clean: int = 0
    label_counts: dict[str, int] = field(default_factory=dict)
    history: list[SentenceFeedback] = field(default_factory=list)

    def practice(self, sentence: str) -> SentenceFeedback:
        feedback = correct_sentence(sentence)
        # An empty input is guidance, not an attempt.
        if feedback.original:
            self.attempts += 1
            if feedback.is_clean:
                self.clean += 1
            for fix in feedback.corrections:
                self.label_counts[fix.label] = self.label_counts.get(fix.label, 0) + 1
            self.history.append(feedback)
        return feedback

    def next_prompt(self) -> str:
        return PRACTICE_PROMPTS[self.attempts % len(PRACTICE_PROMPTS)]

    def summary(self) -> dict:
        top = sorted(self.label_counts.items(), key=lambda kv: (-kv[1], kv[0]))
        return {
            "attempts": self.attempts,
            "clean": self.clean,
            "accuracy": round(self.clean / self.attempts, 3) if self.attempts else None,
            "top_error_labels": [{"label": label, "count": count} for label, count in top[:3]],
        }

    def summary_text(self) -> str:
        s = self.summary()
        if not s["attempts"]:
            return "No practice sentences yet — say one and I will check it."
        text = (f"Practice so far: {s['clean']}/{s['attempts']} sentences clean "
                f"({round((s['accuracy'] or 0) * 100)}%).")
        if s["top_error_labels"]:
            focus = ", ".join(f"{e['label']} ×{e['count']}" for e in s["top_error_labels"])
            text += f" Most frequent: {focus}."
        return text
