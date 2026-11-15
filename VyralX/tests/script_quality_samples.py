"""Sample scripts for the VyralX script-quality system (TASK-VYR-007).

Four GOOD scripts (one per lane/format pairing the channel will actually
run) set the quality bar; four FLAWED scripts prove the scorer catches
the failure modes that sank the old autopilot: throat-clearing hooks,
incomplete countdowns, missing payoffs, template repeats, deceptive
framing and hooks that cannot fit in three seconds.

Used by tests/test_script_quality.py and scripts/run_script_quality_samples.py.
Facts in the good samples are the well-documented ones (Betelgeuse's
size, Pompeii's bakery loaves, Face ID's 30,000-dot grid, Neptune's
diamond rain) - samples are held to the same honesty bar as production.
"""
from __future__ import annotations

GOOD_SPACE_ONE_FACT = {
    "id": "good_space_one_fact",
    "lane": "space_science",
    "format": "one_fact",
    "hook_formula": "scale_anchor",
    "hook": "If Earth were a marble, Betelgeuse fills a stadium.",
    "beats": [
        "If Earth were a marble, Betelgeuse fills a stadium.",
        "Betelgeuse is a red supergiant star, roughly 700 times wider than our Sun.",
        "Place it where the Sun sits, and its surface would swallow the orbit of Jupiter whole.",
        "But light still needs almost an hour just to cross from one side of it to the other.",
        "Astronomers watch this star constantly, because something this large does not die quietly - it collapses, then explodes.",
        "So the next time you see that red shoulder in Orion, remember: one marble, one stadium, one star.",
    ],
    "expect": {"verdict": "PASS"},
}

GOOD_SPACE_TOP5 = {
    "id": "good_space_top5",
    "lane": "space_science",
    "format": "top5",
    "hook_formula": "countdown_promise",
    "hook": "Five worlds stranger than ours - number one rains diamonds.",
    "beats": [
        "Five worlds stranger than ours - number one rains diamonds.",
        "Number five: Venus, hot enough to melt lead, spinning backwards under crushing acid clouds.",
        "Number four: Titan, where rivers of liquid methane carve valleys beneath an orange sky.",
        "Number three: Jupiter, whose great storm has raged wider than planet Earth for 300 years.",
        "Number two: Enceladus, spraying its hidden ocean into space through cracks in the ice.",
        "Number one: Neptune, where pressure crushes carbon into diamonds that rain through the dark.",
        "Five worlds out there, and not one of them plays by Earth's rules.",
    ],
    "expect": {"verdict": "PASS"},
}

GOOD_HISTORY_STORY = {
    "id": "good_history_story",
    "lane": "history_facts",
    "format": "story",
    "hook_formula": "story_cold_open",
    "hook": "79 AD, Pompeii. A baker loads his oven with bread.",
    "beats": [
        "79 AD, Pompeii. A baker loads his oven with bread.",
        "He never came back for it. By noon, Mount Vesuvius had buried the Roman city under ash.",
        "The ruins stayed hidden for almost 1,700 years, the streets frozen exactly as they were.",
        "Then archaeologists found hollow shapes in the ash - people, animals, even furniture, turned to ghosts.",
        "In one bakery they found an oven still sealed, and inside it, 81 loaves of bread.",
        "The loaves were carbonised but whole, every one stamped with the baker's own name.",
        "His bread outlived the baker.",
    ],
    "expect": {"verdict": "PASS"},
}

GOOD_TECH_ONE_FACT = {
    "id": "good_tech_one_fact",
    "lane": "tech_ai",
    "format": "one_fact",
    "hook_formula": "question_gap",
    "hook": "Why does Face ID work in total darkness?",
    "beats": [
        "Why does Face ID work in total darkness?",
        "Your phone is not really looking at you with its camera at all.",
        "A flood illuminator fires 30,000 invisible infrared dots onto your face in a grid, even in pitch black.",
        "Those dots bend around your nose and eyes, but together they draw a depth map of your face.",
        "That map is more detailed than a fingerprint, and the phone rebuilds it at every single unlock.",
        "Which means your face is the password - and darkness was never a lock at all.",
    ],
    "expect": {"verdict": "PASS"},
}

FLAWED_TECH_TOP5 = {
    "id": "flawed_tech_top5",
    "lane": "tech_ai",
    "format": "top5",
    "hook_formula": "countdown_promise",
    "hook": "Hey guys, welcome back to another video about phones.",
    "beats": [
        "Hey guys, welcome back to another video about phones.",
        "Today we are counting down some phone features that are pretty cool.",
        "Number three: some phones have a very good camera for taking photos.",
        "Number two: some phones have a big battery that lasts a long time.",
        "Number one: some phones are fast and have nice screens and stuff.",
        "So yeah, that is it for today, make sure to subscribe for more videos.",
    ],
    "expect": {"verdict_in": ["REVISE", "REJECT"], "notes_contain": ["throat-clearing", "countdown incomplete"]},
}

FLAWED_HISTORY_REPEAT = {
    "id": "flawed_history_repeat",
    "lane": "history_facts",
    "format": "story",
    "hook_formula": "story_cold_open",
    "hook": "79 AD, Pompeii. A baker puts his loaves in the oven.",
    "beats": [
        "79 AD, Pompeii. A baker puts his loaves in the oven.",
        "He never returned for them. By midday, Mount Vesuvius had buried the Roman city in ash.",
        "The ruins stayed hidden for nearly 1,700 years, the streets frozen exactly as they were.",
        "Then archaeologists found hollow shapes in the ash - people, animals, even furniture, turned to ghosts.",
        "In one bakery they found an oven still sealed, and inside it, 81 loaves of bread.",
        "The loaves were carbonised but whole, every one stamped with the baker's own name.",
        "His bread outlived the baker.",
    ],
    # Scored with recent=[GOOD_HISTORY_STORY's result] - must trip the
    # anti-template gate even though the script is 'good' in isolation.
    "expect": {"verdict": "REJECT", "gate_contains": "template_repeat"},
}

FLAWED_SPACE_BANNED = {
    "id": "flawed_space_banned",
    "lane": "space_science",
    "format": "one_fact",
    "hook_formula": "reveal_delay",
    "hook": "NASA doesn't want you to know this about the Moon.",
    "beats": [
        "NASA doesn't want you to know this about the Moon.",
        "Astronomers found a structure on the far side that should not exist.",
        "It is larger than any crater and perfectly geometric in shape.",
        "Officials have refused to comment on it for over fifty years.",
        "Share this before it gets deleted, because the truth matters.",
    ],
    "expect": {"verdict": "REJECT", "gate_contains": "banned_content"},
}

FLAWED_HOOK_TOO_LONG = {
    "id": "flawed_hook_too_long",
    "lane": "history_facts",
    "format": "one_fact",
    "hook_formula": "number_shock",
    "hook": "This is the incredible and absolutely unbelievable story of how one single letter changed the entire course of an empire forever.",
    "beats": [
        "This is the incredible and absolutely unbelievable story of how one single letter changed the entire course of an empire forever.",
        "The empire in question ruled for centuries and shaped the modern world.",
        "One day a letter arrived that changed everything for everyone involved.",
        "Historians still talk about it today because it mattered so much.",
        "And that is why this story is still told in classrooms everywhere.",
    ],
    "expect": {"verdict": "REJECT", "gate_contains": "hook_too_long"},
}

SAMPLES = [
    GOOD_SPACE_ONE_FACT,
    GOOD_SPACE_TOP5,
    GOOD_HISTORY_STORY,
    GOOD_TECH_ONE_FACT,
    FLAWED_TECH_TOP5,
    FLAWED_HISTORY_REPEAT,
    FLAWED_SPACE_BANNED,
    FLAWED_HOOK_TOO_LONG,
]
