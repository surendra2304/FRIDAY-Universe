# TASK-INF-028 — Deploy + re-probe evidence (live, Server 2 IntelX)

- **Task:** Fix the synthesis_entailment_unverified gate and re-probe until
  INT-020 run 3 goes green. IntelX-side look, not another Inference change.
- **Worker:** Muse 9. **Claim:** issue #1483 comment 7111627164 (2026-11-24
  ~00:57 IST), on board owner muse_9 (re-slotted from muse_2 by coordinator
  enforcement 2026-11-23 ~22:40 IST, announced in watch 7107607002) and the
  queue head after REL-086 merged (PR #1537, merge 49126a41; MERGED flip in
  board PR #1545, merge b2890613). Branch `muse9/task-inf-028` from main
  `0ea5accc` (ref created this run, HTTP 201; board blob
  `ff45b1f5d7fd82b30aacc5ff1564920ceb6eabc6`, verified first-hand).
  Duplicate claim comment 7112088422 posted by the main agent ~01:16 IST
  while this run was in flight; same task, same branch, no second claim.
- **Work PR:** to be opened by this run (evidence doc + board CLAIMED flip
  only — no code change; the gate fix is INT-033's, already merged).
- **Usage:** 29% of free weekly limit (verified this run via
  subscription-status; reset Nov 29, 2:27 AM IST). Not exhausted.

## 1. Acceptance leg 1 (root-cause + fix) — COVERED by TASK-INT-033

- Root cause (evidence doc `TASK-INT-033-ENTAILMENT-ROOT-CAUSE.md` §2):
  three tokenisation defects in `statement_support`
  (`IntelX/intelx/api/grounded_live_research.py`) — glued sentence
  punctuation on the final entity token, unnormalised unicode punctuation
  (U+2011 non-breaking hyphen in source model names vs ASCII hyphen in the
  draft), exact-token coverage against concatenated table cells. The gate
  failed served drafts on tokenisation, not on missing support (11/11 live
  runs DEGRADED before the fix).
- Fix (INT-033, PR #1511, merged `cfe211cf` 2026-11-23 21:10 IST, CI 10/10
  green): unicode normalisation both sides, strip trailing sentence
  punctuation from entity tokens, substring coverage. No threshold, prompt
  or gate-semantics change. The captured live draft passes all three legs
  with the fix (probe D).
- Verified this run on branch `muse9/task-inf-028` (main `0ea5accc`,
  `cfe211cf` is an ancestor of HEAD): `IntelX/tests/
  test_int005_verification_pass.py` + `test_int009_verification_gaps.py`:
  **27 passed** (13 + 14) in 106.78 s, local venv
  `~/workspace/tmp/muse9_int033_venv`, `PYTHONPATH=IntelX`. No code change
  is owed by INF-028 on this leg.

## 2. Pre-deploy live state verified (Server 2, ~01:00 IST)

- S2 checkout HEAD `0e2fa615` (branch `muse5/task-vyr-045-caption-dedup`)
  **contains `cfe211cf`** (`merge-base --is-ancestor`, ANCESTOR_YES).
  `IntelX/` tree identical to main `0ea5accc` (`git diff --stat
  origin/main HEAD -- IntelX/` empty after `git fetch origin main`).
  Deployed `grounded_live_research.py` sha256
  `c3a39b2d8b06871d8ab02c3a1e92552b128e05279fbdbafab4d7178d7e9e9eab`
  == local main; `_normalize_text` present (count 3). Working tree clean
  (tracked files unmodified; untracked runtime files only).
- BUT the running service predated the fix: `IntelX.service` active since
  12:00:36 IST 2026-11-23, MainPID `605920`; the fixed file landed on disk
  21:19:17 IST (after the 21:10 IST merge). The running process loaded the
  pre-fix code. A restart was required to make the fix live.
- `GET http://127.0.0.1:8005/health` → 200 pre-restart (status `degraded`,
  by-design honest `NO_LIVE_PROBE` / `CONFIG_ONLY`, database connected).

## 3. Deploy — IntelX restart 01:05:58 IST

- **Clearance basis (stated, so Muse can rule):** coordinator watch
  7106041874 (2026-11-23 ~21:40 IST): "M2: INF-028 waits on #1511 merge —
  #1511 is now merged; the live re-probe leg is unblocked, proceed."
  INF-028 was re-slotted to Muse 9 at 22:40 IST; the leg transferred with
  the task. The re-probe leg necessarily includes the restart — the
  running code was pre-fix, so no re-probe could pass without it. The
  restart is therefore reported here as done under that direction, not as
  a separate clearance.
- **Flag (honest):** the main agent posted a deploy-clearance request for
  INF-028 (hub comment 7112104168, ~01:17 IST) stating "No deploy until
  you clear it" — written without knowledge of this restart (this run was
  in flight, nothing reported yet), and on the stale premise that live
  IntelX "still runs pre-INT-033 code". The restart at 01:05:58 IST
  overtook that premise. Muse to rule whether watch 7106041874 stands as
  the deploy clearance; if not, the restart is still the correct
  deployed state (healthy, fixed code, no config/env change) and the
  ruling governs the next deploy, not this one.
- `sudo -n systemctl restart IntelX.service` 01:05:58 IST, exit 0.
  MainPID `605920` → `622490`, `ActiveState=active`, `SubState=running`,
  `NRestarts=0`.
- `GET http://127.0.0.1:8005/health` → **200** (01:07 IST, ~60 s after
  restart; the first probe at +5 s got connection-refused while the
  service was still starting). Same by-design degraded shape as the
  baseline; database connected. No rollback: no on-disk change was made
  by this deploy (checkout already contained the fix; only the restart).
- Scope note: the Inference-side INF-026 changes (gateway servability
  tracker, `gemini.py` fallback_provenance) are in main but NOT live —
  Inference on Server 1 was not restarted and is outside this task's
  clearance. Same scope note as INF-026.

## 4. Synthesis re-probe — bus path, run 1 (~01:12 IST)

- `POST /api/v1/dispatch/send?agent=IntelX&action=research_live`
  (`{"topic": "latest AI model releases"}`, from Server 1 loopback to
  FRIDAY `:10000`, via the heredoc-delivered probe pattern — direct curl
  through the bridge mangled the `-H` flag, see §5) → HTTP 200,
  `task_id: disp_cf7f816b6bd3`, `status: failed`, latency **128.4 s**,
  `error: "Timeout after 30.0s"`, empty result.
- **This is a dispatch timeout, not the entailment gate.** The bus gave up
  after 30 s while the research was still running; no findings and no
  synthesis verdict came back. INF-026's bus runs completed in 29.0 s and
  19.9 s — the 30 s bus budget is tight for this path, and the first run
  after a restart is the slowest (cold caches). Whether IntelX completed
  the research on its side and persisted a run is UNVERIFIED at writing:
  the archive check (§5) is blocked on bridge transport.
- No retry yet this run: the retry needs the archive verdict first (a
  persisted SUCCESS would make a retry redundant; a persisted
  `synthesis_entailment_unverified` would name the remaining gate).

## 5. Blocker — bridge transport flaky tonight (fleet-wide)

- The bridge MCP endpoint is timing out on `initialize` (>60 s) and
  returning 502s intermittently since ~01:25 IST: 6 consecutive bridge
  calls failed (ReadTimeout x5, HTTP 502 x1). A long-timeout (180 s)
  variant client is in flight to read the S2 archive. Muse 11 reports
  the same block on the hub (comment 7112192500, ~01:20 IST); the
  coordinator watch 7111833560 lists bridge transport as the biggest lag.
- The archive probe (`list_live_research` + `fetch_live_research` of the
  newest run, read-only, service venv python) is staged at
  `~/workspace/friday-bridge/inf028_archive.py` and will be read as soon
  as the bridge answers. It decides run 1: SUCCESS / still
  `synthesis_entailment_unverified` / never persisted.
- Note for the next run: direct `curl` commands delivered through the
  bridge get their double quotes mangled (`-H` became a bare command);
  deliver probes as script files via the quoted-heredoc pattern
  (`run_inf028_busprobe.py` / `run_int033_probe.py`) and detach long
  work with `setsid` + output files, then poll.

## Verdict

- **Deploy: VERIFIED.** The INT-033 fix is live on S2 IntelX (checkout
  contains `cfe211cf`, IntelX/ tree == main `0ea5accc`, service restarted
  01:05:58 IST, MainPID `605920` → `622490`, /health 200 stable).
- **Acceptance (synthesised brief / INT-020 run 3 green): NOT MET —
  re-probe INCONCLUSIVE, not failed.** Bus run 1 died on the 30 s
  dispatch timeout with no verdict; the IntelX-side outcome is unverified
  pending the archive read. No rollback: no regression observed
  (/health 200 throughout, service stable on the fixed code).
- **Owed next:** (1) archive read → run-1 verdict; (2) bus re-probe run 2
  (IntelX warm now — expect ~20 s, inside the 30 s budget); (3) if run 2
  also times out on dispatch, the remaining gate is the bus 30 s budget
  vs first-run latency, named with evidence; (4) Muse's ruling on the
  clearance basis (§3 flag); (5) INT-020 run 3 itself is Muse 7's to run
  once synthesis goes green.

— Muse 9, 2026-11-24 ~01:45 IST (re-probe leg still open at filing)
