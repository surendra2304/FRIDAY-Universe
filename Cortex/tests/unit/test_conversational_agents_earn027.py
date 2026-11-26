"""TASK-EARN-027 — Cortex conversational voice/chat appointment agents.

Checkpoint 1: the new agent family (``cortex_agents.conversational_agent``)
books appointments from scripted caller turns, proposes the CRM landing
(lead + follow-up), refuses to invent services, and routes by event type.
Runs in the Cortex tier-1 CI invocation (see friday-universe-ci.yml).

Demo services text is the clinics' own public wording, read first-hand
from their sites on 2026-11-25 (Spotlight Dental, spotlightdental.in;
Dentaire, dentaire.co.in). Demo dates are real calendar days: Friday
27 November 2026 and Saturday 28 November 2026.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath("packages/agents/src"))
sys.path.insert(0, os.path.abspath("packages/core/src"))
sys.path.insert(0, os.path.abspath("packages/event_schema/src"))
sys.path.insert(0, os.path.abspath("packages/ai_universe_adapter/src"))
sys.path.insert(0, os.path.abspath("packages/tool_runtime/src"))
sys.path.insert(0, os.path.abspath("packages/integrations/src"))
sys.path.insert(0, os.path.abspath("packages/policy_engine/src"))
sys.path.insert(0, os.path.abspath("packages/workflow_engine/src"))
sys.path.insert(0, os.path.abspath("."))

from cortex_agents import AgentInput, AgentRegistry  # noqa: E402
from cortex_agents.conversational_agent import (  # noqa: E402
    ClinicAppointmentVoiceAgent,
    ConversationEngine,
    ConversationalError,
    WebsiteChatBookingAgent,
    build_appointment_agent_prompt,
    build_booking_lead,
    parse_services,
)

# Spotlight Dental, Banjara Hills — services verbatim from
# https://www.spotlightdental.in/ (fetched 2026-11-25). The site offers
# "Call for Appointment" only: no online booking, no chatbot.
SPOTLIGHT_SERVICES = """Teeth Whitening
Dental Implants
Laser Dentistry
Dental Consultation & Examination
Teeth Cleaning & Polishing
Tooth-Coloured Fillings
Root Canal Treatment
Dental Crowns & Bridges
Complete Dentures & Removable Partial Dentures
Full-Mouth Rehabilitation
Smile Design
Laminates & Veneers
Orthodontic Braces
Clear Aligners & Invisalign
Wisdom Tooth Removal
Tooth Extraction
Minor Oral Surgeries
Gum Disease Treatment
Pediatric Dentistry
TMJ Pain-Dysfunction Diagnosis & Treatment
Occlusal Splints & Night Guards
Digital Dentistry"""

# Dentaire, Banjara Hills — services as stated on https://dentaire.co.in/
# (fetched 2026-11-25): routine check-up, cosmetic dentistry, fillings,
# crowns, teeth cleaning, root canal assessment, wisdom tooth removal,
# orthodontic braces, clear aligners (Invisalign), elderly dentistry.
DENTAIRE_SERVICES = """Routine check-up
Cosmetic dentistry
Fillings
Crowns
Teeth cleaning
Root canal assessment
Wisdom tooth removal
Orthodontic braces
Clear aligners (Invisalign)
Elderly dentistry"""


def _voice_input(turns, services=SPOTLIGHT_SERVICES, business="Spotlight Dental"):
    return AgentInput(
        goal="Book an appointment",
        context={
            "business_name": business,
            "services_text": services,
            "niche": "dental clinic",
            "languages": "English, Hindi, Telugu",
            "turns": turns,
        },
        identity_scope={"tenant_id": "tenant-spotlight"},
    )


def _chat_input(turns, services=DENTAIRE_SERVICES, business="Dentaire"):
    return AgentInput(
        goal="Book an appointment",
        context={
            "business_name": business,
            "services_text": services,
            "niche": "dental clinic",
            "languages": "English, Hindi, Telugu",
            "turns": turns,
        },
        identity_scope={"tenant_id": "tenant-dentaire"},
    )


# --- F-35 prompt builder -------------------------------------------------


def test_prompt_embeds_business_and_services_only():
    prompt = build_appointment_agent_prompt(
        "Spotlight Dental", SPOTLIGHT_SERVICES, niche="dental clinic"
    )
    assert "Spotlight Dental" in prompt
    assert "Root Canal Treatment" in prompt
    assert "Teeth Whitening" in prompt
    # Nothing invented: a service the business does not list is absent.
    assert "Botox" not in prompt
    assert "Hair Transplant" not in prompt


def test_prompt_refuses_without_services_text():
    with pytest.raises(ConversationalError):
        build_appointment_agent_prompt("Spotlight Dental", "")
    with pytest.raises(ConversationalError):
        build_appointment_agent_prompt("Spotlight Dental", "   ")


def test_prompt_refuses_without_business_name():
    with pytest.raises(ConversationalError):
        build_appointment_agent_prompt("", SPOTLIGHT_SERVICES)


def test_parse_services_strips_bullets_and_blanks():
    assert parse_services("- Teeth Whitening\n• Dental Implants\n\n2. Laser Dentistry") == [
        "Teeth Whitening",
        "Dental Implants",
        "Laser Dentistry",
    ]
    assert parse_services(SPOTLIGHT_SERVICES)[0] == "Teeth Whitening"
    assert len(parse_services(SPOTLIGHT_SERVICES)) == 22


# --- Demo 1: voice agent, full booking -----------------------------------


async def test_voice_agent_books_spotlight_root_canal():
    agent = ClinicAppointmentVoiceAgent()
    output = await agent.process(
        _voice_input(
            [
                "I need a root canal",
                "Ananya Sharma",
                "+91 98765 43210",
                "Friday, 27 November 2026",
                "11:00 AM",
                "Yes, that's correct",
            ]
        )
    )
    assert output.decision == "BOOKED"
    assert output.agent_id == "agent_conversational_voice"
    assert output.confidence == 1.0
    assert "service=Root Canal Treatment" in output.evidence_refs
    assert "date=Friday, 27 November 2026" in output.evidence_refs
    assert "time=11:00 AM" in output.evidence_refs

    by_type = {a.action_type: a for a in output.proposed_actions}
    lead_action = by_type["lead_create"]
    assert lead_action.side_effect_level == "WRITE"
    assert lead_action.target == "crm_lead"
    lead = lead_action.params
    # Lead params map 1:1 onto the Cortex Lead model / leads table.
    assert lead["tenant_id"] == "tenant-spotlight"
    assert lead["status"] == "new"
    assert lead["source"] == "voice_agent"
    assert lead["metadata"]["service"] == "Root Canal Treatment"
    assert lead["metadata"]["caller_name"] == "Ananya Sharma"
    assert lead["metadata"]["caller_phone"] == "+91 98765 43210"
    assert lead["metadata"]["appointment_date"] == "Friday, 27 November 2026"
    assert lead["metadata"]["appointment_time"] == "11:00 AM"
    assert lead["metadata"]["channel"] == "voice"

    follow_up = by_type["follow_up_schedule"].params
    assert "Ananya Sharma" in follow_up["note"]
    assert "Root Canal Treatment" in follow_up["note"]

    assert "conversation_log" in by_type
    assert output.expected_outcomes["lead_id"] == lead["id"]


async def test_voice_agent_out_of_scope_service_is_not_booked():
    agent = ClinicAppointmentVoiceAgent()
    output = await agent.process(_voice_input(["I want Botox"]))
    assert output.decision == "OUT_OF_SCOPE"
    assert not [a for a in output.proposed_actions if a.action_type == "lead_create"]
    assert "business_follow_up" in output.required_approvals
    assert "Botox" in output.reasoning_summary


async def test_voice_agent_needs_info_when_turns_run_out():
    agent = ClinicAppointmentVoiceAgent()
    output = await agent.process(
        _voice_input(["Teeth cleaning", "Ravi Kumar"])
    )
    assert output.decision == "NEEDS_INFO"
    assert "caller_phone" in output.reasoning_summary
    assert not [a for a in output.proposed_actions if a.action_type == "lead_create"]


async def test_voice_agent_refuses_without_services_text():
    agent = ClinicAppointmentVoiceAgent()
    output = await agent.process(_voice_input(["Root canal"], services=""))
    assert output.decision == "REFUSED_NO_SERVICES"
    assert "provide_services_text" in output.required_approvals
    assert output.proposed_actions == []


# --- Demo 2: chat agent, full booking ------------------------------------


async def test_chat_agent_books_dentaire_checkup():
    agent = WebsiteChatBookingAgent()
    output = await agent.process(
        _chat_input(
            [
                "I want a routine check-up",
                "Ravi Kumar",
                "+91 91234 56780",
                "Saturday, 28 November 2026",
                "4:00 PM",
                "Yes",
            ]
        )
    )
    assert output.decision == "BOOKED"
    assert output.agent_id == "agent_conversational_chat"
    by_type = {a.action_type: a for a in output.proposed_actions}
    lead = by_type["lead_create"].params
    assert lead["source"] == "chat_agent"
    assert lead["metadata"]["service"] == "Routine check-up"
    assert lead["metadata"]["caller_name"] == "Ravi Kumar"
    assert lead["metadata"]["appointment_date"] == "Saturday, 28 November 2026"


# --- Engine unit checks ---------------------------------------------------


def test_engine_transcript_records_every_turn():
    engine = ConversationEngine(
        "Spotlight Dental", SPOTLIGHT_SERVICES, channel="voice"
    )
    result = engine.run(
        [
            "Teeth cleaning",
            "Meera",
            "9876543210",
            "Friday, 27 November 2026",
            "10:00 AM",
            "Yes",
        ]
    )
    assert result.decision == "BOOKED"
    assert result.booking is not None
    assert result.booking.service == "Teeth Cleaning & Polishing"
    assert result.booking.caller_phone == "9876543210"
    roles = [t.role for t in result.transcript]
    assert roles[0] == "agent"  # greeting first
    assert roles.count("caller") == 6
    assert result.system_prompt.startswith(
        "You are the appointment-booking assistant for Spotlight Dental"
    )


def test_build_booking_lead_is_deterministic():
    engine = ConversationEngine("Spotlight Dental", SPOTLIGHT_SERVICES)
    result = engine.run(
        ["Dental implants", "Kiran", "+91 99999 11111",
         "Friday, 27 November 2026", "5:00 PM", "Confirmed"]
    )
    assert result.decision == "BOOKED"
    lead_a = build_booking_lead("t1", result.booking)
    lead_b = build_booking_lead("t1", result.booking)
    assert lead_a == lead_b
    assert lead_a["id"].startswith("lead_voice_919999911111_")


# --- Registry + routing ---------------------------------------------------


def test_registry_registers_both_conversational_agents():
    registry = AgentRegistry()
    assert registry.get("agent_conversational_voice") is not None
    assert registry.get("conversational_voice") is not None
    assert registry.get("agent_conversational_chat") is not None
    assert registry.get("conversational_chat") is not None


def test_routing_sends_conversation_events_to_conversational_agents():
    registry = AgentRegistry()
    assert registry.route_for_event("appointment_booked").agent_id == "agent_conversational_voice"
    assert registry.route_for_event("voice_call_started").agent_id == "agent_conversational_voice"
    assert registry.route_for_event("chat_message_received").agent_id == "agent_conversational_chat"
    # COR-004 pin: "booked" must NOT steal this one — it stays with sales.
    assert registry.route_for_event("sales_meeting_booked").agent_id == "agent_sales"
