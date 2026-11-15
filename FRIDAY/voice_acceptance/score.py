#!/usr/bin/env python3
"""TASK-FRD-005 — score a voice acceptance run.

Combines three evidence sources from one run:
  * the participant timeline (per-turn silence gaps, measured on the
    participant's wall clock — the primary speed evidence);
  * the FRIDAY-Voice journal for the run window (what FRIDAY heard,
    what it answered, in order);
  * the worker status file (serving provider for the session).

Verdicts follow the owner's criterion: SPEED first — a correct
answer after a long silence is a FAIL. A turn PASSes only if its
silence gap is within the battery's pre-declared threshold AND its
content check passes. The provider verdict enforces the post-
TASK-VOI-009 contract: Gemini Live only; any journal evidence of a
Groq/Whisper/Orpheus serving path is an automatic FAIL.

Usage:
  python3 score.py --timeline <room>_timeline.json \
      --journal journal.txt [--status voice_worker_status.json] \
      --battery battery.json --out-json results.json --out-md results.md
Exit code: 0 if overall PASS, 1 if FAIL, 3 if UNVERIFIED.
"""
import argparse
import json
import re
import sys

WORD_NUMBERS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20,
}

ASSISTANT_RE = re.compile(r"conversation_item_added role=assistant text='(.*)'")
USER_FINAL_RE = re.compile(r"user_input_transcribed final=True text='(.*)'")
CONTAMINATION_RE = re.compile(r"(groq|whisper|orpheus)", re.IGNORECASE)
SERVING_CONTEXT_RE = re.compile(
    r"(provider|pipeline|stt|tts|serving|fallback|ladder)", re.IGNORECASE
)


def parse_journal(text):
    """Extract ordered assistant answers, user finals, contamination."""
    assistant, user_finals, contamination, serving_hits = [], [], [], []
    for line in text.splitlines():
        if line.lstrip().startswith("{"):
            continue  # JSON duplicate of the plain log line
        m = ASSISTANT_RE.search(line)
        if m:
            assistant.append(m.group(1))
        m = USER_FINAL_RE.search(line)
        if m:
            user_finals.append(m.group(1))
        if CONTAMINATION_RE.search(line):
            contamination.append(line.strip()[:240])
            if SERVING_CONTEXT_RE.search(line):
                serving_hits.append(line.strip()[:240])
    return assistant, user_finals, contamination, serving_hits


def align_answers(assistant, user_finals, n_turns):
    """Assign assistant items to turns.

    The greeting consumes every assistant item before the first user
    final (a session may emit a fixed greeting line AND a generated
    greeting). Each turn then takes the assistant items that follow
    its user final, up to the next user final. If user finals are
    missing (STT gaps), fall back to plain order and say so.
    Returns (greeting_texts, per_turn_texts, alignment_note).
    """
    if len(user_finals) >= n_turns and assistant:
        # We cannot see interleaving from separated lists alone, so
        # this path is only used when counts line up exactly with a
        # single greeting item; otherwise prefer the degraded path.
        pass
    # Order-based assignment (journal lists were extracted in order;
    # the runner guarantees the window holds only this run's call).
    if not assistant:
        return [], [""] * n_turns, "no assistant items in journal window"
    greeting = [assistant[0]]
    rest = assistant[1:]
    per_turn = []
    for i in range(n_turns):
        per_turn.append(rest[i] if i < len(rest) else "")
    note = "order-based"
    if len(rest) > n_turns:
        # Extra assistant items (e.g. fixed greeting line + generated
        # greeting): fold leading extras into the greeting.
        extra = len(rest) - n_turns
        greeting = assistant[: 1 + extra]
        per_turn = []
        rest2 = assistant[1 + extra:]
        for i in range(n_turns):
            per_turn.append(rest2[i] if i < len(rest2) else "")
        note = f"order-based; {extra} extra assistant item(s) folded into greeting"
    return greeting, per_turn, note


def extract_closed_trade_count(text):
    if not text:
        return None
    low = text.lower()
    m = re.search(
        r"(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)"
        r"\s+closed trades",
        low,
    )
    if m:
        tok = m.group(1)
        return int(tok) if tok.isdigit() else WORD_NUMBERS.get(tok)
    m = re.search(r"closed trades[^0-9]{0,40}(\d+)", low)
    if m:
        return int(m.group(1))
    return None


def word_overlap(expected, heard):
    def words(s):
        return set(re.findall(r"[a-z0-9']+", (s or "").lower()))
    exp, got = words(expected), words(heard)
    if not exp:
        return None
    return round(len(exp & got) / len(exp), 2)


def content_check(kind, answer, context):
    """Returns (verdict, detail). verdict in PASS/FAIL/UNVERIFIED."""
    if kind == "any_speech":
        return ("PASS", "agent spoke") if context.get("speech_s", 0) > 0 else (
            "FAIL", "no agent speech recorded")
    if kind == "any_reply":
        return ("PASS", "reply present") if answer.strip() else (
            "FAIL", "no assistant reply in journal")
    if kind == "stratex_figures":
        has_number = bool(re.search(r"\d[\d,]*\.?\d*", answer))
        has_terms = bool(
            re.search(r"(balance|position|trade)", answer, re.IGNORECASE)
        )
        if has_number and has_terms:
            return "PASS", "figures + Stratex terms present"
        return "FAIL", f"number={has_number} stratex_terms={has_terms}"
    if kind == "matches_delegation_count":
        mine = extract_closed_trade_count(answer)
        theirs = context.get("delegation_count")
        if mine is None or theirs is None:
            return "UNVERIFIED", f"followup_count={mine} delegation_count={theirs}"
        if mine == theirs:
            return "PASS", f"counts match ({mine})"
        return "FAIL", f"followup says {mine}, delegation said {theirs}"
    if kind == "contains_time":
        ok = bool(
            re.search(r"\b\d{1,2}:\d{2}\b", answer)
            or re.search(r"\b\d{1,2}\s*(am|pm)\b", answer, re.IGNORECASE)
        )
        return ("PASS", "time present") if ok else ("FAIL", "no time in answer")
    if kind.startswith("contains_word:"):
        word = kind.split(":", 1)[1]
        ok = bool(re.search(rf"\b{re.escape(word)}\b", answer, re.IGNORECASE))
        return ("PASS", f"'{word}' present") if ok else (
            "FAIL", f"'{word}' missing from answer")
    return "UNVERIFIED", f"unknown content check {kind}"


def latency_verdict(gap, threshold):
    if gap is None:
        return "FAIL", "no reply audio recorded"
    return ("PASS", "") if gap <= threshold else (
        "FAIL", f"{gap:.2f}s over the {threshold:.1f}s limit")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeline", required=True)
    ap.add_argument("--journal", required=True)
    ap.add_argument("--status")
    ap.add_argument("--battery", required=True)
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--out-md", required=True)
    args = ap.parse_args()

    with open(args.battery, "r", encoding="utf-8") as fh:
        battery = json.load(fh)
    with open(args.timeline, "r", encoding="utf-8") as fh:
        timeline = json.load(fh)
    with open(args.journal, "r", encoding="utf-8") as fh:
        journal_text = fh.read()

    status = None
    status_note = "status file not supplied"
    if args.status:
        try:
            with open(args.status, "r", encoding="utf-8") as fh:
                status = json.load(fh)
            if status.get("room") not in (None, timeline.get("room")):
                status_note = (
                    f"status file is for room {status.get('room')}, "
                    f"not this run's room — treated as stale"
                )
                status = None
            else:
                status_note = "status file matches this run's room"
        except (OSError, ValueError) as exc:
            status_note = f"status file unreadable: {exc}"

    assistant, user_finals, contamination, serving_hits = parse_journal(
        journal_text
    )
    turns_cfg = battery["turns"]
    greeting_texts, per_turn_texts, align_note = align_answers(
        assistant, user_finals, len(turns_cfg)
    )

    results = {
        "task": "TASK-FRD-005",
        "room": timeline.get("room"),
        "battery_version": battery["battery_version"],
        "alignment": align_note,
        "turns": [],
    }
    reasons = []

    # ---- greeting ------------------------------------------------------
    g = timeline.get("greeting", {})
    g_lat_v, _ = latency_verdict(g.get("gap_s"), battery["greeting"]["threshold_s"])
    g_con_v, g_con_d = content_check(
        battery["greeting"]["content_check"], " ".join(greeting_texts),
        {"speech_s": g.get("speech_s", 0)},
    )
    g_verdict = "PASS" if (g_lat_v == "PASS" and g_con_v == "PASS") else (
        "UNVERIFIED" if "UNVERIFIED" in (g_lat_v, g_con_v) else "FAIL")
    results["greeting"] = {
        "gap_s": g.get("gap_s"),
        "threshold_s": battery["greeting"]["threshold_s"],
        "answer": " ".join(greeting_texts),
        "latency": g_lat_v, "content": g_con_v, "content_detail": g_con_d,
        "verdict": g_verdict,
    }
    if g_verdict != "PASS":
        reasons.append(f"greeting: latency={g_lat_v} content={g_con_v} ({g_con_d})")

    # ---- turns -----------------------------------------------------------
    delegation_count = None
    for idx, cfg in enumerate(turns_cfg):
        tl = next((t for t in timeline.get("turns", []) if t["id"] == cfg["id"]), {})
        answer = per_turn_texts[idx] if idx < len(per_turn_texts) else ""
        heard = user_finals[idx] if idx < len(user_finals) else ""
        lat_v, _ = latency_verdict(tl.get("gap_s"), cfg["threshold_s"])
        con_v, con_d = content_check(
            cfg["content_check"], answer,
            {"speech_s": tl.get("speech_s", 0),
             "delegation_count": delegation_count},
        )
        if cfg["id"] == "delegation_stratex":
            delegation_count = extract_closed_trade_count(answer)
        verdict = "PASS" if (lat_v == "PASS" and con_v == "PASS") else (
            "UNVERIFIED" if "UNVERIFIED" in (lat_v, con_v) else "FAIL")
        overlap = word_overlap(cfg["text"], heard)
        results["turns"].append({
            "id": cfg["id"],
            "prompt": cfg["text"],
            "gap_s": tl.get("gap_s"),
            "threshold_s": cfg["threshold_s"],
            "heard": heard,
            "heard_overlap": overlap,
            "answer": answer,
            "latency": lat_v, "content": con_v, "content_detail": con_d,
            "verdict": verdict,
        })
        if verdict != "PASS":
            reasons.append(
                f"{cfg['id']}: latency={lat_v} content={con_v} ({con_d})")

    # ---- provider ---------------------------------------------------------
    provider = (status or {}).get("provider")
    if serving_hits:
        prov_v = "FAIL"
        prov_d = f"{len(serving_hits)} journal line(s) show a Groq/Whisper/Orpheus serving path"
    elif provider and provider.startswith("gemini"):
        prov_v = "PASS"
        prov_d = f"status provider = {provider}"
    elif provider:
        prov_v = "FAIL"
        prov_d = f"status provider = {provider} (not Gemini)"
    else:
        prov_v = "UNVERIFIED"
        prov_d = status_note
    results["provider"] = {
        "provider": provider,
        "verdict": prov_v,
        "detail": prov_d,
        "contamination_lines": contamination,
        "serving_hits": serving_hits,
    }
    if prov_v != "PASS":
        reasons.append(f"provider: {prov_v} ({prov_d})")

    # ---- overall -----------------------------------------------------------
    verdicts = [results["greeting"]["verdict"], prov_v] + [
        t["verdict"] for t in results["turns"]
    ]
    if all(v == "PASS" for v in verdicts):
        overall = "PASS"
    elif any(v == "FAIL" for v in verdicts):
        overall = "FAIL"
    else:
        overall = "UNVERIFIED"
    results["overall"] = {"verdict": overall, "reasons": reasons}

    with open(args.out_json, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=1)

    def fmt_gap(v):
        return f"{v:.2f}" if isinstance(v, (int, float)) else "—"

    lines = [
        f"# Voice acceptance — TASK-FRD-005",
        f"Room: `{results['room']}` · battery v{battery['battery_version']} · "
        f"provider: {provider or 'unknown'} ({prov_v}) · overall: **{overall}**",
        "",
        "| # | Turn | Silence gap (s) | Limit (s) | Heard (STT) | FRIDAY's answer | Verdict |",
        "|---|------|-----------------|-----------|-------------|-----------------|---------|",
    ]
    g = results["greeting"]
    lines.append(
        f"| 0 | greeting | {fmt_gap(g['gap_s'])} | {g['threshold_s']:.1f} | — "
        f"| {g['answer'][:90]} | {g['verdict']} |"
    )
    for i, t in enumerate(results["turns"], 1):
        heard_short = (t["heard"][:40] + "…") if len(t["heard"]) > 40 else t["heard"]
        lines.append(
            f"| {i} | {t['id']} | {fmt_gap(t['gap_s'])} | {t['threshold_s']:.1f} "
            f"| {heard_short} | {t['answer'][:90]} | {t['verdict']} |"
        )
    lines += ["", f"Alignment: {align_note}. Provider detail: {prov_d}."]
    if contamination:
        lines.append(f"Contamination scan: {len(contamination)} line(s) mention "
                     f"groq/whisper/orpheus; {len(serving_hits)} in a serving context.")
    if reasons:
        lines += ["", "Why not a clean PASS:"] + [f"- {r}" for r in reasons]
    with open(args.out_md, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    print(f"overall: {overall}")
    for r in reasons:
        print(f"  - {r}")
    return 0 if overall == "PASS" else (3 if overall == "UNVERIFIED" else 1)


if __name__ == "__main__":
    raise SystemExit(main())
