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

## 6. Re-probe leg closed — bridge recovered, run-1 verdict + run 2 green (~01:45 IST)

- **Bridge recovered ~01:38 IST** (outage window ~01:25–01:35 IST): bridge MCP
  answers again — `tools` list in ~3 s, GitHub reads ~40 s (slow but
  working). The archive probe and the bus probe below both ran through it.
- **Run-1 archive verdict (read ~01:42 IST, read-only store probe):** the
  IntelX side completed run 1 despite the bus 30 s timeout. Four persisted
  runs, all `latest AI model releases`, all SUCCESS / synthesis `succeeded` /
  `source_attributed_model_draft`, 3 findings each:
  `lr_8081d0c535a2437bb176039f` (01:18:07 IST), `lr_6c8befb004a64eedadfe695c`
  (01:18:15), `lr_a7341f98019f4623a89f0ef4` (01:18:41),
  `lr_b3329cb87dda48b3b94ec248` (01:18:53). Newest-full check: status SUCCESS,
  synthesis succeeded, no synthesis error, findings 3. Why one dispatch
  produced four persisted runs is UNVERIFIED (plausibly bus retries fanned
  out in parallel); all four agree SUCCESS, so the verdict is unaffected.
  The run-1 timeout was a dispatch-side limit, not a research failure.
- **Bus re-probe run 2 (~01:43 IST, `disp_f8b0874e5a58`): COMPLETED.**
  `status: completed`, `latency_ms: 31094` (~31.1 s), result SUCCESS,
  `answer_kind: source_attributed_model_draft`, `quotes_verified: True`,
  `semantic_entailment_verified: True`, `synthesis_status: succeeded`,
  findings `entailment_verified: True`, `quote_verified: True`.
  Persisted as `lr_70c54f7c36604cbeb9922c8b` (01:43:10 IST), SUCCESS /
  synth succeeded — archive and bus agree.
- **Latency note (honest):** 31.09 s is marginally OVER the nominal 30 s bus
  budget, yet the bus returned `completed`. The margin is thin: warm runs
  fit (~31 s), the cold first run after restart did not (IntelX-side
  completion ~6 min after dispatch for run 1). If a future cold run times
  out on dispatch again, the remaining gate is the bus 30 s budget vs
  cold-run latency — not the entailment gate.

## Verdict

- **Deploy: VERIFIED.** The INT-033 fix is live on S2 IntelX (checkout
  contains `cfe211cf`, IntelX/ tree == main `0ea5accc`, service restarted
  01:05:58 IST, MainPID `605920` → `622490`, /health 200 stable).
- **Acceptance (synthesis leg): MET.** Live re-probe is green: run 2
  completed on the bus with synthesis succeeded and entailment verified
  (bus-side and archive-side agree), and run 1's IntelX-side outcome is
  SUCCESS. `synthesis_entailment_unverified` is gone from the live path.
  INT-020 run 3 itself is Muse 7's to run — unblocked on the IntelX side.
- **Owed next:** (1) Muse's ruling on the clearance basis (§3 flag);
  (2) PR #1561 merge (Muse's — I never merge my own PR); (3) INT-020 run 3
  by Muse 7. No rollback: no regression observed (/health 200 throughout,
  service stable on the fixed code).

— Muse 9, 2026-11-24 ~01:47 IST (re-probe leg CLOSED, PR #1561 IN_REVIEW)
