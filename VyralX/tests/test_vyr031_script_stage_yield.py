"""TASK-VYR-031: script-stage yield fix.

The script stage lost ~42% of attempts at the quality gates (cycle 2:
5 script_unverifiable of 12 attempts) while the candidate pool (111)
and the voice audition (1 second pass, 0 disagreements) were healthy.
Two structural causes, both fixed here:

1. The editorial prompts told the model the strict rules only AFTER a
   rejection (feedback block). The first draft was written blind to the
   checkable-claims rules (colour / clothing / time of day / posture /
   emotion / eye state) and, on the commentary path, to the
   description-question grounding rule — so attempt 1 was near-guaranteed
   to fail and the 3-attempt budget burned on re-rolls.
2. check_structure's paraphrased-repeat rule fired on legitimate beat
   progression: the prompt writes one sentence per beat and every
   sentence names something concrete, so adjacent beats share the
   clip's central objects. Two beats sharing backdrop nouns is
   progression, not repetition — the rule now also requires a shared
   action verb from the record (job 721's switch reach still fails).
"""
from __future__ import annotations

import json

from app.services import viral_framing, viral_quality as vq
from app.services import viral_remix as vr
from test_vyr014_quality_gates import RECORD_721, RECORD_741, RECORD_761


def kinds(violations) -> set[str]:
    return {violation.kind for violation in violations}


# --------------------------------------------------------------------------- #
# fixtures — prompt-compliant, fully-grounded drafts
# --------------------------------------------------------------------------- #
DRAFTS_761 = [
    # Plain beat-by-beat narration; central objects recur naturally.
    ("Watch his face when the phone photo appears in bright daylight. "
     "She laughs and runs right past him under the string lights. "
     "He just stands there grinning with both hands over his mouth."),
    ("The phone photo pops up and his whole face changes in daylight. "
     "Under the string lights she runs past him laughing. "
     "He stands grinning with both hands over his mouth."),
    ("His face freezes the second the phone photo appears. "
     "She runs past laughing under the string lights. "
     "Both hands fly to his mouth as he grins."),
    ("Watch the phone photo land in bright daylight. "
     "She laughs and runs past him under the string lights. "
     "That same phone photo leaves him grinning with both hands over his mouth."),
]

DRAFTS_741 = [
    ("A man lies on the white tiles holding a phone. "
     "The woman presses her pink-gloved hand flat against the wall beside the red handprint. "
     "The man lies still on the tiles with the phone beside him."),
    # Beat progression, not repetition: beat 2 presses the hand, beat 3
    # is the man lying still while the handprint stays — the two adjacent
    # sentences share only the backdrop nouns (handprint, wall).
    ("He lies on the tiles holding the phone. "
     "Her pink-gloved hand presses flat against the wall by the red handprint. "
     "He stays still on the tiles as the handprint stays on the wall."),
    ("The phone stays beside him on the white tiles. "
     "A pink-gloved hand flattens against the wall next to the red handprint. "
     "The red handprint is still there while the man lies still."),
]

RECORD_DOG = {
    "beats": [
        {"setting": "living room", "time_of_day": "indoor",
         "subjects": [{"hair": "dark", "clothing": "grey shirt", "posture": "sitting",
                       "action": "pressing buttons on a panel", "emotion": "calm",
                       "eyes": "open"}],
         "objects": ["buttons", "panel"],
         "summary": "A man sits pressing buttons on a panel while a dog watches."},
        {"setting": "living room", "time_of_day": "indoor",
         "subjects": [{"hair": "dark", "clothing": "grey shirt", "posture": "sitting",
                       "action": "pressing the buttons again", "emotion": "calm",
                       "eyes": "open"}],
         "objects": ["buttons", "panel"],
         "summary": "The man keeps pressing the buttons while the dog watches every move."},
        {"setting": "living room", "time_of_day": "indoor",
         "subjects": [{"hair": "dark", "clothing": "grey shirt", "posture": "sitting",
                       "action": "pressing the last button", "emotion": "calm",
                       "eyes": "open"}],
         "objects": ["buttons"],
         "summary": "The man presses the last button and the dog looks away."},
    ],
    "event_arc": "The man presses buttons while the dog watches.",
    "static": False,
}

# Same action restated in adjacent sentences: hook and setup both cover
# the man pressing the buttons. This IS the repetition the gate is for.
DOG_REPEAT = (
    "Watch the dog stare at the man pressing the buttons. "
    "The man keeps pressing the buttons while the dog watches every move. "
    "The dog finally looks away as the man presses the last button."
)

COMMENTARY_721 = (
    "He sits on the floor holding a small teapot beside a woman in a pink robe. "
    "Then he reaches up to press a wall switch while she crouches right beside him. "
    "Finally he holds his arm toward the switch while she laughs and reaches for him. "
    "This poor ghost routine is legendary."
)


def full_gate_suite(commentary: str, record: dict, duration: float):
    """The commentary path's pre-render gate suite (see produce_viral_short)."""
    return (
        vq.check_consistency(commentary=commentary, record=record)
        + vq.check_structure(commentary=commentary, record=record)
        + vq.check_script_length(commentary=commentary, duration=duration)
    )


# --------------------------------------------------------------------------- #
# the gate fix — beat progression is not repetition
# --------------------------------------------------------------------------- #
def test_beat_progression_is_not_repetition():
    # DRAFTS_741[1] failed check_structure on main (repeated_action):
    # its last two sentences share "handprint" and "wall", but they
    # narrate different beats with different subjects and actions.
    assert kinds(vq.check_structure(
        commentary=DRAFTS_741[1], record=RECORD_741,
    )) == set()


def test_job721_repetition_still_rejected():
    # The case the rule was written for: the switch reach, twice, with
    # the shared action verb ("reaches" / "reaching" -> "reach").
    assert "repeated_action" in kinds(vq.check_structure(
        commentary=COMMENTARY_721, record=RECORD_721,
    ))


def test_same_action_restated_still_rejected():
    # Adjacent sentences restating the same recorded action (pressing
    # the buttons) still trip the gate — the fix exempts shared backdrop
    # nouns, not a shared action.
    assert "repeated_action" in kinds(vq.check_structure(
        commentary=DOG_REPEAT, record=RECORD_DOG,
    ))


def test_stem_matches_verb_forms():
    assert vq._stem("reaches") == vq._stem("reaching") == "reach"
    assert vq._stem("presses") == vq._stem("pressing") == "press"
    assert vq._stem("runs") == vq._stem("running") == "run"
    assert vq._stem("holds") == vq._stem("holding") == "hold"
    assert vq._stem("lies") == vq._stem("lying")
    assert vq._stem("switch") == "switch"


def test_action_verbs_come_from_record_actions():
    vocab = vq.record_vocabulary(RECORD_721)
    assert "reach" in vocab.action_verbs
    assert "hold" in vocab.action_verbs
    assert "wall" not in vocab.action_verbs
    assert "switch" not in vocab.action_verbs


def test_prompt_compliant_drafts_pass_the_full_gate_suite():
    # The yield probe: every draft below follows generate_editorial's
    # instructions (one sentence per beat, in order; every sentence
    # names something concrete; hook <= 18 words; payoff on the final
    # beat) and is fully grounded. On main, DRAFTS_741[1] failed.
    for draft in DRAFTS_761:
        assert full_gate_suite(draft, RECORD_761, 21.0) == []
    for draft in DRAFTS_741:
        assert full_gate_suite(draft, RECORD_741, 25.0) == []


# --------------------------------------------------------------------------- #
# the prompt fix — the strict rules are stated before the first draft
# --------------------------------------------------------------------------- #
_CLAIM_RULES = (
    "Never state a colour, item of clothing, time of day, posture, emotion "
    "or eye state that the frame analysis does not record."
)
_QUESTION_RULE = (
    "The question must name a concrete object, person or action from the "
    "frame analysis"
)


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def _capture_prompt(monkeypatch, module, payload):
    captured: dict = {}

    def fake_post(url, **kwargs):
        captured.update(kwargs.get("json") or {})
        return _Response(payload)

    monkeypatch.setattr(module.httpx, "post", fake_post)
    return captured


def test_editorial_prompt_states_claim_rules_up_front(monkeypatch):
    package = {
        "title": "Keeper Pulls Off Impossible Save #Shorts",
        "commentary": "Watch the keeper dive and somehow keep it out.",
        "description": "An impossible save.\n\nDid you spot the keeper?\n\n#Shorts",
    }
    payload = {"choices": [{"message": {"content": json.dumps(package)}}]}
    captured = _capture_prompt(monkeypatch, vr, payload)
    result = vr.generate_editorial(
        "SPORTS", "Original title", "Channel", "transcript text", 21.0, scene=""
    )
    assert result["commentary"] == package["commentary"]
    user_prompt = captured["messages"][1]["content"]
    # The rules were previously only in the post-rejection feedback
    # block; a first draft written without them was near-guaranteed to
    # fail consistency and burn one of three attempts.
    assert _CLAIM_RULES in user_prompt
    assert _QUESTION_RULE in user_prompt
    assert "REJECTED by the footage checker" not in user_prompt


def test_framing_prompt_states_claim_rules_up_front(monkeypatch):
    package = {
        "title": "Keeper Pulls Off Impossible Save #Shorts",
        "hook": "Watch this keeper somehow keep it out.",
        "payoff": "That save wins the match on its own.",
        "description": "An impossible save.\n\nDid you spot the keeper?\n\n#Shorts",
    }
    payload = {"choices": [{"message": {"content": json.dumps(package)}}]}
    captured = _capture_prompt(monkeypatch, viral_framing, payload)
    result = viral_framing.generate_framing(
        "SPORTS", "Original title", "Channel", "transcript text",
        scene="a keeper dives",
    )
    assert result["hook"] == package["hook"]
    user_prompt = captured["messages"][1]["content"]
    assert _CLAIM_RULES in user_prompt
    assert "REJECTED by the footage checker" not in user_prompt
