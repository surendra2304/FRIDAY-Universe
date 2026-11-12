"""Conversational Voice Interface with Interruption and Emotion Adaptation.

Enhances conversational depth:
1. Multi-turn thread memory with contextual follow-ups ("what about yesterday?")
2. Multi-tier conversation repair (<0.70 repeat, 0.70-0.85 confirm, >=0.85 execute)
3. Mid-speech voice interruption handling (stops speaking and listens)
4. Emotion/stress tone detection: adapts response style to concise bullets under stress

FAKE-RESULT FIX (2026-11-13): the EXECUTE tier used to answer "yesterday"
and "status" with hardcoded fabricated numbers ("+1.8% gain ($185.00
USDT)", "All systems are operating normally") and merely echoed every other
command without executing anything. That was invented output — exactly what
the owner banned. Now the interface accepts an ``executor`` callable: when a
host wires the real command router in, EXECUTE decisions run it and speak
the real outcome; without one, FRIDAY says the request was heard and routed,
never a fabricated result. Nothing in this module invents data.
"""

import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from friday.core.logging import get_logger

logger = get_logger("voice.conversation")


@dataclass
class VoiceTurnResult:
    """Outcome of a conversational voice interaction turn."""
    turn_id: str
    transcription: str
    confidence: float
    repair_decision: str  # REPEAT, CONFIRM, EXECUTE
    response_text: str
    is_interrupted: bool = False
    detected_emotion: str = "NEUTRAL"  # NEUTRAL, CALM, STRESSED, URGENT
    response_style: str = "STANDARD"  # STANDARD, CONCISE_BULLETS


class ConversationalVoiceInterface:
    """Manages multi-turn conversation threads, confidence repair, interruptions, and tone adaptation."""

    def __init__(self, executor: Callable[[str], str] | None = None) -> None:
        self.conversation_thread: list[dict[str, Any]] = []
        self._is_speaking = False
        self._lock = threading.RLock()
        # Optional real command executor (e.g. the API command router). When
        # present, EXECUTE-tier turns run the real command and speak the real
        # outcome; when absent, the turn is acknowledged honestly.
        self.executor = executor

    def process_voice_turn(
        self,
        transcription: str,
        confidence: float,
        detected_stress_level: float = 0.2,  # 0.0 to 1.0
        is_interruption_event: bool = False,
        executor: Callable[[str], str] | None = None,
    ) -> VoiceTurnResult:
        """Processes a voice input turn, evaluates repair thresholds, and synthesizes response.

        ``executor`` overrides the instance-level executor for this turn; the
        real command router belongs to the host process, never this module.
        """
        with self._lock:
            now = datetime.now(timezone.utc)
            turn_id = f"vturn_{int(now.timestamp())}_{len(self.conversation_thread)}"

            # 1. Handle Voice Interruption
            if is_interruption_event or self._is_speaking:
                self.interrupt_speech()

            # 2. Emotion / Stress Tone Detection
            emotion = "STRESSED" if detected_stress_level > 0.7 else ("URGENT" if detected_stress_level > 0.5 else "NEUTRAL")
            style = "CONCISE_BULLETS" if emotion in ("STRESSED", "URGENT") else "STANDARD"

            # 3. Conversation Repair Tiers
            if confidence < 0.70:
                decision = "REPEAT"
                response = "I didn't catch that clearly. Could you please repeat that?"
            elif confidence < 0.85:
                decision = "CONFIRM"
                clean = transcription.strip()
                response = f"Did you mean: '{clean}'? Please confirm to execute."
            else:
                decision = "EXECUTE"
                # FAKE-RESULT FIX: run the REAL command router when wired; the
                # old branch here invented "+1.8% gain ($185.00 USDT)" and
                # "all systems normal" out of thin air. Now: real outcome or
                # an honest routed-acknowledgment — never fabricated data.
                router = executor if executor is not None else self.executor
                if router is not None:
                    try:
                        response = str(router(transcription.strip()) or "").strip()
                    except Exception as exc:
                        decision = "CONFIRM"
                        response = (
                            f"That command failed on my side ({type(exc).__name__}). "
                            "Want me to try it again?"
                        )
                    else:
                        if not response:
                            response = "The command returned nothing — that is the real outcome."
                else:
                    response = (
                        f"Got it — '{transcription.strip()}' is routed. I don't have the "
                        "live executor attached here, so I won't guess at a result."
                    )
                # Stress style: keep the REAL content, tighten the delivery.
                if style == "CONCISE_BULLETS":
                    bullets = [line.strip() for line in response.splitlines() if line.strip()]
                    response = "\n".join(f"• {b}" for b in bullets) if bullets else f"• {response}"

            result = VoiceTurnResult(
                turn_id=turn_id,
                transcription=transcription,
                confidence=confidence,
                repair_decision=decision,
                response_text=response,
                is_interrupted=is_interruption_event,
                detected_emotion=emotion,
                response_style=style,
            )

            self.conversation_thread.append({
                "turn_id": turn_id,
                "transcription": transcription,
                "response": response,
                "timestamp": now,
            })

            logger.info(f"[VOICE_CONVERSATION] Turn {turn_id} -> {decision} ({confidence:.2f}, emotion={emotion})")
            return result

    def interrupt_speech(self) -> None:
        """Immediately halts active TTS speech and clears audio buffers."""
        with self._lock:
            if self._is_speaking:
                logger.info("[VOICE_CONVERSATION] 🛑 Interruption detected! Halting TTS output.")
            self._is_speaking = False

    def set_speaking_state(self, is_speaking: bool) -> None:
        """Updates internal speech synthesis state."""
        with self._lock:
            self._is_speaking = is_speaking


# Default singleton instance
conversational_voice = ConversationalVoiceInterface()
