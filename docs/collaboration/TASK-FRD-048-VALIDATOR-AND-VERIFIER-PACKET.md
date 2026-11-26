# TASK-FRD-048 — Fish Audio vs Gemini Live: offline validator + verifier packet (checkpoint 4)

**Date:** 2026-11-26 ~09:2x IST (Muse TP3)
**Status:** REPO-SIDE ONLY. No live run, no account created, no key used.
**Branch:** `musetp3/task-frd-048-fish-audio-voice-eval`
(checkpoint 1: `d4312b88`; checkpoint 2: `9fc7a307`; checkpoint 3: `3430343a`)
**Board:** TASK-FRD-048 AVAILABLE / owner muse_tp3 / P2 (verified on main
`036fb2da`, board blob `53de3c97`, 23,812 lines).
**Builds on:** checkpoints 1–3 (scope, battery + scoring sheet,
harness spec + cost arithmetic).

Checkpoints 1–3 fixed the design on paper. This checkpoint proves the
verdict logic offline: a stdlib-only validator (manifest schema,
blind-score aggregation, cost arithmetic) exercised on synthetic data,
plus the paired-verifier packet (owner rule 3). On clearance the live
leg is renders + scoring, not logic debugging.

## 1. Offline validator (runnable, stdlib only)

Validates each manifest row against the checkpoint-3 schema (required
fields, arm, attempt 1–3, battery byte count per utterance), flags a
silent failure (HTTP 200 with no audio hash) as auto-reject, computes
TTFA medians over 3 attempts (failures recorded, not dropped),
aggregates blind scores as medians per arm with worst-3 utterances by
name, and recomputes cost per 1,000 turns. Latency families stay
separate: Arm A conversational silence is never averaged with Arms
B/C TTFA (checkpoint 2, §1; checkpoint 3, §3).

```python
#!/usr/bin/env python3
"""TASK-FRD-048 offline validator (checkpoint 4 dry-run).

Stdlib only. No network, no key, no render. Validates manifest rows
against the checkpoint-3 schema, aggregates blind scores (medians +
worst-3), and recomputes cost arithmetic. Run with synthetic data to
prove the live-leg logic before any clearance.
"""
import statistics

BATTERY_BYTES = [131, 45, 35, 57, 28, 29, 63, 65, 61, 66,
                 48, 52, 69, 55, 32, 50, 59, 135, 43, 52]
UTTERANCES = ["delegation_stratex", "context_followup", "clock_tokyo",
              "memory_remember", "memory_recall", "goodbye",
              "numbers_money", "date_time", "place_names",
              "person_names", "code_switch", "abbreviation",
              "list_turn", "negative", "question_rise", "cheerful",
              "serious", "long_sentence", "cluster_stress",
              "quiet_instruction"]

REQUIRED = ["utterance_id", "arm", "model", "voice_id",
            "text_utf8_bytes", "attempt", "http_status", "ttfa_ms",
            "full_render_ms", "audio_sha256", "audio_format",
            "sample_rate_hz", "error_shape", "started_at_ist"]


def validate_row(row):
    """Return list of problems; empty = valid."""
    p = []
    for f in REQUIRED:
        if f not in row:
            p.append(f"missing field {f}")
    if row.get("arm") not in ("A", "B", "C"):
        p.append("arm must be A/B/C")
    if row.get("attempt") not in (1, 2, 3):
        p.append("attempt must be 1..3")
    if row.get("utterance_id") in UTTERANCES:
        want = BATTERY_BYTES[UTTERANCES.index(row["utterance_id"])]
        if row.get("text_utf8_bytes") != want:
            p.append(f"byte count {row.get('text_utf8_bytes')} != battery {want}")
    status = row.get("http_status")
    if status == 200 and not row.get("audio_sha256"):
        p.append("SILENT FAILURE: HTTP 200 with no audio hash (auto-reject)")
    if status == 200 and row.get("audio_sha256") and not row.get("audio_format"):
        p.append("success row missing audio_format")
    if status in (401, 429) and row.get("audio_sha256"):
        p.append("error row must not carry audio")
    return p


def median3(values):
    vals = [v for v in values if v is not None]
    return statistics.median(vals) if vals else None


def aggregate(scores):
    """scores: list of dicts utterance_id/arm/intelligibility/naturalness/emotion."""
    out = {}
    for arm in ("B", "C"):
        rows = [s for s in scores if s["arm"] == arm]
        if not rows:
            continue
        med = {d: statistics.median([r[d] for r in rows])
               for d in ("intelligibility", "naturalness", "emotion")}
        ranked = sorted(rows, key=lambda r: (r["intelligibility"] +
                                             r["naturalness"] + r["emotion"]))
        out[arm] = {"medians": med,
                    "worst3": [r["utterance_id"] for r in ranked[:3]]}
    return out


def cost_per_1k(mean_bytes, price_per_1m):
    return round(mean_bytes * 1000 / 1_000_000 * price_per_1m, 2)


def main():
    total = sum(BATTERY_BYTES)
    mean = total / len(BATTERY_BYTES)
    print(f"battery total={total} bytes mean={mean} bytes/turn n={len(BATTERY_BYTES)}")
    assert total == 1175, total
    for price in (0, 5, 15):
        print(f"cost/1k at ${price}/1M = ${cost_per_1k(mean, price):.2f}")

    good = {"utterance_id": "numbers_money", "arm": "B",
            "model": "s2.1-pro-free", "voice_id": "synthetic-voice",
            "text_utf8_bytes": 63, "attempt": 1, "http_status": 200,
            "ttfa_ms": 180, "full_render_ms": 900,
            "audio_sha256": "synthetic-hash", "audio_format": "mp3",
            "sample_rate_hz": 44100, "error_shape": None,
            "started_at_ist": "SYNTHETIC"}
    silent = dict(good, audio_sha256=None)
    loud401 = dict(good, http_status=401, audio_sha256=None,
                   audio_format=None, ttfa_ms=None, full_render_ms=None,
                   error_shape="unauthorized")
    badbytes = dict(good, text_utf8_bytes=999)
    for name, row in [("good", good), ("silent", silent),
                      ("loud401", loud401), ("badbytes", badbytes)]:
        print(f"row {name}: problems={validate_row(row)}")

    print(f"ttfa median of [180, 210, 195] = {median3([180, 210, 195])}")
    print(f"ttfa median with failure [180, None, 195] = {median3([180, None, 195])}")

    synth = []
    for i, u in enumerate(UTTERANCES):
        base = 3 + (i % 3)
        synth.append({"utterance_id": u, "arm": "B",
                      "intelligibility": base, "naturalness": base,
                      "emotion": 3})
        synth.append({"utterance_id": u, "arm": "C",
                      "intelligibility": 4, "naturalness": 4,
                      "emotion": 4})
    print(f"aggregate(synthetic) = {aggregate(synth)}")
    print("DRY-RUN OK: validator logic exercised; no live data used.")


if __name__ == "__main__":
    main()
```

## 2. Dry-run output (2026-11-26, synthetic data only)

```text
battery total=1175 bytes mean=58.75 bytes/turn n=20
cost/1k at $0/1M = $0.00
cost/1k at $5/1M = $0.29
cost/1k at $15/1M = $0.88
row good: problems=[]
row silent: problems=['SILENT FAILURE: HTTP 200 with no audio hash (auto-reject)']
row loud401: problems=[]
row badbytes: problems=['byte count 999 != battery 63']
ttfa median of [180, 210, 195] = 195
ttfa median with failure [180, None, 195] = 187.5
aggregate(synthetic) = {'B': {'medians': {'intelligibility': 4.0, 'naturalness': 4.0, 'emotion': 3.0}, 'worst3': ['delegation_stratex', 'memory_remember', 'numbers_money']}, 'C': {'medians': {'intelligibility': 4.0, 'naturalness': 4.0, 'emotion': 4.0}, 'worst3': ['delegation_stratex', 'context_followup', 'clock_tokyo']}}
DRY-RUN OK: validator logic exercised; no live data used.
```

Cost figures reproduce checkpoint 3 exactly ($0.88/1k at $15/1M,
$0.29/1k at $5/1M; mean 58.75 = 1,175/20, checkpoint 3's 58.8
rounded). The synthetic scores are logic fixtures, not results — no
quality claim is made or implied.

## 3. Paired-verifier packet (owner rule 3)

The verifier is a different chat from TP3. On the live leg the
verifier independently:

1. Holds the clip-id → arm mapping (blinding, checkpoint 3, §5);
   reveals it only after scores are filed. Scores each clip 1–5 on
   intelligibility, naturalness, emotion fit (checkpoint 2, §3)
   without seeing arm labels, TP3's notes, or vendor claims.
2. Re-runs the §1 validator on the filed manifest: every attempt row
   present (20 utterances × 3 attempts × Arms B/C + failure probes),
   byte counts match the battery, every success row's `audio_sha256`
   recomputes from the filed audio, no silent failure anywhere
   (one silent failure = auto-reject stands regardless of scores).
3. Recomputes medians + worst-3 from the raw scores and checks them
   against the work PR's verdict table; confirms Arm A silence and
   Arms B/C TTFA are reported side by side, never averaged.
4. Checks the gates before quality: nothing-paid (free tier live at
   run date, else checkpoint-3 §5 expiry tree applies), privacy
   terms read, licence terms recorded, architecture gate stated
   (quality win alone cannot adopt; verdict adopt/reject/offline-only).
5. Posts PASS/FAIL with the recomputed figures on the work PR. A
   verifier FAIL on any of 2–4 blocks completion until fixed.

## 4. Gates (unchanged)

- Owner stop order in force; WATCH134–136 carry no lift and no TP3
  directive. No account, no render, no server change until Muse
  clearance on #1483. Free tier `s2.1-pro-free` $0 runs through
  2026-11-30 — expiry tree in checkpoint 3, §5 governs if clearance
  lands later.
- SECURITY held: the displayed key in the source reel is never used,
  copied, or stored; own accounts only, keys in Server 2
  `CREDENTIALS.md` / Secure Vault, never in repo, hub, or chat.
- Board flip (AVAILABLE → CLAIMED, branch) rides in the work PR per
  owner rule 4; this checkpoint is a branch commit, not a PR (rule 1).

— Muse TP3, checkpoint 4
