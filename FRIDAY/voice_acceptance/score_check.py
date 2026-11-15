#!/usr/bin/env python3
"""TASK-FRD-005 — offline checks for score.py (not a pytest module;
run directly: python3 score_check.py). Builds synthetic run fixtures
and asserts the scorer's verdicts, including the two failure modes
this harness exists to catch: a correct answer after a long silence
(FAIL on speed) and a Groq serving path after TASK-VOI-009 (FAIL on
provider). Exits non-zero on the first broken assertion.
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCORE = os.path.join(HERE, "score.py")
BATTERY = os.path.join(HERE, "battery.json")

TURN_IDS = [
    "delegation_stratex", "context_followup", "clock_tokyo",
    "memory_remember", "memory_recall", "goodbye",
]

ANSWERS = [
    "Your Stratex demo portfolio has a balance of 10,792.80 with no "
    "open positions and a net profit of 195.06 from nine closed trades.",
    "There are currently nine closed trades recorded in your ledger.",
    "It is 2:29 PM in Tokyo right now.",
    "Noted. I will remember that your favourite colour is teal.",
    "Your favourite colour is teal.",
    "Goodbye, Boss. Talk soon.",
]
PROMPTS = [
    "FRIDAY, check Stratex for me. What is the balance, how many open "
    "positions are there, and how many closed trades are in the ledger?",
    "And how many closed trades was that, exactly?",
    "What time is it in Tokyo right now?",
    "Please remember this for me. My favourite colour is teal.",
    "What is my favourite colour?",
    "That is all for now. Goodbye.",
]


def make_timeline(gaps, greeting_gap=3.0):
    return {
        "room": "friday-frd005-check",
        "battery_version": 1,
        "greeting": {"gap_s": greeting_gap, "speech_s": 2.0},
        "turns": [
            {"id": tid, "gap_s": gap, "speech_s": 3.0}
            for tid, gap in zip(TURN_IDS, gaps)
        ],
    }


def make_journal(answers=ANSWERS, extra_lines=()):
    lines = ["2026-11-15T00:00:00+0530 host python[1]: 2026-11-15 00:00:00 INFO "
             "friday.voice VOICE conversation_item_added role=assistant "
             "text='I am here, Boss. What would you like to work on?'"]
    for prompt, ans in zip(PROMPTS, answers):
        lines.append(
            "x friday.voice VOICE user_input_transcribed final=True "
            f"text='{prompt}'")
        lines.append(
            "x friday.voice VOICE conversation_item_added role=assistant "
            f"text='{ans}'")
    lines.extend(extra_lines)
    return "\n".join(lines) + "\n"


def run_case(name, timeline, journal, status, expect_code, expect_overall):
    with tempfile.TemporaryDirectory() as td:
        tl = os.path.join(td, "timeline.json")
        jo = os.path.join(td, "journal.txt")
        oj = os.path.join(td, "results.json")
        om = os.path.join(td, "results.md")
        with open(tl, "w") as fh:
            json.dump(timeline, fh)
        with open(jo, "w") as fh:
            fh.write(journal)
        cmd = [sys.executable, SCORE, "--timeline", tl, "--journal", jo,
               "--battery", BATTERY, "--out-json", oj, "--out-md", om]
        if status is not None:
            st = os.path.join(td, "status.json")
            with open(st, "w") as fh:
                json.dump(status, fh)
            cmd += ["--status", st]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        with open(oj) as fh:
            results = json.load(fh)
        assert proc.returncode == expect_code, (
            f"{name}: exit {proc.returncode} != {expect_code}\n{proc.stdout}")
        assert results["overall"]["verdict"] == expect_overall, (
            f"{name}: overall {results['overall']['verdict']} != {expect_overall}")
        print(f"ok: {name} -> {expect_overall}")
        return results


def main():
    good_status = {"provider": "gemini-realtime:gemini-3.8-live",
                   "room": "friday-frd005-check", "state": "closed"}
    good_gaps = [9.0, 2.0, 2.0, 3.0, 3.0, 2.0]

    run_case("clean pass", make_timeline(good_gaps), make_journal(),
             good_status, 0, "PASS")

    slow = list(good_gaps)
    slow[0] = 18.6  # VOI-007's delegation gap under load
    r = run_case("slow delegation fails on speed",
                 make_timeline(slow), make_journal(), good_status, 1, "FAIL")
    assert r["turns"][0]["latency"] == "FAIL"

    run_case("slow greeting fails", make_timeline(good_gaps, greeting_gap=25.6),
             make_journal(), good_status, 1, "FAIL")

    contam = make_journal(extra_lines=[
        "x friday.voice VOICE provider fallback engaged: groq pipeline "
        "whisper stt -> gpt-oss"])
    r = run_case("groq serving path fails provider",
                 make_timeline(good_gaps), contam, good_status, 1, "FAIL")
    assert r["provider"]["verdict"] == "FAIL"

    bad_answers = list(ANSWERS)
    bad_answers[1] = "There are currently seven closed trades recorded."
    r = run_case("follow-up count mismatch fails",
                 make_timeline(good_gaps), make_journal(bad_answers),
                 good_status, 1, "FAIL")
    assert r["turns"][1]["content"] == "FAIL"

    no_teal = list(ANSWERS)
    no_teal[4] = "Your favourite colour is blue."
    run_case("wrong recall fails", make_timeline(good_gaps),
             make_journal(no_teal), good_status, 1, "FAIL")

    # Run 1's real shape (2026-11-15): the delegation's answer was
    # logged only AFTER the follow-up had been transcribed. The
    # scorer must flag degraded alignment, leave the delegation's
    # content UNVERIFIED (not a guessed FAIL), and keep the answers
    # available in journal order for human attribution.
    ooo_lines = [
        "x friday.voice VOICE user_input_transcribed final=True "
        f"text='{PROMPTS[0]}'",
        "x friday.voice VOICE user_input_transcribed final=True "
        f"text='{PROMPTS[1]}'",
        "x friday.voice VOICE conversation_item_added role=assistant "
        "text='Stratex could not answer that: ReadTimeout.'",
    ]
    for prompt, ans in zip(PROMPTS[2:], ANSWERS[2:]):
        ooo_lines.append(
            "x friday.voice VOICE user_input_transcribed final=True "
            f"text='{prompt}'")
        ooo_lines.append(
            "x friday.voice VOICE conversation_item_added role=assistant "
            f"text='{ans}'")
    r = run_case("out-of-order answers degrade, not mis-attribute",
                 make_timeline(good_gaps), "\n".join(ooo_lines) + "\n",
                 good_status, 3, "UNVERIFIED")
    assert "DEGRADED" in r["alignment"], r["alignment"]
    assert r["turns"][0]["content"] == "UNVERIFIED"
    assert r["journal_order_answers"][0].startswith("Stratex could not")

    run_case("missing status is unverified, never a pass",
             make_timeline(good_gaps), make_journal(), None, 3, "UNVERIFIED")

    silent = list(good_gaps)
    silent[2] = None
    run_case("no reply audio fails", make_timeline(silent),
             make_journal(), good_status, 1, "FAIL")

    print("all score checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
