"""Spoken-English Practice Skill for FRIDAY (TASK-IG2-VOI-01).

IG cluster #111 (PeerUp-style reel, IG DeIyWtZs9uv): a practice mode
where the owner speaks or types a sentence and FRIDAY answers with
the correction, an error label and a tip — per sentence, in the flow
of conversation.

The skill sits on FRIDAY's existing chat/voice surfaces: voice turns
arrive as transcripts and chat turns as text, both reach skills as a
plain user_request, and the rendered feedback is short enough to be
spoken back by the voice layer (Gemini Live) unchanged. Correction
itself is the deterministic, offline engine in
friday.voice.english_practice — no new provider, no paid service.

Usage shapes:
  "practice english: He don't like coffee"
  "correct my english: Yesterday I go to market"
  "english practice"            -> FRIDAY offers a prompt sentence
  "english practice score"      -> session summary (attempts, focus labels)
Sessions are kept per skill instance, keyed by the `session_id`
kwarg when the caller supplies one (voice session / chat thread).
"""

from typing import Any

from friday.core.logging import get_logger
from friday.skills.base_skill import BaseSkill, SkillExecutionResult
from friday.voice.english_practice import EnglishPracticeSession

logger = get_logger("skills.english_practice")

# Prefixes that hand the rest of the request to the practice engine.
_SENTENCE_PREFIXES = (
    "practice english:",
    "practice english -",
    "correct my english:",
    "correct my english -",
    "english practice:",
    "english practice -",
    "check my english:",
    "check my english -",
)


def extract_practice_sentence(user_request: str) -> str | None:
    """The sentence to check, when the request carries one.

    Returns None for a bare mode/score request (handled by the skill
    itself) so the engine never "corrects" the command words.
    """
    clean = (user_request or "").strip()
    lowered = clean.lower()
    for prefix in _SENTENCE_PREFIXES:
        if lowered.startswith(prefix):
            sentence = clean[len(prefix):].strip()
            return sentence or None
    # Colon-less shape: "practice english he don't like coffee" — strip
    # the command phrase and treat the rest as the sentence, unless the
    # rest is a score/prompt keyword handled by the skill itself.
    import re

    match = re.match(
        r"(?:practice\s+(?:my\s+)?english|correct\s+my\s+english|check\s+my\s+english|english\s+practice)\s+(.+)$",
        lowered,
    )
    if match:
        rest = match.group(1).strip()
        if rest and not any(word in rest for word in ("score", "summary", "progress", "mode", "start")):
            start, end = match.span(1)
            return clean[start:end].strip() or None
    return None


class EnglishPracticeSkill(BaseSkill):
    """Per-sentence spoken-English practice with labelled corrections."""

    name = "english_practice"
    description = (
        "Spoken-English practice mode: give FRIDAY a sentence (spoken or typed) "
        "and get back the correction with an error label and a tip, PeerUp-style."
    )
    required_capabilities: list[str] = []
    tools: list[str] = []
    system_prompt = (
        "You are FRIDAY's English practice partner. The learner says one sentence; "
        "you return the corrected sentence with the error label and one short tip, "
        "then invite the next sentence. Keep it encouraging and brief — this is "
        "spoken practice, not a grammar lecture."
    )
    match_patterns = [
        r"\bpractice\s+(?:my\s+)?english\b",
        r"\bcorrect\s+my\s+english\b",
        r"\bcheck\s+my\s+english\b",
        r"\benglish\s+practice\b",
        r"\bspoken\s+english\s+practice\b",
    ]

    def __init__(self) -> None:
        self._sessions: dict[str, EnglishPracticeSession] = {}

    def _session(self, session_id: str) -> EnglishPracticeSession:
        if session_id not in self._sessions:
            self._sessions[session_id] = EnglishPracticeSession()
        return self._sessions[session_id]

    def execute(
        self,
        user_request: str,
        agent: Any | None = None,
        tool_registry: Any | None = None,
        llm_provider: Any | None = None,
        authorizer: Any | None = None,
        **kwargs: Any,
    ) -> SkillExecutionResult:
        session_id = str(kwargs.get("session_id") or "default")
        session = self._session(session_id)
        clean = (user_request or "").strip()
        lowered = clean.lower()
        step_results: list[dict[str, Any]] = []

        # Score / summary request.
        if "score" in lowered or "summary" in lowered or "progress" in lowered:
            summary = session.summary()
            step_results.append({"action": "summary", **summary})
            return SkillExecutionResult(
                skill_name=self.name,
                success=True,
                output=session.summary_text(),
                step_results=step_results,
                metadata={"summary": summary},
            )

        sentence = extract_practice_sentence(clean)
        if sentence is None:
            # Bare mode request: open the practice with a prompt.
            prompt = session.next_prompt()
            step_results.append({"action": "prompt", "prompt": prompt})
            return SkillExecutionResult(
                skill_name=self.name,
                success=True,
                output=(
                    "English practice is on. Say or type one sentence at a time and "
                    "I will correct it with the error label and a tip.\n"
                    f"Try this: {prompt}\n"
                    "Or say 'practice english: <your sentence>'. "
                    "Ask for 'english practice score' any time to see your focus areas."
                ),
                step_results=step_results,
                metadata={"prompt": prompt},
            )

        feedback = session.practice(sentence)
        step_results.append({"action": "correct", **feedback.to_dict()})
        return SkillExecutionResult(
            skill_name=self.name,
            success=True,
            output=feedback.render(),
            step_results=step_results,
            metadata={"feedback": feedback.to_dict(), "summary": session.summary()},
        )
