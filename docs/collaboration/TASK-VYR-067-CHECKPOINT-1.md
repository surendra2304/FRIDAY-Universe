# TASK-VYR-067 — CHECKPOINT 1 — scoping + route — Muse 20

- Task: TASK-VYR-067 (P2, VyralX: reference-video style-guide editing for renders).
- Claimed 2026-11-27 ~11:35 IST (hub #2045 comment 7211172252). Branch
  `muse20/task-vyr-067` @ `83d53187` (base; main has since moved to `888d6461`
  — rebase owed at work-PR time, not now).
- Board on live main `888d6461` (verified first-hand this run): VYR-067
  AVAILABLE / muse_20 / branch null / pr null. The CLAIMED flip rides the
  coordinator board PR (ruling 7200564540 §3 — coordinator-only flips; no
  board hunk in my diff).

## Scope verified first-hand this run

- **Inputs LOCATE FAILED — confirmed, not assumed.** `CLASSIFICATION-2026-11-24.md`
  returns 404 at all four likely paths on main: repo root,
  `docs/collaboration/`, `VyralX/docs/`, `VyralX/`. Code search for the
  filename returns 8 hits, all mentions inside other docs, zero files named
  that. Ruling watch179 (b) stands: no classification file exists to edit
  against.
- **No prior VYR-067 work on main.** Code search for `TASK-VYR-067` returns
  0 hits; no checkpoint or evidence doc exists. Nothing to adopt, nothing
  duplicated.
- **Route source confirmed.** The VyralX "most-popular discovery" method is
  the candidate-pool precedent on main (VYR-051/053/054/055/057/087/089):
  latest instance VYR-089 (Muse 14, 2026-11-27 ~09:50 IST) — S2 flat-playlist
  via bridge `run_shell`, 6 queries, `ytsearch10`, 10 results per query,
  Shorts-length 15–60s, fresh, VYR-065 banned-niche guard; candidates recorded
  with exact view counts. That is the method VYR-067 re-derives from.

## Route (checkpoint 2)

1. Discovery run on S2 (same read-only operation class as VYR-089): 6 queries,
   ytsearch10, Shorts-length + fresh + niche-guard gates. **Top-3 by views
   among passing results = the reference videos.**
2. Extract the written editing style guide from the top-3: cuts, B-roll,
   captions, music — evidenced per video, not asserted.
3. Edit a new render against the guide: pauses cut, word-by-word captions,
   B-roll matched to spoken words, clean voice + SFX. Steps rest on the
   reel's on-screen text; spoken Telugu narration not recovered (named gap
   from the claim — carries forward, not hidden).

## Gap / block (named, not worked around)

- **Discovery run needs bridge `run_shell` on S2, and run_shell is reported
  down fleet-wide this run** (Muse 3, hub 7211839108: 5 failed attempts,
  S2+S3; WATCH209 §7: ~15 IncompleteRead/RemoteDisconnected transport faults
  this run). **No bridge call made this run.** Retry at checkpoint 2; if
  still down, post a one-line block and hold the discovery leg — do not
  substitute an unverified source for the top-3.
- Grant position: settled per WATCH205 §6 (owner order 2026-11-26 18:25:56 IST);
  my first-hand permissions record (21:28 IST Nov 26) still shows no
  run_shell grant on record — the discrepancy is recorded, not re-litigated
  here; no live leg runs on the disputed grant alone while the bridge itself
  is down.

## Format correction (Burn Enforcer 11:58 §G)

- My 11:35 claim post was flagged as an essay. Claims/completions go to the
  hub as the one-line record (CHAT | TASK | STATE | EVIDENCE | NEXT), ≤5
  lines. This checkpoint doc is evidence, not a hub post; hub posts from
  here conform.

## Five states

implemented NO / tested NO / merged NO / deployed NO / production-verified NO.
Checkpoint 1 is read-only scoping evidence; the style guide and the render
are owed.

## Next

Checkpoint 2: discovery run (bridge recovery permitting) + top-3 reference
videos + style-guide draft.

— Muse 20, 2026-11-27 ~12:35 IST
