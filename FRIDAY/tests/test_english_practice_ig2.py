"""
test_english_practice_ig2.py — TASK-IG2-VOI-01 (IG cluster #111).

Guards the PeerUp-pattern spoken-English practice mode: the
deterministic correction engine (per-sentence correction + error
label + tip), its false-positive guards, session scoring, and the
skill surface that chat/voice turns reach.
"""

from friday.skills.english_practice import EnglishPracticeSkill, extract_practice_sentence
from friday.voice.english_practice import (
    EnglishPracticeSession,
    correct_sentence,
)


def _labels(feedback) -> list[str]:
    return [c.label for c in feedback.corrections]


# --- Engine: one labelled correction per error class -----------------

def test_agreement_dont_becomes_doesnt_for_third_person():
    fb = correct_sentence("He don't like coffee.")
    assert fb.corrected == "He doesn't like coffee."
    assert fb.headline_label == "Subject–verb agreement"
    assert not fb.is_clean


def test_agreement_doesnt_becomes_dont_for_plural():
    fb = correct_sentence("They doesn't know the answer.")
    assert fb.corrected == "They don't know the answer."
    assert "Subject–verb agreement" in _labels(fb)


def test_past_tense_after_yesterday():
    fb = correct_sentence("Yesterday I go to the market.")
    assert fb.corrected == "Yesterday I went to the market."
    assert "Verb tense" in _labels(fb)


def test_article_a_before_vowel_becomes_an():
    fb = correct_sentence("I ate a apple.")
    assert fb.corrected == "I ate an apple."
    assert "Article (a/an)" in _labels(fb)


def test_article_an_before_consonant_becomes_a():
    fb = correct_sentence("She bought an book.")
    assert fb.corrected == "She bought a book."


def test_double_comparative():
    fb = correct_sentence("This phone is more better.")
    assert fb.corrected == "This phone is better."
    assert "Double comparative" in _labels(fb)


def test_redundant_preposition():
    fb = correct_sentence("We will discuss about the plan.")
    assert fb.corrected == "We will discuss the plan."
    assert "Unnecessary preposition" in _labels(fb)


def test_i_am_agree_structure():
    fb = correct_sentence("I am agree with you.")
    assert fb.corrected == "I agree with you."
    assert "Sentence structure and clarity" in _labels(fb)


def test_capitalisation_and_punctuation_are_labelled():
    fb = correct_sentence("i went home")
    assert fb.corrected == "I went home."
    assert "Capitalisation" in _labels(fb)
    assert "End punctuation" in _labels(fb)


def test_render_carries_label_and_tip():
    fb = correct_sentence("He don't like coffee.")
    rendered = fb.render()
    assert "doesn't" in rendered
    assert "Error: Subject–verb agreement." in rendered


# --- Engine: false-positive guards (never "fix" correct English) ----

def test_clean_sentence_stays_clean():
    fb = correct_sentence("She goes to school every day.")
    assert fb.is_clean
    assert fb.corrected == "She goes to school every day."


def test_a_university_is_not_fixed():
    fb = correct_sentence("He studies at a university.")
    assert "an university" not in fb.corrected
    assert fb.is_clean


def test_an_hour_is_not_fixed():
    fb = correct_sentence("The train leaves in an hour.")
    assert fb.corrected == "The train leaves in an hour."
    assert fb.is_clean


def test_empty_input_is_guidance_not_an_attempt():
    session = EnglishPracticeSession()
    fb = session.practice("   ")
    assert session.attempts == 0
    assert "Sentence structure and clarity" in _labels(fb)


# --- Session scoring ---------------------------------------------------

def test_session_tracks_attempts_clean_and_labels():
    session = EnglishPracticeSession()
    session.practice("He don't like coffee.")
    session.practice("She goes to school every day.")
    session.practice("They doesn't know.")
    summary = session.summary()
    assert summary["attempts"] == 3
    assert summary["clean"] == 1
    assert summary["top_error_labels"][0] == {"label": "Subject–verb agreement", "count": 2}
    assert "1/3" in session.summary_text()


def test_prompts_rotate():
    session = EnglishPracticeSession()
    first = session.next_prompt()
    session.practice("I went home.")
    assert session.next_prompt() != first


# --- Skill surface -----------------------------------------------------

def test_skill_matches_practice_requests():
    skill = EnglishPracticeSkill()
    assert skill.can_handle("practice english: He don't know")
    assert skill.can_handle("correct my english: a apple")
    assert skill.can_handle("I want spoken english practice")
    assert not skill.can_handle("what is the weather today")


def test_extract_sentence_shapes():
    assert extract_practice_sentence("practice english: He don't know") == "He don't know"
    assert extract_practice_sentence("correct my english: a apple") == "a apple"
    assert extract_practice_sentence("practice english He don't know") == "He don't know"
    assert extract_practice_sentence("english practice") is None
    assert extract_practice_sentence("english practice score") is None


def test_skill_corrects_and_renders():
    skill = EnglishPracticeSkill()
    result = skill.execute("practice english: He don't like coffee")
    assert result.success
    assert "doesn't" in result.output
    assert "Subject–verb agreement" in result.output
    assert result.metadata["feedback"]["corrected"] == "He doesn't like coffee."


def test_skill_bare_request_offers_prompt():
    skill = EnglishPracticeSkill()
    result = skill.execute("english practice")
    assert result.success
    assert "Try this:" in result.output


def test_skill_score_reports_session():
    skill = EnglishPracticeSkill()
    skill.execute("practice english: He don't like coffee", session_id="s1")
    result = skill.execute("english practice score", session_id="s1")
    assert result.success
    assert "0/1" in result.output
    other = skill.execute("english practice score", session_id="s2")
    assert "No practice sentences yet" in other.output


def test_skill_registered_in_registry():
    from friday.skills.registry import SkillRegistry

    registry = SkillRegistry()
    registry.load_builtins()
    assert registry.get("english_practice") is not None
