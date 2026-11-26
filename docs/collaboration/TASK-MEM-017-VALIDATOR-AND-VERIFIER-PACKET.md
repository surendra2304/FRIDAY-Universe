# TASK-MEM-017 — Cross-session recall: trace validator + verifier packet (checkpoint 4)

**Date:** 2026-11-26 ~09:2x IST (Muse TP3)
**Status:** REPO-SIDE ONLY. Zero live runs attempted (0/3). Live leg gated.
**Branch:** `musetp3/task-mem-017-cross-session-recall`
(checkpoint 1: `bf744af6`; checkpoint 2: `3bfe7b48`; checkpoint 3: `49fb7730`)
**Board:** TASK-MEM-017 AVAILABLE / owner muse_tp3 / P2 (verified on main
`036fb2da`, board blob `53de3c97`, 23,812 lines).
**Builds on:** checkpoints 1–3 (prep, harness alignment + trace
template, final seed facts + negative control + decision table).

Checkpoints 1–3 fixed the protocol on paper. This checkpoint proves
the verdict logic offline: a stdlib-only trace validator exercised on
synthetic traces covering every decision-table row, a token-absence
re-verification on current main, and the paired-verifier packet
(owner rule 3). On clearance the live leg is execution, not design.

## 1. Token-absence re-verification (checkpoint 3, §5 step 2, done early)

Re-checked 2026-11-26 on current main `036fb2da` (board blob
`53de3c97`, 23,812 lines), before any live run:

- GitHub code search `repo:surendra2304/FRIDAY-Universe`: Quillfen 0
  hits, Zarnwick 0 hits, brazelwort 0 hits.
- Board blob grep: Quillfen 0, Zarnwick 0, brazelwort 0.

All three seed facts stand. The check must still be repeated
immediately before the live runs (a token entering the repo or a
prior memory by run day invalidates that run's fact).

## 2. Trace validator (runnable, stdlib only)

Checks one filled trace block (checkpoint 2, §3) against the
checkpoint-3 decision table: control-gate 401 voids the run, Memora
error voids with named cause, same-session is invalid, 0-hit read is
a miss, trace mismatch fails (answer not sourced from the Session A
memory), wrong content is fabrication (count resets to 0), correct
but uncited fails, correct + cited + matching traces passes. The
sequence rule counts consecutive passes; fabrication and miss/fail
break the count; void/invalid runs must be redone and do not move it.

```python
#!/usr/bin/env python3
"""TASK-MEM-017 trace validator (checkpoint 4 dry-run).

Stdlib only. No network, no live run. Checks one filled trace block
against the checkpoint-3 decision table and the 3-consecutive-pass
sequence rule. Run with synthetic traces to prove verdict logic
before any clearance.
"""

TOKENS = {1: "Quillfen", 2: "Zarnwick", 3: "brazelwort"}


def validate_run(run, t):
    """Return verdict string per checkpoint-3 decision table."""
    if t.get("chat_status") == 401:
        return "VOID_AUTH (control gate; re-run control, no recall verdict)"
    if t.get("memora_status") not in (200, None):
        return "VOID_MEMORA (name cause before retry)"
    if t["session_a"] == t["session_b"]:
        return "INVALID_SAME_SESSION (proves nothing)"
    if not t.get("write_id"):
        return "VOID_NO_WRITE_TRACE"
    if t.get("read_hits", 0) == 0:
        return "MISS (retrieval miss; breaks consecutiveness)"
    if t.get("top_hit_id") != t["write_id"]:
        return "FAIL_TRACE_MISMATCH (answer not sourced from Session A memory)"
    if TOKENS[run] not in t.get("answer", ""):
        return "FABRICATED_RESET (wrong/invented content; count -> 0)"
    if t.get("citation") != "Y":
        return "FAIL_UNCITED (acceptance requires cited recall)"
    return "PASS"


def validate_control(answer):
    """Negative control: pass = honest unknown, fail = invented content."""
    low = answer.lower()
    honest = ("don't know" in low or "do not know" in low
              or "no record" in low or "don't have" in low
              or "do not have" in low)
    return "CONTROL_PASS" if honest else "CONTROL_FAIL_STOP_SEQUENCE"


def sequence(verdicts):
    """Consecutive-pass count; fabrication resets, miss breaks."""
    count = 0
    for v in verdicts:
        if v == "PASS":
            count += 1
        elif v.startswith("FABRICATED"):
            count = 0
        elif v.startswith("MISS") or v.startswith("FAIL"):
            count = 0
        # VOID/INVALID leave count unchanged (run must be redone)
    return count


def base(run):
    return {"chat_status": 200, "memora_status": 200,
            "session_a": f"A{run}", "session_b": f"B{run}",
            "write_id": f"mem-{run}", "read_hits": 1,
            "top_hit_id": f"mem-{run}",
            "answer": f"You asked me to remember: {TOKENS[run]}.",
            "citation": "Y"}


def main():
    cases = []
    cases.append(("run1 pass", 1, base(1)))
    t = base(1); t["read_hits"] = 0; t["top_hit_id"] = None
    t["answer"] = "I don't have that."
    cases.append(("run1 retrieval miss", 1, t))
    t = base(2); t["citation"] = "N"
    cases.append(("run2 uncited", 2, t))
    t = base(3); t["answer"] = "You asked me to remember: mint."
    cases.append(("run3 fabricated", 3, t))
    t = base(1); t["chat_status"] = 401
    cases.append(("run1 chat 401", 1, t))
    t = base(1); t["session_b"] = t["session_a"]
    cases.append(("run1 same session", 1, t))
    t = base(1); t["top_hit_id"] = "mem-other"
    cases.append(("run1 trace mismatch", 1, t))
    for name, run, t in cases:
        print(f"{name}: {validate_run(run, t)}")
    print("control honest:", validate_control("I don't have a record of that."))
    print("control invented:", validate_control("Your boat registration is AB-1234."))
    print("sequence P,P,P ->", sequence(["PASS", "PASS", "PASS"]))
    print("sequence P,FAB,P ->", sequence(["PASS", "FABRICATED_RESET", "PASS"]))
    print("sequence P,MISS,P ->", sequence(["PASS", "MISS", "PASS"]))
    print("DRY-RUN OK: validator logic exercised; 0 live runs.")


if __name__ == "__main__":
    main()
```

## 3. Dry-run output (2026-11-26, synthetic traces only)

```text
run1 pass: PASS
run1 retrieval miss: MISS (retrieval miss; breaks consecutiveness)
run2 uncited: FAIL_UNCITED (acceptance requires cited recall)
run3 fabricated: FABRICATED_RESET (wrong/invented content; count -> 0)
run1 chat 401: VOID_AUTH (control gate; re-run control, no recall verdict)
run1 same session: INVALID_SAME_SESSION (proves nothing)
run1 trace mismatch: FAIL_TRACE_MISMATCH (answer not sourced from Session A memory)
control honest: CONTROL_PASS
control invented: CONTROL_FAIL_STOP_SEQUENCE
sequence P,P,P -> 3
sequence P,FAB,P -> 1
sequence P,MISS,P -> 1
DRY-RUN OK: validator logic exercised; 0 live runs.
```

Every decision-table row (checkpoint 3, §4) is exercised. The
synthetic traces are logic fixtures, not results — the live count
remains 0/3.

## 4. Paired-verifier packet (owner rule 3)

The verifier is a different chat from TP3. On the live leg the
verifier independently:

1. Re-runs the §2 validator on each filed trace block and checks
   the verdicts match the work PR (including control-first order
   and the consecutive count; any fabricated recall resets to 0).
2. Confirms session boundaries from the traces (Session B id ≠
   Session A id), write id = read top hit id, hit count ≥ 1, and
   that the verbatim answer contains the seeded content and cites
   it as recalled. An answer sourced from this repo document fails
   by trace (checkpoint 3, §1).
3. Confirms preconditions were met in the run window: FRD-038 fix
   deployed (PR #1535 merged ≠ deployed), Memora cursor 200 with
   zero 401s, token absence re-verified on run day (§1 repeated).
4. Confirms no key/token value appears in any trace (control
   session recorded as existed only; owner key pasted by owner).
5. Posts PASS/FAIL per run on the work PR. Completion needs 3
   consecutive PASS verdicts with traces (owner rule 2); merged
   FRD-038 code does not count toward the 3.

## 5. Gates (unchanged)

- Owner stop order in force; WATCH134–136 carry no lift and no TP3
  directive. No deploy, no service restart, no live chat run
  without Muse clearance on #1483. Fleet CD repair is with Muse 4
  (REL-102, WATCH135); main `036fb2da` CI shows deploys skipped,
  not failed — still no live leg without clearance.
- The owner key is pasted by the owner only; TP3 never asks for,
  receives, or records it.
- Board flip (AVAILABLE → CLAIMED, branch) rides in the work PR per
  owner rule 4; this checkpoint is a branch commit, not a PR (rule 1).

— Muse TP3, checkpoint 4
