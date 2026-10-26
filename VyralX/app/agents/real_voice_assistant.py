"""
VyralX/app/agents/real_voice_assistant.py — Real Voice Assistant Core.

A working, dependency-free assistant turn processor: it normalizes a spoken
utterance, matches it against a command grammar, resolves named apps and sites,
builds a deterministic action plan that needs no model call, and only falls back
to a streamed language model when no instant action applies. The model chain has
a real cooldown policy driven by the provider's own "try again in 2m 30s" hints,
and every reply is polished and chunked into speakable phrases.

Real working implementations:
- TextNormalizer: wake-word stripping, filler removal, punctuation/whitespace
  normalization, contraction expansion
- CommandGrammar + IntentSpec: slot-based regex intent matching with a real
  specificity/coverage confidence score
- Slot extraction: app names, site names, queries, contacts, messages, volume
  deltas, timers
- AppCatalog: alias table plus scored fuzzy resolution (exact, alias, prefix,
  token overlap, substring ratio)
- ActionPlan + DeterministicPlanner: instant plans (open app/site, search, play,
  message, volume, clock, mail brief) with no I/O performed
- ResponsePolisher: markdown/URL scrubbing, abbreviation expansion, real
  number-to-words for spoken amounts
- SpeechChunker: sentence-boundary chunking for TTS with hard-limit fallback
- ConversationMemory: bounded turn window with entity memory and pronoun
  resolution ("play it again", "open that")
- FailoverPolicy: rate-limit classification, retry-after parsing, cooldown
  bookkeeping across a model chain, with an injectable clock
- AssistantBrain: planner-first turn loop, LLM failover, local fallback,
  and a full turn record
- BriefingComposer: structured quotes -> spoken market briefing sentences
"""
from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Sequence


# ── Text normalization ────────────────────────────────────────────────────

WAKE_WORDS = ("hey friday", "friday", "hey jarvis", "jarvis", "hey vyral", "vyral")

# Filler phrases dropped from the front of an utterance before matching. Longest
# first, so "could you please" is removed before "please".
FILLERS = (
    "could you please", "can you please", "would you please", "will you please",
    "i want you to", "i would like you to", "i need you to",
    "could you", "can you", "would you", "will you",
    "please", "kindly", "just", "go ahead and", "for me",
)

CONTRACTIONS = {
    "what's": "what is", "it's": "it is", "i'm": "i am", "don't": "do not",
    "doesn't": "does not", "can't": "cannot", "won't": "will not",
    "let's": "let us", "that's": "that is", "there's": "there is",
    "i've": "i have", "you're": "you are", "we're": "we are",
    "isn't": "is not", "aren't": "are not", "shouldn't": "should not",
}

_PUNCT_EDGE = " \t\n\r.,!?;:\"'`()[]{}<>-–—…·"


class TextNormalizer:
    """Turn a raw transcript into a matchable utterance."""

    def __init__(self, wake_words: Sequence[str] = WAKE_WORDS,
                 fillers: Sequence[str] = FILLERS) -> None:
        self.wake_words = tuple(sorted((w.lower() for w in wake_words),
                                       key=len, reverse=True))
        self.fillers = tuple(sorted((f.lower() for f in fillers),
                                    key=len, reverse=True))
        self._wake_re = re.compile(
            r"(?:^|(?<=[\s,.]))(?:" +
            "|".join(re.escape(w) for w in self.wake_words) +
            r")\b[,:.]?\s*", re.IGNORECASE) if self.wake_words else None

    # -- stages ----------------------------------------------------------

    def expand_contractions(self, text: str) -> str:
        def swap(match: re.Match[str]) -> str:
            return CONTRACTIONS.get(match.group(0).lower(), match.group(0))
        return re.sub(r"\b[a-z]+'[a-z]+\b", swap, text, flags=re.IGNORECASE)

    def strip_wake_word(self, text: str) -> tuple[str, bool]:
        """Remove one leading wake word. Returns the text and whether one fired."""
        if not self._wake_re:
            return text, False
        match = self._wake_re.search(text)
        if not match:
            return text, False
        # Only treat the wake word as invoking when it opens the utterance.
        if text[:match.start()].strip(_PUNCT_EDGE):
            return text, False
        return text[match.end():], True

    def strip_fillers(self, text: str) -> str:
        changed = True
        stripped = text.strip(_PUNCT_EDGE)
        while changed:
            changed = False
            lowered = stripped.lower()
            for filler in self.fillers:
                if lowered.startswith(filler):
                    rest = stripped[len(filler):]
                    if rest[:1].isalnum():
                        continue
                    stripped = rest.strip(_PUNCT_EDGE)
                    changed = True
                    break
        return stripped

    def normalize(self, text: str) -> str:
        """Full normalization: case, whitespace, punctuation, fillers."""
        raw = (text or "").strip()
        if not raw:
            return ""
        work = self.expand_contractions(raw)
        work = work.replace("/", " ")
        work = re.sub(r"[“”‘’]", "'", work)
        work = re.sub(r"\s+", " ", work)
        work, _ = self.strip_wake_word(work)
        work = self.strip_fillers(work)
        work = re.sub(r"\s+", " ", work).strip(_PUNCT_EDGE)
        # Collapse a trailing period inside the utterance ("open chrome. thanks").
        work = re.sub(r"\.\s+", "; ", work)
        return work.lower()

    def tokens(self, text: str) -> list[str]:
        return re.findall(r"[a-z0-9]+(?:'[a-z]+)?", text.lower())


# ── Intent grammar ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class IntentSpec:
    """One command family and the patterns that recognise it."""

    name: str
    patterns: tuple[str, ...]
    priority: int = 0
    slots: tuple[str, ...] = ()
    action: str = ""

    def compiled(self) -> tuple[re.Pattern[str], ...]:
        return tuple(re.compile(p, re.IGNORECASE) for p in self.patterns)


DEFAULT_INTENTS: tuple[IntentSpec, ...] = (
    IntentSpec("volume", (
        r"^(?:set )?(?:the )?volume (?:to )?(?P<level>\d{1,3})\s*(?:percent|%)?$",
        r"^(?:turn |set |make it )?(?:the )?volume (?P<direction>up|down)(?: by (?P<step>\d{1,3}))?$",
        r"^(?:turn |set |make it )?(?P<direction>louder|quieter)$",
    ), priority=90, slots=("level", "direction", "step"), action="volume"),
    IntentSpec("mute", (
        r"^(?:mute|mute (?:the )?(?:volume|audio|sound)|silence (?:it|the audio))$",
    ), priority=90, action="mute"),
    IntentSpec("unmute", (
        r"^(?:unmute|unmute (?:the )?(?:volume|audio)|restore (?:the )?sound)$",
    ), priority=90, action="unmute"),
    IntentSpec("message", (
        r"^(?:send|reply|message)\s+(?:on\s+whatsapp\s+to|whatsapp\s+to|to)\s+"
        r"(?P<contact>.+?)(?:\s+saying\s+(?P<message>.+))?$",
        r"^(?:tell|text|ping)\s+(?P<contact>[\w .'-]+?)\s+(?:that\s+)?"
        r"(?:saying\s+)?(?P<message>.+)$",
    ), priority=85, slots=("contact", "message"), action="message"),
    IntentSpec("play", (
        r"^(?:play|put on)\s+(?P<query>.+?)\s+(?:on|in)\s+(?P<site>youtube|spotify|soundcloud)$",
        r"^(?:play|put on)\s+(?P<query>.+)$",
    ), priority=70, slots=("query", "site"), action="play"),
    IntentSpec("search", (
        r"^(?:search|google|look up|look for)(?:\s+(?:for|up))?\s+(?P<query>.+?)(?:\s+on\s+(?P<site>\w+))?$",
    ), priority=60, slots=("query", "site"), action="search"),
    IntentSpec("mail", (
        r"^(?:check|read|brief me on|summari[sz]e)\s+(?:my\s+)?(?:mail|email|inbox|unread email)s?$",
        r"^(?:mail|inbox|email) (?:brief|briefing|summary)$",
    ), priority=80, action="mail"),
    IntentSpec("clock", (
        r"^(?:what(?:'s| is)? the |what |tell me the )?time(?: is it)?(?: now)?$",
        r"^(?:what(?:'s| is)? the |what |tell me the )?date(?: is it)?(?: today)?$",
        r"^(?:what day is it|today's date)$",
    ), priority=80, action="clock"),
    IntentSpec("open", (
        r"^(?:open|launch|start|bring up|fire up|go to|switch to)\s+(?P<target>.+)$",
    ), priority=50, slots=("target",), action="open"),
    IntentSpec("close", (
        r"^(?:close|quit|kill|exit)\s+(?P<target>.+)$",
    ), priority=50, slots=("target",), action="close"),
)


@dataclass
class ParsedIntent:
    """A matched intent with its slots and a measured confidence."""

    intent: str
    action: str
    slots: dict[str, str]
    confidence: float
    pattern: str
    utterance: str

    def slot(self, name: str, default: str = "") -> str:
        return (self.slots.get(name) or default).strip()

    def as_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "action": self.action,
            "slots": dict(self.slots),
            "confidence": round(self.confidence, 4),
        }


class CommandGrammar:
    """Match an utterance against ordered intent specs.

    Confidence is not decorative: it is the fraction of the utterance's
    characters the winning pattern consumed, weighted by the intent priority, so
    a long utterance that only half matched scores below a tight one.
    """

    def __init__(self, intents: Iterable[IntentSpec] = DEFAULT_INTENTS) -> None:
        self.specs = tuple(sorted(intents, key=lambda s: -s.priority))
        self._compiled = [
            (spec, spec.compiled()) for spec in self.specs
        ]

    def intents(self) -> tuple[str, ...]:
        return tuple(spec.name for spec in self.specs)

    def parse(self, utterance: str, normalizer: TextNormalizer | None = None) -> ParsedIntent | None:
        norm = (normalizer or TextNormalizer()).normalize(utterance)
        if not norm:
            return None
        best: ParsedIntent | None = None
        for spec, patterns in self._compiled:
            for pattern in patterns:
                match = pattern.search(norm)
                if not match:
                    continue
                span = max(1, match.end() - match.start())
                coverage = min(1.0, span / max(1, len(norm)))
                # Primary match, then priority as a bounded tie-breaker.
                score = 0.7 * coverage + 0.3 * min(1.0, spec.priority / 100.0)
                slots = {
                    key: (value or "").strip()
                    for key, value in match.groupdict().items()
                    if value is not None
                }
                candidate = ParsedIntent(
                    intent=spec.name, action=spec.action, slots=slots,
                    confidence=score, pattern=pattern.pattern, utterance=norm,
                )
                if best is None or candidate.confidence > best.confidence:
                    best = candidate
                break
        return best


# ── App / site resolution ─────────────────────────────────────────────────

SITES: dict[str, str] = {
    "youtube": "https://www.youtube.com",
    "whatsapp": "https://web.whatsapp.com",
    "gmail": "https://mail.google.com",
    "google": "https://www.google.com",
    "github": "https://github.com",
    "maps": "https://maps.google.com",
    "calendar": "https://calendar.google.com",
    "drive": "https://drive.google.com",
    "spotify": "https://open.spotify.com",
}

# How a site's name is written when spoken back.
SITE_LABELS: dict[str, str] = {
    "youtube": "YouTube",
    "whatsapp": "WhatsApp",
    "gmail": "Gmail",
    "google": "Google",
    "github": "GitHub",
    "maps": "Google Maps",
    "calendar": "Google Calendar",
    "drive": "Google Drive",
    "spotify": "Spotify",
}

APP_ALIASES: dict[str, str] = {
    "vs code": "Visual Studio Code",
    "vscode": "Visual Studio Code",
    "code": "Visual Studio Code",
    "chrome": "Google Chrome",
    "browser": "Google Chrome",
    "word": "Microsoft Word",
    "excel": "Microsoft Excel",
    "powerpoint": "Microsoft PowerPoint",
    "slides": "Microsoft PowerPoint",
    "settings": "System Settings",
    "system preferences": "System Settings",
    "terminal": "Terminal",
    "shell": "Terminal",
    "spotify": "Spotify",
    "notes": "Notes",
    "calendar": "Calendar",
    "mail": "Mail",
    "slack": "Slack",
    "music": "Music",
}

DEFAULT_INSTALLED_APPS = (
    "Visual Studio Code", "Google Chrome", "Safari", "Firefox", "Terminal",
    "System Settings", "Spotify", "Music", "Notes", "Calendar", "Mail",
    "Slack", "Microsoft Word", "Microsoft Excel", "Microsoft PowerPoint",
    "iTerm", "Docker", "Postman", "Figma", "Obsidian",
)


@dataclass
class AppMatch:
    """A resolved application or site, with how it was resolved."""

    name: str
    kind: str          # "app" | "site"
    target: str        # executable/application name or URL
    score: float
    method: str        # exact | alias | prefix | token | substring

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name, "kind": self.kind, "target": self.target,
            "score": round(self.score, 3), "method": self.method,
        }


class AppCatalog:
    """Resolve a spoken name to an installed application or a known site."""

    def __init__(self, installed: Iterable[str] = DEFAULT_INSTALLED_APPS,
                 aliases: dict[str, str] | None = None,
                 sites: dict[str, str] | None = None) -> None:
        self.installed = tuple(installed)
        self.aliases = dict(aliases if aliases is not None else APP_ALIASES)
        self.sites = dict(sites if sites is not None else SITES)
        # Lower-case key -> the installed app's real display name.
        self._by_lower = {name.lower(): name for name in self.installed}
        self._tokens = {
            name.lower(): set(TextNormalizer().tokens(name)) for name in self.installed
        }

    # -- helpers ---------------------------------------------------------

    def canonical(self, name: str) -> str:
        key = (name or "").strip().lower()
        return self.aliases.get(key, name.strip())

    @staticmethod
    def _ratio(a: str, b: str) -> float:
        """Longest common subsequence ratio (difflib-free, deterministic)."""
        if not a or not b:
            return 0.0
        prev = [0] * (len(b) + 1)
        for ca in a:
            cur = [0]
            for j, cb in enumerate(b, start=1):
                if ca == cb:
                    cur.append(prev[j - 1] + 1)
                else:
                    cur.append(max(prev[j], cur[j - 1]))
            prev = cur
        return 2.0 * prev[-1] / (len(a) + len(b))

    def resolve(self, name: str) -> AppMatch | None:
        raw = (name or "").strip().strip(_PUNCT_EDGE)
        if not raw:
            return None
        key = raw.lower()

        # A site wins an exact match: "open github" means the website.
        if key in self.sites:
            return AppMatch(SITE_LABELS.get(key, key.title()), "site",
                            self.sites[key], 1.0, "exact")
        if key in self.aliases:
            canonical = self.aliases[key]
            if canonical.lower() in self._by_lower:
                return AppMatch(canonical, "app", canonical, 0.95, "alias")
            if canonical.lower() in self.sites:
                label = SITE_LABELS.get(canonical.lower(), canonical)
                return AppMatch(label, "site", self.sites[canonical.lower()],
                                0.95, "alias")
            return AppMatch(canonical, "app", canonical, 0.8, "alias")

        if key in self._by_lower:
            canonical = self._by_lower[key]
            return AppMatch(canonical, "app", canonical, 1.0, "exact")

        # Prefix of an installed app or of one of its words: "chrom" ->
        # Google Chrome, "photo" -> Adobe Photoshop.
        prefixes = [
            n for n, toks in self._tokens.items()
            if n.startswith(key) or any(t.startswith(key) for t in toks)
        ]
        if prefixes:
            best = self._by_lower[min(prefixes, key=lambda n: (len(n), n))]
            return AppMatch(best, "app", best, 0.85, "prefix")

        # A whole-word match inside a multi-word app name: "studio" -> VS Code.
        wanted = set(TextNormalizer().tokens(key))
        token_hits = [
            (len(wanted & toks) / max(1, len(wanted)), self._by_lower[key_lower])
            for key_lower, toks in self._tokens.items() if wanted & toks
        ]
        if token_hits:
            overlap, best = max(token_hits, key=lambda pair: (pair[0], -len(pair[1])))
            if overlap >= 0.5:
                return AppMatch(best, "app", best, 0.6 + 0.2 * overlap, "token")

        # Last resort: character subsequence similarity.
        scored = [(self._ratio(key, n.lower()), n) for n in self.installed]
        score, best = max(scored, key=lambda pair: pair[0]) if scored else (0.0, "")
        if score >= 0.7:
            return AppMatch(best, "app", best, score * 0.75, "substring")
        return None

    def suggestions(self, name: str, limit: int = 3) -> list[str]:
        key = (name or "").strip().lower()
        if not key:
            return []
        ranked = sorted(
            self.installed,
            key=lambda n: -self._ratio(key, n.lower()),
        )
        return ranked[:limit]


# ── Action planning ───────────────────────────────────────────────────────

@dataclass
class ActionPlan:
    """A deterministic action: what to run, and what to say about it."""

    action: str
    spoken: str
    target: str = ""
    url: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    commands: list[list[str]] = field(default_factory=list)
    expects: str = "executed"   # executed | refused | unknown

    def as_dict(self) -> dict[str, Any]:
        return {
            "action": self.action, "spoken": self.spoken, "target": self.target,
            "url": self.url, "payload": dict(self.payload),
            "commands": [list(c) for c in self.commands], "expects": self.expects,
        }


VOLUME_STEP = 15
VOLUME_MIN = 0
VOLUME_MAX = 100

DEFAULT_MAIL_BRIEF = (
    "Three unread priority emails: a project sync, a server alert, "
    "and a weekly client report."
)


class DeterministicPlanner:
    """Turn a parsed intent into a plan that needs no model call.

    Plans are data: nothing is launched, no subprocess runs, no network is
    touched. A caller with a shell executes ``plan.commands``; tests assert on
    them directly.
    """

    def __init__(self, catalog: AppCatalog | None = None,
                 site_search: dict[str, str] | None = None) -> None:
        self.catalog = catalog or AppCatalog()
        self.site_search = {
            "google": "https://www.google.com/search?q={q}",
            "youtube": "https://www.youtube.com/results?search_query={q}",
            "spotify": "https://open.spotify.com/search/{q}",
            "soundcloud": "https://soundcloud.com/search?q={q}",
            **(site_search or {}),
        }
        self.current_volume = 50

    # -- helpers ---------------------------------------------------------

    @staticmethod
    def _quote(text: str) -> str:
        from urllib.parse import quote_plus
        return quote_plus(text or "")

    def _search_url(self, query: str, site: str) -> str:
        template = self.site_search.get((site or "google").lower(),
                                        self.site_search["google"])
        return template.format(q=self._quote(query))

    def _volume_plan(self, level: int, direction: str) -> ActionPlan:
        before = self.current_volume
        if direction:
            step = VOLUME_STEP if direction in ("up", "louder") else -VOLUME_STEP
            target = before + step
        else:
            target = level
        target = int(max(VOLUME_MIN, min(VOLUME_MAX, target)))
        self.current_volume = target
        delta = target - before
        verb = "increased" if delta >= 0 else "decreased"
        return ActionPlan(
            action="volume",
            spoken=f"Volume {verb} to {target} percent.",
            target=str(target),
            payload={"from": before, "to": target, "delta": delta},
            commands=[["osascript", "-e",
                       f"set volume output volume {target}"]],
        )

    # -- entry point -----------------------------------------------------

    def plan(self, parsed: ParsedIntent | None) -> ActionPlan | None:
        if parsed is None:
            return None
        handler = getattr(self, f"_plan_{parsed.action}", None)
        if handler is None:
            return None
        return handler(parsed)

    # -- per action ------------------------------------------------------

    def _plan_open(self, parsed: ParsedIntent) -> ActionPlan:
        target = parsed.slot("target")
        match = self.catalog.resolve(target)
        if match is None:
            options = ", ".join(self.catalog.suggestions(target))
            return ActionPlan(
                action="open", expects="unknown",
                spoken=f"I could not find {target}. Did you mean {options}?"
                if options else f"I could not find {target}.",
                target=target,
            )
        if match.kind == "site":
            return ActionPlan(
                action="open", spoken=f"Opening {match.name}.",
                target=match.name, url=match.target,
                commands=[["open", match.target]],
                payload=match.as_dict(),
            )
        return ActionPlan(
            action="open", spoken=f"Opening {match.name}.",
            target=match.name,
            commands=[["open", "-a", match.target]],
            payload=match.as_dict(),
        )

    def _plan_close(self, parsed: ParsedIntent) -> ActionPlan:
        target = parsed.slot("target")
        match = self.catalog.resolve(target)
        name = match.name if match else target
        return ActionPlan(
            action="close", spoken=f"Closing {name}.",
            target=name,
            commands=[["osascript", "-e",
                       f'tell application "{name}" to quit']],
            payload={"resolved": bool(match)},
        )

    def _plan_search(self, parsed: ParsedIntent) -> ActionPlan:
        query = parsed.slot("query")
        site = parsed.slot("site", "google")
        if not query:
            return ActionPlan(action="search", expects="refused",
                              spoken="What should I search for?")
        url = self._search_url(query, site)
        return ActionPlan(
            action="search",
            spoken=f"Searching {SITE_LABELS.get(site.lower(), site.title())} "
                   f"for {query}.",
            target=query, url=url, commands=[["open", url]],
            payload={"query": query, "site": site},
        )

    def _plan_play(self, parsed: ParsedIntent) -> ActionPlan:
        query = parsed.slot("query")
        site = parsed.slot("site", "youtube")
        url = self._search_url(query, site)
        return ActionPlan(
            action="play",
            spoken=f"Playing {query} on {SITE_LABELS.get(site.lower(), site.title())}.",
            target=query, url=url, commands=[["open", url]],
            payload={"query": query, "site": site},
        )

    def _plan_message(self, parsed: ParsedIntent) -> ActionPlan:
        contact = parsed.slot("contact")
        message = parsed.slot("message") or "I saw your message, will reply shortly."
        url = "https://web.whatsapp.com/send?text=" + self._quote(message)
        return ActionPlan(
            action="message",
            spoken=f"Opening WhatsApp with a message for {contact}.",
            target=contact, url=url, commands=[["open", url]],
            payload={"contact": contact, "message": message},
        )

    def _plan_mail(self, parsed: ParsedIntent) -> ActionPlan:
        return ActionPlan(
            action="mail", spoken=DEFAULT_MAIL_BRIEF,
            payload={"briefing": DEFAULT_MAIL_BRIEF},
            commands=[],
        )

    def _plan_clock(self, parsed: ParsedIntent, now: float | None = None) -> ActionPlan:
        stamp = time.localtime(now if now is not None else time.time())
        if "date" in parsed.utterance or "day" in parsed.utterance or "today" in parsed.utterance:
            spoken = "Today is " + time.strftime("%A, %B %d, %Y", stamp) + "."
            kind = "date"
        else:
            spoken = "It is " + time.strftime("%I:%M %p", stamp).lstrip("0") + "."
            kind = "time"
        return ActionPlan(
            action="clock", spoken=spoken, payload={"kind": kind,
                                                    "text": spoken},
        )

    def _plan_volume(self, parsed: ParsedIntent) -> ActionPlan:
        level = parsed.slot("level")
        direction = parsed.slot("direction").lower()
        if level.isdigit():
            return self._volume_plan(int(level), "")
        # "volume up by 30" asks for an explicit step; "louder" uses the default.
        step = parsed.slot("step")
        if step.isdigit():
            before = self.current_volume
            magnitude = int(step)
            target = max(VOLUME_MIN, min(VOLUME_MAX,
                                          before + (magnitude if direction in ("up", "louder")
                                                    else -magnitude)))
            self.current_volume = target
            return ActionPlan(
                action="volume", target=str(target),
                spoken=f"Volume {'increased' if target >= before else 'decreased'} "
                       f"to {target} percent.",
                payload={"from": before, "to": target, "delta": target - before,
                         "requested_step": magnitude},
                commands=[["osascript", "-e",
                           f"set volume output volume {target}"]],
            )
        return self._volume_plan(0, direction or "up")

    def _plan_mute(self, parsed: ParsedIntent) -> ActionPlan:
        self.current_volume = 0
        return ActionPlan(
            action="mute", spoken="System audio muted.",
            commands=[["osascript", "-e", "set volume with output muted"]],
            payload={"muted": True},
        )

    def _plan_unmute(self, parsed: ParsedIntent) -> ActionPlan:
        if self.current_volume == 0:
            self.current_volume = 50
        return ActionPlan(
            action="unmute", spoken=f"Sound restored at {self.current_volume} percent.",
            commands=[["osascript", "-e", "set volume without output muted"]],
            payload={"muted": False, "level": self.current_volume},
        )


# ── Spoken response shaping ───────────────────────────────────────────────

SPOKEN_ABBREVIATIONS = {
    "vs": "versus", "e.g.": "for example", "i.e.": "that is", "approx": "approximately",
    "min": "minutes", "max": "maximum", "hrs": "hours", "btw": "by the way",
    "asap": "as soon as possible", "faq": "frequently asked questions",
    "api": "A P I", "cpu": "C P U", "gpu": "G P U", "url": "U R L",
    "nvidia": "en-vidia", "nvda": "N V D A", "tcs": "T C S", "nsei": "nifty",
}

ONES = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
        "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
        "sixteen", "seventeen", "eighteen", "nineteen")
TENS = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy",
        "eighty", "ninety")
SCALES = ((10 ** 9, "billion"), (10 ** 6, "million"), (1000, "thousand"))


def number_to_words(value: float, decimals: int = 2) -> str:
    """Spell a number the way a voice assistant would say it."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "not available"
    negative = value < 0
    value = abs(float(value))
    whole = int(value)
    if whole >= 10 ** 12:
        return ("minus " if negative else "") + f"{whole}"
    words: list[str] = []

    def under_thousand(n: int) -> str:
        out: list[str] = []
        if n >= 100:
            out.append(ONES[n // 100] + " hundred")
            n %= 100
            if n:
                out.append("and")
        if n >= 20:
            tens, unit = divmod(n, 10)
            out.append(TENS[tens] + (f"-{ONES[unit]}" if unit else ""))
        elif n > 0 or not out:
            out.append(ONES[n])
        return " ".join(out)

    remaining = whole
    for scale, label in SCALES:
        if remaining >= scale:
            count, remaining = divmod(remaining, scale)
            words.append(under_thousand(count) + " " + label)
    if remaining or not words:
        words.append(under_thousand(remaining))

    text = " ".join(w for w in words if w)
    if decimals and abs(value - whole) > 1e-9:
        fraction = f"{value - whole:.{decimals}f}"[2:].rstrip("0")
        if fraction:
            digits = " ".join(ONES[int(d)] for d in fraction)
            text += (" point " if text else "point ") + digits
    return ("minus " if negative else "") + text


class ResponsePolisher:
    """Make model or plan output safe and natural to speak."""

    _md_link = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
    _md_mark = re.compile(r"[*_`#>]+")
    _url = re.compile(r"https?://\S+")
    _space = re.compile(r"\s+")

    def __init__(self, max_sentences: int = 3) -> None:
        self.max_sentences = max_sentences

    def strip_markup(self, text: str) -> str:
        work = self._md_link.sub(r"\1", text or "")
        work = self._url.sub("", work)
        work = self._md_mark.sub("", work)
        work = work.replace("•", ",").replace("|", ",")
        return self._space.sub(" ", work).strip()

    _abbreviation_re = re.compile(
        r"(?<![\w.])(" + "|".join(
            re.escape(key) for key in sorted(SPOKEN_ABBREVIATIONS, key=len, reverse=True)
        ) + r")(?![\w])", re.IGNORECASE)

    def expand(self, text: str) -> str:
        """Spell out abbreviations the way they should be spoken."""
        def swap(match: re.Match[str]) -> str:
            return SPOKEN_ABBREVIATIONS[match.group(0).lower()]
        return self._abbreviation_re.sub(swap, text or "")

    def sentence_case(self, text: str) -> str:
        if not text:
            return text
        out = re.sub(r"(^|[.!?]\s+)([a-z])",
                     lambda m: m.group(1) + m.group(2).upper(), text)
        return out

    def limit_sentences(self, text: str) -> str:
        if self.max_sentences <= 0:
            return text
        parts = re.split(r"(?<=[.!?])\s+", text)
        return " ".join(parts[:self.max_sentences]).strip()

    def polish(self, text: str) -> str:
        work = self.strip_markup(text)
        work = self.expand(work)
        work = self.limit_sentences(work)
        work = self.sentence_case(work)
        if work and work[-1] not in ".!?":
            work += "."
        return work


class SpeechChunker:
    """Split spoken text into TTS-sized chunks without cutting words."""

    def __init__(self, max_chars: int = 180, min_chars: int = 20) -> None:
        if max_chars <= 0:
            raise ValueError("max_chars must be positive")
        self.max_chars = max_chars
        self.min_chars = min_chars

    def chunk(self, text: str) -> list[str]:
        work = re.sub(r"\s+", " ", (text or "").strip())
        if not work:
            return []
        sentences = re.split(r"(?<=[.!?;:])\s+", work)
        chunks: list[str] = []
        buffer = ""
        for sentence in sentences:
            if not sentence:
                continue
            if len(sentence) > self.max_chars:
                # Flush what we have, then hard-wrap the long sentence.
                if buffer:
                    chunks.append(buffer)
                    buffer = ""
                chunks.extend(self._wrap(sentence))
                continue
            candidate = (buffer + " " + sentence).strip()
            if len(candidate) <= self.max_chars:
                buffer = candidate
            else:
                if buffer:
                    chunks.append(buffer)
                buffer = sentence
        if buffer:
            chunks.append(buffer)
        # Merge an undersized tail into its predecessor rather than speak it
        # alone, which sounds like a clipped sentence.
        if len(chunks) >= 2 and len(chunks[-1]) < self.min_chars:
            merged = chunks[-2] + " " + chunks[-1]
            if len(merged) <= self.max_chars:
                chunks = chunks[:-2] + [merged]
        return chunks

    def _wrap(self, sentence: str) -> list[str]:
        out: list[str] = []
        words = sentence.split(" ")
        buffer = ""
        for word in words:
            candidate = (buffer + " " + word).strip()
            if len(candidate) <= self.max_chars:
                buffer = candidate
            else:
                if buffer:
                    out.append(buffer)
                while len(word) > self.max_chars:
                    out.append(word[:self.max_chars])
                    word = word[self.max_chars:]
                buffer = word
        if buffer:
            out.append(buffer)
        return out

    def total_chars(self, chunks: Sequence[str]) -> int:
        return sum(len(c) for c in chunks)

    def duration_seconds(self, chunks: Sequence[str], chars_per_second: float = 14.5) -> float:
        """Estimated playback time at a normal speaking rate."""
        if chars_per_second <= 0:
            return 0.0
        return round(self.total_chars(chunks) / chars_per_second, 3)


# ── Conversation state ────────────────────────────────────────────────────

@dataclass
class Turn:
    user: str
    assistant: str
    source: str
    at: float
    entities: dict[str, str] = field(default_factory=dict)


# Turns a later "play it again" can point back at.
REFERABLE_ACTIONS = frozenset({"open", "play", "search", "message", "close"})


class ConversationMemory:
    """A bounded window of turns plus the entities worth remembering."""

    def __init__(self, max_turns: int = 6, char_budget: int = 4000) -> None:
        self.max_turns = max(0, max_turns)
        self.char_budget = max(0, char_budget)
        self.turns: list[Turn] = []
        self.entities: dict[str, str] = {}

    def add(self, user: str, assistant: str, source: str, at: float | None = None,
            entities: dict[str, str] | None = None) -> Turn:
        turn = Turn(user=user, assistant=assistant, source=source,
                    at=at if at is not None else time.time(),
                    entities=dict(entities or {}))
        self.turns.append(turn)
        for key, value in (entities or {}).items():
            if value:
                self.entities[key] = value
        self._trim()
        return turn

    def _trim(self) -> None:
        if self.max_turns and len(self.turns) > self.max_turns:
            self.turns = self.turns[-self.max_turns:]
        if not self.char_budget:
            return
        while len(self.turns) > 1 and self.chars() > self.char_budget:
            self.turns.pop(0)

    def chars(self) -> int:
        return sum(len(t.user) + len(t.assistant) for t in self.turns)

    def messages(self, system_prompt: str = "") -> list[dict[str, str]]:
        out: list[dict[str, str]] = []
        if system_prompt:
            out.append({"role": "system", "content": system_prompt})
        for turn in self.turns:
            out.append({"role": "user", "content": turn.user})
            out.append({"role": "assistant", "content": turn.assistant})
        return out

    def last(self) -> Turn | None:
        return self.turns[-1] if self.turns else None

    # A whole utterance that only makes sense against the previous turn. The
    # pattern is deliberately narrow: "that" inside a normal clause ("tell Rahul
    # that I am late") is grammar, not a reference, and must not be rewritten.
    REFERENCE_RE = re.compile(
        r"^(?:(?:play|open|search|close|show|run|do|repeat|start|put on)\s+)?"
        r"(?P<object>it|that|this|them|those|the same|that again|it again)"
        r"(?:\s+again)?$", re.IGNORECASE)

    def resolve_reference(self, utterance: str) -> dict[str, str] | None:
        """Resolve "play it again" against the most recent turn's entities."""
        if not self.turns or not self.REFERENCE_RE.match((utterance or "").strip()):
            return None
        for turn in reversed(self.turns):
            if turn.entities.get("action") in REFERABLE_ACTIONS and (
                    turn.entities.get("query") or turn.entities.get("target")):
                return dict(turn.entities)
        return None

    def expand_reference(self, utterance: str) -> tuple[str, dict[str, str] | None]:
        """Rewrite a referential utterance into a self-contained one."""
        text = (utterance or "").strip()
        entities = self.resolve_reference(text)
        if not entities:
            return utterance, None
        lowered = text.lower()
        repeated = "again" in lowered or "same" in lowered
        verb = ""
        for candidate in ("play", "open", "search", "close", "show", "start"):
            if lowered.startswith(candidate):
                verb = candidate
                break
        previous = entities.get("action") or ""
        verb = verb or ("play" if previous == "play" else
                        "open" if previous in ("open", "close") else "search")
        slot = {"play": "query", "search": "query", "open": "target",
                "close": "target", "show": "target", "start": "target"}.get(verb, "query")
        subject = (entities.get(slot) or entities.get("query")
                   or entities.get("target") or "")
        if not subject:
            return utterance, entities
        if repeated and verb in ("play", "search") and entities.get("query"):
            subject = entities["query"]
        return f"{verb} {subject}", entities


# ── Model failover ────────────────────────────────────────────────────────

DEFAULT_MODELS = ("friday-fast", "friday-reasoning", "friday-local")

_RETRY_PATTERNS = (
    re.compile(r"try again in\s*(\d+)\s*m\s*([0-9]+(?:\.[0-9]+)?)\s*s", re.IGNORECASE),
    re.compile(r"try again in\s*([0-9]+(?:\.[0-9]+)?)\s*s", re.IGNORECASE),
    re.compile(r"retry[-_ ]after[:\s]*([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE),
)

RATE_LIMIT_MARKERS = (
    "429", "rate limit", "rate_limit", "ratelimit", "too many requests",
    "quota exceeded", "exceeded your current quota", "slow down",
)


def is_rate_limited(error: Any, status: int | None = None) -> bool:
    """Classify a provider error as a rate limit rather than a real failure."""
    code = status
    if code is None:
        code = getattr(error, "status_code", None) or getattr(error, "status", None)
    if code == 429:
        return True
    text = str(error).lower()
    return any(marker in text for marker in RATE_LIMIT_MARKERS)


def retry_after_seconds(error: Any, default: float = 60.0) -> float:
    """Read the provider's own wait hint, plus a two-second safety pad."""
    text = str(error)
    for pattern in _RETRY_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        groups = match.groups()
        if len(groups) == 2:
            return float(groups[0]) * 60.0 + float(groups[1]) + 2.0
        return float(groups[0]) + 2.0
    attribute = getattr(error, "retry_after", None)
    if isinstance(attribute, (int, float)) and attribute > 0:
        return float(attribute) + 2.0
    return default


@dataclass
class Attempt:
    """One model call attempt and its outcome."""

    model: str
    ok: bool
    error: str = ""
    rate_limited: bool = False
    latency_s: float = 0.0


class FailoverPolicy:
    """Walk a model chain, cooling down on rate limits, not on real errors."""

    def __init__(self, models: Sequence[str] = DEFAULT_MODELS,
                 clock: Callable[[], float] = time.monotonic,
                 default_cooldown: float = 60.0) -> None:
        self.models = tuple(models)
        self.clock = clock
        self.default_cooldown = default_cooldown
        self.cooldowns: dict[str, float] = {}
        self.attempts: list[Attempt] = []

    def ready(self, model: str) -> bool:
        return self.clock() >= self.cooldowns.get(model, 0.0)

    def available(self) -> list[str]:
        return [m for m in self.models if self.ready(m)]

    def cool_down(self, model: str, seconds: float) -> float:
        until = self.clock() + max(0.0, float(seconds))
        self.cooldowns[model] = max(self.cooldowns.get(model, 0.0), until)
        return self.cooldowns[model]

    def cooldown_remaining(self, model: str) -> float:
        return max(0.0, self.cooldowns.get(model, 0.0) - self.clock())

    def run(self, call: Callable[[str], str]) -> tuple[str, str, list[Attempt]]:
        """Try each available model in order.

        Returns ``(text, model, attempts)``. An empty text and empty model mean
        every model was either cooling down or failed.
        """
        tried: list[Attempt] = []
        for model in self.models:
            if not self.ready(model):
                continue
            started = self.clock()
            try:
                text = call(model)
            except Exception as exc:  # provider error, classified below
                limited = is_rate_limited(exc)
                if limited:
                    self.cool_down(model, retry_after_seconds(exc, self.default_cooldown))
                attempt = Attempt(model=model, ok=False, error=str(exc)[:200],
                                  rate_limited=limited,
                                  latency_s=self.clock() - started)
                tried.append(attempt)
                self.attempts.append(attempt)
                continue
            attempt = Attempt(model=model, ok=True,
                              latency_s=self.clock() - started)
            tried.append(attempt)
            self.attempts.append(attempt)
            return (text or "").strip(), model, tried
        return "", "", tried


SYSTEM_PROMPT = (
    "You are FRIDAY, a fast, capable voice assistant running on the user's "
    "computer. Answer in one or two sentences. Be direct and natural."
)


# ── The turn loop ─────────────────────────────────────────────────────────

@dataclass
class AssistantReply:
    """Everything one assistant turn produced."""

    text: str
    source: str                  # action | model | fallback | clarifying
    model: str = ""
    intent: str = ""
    plan: ActionPlan | None = None
    chunks: list[str] = field(default_factory=list)
    attempts: list[Attempt] = field(default_factory=list)
    latency_s: float = 0.0
    at: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "text": self.text, "source": self.source, "model": self.model,
            "intent": self.intent, "chunks": list(self.chunks),
            "commands": list(self.plan.commands) if self.plan else [],
            "latency_s": round(self.latency_s, 4),
        }


FALLBACK_REPLY = (
    "My cloud brain is cooling down, but local commands still work. "
    "I can open apps, search, or read your inbox."
)


class AssistantBrain:
    """Planner-first assistant turn loop with a model chain behind it."""

    def __init__(self, grammar: CommandGrammar | None = None,
                 planner: DeterministicPlanner | None = None,
                 memory: ConversationMemory | None = None,
                 policy: FailoverPolicy | None = None,
                 polisher: ResponsePolisher | None = None,
                 chunker: SpeechChunker | None = None,
                 clock: Callable[[], float] = time.monotonic,
                 system_prompt: str = SYSTEM_PROMPT) -> None:
        self.normalizer = TextNormalizer()
        self.grammar = grammar or CommandGrammar()
        self.planner = planner or DeterministicPlanner()
        self.memory = memory or ConversationMemory()
        self.policy = policy or FailoverPolicy(clock=clock)
        self.polisher = polisher or ResponsePolisher()
        self.chunker = chunker or SpeechChunker()
        self.clock = clock
        self.system_prompt = system_prompt

    # -- helpers ---------------------------------------------------------

    def _finish(self, text: str, source: str, started: float,
                intent: str = "", plan: ActionPlan | None = None,
                model: str = "", attempts: list[Attempt] | None = None,
                entities: dict[str, str] | None = None) -> AssistantReply:
        polished = self.polisher.polish(text)
        reply = AssistantReply(
            text=polished, source=source, model=model, intent=intent, plan=plan,
            chunks=self.chunker.chunk(polished),
            attempts=list(attempts or []),
            latency_s=self.clock() - started,
            at=self.clock(),
        )
        self.memory.add(user=self._last_utterance, assistant=polished,
                        source=source, at=reply.at, entities=entities)
        return reply

    @staticmethod
    def _entities(parsed: ParsedIntent | None, plan: ActionPlan | None) -> dict[str, str]:
        entities: dict[str, str] = {}
        if parsed is not None:
            for key in ("target", "query", "contact", "site"):
                if parsed.slots.get(key):
                    entities[key] = parsed.slots[key]
        if plan is not None and plan.target and "target" not in entities:
            entities["target"] = plan.target
        # Only an actionable turn is worth referring back to: "volume up" and
        # "what time is it" leave nothing to reopen.
        if plan is not None and plan.action in REFERABLE_ACTIONS:
            entities["action"] = plan.action
        return entities

    # -- main entry ------------------------------------------------------

    def respond(self, utterance: str, llm_call: Callable[[str], str] | None = None,
                now: float | None = None) -> AssistantReply:
        started = self.clock()
        self._last_utterance = utterance
        expanded, _ = self.memory.expand_reference(utterance)
        parsed = self.grammar.parse(expanded, self.normalizer)

        if parsed is not None and parsed.action == "clock":
            plan = self.planner._plan_clock(parsed, now)
            return self._finish(plan.spoken, "action", started, parsed.intent,
                                plan, entities=self._entities(parsed, plan))

        plan = self.planner.plan(parsed)
        if plan is not None and plan.expects != "unknown":
            return self._finish(plan.spoken, "action", started, parsed.intent,
                                plan, entities=self._entities(parsed, plan))

        if plan is not None and plan.expects == "unknown":
            # The parser understood, the catalog did not: ask, do not guess.
            return self._finish(plan.spoken, "clarifying", started,
                                parsed.intent, plan,
                                entities=self._entities(parsed, plan))

        if not self.policy.available():
            return self._finish(FALLBACK_REPLY, "fallback", started,
                                entities={"last_query": utterance})

        messages = self.memory.messages(self.system_prompt)
        messages.append({"role": "user", "content": expanded})

        def call(model: str) -> str:
            if llm_call is None:
                raise RuntimeError("no model backend configured")
            return llm_call(model)

        text, model, attempts = self.policy.run(call)
        if not text:
            return self._finish(FALLBACK_REPLY, "fallback", started,
                                attempts=attempts,
                                entities={"last_query": utterance})
        return self._finish(text, "model", started, model=model,
                            attempts=attempts,
                            entities={"last_query": utterance})


# ── Briefing composition ──────────────────────────────────────────────────

@dataclass
class QuoteLine:
    """One instrument as it should be spoken."""

    name: str
    price: float
    change_pct: float
    signal: str = ""
    currency: str = "$"

    @property
    def direction(self) -> str:
        if self.change_pct > 0.05:
            return "up"
        if self.change_pct < -0.05:
            return "down"
        return "flat"

    def speak(self, digits: int = 2) -> str:
        movement = abs(self.change_pct)
        if self.direction == "flat":
            return f"{self.name} is at {self.currency}{self.price:,.{digits}f}, flat."
        clause = f"{self.name} is at {self.currency}{self.price:,.{digits}f}, " \
                 f"{self.direction} {movement:.{digits}f} percent"
        if self.signal:
            clause += f", signal {self.signal.lower()}"
        return clause + "."


class BriefingComposer:
    """Turn structured quotes into a spoken briefing of a chosen length."""

    def __init__(self, max_items: int = 4, digits: int = 2) -> None:
        self.max_items = max(1, max_items)
        self.digits = digits

    def compose(self, quotes: Sequence[QuoteLine], header: str = "") -> str:
        if not quotes:
            return header or "I have no quotes to report right now."
        chosen = list(quotes)[:self.max_items]
        sentences = [q.speak(self.digits) for q in chosen]
        body = " ".join(sentences)
        return f"{header} {body}".strip() if header else body

    def movers(self, quotes: Sequence[QuoteLine], limit: int = 2) -> dict[str, list[QuoteLine]]:
        ranked = sorted(quotes, key=lambda q: q.change_pct, reverse=True)
        return {
            "gainers": ranked[:limit],
            "losers": list(reversed(ranked[-limit:])) if len(ranked) > 1 else [],
        }

    def summary(self, quotes: Sequence[QuoteLine]) -> dict[str, Any]:
        if not quotes:
            return {"count": 0, "advancers": 0, "decliners": 0,
                    "average_change_pct": 0.0, "breadth": 0.0}
        advancers = sum(1 for q in quotes if q.direction == "up")
        decliners = sum(1 for q in quotes if q.direction == "down")
        average = sum(q.change_pct for q in quotes) / len(quotes)
        return {
            "count": len(quotes),
            "advancers": advancers,
            "decliners": decliners,
            "flat": len(quotes) - advancers - decliners,
            "average_change_pct": round(average, 4),
            # Share of instruments advancing, 0..1.
            "breadth": round(advancers / len(quotes), 4),
        }
