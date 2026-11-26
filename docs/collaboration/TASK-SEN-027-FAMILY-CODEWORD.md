# TASK-SEN-027 — Family codeword as a named Sentinel guidance item

**Task:** TASK-SEN-027 — Sentinel: family secret-phrase anti-impersonation practice in
owner-security guidance (P2, Sentinel lane; IG package SE-03).
**Owner:** Muse 4. **Claim:** hub #1483 comment 7179307127, 2026-11-26 ~06:30 IST.
**Branch:** `muse4/task-sen-027-family-codeword`. **Work PR:** (stamped on the board
after creation; single work PR per owner order 7143628341 rule 1, board flip rides in it).

## Acceptance (board, verbatim)

> "The practice is a named Sentinel guidance item in the scam-verification flow: a
> family codeword any 'we are in trouble, send money' claim must produce, which the
> owner can set up. The phrase itself is never stored by the fleet."

Source: GAP-LIST.md section 2, TASK-SEN-FAMILY-PHRASE (IG package SE-03); practice
banked in `Sentinel/docs/SECURITY_REFERENCE_IG.md` §5 (2026-11-16 full re-watch,
supervisor-audited). Assigned to Muse 4 by the coordinator (watch085), queue position
3 behind TASK-SEN-032 and TASK-SEN-026 — both MERGED on main before this claim, so
SEN-027 was the queue head.

## What was already there, what was missing

- The SE-03 practice already existed as reference prose in
  `Sentinel/docs/SECURITY_REFERENCE_IG.md` §5 — agree one phrase offline/in person,
  any urgent money/credentials/secrecy request must produce it, agree before travel,
  burned phrase → re-agree in person. It was not wired into any live flow.
- The scam-verification flow is `Sentinel/app/services/extortion_mail_triage.py`
  (TASK-IG2-SEN-06): it classifies received mail and produces calm do-not-pay
  guidance. It had no family-codeword item and no detection of the "in trouble,
  send money" plea shape. (Verified: grep for codeword/family/secret-phrase in the
  module before this change returned nothing; the module is the only scam flow in
  Sentinel/FRIDAY services.)

## Change (3 files + board)

`Sentinel/app/services/extortion_mail_triage.py`
- `FAMILY_CODEWORD_GUIDANCE` — the named guidance item, carrying the whole practice:
  the claim must produce the codeword before anything moves; no codeword, no
  transfer, call the person back on a number already trusted; agree one codeword
  offline, in person, before travel; never write it into a chat, email or note;
  burned → re-agree a new one in person; "The fleet never stores the codeword —
  there is nothing to look up, only something to ask for."
- Plea detection: `_TROUBLE_PLEA_RE` (in trouble / stranded / stuck abroad /
  stuck overseas / in jail / locked up / arrested / in (the) hospital / had an
  accident / emergency) AND a money request (payment demand or a monetary amount).
  Bare "abroad"/"overseas" is deliberately not a marker on its own — a tuition mail
  would match. Trouble without a money ask is a notification, not a plea.
- Named signal `family_impersonation_plea` (+1 score, like the tracking pixel) and
  a `family_plea` flag on the verdict, exposed in `as_dict()`; `to_markdown()`
  carries a "**Family codeword (SE-03)**" section when the flag is set.

`Sentinel/tests/test_ig2_sen_extortion_mail_triage.py` — 7 new tests (see below).

`docs/collaboration/WORK_BOARD.yaml` — SEN-027 AVAILABLE → IN_REVIEW (owner muse_4,
branch stamped; pr stamped after PR creation).

No workflow change: the test file is already in the Sentinel tier-1 list in
`.github/workflows/friday-universe-ci.yml` (line 390 on main, added by SEN-026).

## Design decision, stated plainly

Unlike the tracking pixel (TASK-SEN-026 precedent: signal + flag only, guidance
stays empty on NOT_EXTORTION), the codeword guidance fires **even when the mail is
not extortion** — category stays NOT_EXTORTION, no verdict is manufactured. Reason:
a trouble-plea + money-request is itself the scam shape the codeword guards; a
plain "Mum, I'm in trouble abroad, send $500" mail has no threat and no ransom
framing, so under the old rule the owner would get a bare NOT_EXTORTION verdict
with no instruction — the feature would be dead for its primary shape. The pixel
precedent differs because pixels are common in legitimate mail; a plea is not.
The module docstring records this difference. The false-positive cost is one
extra advisory line (e.g., a charity "emergency — send money" mail); the
false-negative cost is an unguarded impersonation plea. Recall over precision,
deliberately, for a guidance-only signal that never changes the verdict.

## No-storage rule, verified

The module accepts no phrase and stores none: `triage_email` takes only
`(subject, body, headers)`; the result has no `codeword`/`phrase` attribute or
result key; the only "codeword" in the module is the guidance item itself. Pinned
by `test_codeword_is_never_stored` (signature inspection + attribute/key checks).

## Verification (local, first-hand this run)

Worktree at main `dd659e3e` + the edited files; venv
`~/workspace/muse4-runs/sen027-venv` (Python 3.12, pytest + the conftest chain's
deps installed: pydantic, pydantic-settings, sqlalchemy, fastapi, httpx, greenlet —
the root `tests/conftest.py` imports the full agent mesh).

- `pytest Sentinel/tests/test_ig2_sen_extortion_mail_triage.py`: **18 passed,
  0 failed** (11 pre-existing + 7 new SEN-027 tests), with the root conftest
  loaded. One pre-existing warning only: `asyncio_mode` unknown-config
  (pytest-asyncio not in the local venv; CI has it).
- `py_compile` clean on both edited files; `ruff check` clean on both.
- Pre-change behaviour re-checked, not assumed: the 11 pre-existing tests pass
  unchanged (no category or guidance regressions); the tuition-mail and
  trouble-without-money cases pin the two-part plea gate.
- New tests: plea triggers codeword guidance on NOT_EXTORTION; plea + threat is
  FAKE_RANSOM_DEMAND with the codeword item alongside base guidance; trouble
  without a money request is not a plea; money request without trouble is not a
  plea; bare "abroad" is not a plea; guidance states setup + no-storage;
  codeword is never stored.

## Live leg

N/A — library-only change, no endpoint, no fleet state. Behaviour proven by the
unit suite (same standing as SEN-026). No live step taken; owner stop order
untouched. The practice itself is owner-side (agree the phrase with family
offline); there is nothing for the fleet to deploy.

## Five states

- Implemented: YES
- Tested: YES (local, 18/18; CI pending at PR time — not claimed green)
- Merged: NO (work PR open, awaiting Muse — workers never merge)
- Deployed: N/A (library-only)
- Production-verified: NO (live leg N/A; see above)

## Queue after SEN-027

None assigned — SEN-027 was the last item in the watch085 queue (SEN-032 →
SEN-026 → SEN-027). Next pull comes from the pool at merge, per the central-pool
model (Stratex/VyralX first; WATCH129 pool floor is 6 unassigned EARN tasks).

— Muse 4, 2026-11-26
