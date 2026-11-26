"""Conversational voice/chat appointment agents for Cortex (TASK-EARN-027).

New agent family: the business's customers talk to the agent IN Cortex, and
every booking lands as a Lead + follow-up in Cortex CRM (the full loop the
owner clarification of 2026-11-25 ~09:30 IST requires: the agent lives in
Cortex, and the lead, customer record and follow-up are visible in Cortex).

Two demos, one engine:

* Demo 1 — clinic appointment VOICE agent (OmniDimension pattern):
  ``ClinicAppointmentVoiceAgent`` (``agent_conversational_voice``).
* Demo 2 — website CHAT agent that books appointments (Voiceflow pattern):
  ``WebsiteChatBookingAgent`` (``agent_conversational_chat``).

Provenance, stated honestly:

* The F-35 "Riley" prompt's own text was NEVER recovered — only the method
  was (take the business's services text from its own site, generate the
  agent's system prompt from it). ``build_appointment_agent_prompt`` below
  implements that method with Cortex's own prompt text. FRIDAY already
  implements the same method in
  ``FRIDAY/src/friday/workflows/local_business.py``; this module vendors the
  method into Cortex rather than importing across apps, and says so.
* The conversation engine is deterministic and rule-driven (no LLM call):
  it walks the booking flow, matches the requested service against the
  business's own services list, and refuses to invent services, prices,
  timings or policies. A live LLM voice/chat leg is NOT claimed here — the
  live answer/call test is the gated follow-up (see
  ``docs/collaboration/TASK-EARN-027.md``).
* Demo services text is the clinics' own public wording, read first-hand
  from their sites on 2026-11-25: Spotlight Dental
  (https://www.spotlightdental.in/) for demo 1, Dentaire
  (https://dentaire.co.in/) for demo 2. Nothing is invented for either
  business.

Hard boundaries, enforced in code:

* **No invented facts.** The system prompt embeds only the services text it
  is given; with no services text the builder refuses
  (``ConversationalError``) rather than emitting a hollow prompt, and the
  engine answers OUT_OF_SCOPE for any service outside the list.
* **Generation + proposal only.** The agents propose ``lead_create`` /
  ``follow_up_schedule`` / ``conversation_log`` actions for the ToolBus;
  they do not write to the CRM store themselves. The proposed lead params
  map 1:1 onto the Cortex ``Lead`` model (``cortex_core.models``) and the
  ``leads`` table (``cortex_api.db_models.LeadModel``).

Stdlib + pydantic only — no new dependencies, Python 3.10.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from cortex_agents import AgentInput, AgentOutput, ProposedAction, SpecialistAgent


class ConversationalError(ValueError):
    """Raised when a conversational agent cannot run honestly."""


# ---------------------------------------------------------------------------
# F-35 method: system prompt from the business's own services text
# ---------------------------------------------------------------------------


def build_appointment_agent_prompt(
    business_name: str,
    services_text: str,
    niche: str = "",
    languages: str = "",
) -> str:
    """Generate an appointment-booking agent's system prompt (F-35 method).

    The method: take the services text from the business's own site and
    generate the agent's system prompt from it. The generated text is
    Cortex's own — the video's "Riley" prompt was never recovered.
    Refuses without services text: the services are the substance of the
    prompt, and inventing them would make the agent lie to callers.
    """
    name = (business_name or "").strip()
    services = (services_text or "").strip()
    if not name:
        raise ConversationalError(
            "build_appointment_agent_prompt needs a business name."
        )
    if not services:
        raise ConversationalError(
            "build_appointment_agent_prompt needs the business's services text "
            "(copied from its own website, per the F-35 method) — without it "
            "the agent would have to invent services."
        )
    lines = [
        f"You are the appointment-booking assistant for {name}"
        + (f", a {niche.strip()} business" if niche.strip() else "")
        + ".",
        "",
        "Your one job: help callers book appointments for the services below.",
        "",
        "Services (from the business's own website — offer exactly these):",
        services,
        "",
        "How you work:",
        "- Greet the caller, ask which service they want, and offer the services above by name.",
        "- Collect the caller's name, a contact number, and a preferred date and time.",
        "- Repeat the booking details back and confirm them before ending the conversation.",
        "- Never invent services, prices, timings or policies that are not in the services text above.",
        "- If a caller asks for something outside the services above, say honestly that you "
        "cannot help with that and offer to pass a message to the business.",
        "- Keep answers short and warm; you are a booking assistant, not a salesperson.",
    ]
    if languages.strip():
        lines.append(
            f"- Languages: answer in the caller's language ({languages.strip()})."
        )
    return "\n".join(lines)


def parse_services(services_text: str) -> list[str]:
    """Split services text into the business's own service names.

    One service per line; leading bullets (``-``, ``•``, ``*``, ``✦``) and
    numbering (``1. ``) are stripped. Blank lines are dropped. Lines are
    never split on commas — a service name may contain one.
    """
    services: list[str] = []
    for raw in (services_text or "").splitlines():
        line = raw.strip()
        line = re.sub(r"^(?:[-•*✦]|\d+[.)])\s*", "", line)
        if line:
            services.append(line)
    return services


def _normalise(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


_STOPWORDS = {
    "i", "need", "want", "to", "book", "a", "an", "the", "for", "please",
    "appointment", "get", "have", "would", "like", "me", "my", "do", "you",
    "can", "could", "and", "or", "of", "in", "on", "is", "an", "please",
}


def _find_service(phrase: str, services: list[str]) -> str | None:
    """Match a caller's phrase to one of the business's services.

    First tries a substring match either way ("root canal" in
    "Root Canal Treatment"); then falls back to content-word matching
    ("I need a root canal" -> words {root, canal} -> "Root Canal
    Treatment"). The longest substring match wins; word matches take the
    first service in list order containing every content word. Returns
    None when nothing matches — the caller is then OUT_OF_SCOPE, never
    silently booked into a wrong service.
    """
    want = _normalise(phrase)
    if not want:
        return None
    best: str | None = None
    for service in services:
        have = _normalise(service)
        if want in have or have in want:
            if best is None or len(service) > len(best):
                best = service
    if best is not None:
        return best
    words = [w for w in want.split() if w not in _STOPWORDS]
    if not words:
        return None
    for service in services:
        have_words = set(_normalise(service).split())
        if all(w in have_words for w in words):
            return service
    return None


_PHONE_RE = re.compile(r"\+?\d[\d\s\-()]{7,}\d")


def _find_phone(text: str) -> str | None:
    match = _PHONE_RE.search(text or "")
    return match.group(0).strip() if match else None


# ---------------------------------------------------------------------------
# Booking record + deterministic conversation engine
# ---------------------------------------------------------------------------


@dataclass
class Booking:
    """One confirmed appointment, exactly as the caller stated it."""

    business_name: str
    service: str
    caller_name: str
    caller_phone: str
    date_text: str
    time_text: str
    channel: str  # "voice" | "chat"


@dataclass
class ConversationTurn:
    role: str  # "agent" | "caller"
    text: str


@dataclass
class BookingResult:
    decision: str  # BOOKED | NEEDS_INFO | OUT_OF_SCOPE | REFUSED_NO_SERVICES
    booking: Booking | None = None
    transcript: list[ConversationTurn] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    system_prompt: str = ""
    out_of_scope_request: str = ""


class ConversationEngine:
    """Deterministic booking flow over caller utterances (no LLM call).

    States: ASK_SERVICE -> ASK_NAME -> ASK_PHONE -> ASK_DATE -> ASK_TIME
    -> CONFIRM -> DONE. Every collected value is the caller's own wording;
    the date/time are kept verbatim — the engine never invents a slot.
    """

    def __init__(
        self,
        business_name: str,
        services_text: str,
        niche: str = "",
        channel: str = "voice",
        languages: str = "",
    ) -> None:
        self.business_name = (business_name or "").strip()
        self.services = parse_services(services_text)
        self.niche = niche
        self.channel = channel
        self.system_prompt = build_appointment_agent_prompt(
            business_name, services_text, niche=niche, languages=languages
        )

    def run(self, caller_turns: list[str]) -> BookingResult:
        turns = list(caller_turns or [])
        transcript: list[ConversationTurn] = []
        missing: list[str] = []

        def say(text: str) -> None:
            transcript.append(ConversationTurn(role="agent", text=text))

        def hear() -> str | None:
            if not turns:
                return None
            text = turns.pop(0)
            transcript.append(ConversationTurn(role="caller", text=text))
            return text

        example = ", ".join(self.services[:3])
        say(
            f"Hello, thank you for calling {self.business_name}. "
            f"Which service would you like to book — for example, {example}?"
        )
        service = None
        while service is None:
            reply = hear()
            if reply is None:
                missing.append("service")
                return BookingResult(
                    decision="NEEDS_INFO",
                    transcript=transcript,
                    missing=missing,
                    system_prompt=self.system_prompt,
                )
            service = _find_service(reply, self.services)
            if service is None:
                say(
                    f"I'm sorry — {self.business_name} doesn't offer {reply.strip()}. "
                    "I can pass a message to the clinic, or help you book one of our services instead."
                )
                return BookingResult(
                    decision="OUT_OF_SCOPE",
                    transcript=transcript,
                    system_prompt=self.system_prompt,
                    out_of_scope_request=reply.strip(),
                )

        say("May I have your name, please?")
        name = hear()
        if name is None or not name.strip():
            missing.append("caller_name")
            return BookingResult(
                decision="NEEDS_INFO",
                transcript=transcript,
                missing=missing,
                system_prompt=self.system_prompt,
            )

        say("And a contact number where we can reach you?")
        phone = None
        reply = hear()
        if reply is not None:
            phone = _find_phone(reply)
        if phone is None:
            missing.append("caller_phone")
            return BookingResult(
                decision="NEEDS_INFO",
                transcript=transcript,
                missing=missing,
                system_prompt=self.system_prompt,
            )

        say("Which date would you prefer?")
        date_text = hear()
        if date_text is None or not date_text.strip():
            missing.append("date")
            return BookingResult(
                decision="NEEDS_INFO",
                transcript=transcript,
                missing=missing,
                system_prompt=self.system_prompt,
            )

        say("And what time works for you?")
        time_text = hear()
        if time_text is None or not time_text.strip():
            missing.append("time")
            return BookingResult(
                decision="NEEDS_INFO",
                transcript=transcript,
                missing=missing,
                system_prompt=self.system_prompt,
            )

        say(
            f"Just to confirm: {service} for {name.strip()} on {date_text.strip()} "
            f"at {time_text.strip()}. Is that correct?"
        )
        confirm = hear()
        if confirm is None:
            missing.append("confirmation")
            return BookingResult(
                decision="NEEDS_INFO",
                transcript=transcript,
                missing=missing,
                system_prompt=self.system_prompt,
            )
        ok = _normalise(confirm)
        if not (
            ok.startswith("yes")
            or ok in ("correct", "confirmed", "that is correct", "that is right")
            or "confirm" in ok
        ):
            missing.append("confirmation")
            return BookingResult(
                decision="NEEDS_INFO",
                transcript=transcript,
                missing=missing,
                system_prompt=self.system_prompt,
            )

        booking = Booking(
            business_name=self.business_name,
            service=service,
            caller_name=name.strip(),
            caller_phone=phone,
            date_text=date_text.strip(),
            time_text=time_text.strip(),
            channel=self.channel,
        )
        say(
            f"Done — your {service} appointment is booked for {date_text.strip()} "
            f"at {time_text.strip()}. We will call {phone} if anything changes. Thank you!"
        )
        return BookingResult(
            decision="BOOKED", booking=booking, transcript=transcript, system_prompt=self.system_prompt
        )


# ---------------------------------------------------------------------------
# CRM landing: Lead + follow-up proposed actions (ToolBus targets)
# ---------------------------------------------------------------------------


def build_booking_lead(tenant_id: str, booking: Booking) -> dict[str, Any]:
    """Lead params for a confirmed booking — 1:1 with the Cortex Lead model.

    ``source`` names the agent channel; the appointment itself lives in
    ``metadata`` (the leads table has no appointment columns yet — a
    follow-up task may add them; see TASK-EARN-027 evidence doc).
    """
    phone_digits = re.sub(r"\D", "", booking.caller_phone)
    date_slug = re.sub(r"[^a-z0-9]+", "-", booking.date_text.lower()).strip("-")
    return {
        "id": f"lead_{booking.channel}_{phone_digits}_{date_slug}",
        "tenant_id": tenant_id,
        "profile_id": None,
        "score": 0.0,
        "status": "new",
        "source": f"{booking.channel}_agent",
        "metadata": {
            "business_name": booking.business_name,
            "service": booking.service,
            "caller_name": booking.caller_name,
            "caller_phone": booking.caller_phone,
            "appointment_date": booking.date_text,
            "appointment_time": booking.time_text,
            "channel": booking.channel,
        },
    }


def suggest_booking_follow_up(booking: Booking) -> dict[str, Any]:
    """Follow-up for a confirmed booking: confirm with the business.

    The clinic confirms the slot; the agent's job ends at the booking.
    (EnhancedCRM.suggest_follow_up scores leads — it does not schedule;
    this dict is the schedule the ToolBus can file.)
    """
    return {
        "due": f"next business day after {booking.date_text}",
        "channel": "phone",
        "note": (
            f"Confirm {booking.service} appointment for {booking.caller_name} "
            f"({booking.caller_phone}) on {booking.date_text} at {booking.time_text}."
        ),
    }


# ---------------------------------------------------------------------------
# Specialist agents (one per demo channel)
# ---------------------------------------------------------------------------


def _agent_output_for_result(
    agent_id: str,
    result: BookingResult,
    tenant_id: str,
) -> AgentOutput:
    if result.decision == "BOOKED" and result.booking is not None:
        booking = result.booking
        lead = build_booking_lead(tenant_id, booking)
        follow_up = suggest_booking_follow_up(booking)
        return AgentOutput(
            agent_id=agent_id,
            decision="BOOKED",
            reasoning_summary=(
                f"5/5 booking fields collected over {len(result.transcript)} turns; "
                f"service matched '{booking.service}' from the business's own list; "
                "caller confirmed the booking."
            ),
            confidence=1.0,
            evidence_refs=[
                f"service={booking.service}",
                f"caller={booking.caller_name}",
                f"phone={booking.caller_phone}",
                f"date={booking.date_text}",
                f"time={booking.time_text}",
            ],
            proposed_actions=[
                ProposedAction(
                    action_type="lead_create",
                    target="crm_lead",
                    params=lead,
                    rationale="Confirmed booking becomes a new lead in Cortex CRM.",
                    side_effect_level="WRITE",
                ),
                ProposedAction(
                    action_type="follow_up_schedule",
                    target="crm_follow_up",
                    params=follow_up,
                    rationale="Clinic confirms the slot with the caller.",
                    side_effect_level="WRITE",
                ),
                ProposedAction(
                    action_type="conversation_log",
                    target="crm_conversation",
                    params={
                        "channel": booking.channel,
                        "turns": [
                            {"role": t.role, "text": t.text} for t in result.transcript
                        ],
                    },
                    rationale="Full transcript filed against the lead.",
                    side_effect_level="READ",
                ),
            ],
            expected_outcomes={"lead_id": lead["id"], "booking": lead["metadata"]},
        )
    if result.decision == "OUT_OF_SCOPE":
        return AgentOutput(
            agent_id=agent_id,
            decision="OUT_OF_SCOPE",
            reasoning_summary=(
                f"Caller asked for '{result.out_of_scope_request}', which is not "
                "in the business's services list; no booking was made and no "
                "service was invented."
            ),
            confidence=1.0,
            evidence_refs=[f"requested={result.out_of_scope_request}"],
            proposed_actions=[
                ProposedAction(
                    action_type="message_relay",
                    target="business_inbox",
                    params={"message": result.out_of_scope_request},
                    rationale="Pass the out-of-scope request to the business.",
                    side_effect_level="WRITE",
                )
            ],
            required_approvals=["business_follow_up"],
        )
    if result.decision == "REFUSED_NO_SERVICES":
        return AgentOutput(
            agent_id=agent_id,
            decision="REFUSED_NO_SERVICES",
            reasoning_summary="No services text was provided, so no prompt or booking was attempted.",
            confidence=0.0,
            required_approvals=["provide_services_text"],
        )
    return AgentOutput(
        agent_id=agent_id,
        decision="NEEDS_INFO",
        reasoning_summary=(
            "Booking incomplete — still missing: " + ", ".join(result.missing) + "."
        ),
        confidence=0.5,
        evidence_refs=[f"missing={','.join(result.missing)}"],
        proposed_actions=[
            ProposedAction(
                action_type="conversation_log",
                target="crm_conversation",
                params={
                    "turns": [
                        {"role": t.role, "text": t.text} for t in result.transcript
                    ],
                },
                rationale="Partial transcript filed; no lead created for an unconfirmed booking.",
                side_effect_level="READ",
            )
        ],
    )


class _ConversationalAgentBase(SpecialistAgent):
    """Shared process() for both demo channels; subclasses fix the channel."""

    channel: str = "voice"

    def __init__(self, agent_id: str, domain: str):
        super().__init__(
            agent_id=agent_id,
            domain=domain,
            capabilities=["voice_booking" if self.channel == "voice" else "chat_booking", "lead_create", "follow_up_schedule"],
        )

    async def process(self, input_data: AgentInput) -> AgentOutput:
        context = input_data.context or {}
        business_name = str(context.get("business_name", "") or "")
        services_text = str(context.get("services_text", "") or "")
        niche = str(context.get("niche", "") or "")
        languages = str(context.get("languages", "") or "")
        turns = list(context.get("turns", []) or [])
        tenant_id = str(
            (input_data.identity_scope or {}).get("tenant_id", "demo-tenant") or "demo-tenant"
        )
        if not services_text.strip():
            result = BookingResult(decision="REFUSED_NO_SERVICES")
            return _agent_output_for_result(self.agent_id, result, tenant_id)
        engine = ConversationEngine(
            business_name=business_name,
            services_text=services_text,
            niche=niche,
            channel=self.channel,
            languages=languages,
        )
        result = engine.run([str(t) for t in turns])
        return _agent_output_for_result(self.agent_id, result, tenant_id)


class ClinicAppointmentVoiceAgent(_ConversationalAgentBase):
    """Demo 1 — clinic appointment VOICE agent (OmniDimension pattern).

    Triggered by voice-call events; the caller talks, the agent books, and
    the booking lands as a lead + follow-up in Cortex CRM.
    """

    channel = "voice"

    def __init__(self):
        super().__init__(agent_id="agent_conversational_voice", domain="conversational_voice")


class WebsiteChatBookingAgent(_ConversationalAgentBase):
    """Demo 2 — website CHAT agent that books appointments (Voiceflow pattern).

    Triggered by chat-message events; the visitor chats, the agent books,
    and the booking lands as a lead + follow-up in Cortex CRM.
    """

    channel = "chat"

    def __init__(self):
        super().__init__(agent_id="agent_conversational_chat", domain="conversational_chat")
