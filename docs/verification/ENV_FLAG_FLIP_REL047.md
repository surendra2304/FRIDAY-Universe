# TASK-REL-047 — Deploy note: ENVIRONMENT / APP_ENV flip to production

**Status: PREPARED, NOT EXECUTED.** The server-side steps below are the deploy
action for the Memora half of TASK-REL-047 item 3 (decided in TASK-REL-045's
tuning table). They run on **Server 1** at deploy time, after the REL-047 PR
merges. Until they are executed and the §4 matrix re-run passes, item 3 is
**not deployed and not production-verified**.

## 1. Why

TASK-REL-045's live sweep (2026-11-15) found Memora is the only production
service whose generic env flags disagree with its own environment flag:

| Flag (deployed `/opt/friday_universe/Memora/.env`, read live 2026-11-15) | Value |
|---|---|
| `MEMORA_ENV` | `production` |
| `ENVIRONMENT` | `development` ← drift |
| `APP_ENV` | `development` ← drift |

Memora's auth production check (`apps/api/dependencies.py`) takes the
production branch when `MEMORA_ENV` **or** `ENVIRONMENT` is `production`, so
today the drift is latent (TASK-MEM-005 finding F5: "fail-closed behaviour
verified today; the drift is a latent trap, not a live hole"). But other code
paths read only the generic flags — `apps/api/routers/v1_events.py` and
`storage/relational/session.py` read `ENVIRONMENT`, `core/config.py` falls
back to `ENVIRONMENT` — so any future edit that drops or reorders the
`MEMORA_ENV` leg silently flips those paths to development behaviour in
production. The fix is to make all three flags agree: `production`.

Repo side (this PR): `Memora/.env.example` now ships all three flags as
`production` with the reasoning recorded inline.

## 2. Pre-flip snapshot (Server 1, read-only)

```bash
grep -E '^(ENVIRONMENT|APP_ENV|MEMORA_ENV)=' /opt/friday_universe/Memora/.env
sha256sum /opt/friday_universe/Memora/.env
systemctl is-active Memora   # record the unit name/state as found
```

Expected today: `ENVIRONMENT=development`, `APP_ENV=development`,
`MEMORA_ENV=production` (verified by the REL-047 crew on 2026-11-15).

## 3. Flip (Server 1)

```bash
cp -a /opt/friday_universe/Memora/.env /opt/friday_universe/Memora/.env.bak-rel047
chmod 600 /opt/friday_universe/Memora/.env.bak-rel047
sed -i 's/^ENVIRONMENT=.*/ENVIRONMENT=production/' /opt/friday_universe/Memora/.env
sed -i 's/^APP_ENV=.*/APP_ENV=production/'       /opt/friday_universe/Memora/.env
grep -E '^(ENVIRONMENT|APP_ENV|MEMORA_ENV)=' /opt/friday_universe/Memora/.env
# all three must now read production; MEMORA_ENV must be untouched
systemctl restart Memora
systemctl is-active Memora
curl -s http://127.0.0.1:8002/health   # must answer healthy before §4
```

Touch nothing else in the file. Key values are never printed or copied
anywhere outside the `.env` and its mode-600 backup.

## 4. Post-flip: MEM-005 auth-matrix re-run (MANDATORY)

The flip changes inputs to Memora's auth decisions, so the empirical matrix
from TASK-MEM-005 (`Memora/MEMORA_SHARING_AUDIT_MEM005.md`, §3–§5, run
MEM005F-2cf90132) **must be re-run in full immediately after the restart**,
using the same method: synthetic token-tagged records planted per agent
identity with each agent's own per-agent key (values stay server-side, read
from Memora's env by name only), the full matrix executed, then every probe
record hard-deleted as its owner and its absence verified three ways
(search as memora ✘, search as owner ✘, GET by id as owner 404).

Expected verdicts — **identical to MEM-005's recorded matrix**. Any cell
that differs is a behaviour change caused by the flip: stop, report the
diff cell-by-cell, and roll back (§5) unless the coordinator accepts the
change explicitly.

Read matrix (via `GET /v1/memories/search`; ✔ = returned, ✘ = not returned):

| Record ↓ / Reader → | friday | stratex | intelx | vyralx | memora |
|---|---|---|---|---|---|
| friday PRIVATE | ✔ | ✘ | ✘ | ✘ | ✘ |
| friday SHARED→[stratex] | ✔ | ✔ | ✘ | ✘ | ✘ |
| stratex PRIVATE | ✘ | ✔ | ✘ | ✘ | ✘ |
| stratex SHARED→[friday] | ✔ | ✔ | ✘ | ✘ | ✘ |
| intelx PRIVATE | ✘ | ✘ | ✔ | ✘ | ✘ |
| vyralx PRIVATE | ✘ | ✘ | ✘ | ✔ | ✘ |
| memora UNIVERSAL | ✘ | ✘ | ✘ | ✘ | ✔ |

Plus every secondary surface MEM-005 verified:

- `POST /v1/memories/query` and `GET /v1/memories/{id}`: same scope verdicts
  (cross-scope get-by-id = **404**, existence hidden).
- Legacy surface (`GET /memories/{id}`, `GET /memories`,
  `POST /memories/query`): identical denials.
- Planting rules still enforced: SHARED→[unregistered recipient] **403**;
  SHARED→[`*`] **403**; UNIVERSAL authored by a non-memora identity **403**.
- Auth negatives: no credentials → **401**; wrong key → **401**; mismatched
  name/key pair → **401**; unknown agent name → **503**.
- Non-owner mutations on friday's PRIVATE record (as stratex):
  `DELETE /v1/memories/{id}?hard=true` → **404**;
  `POST /v1/memories/{id}/share` → **404**;
  legacy `POST /memories/{id}/transition` → **422**; record survives intact.
- Body-selector spoof (write with another agent's `agent_id` in the body)
  → **403**.
- Decisive cells re-checked: (a) FRIDAY's env per-agent keys still
  authenticate as their owners (fingerprint comparison only — no values
  printed); (b) the master-key impersonation semantics are **unchanged**
  by this flip (that exposure is the separate MEM-005 remediation, not
  this task — the flip must neither widen nor narrow it silently; any
  change here is reported, not celebrated or hidden).

## 5. Rollback

```bash
cp -a /opt/friday_universe/Memora/.env.bak-rel047 /opt/friday_universe/Memora/.env
systemctl restart Memora
```

Then re-verify §2's snapshot values and the /health answer.

## 6. Stratex — the same flip (companion commit, same maintenance window)

TASK-REL-045's appendix recorded the identical drift in Stratex — "the same
flag incoherence as Memora's row, in the agent where fail-closed matters
most" — and referred it here. Verified live by the REL-047 crew on
2026-11-15 (Server 1, read-only):

| Flag (deployed `/opt/friday_universe/Stratex/.env`) | Value |
|---|---|
| `ENVIRONMENT` | `development` ← drift |
| `APP_ENV` | `development` ← drift |

Why it matters here: `Stratex/api/auth.py` decides production mode from
`ENVIRONMENT` alone (`_is_production()`), and `Stratex/dashboard.py` falls
back to `ENVIRONMENT`/`APP_ENV`, defaulting to `development`. Stratex's API
auth is therefore running with its production check **off** today — the
flip turns it on, which is the point, and is also why this half gets the
same caution as Memora's: any caller that was silently relying on
development-mode leniency will start failing, and that must surface in the
post-flip checks below, not in the trading daemon's next incident.

This is **not** a trading-parameter change: no risk, sizing, or strategy
value is touched (those are FWD-006/RISK-001 territory and out of scope).

### 6.1 Flip (Server 1, immediately after §3, same window)

```bash
grep -E '^(ENVIRONMENT|APP_ENV)=' /opt/friday_universe/Stratex/.env   # snapshot first
cp -a /opt/friday_universe/Stratex/.env /opt/friday_universe/Stratex/.env.bak-rel047
chmod 600 /opt/friday_universe/Stratex/.env.bak-rel047
sed -i 's/^ENVIRONMENT=.*/ENVIRONMENT=production/' /opt/friday_universe/Stratex/.env
sed -i 's/^APP_ENV=.*/APP_ENV=production/'       /opt/friday_universe/Stratex/.env
grep -E '^(ENVIRONMENT|APP_ENV)=' /opt/friday_universe/Stratex/.env   # both production
systemctl restart Stratex Stratex-Daemon   # use the unit names as found in the §2-style snapshot
systemctl is-active Stratex Stratex-Daemon
```

### 6.2 Post-flip checks (MANDATORY, before the window closes)

1. Stratex `/health` answers healthy on :8003.
2. One authenticated read with Stratex's own API credential succeeds
   (the credential stays server-side; only the HTTP status is recorded).
3. One **unauthenticated** API call is now rejected (401/403). Before the
   flip this same call is the control: record its pre-flip status in the
   snapshot step — if it was already rejected pre-flip, say so; the flip
   must not be credited with a change that did not happen.
4. The trading daemon's journal for the first full scan cycle after
   restart shows normal operation (scans running, no auth-error storm,
   no new exception class). The daemon must be reading the same `.env`
   (its unit's `EnvironmentFile` is this file — `deploy/Stratex-Daemon.service`).
5. Memora §4 matrix is unaffected by this half (different service), but
   both restarts happen in one window so any cross-effect is visible in
   the same journal pass.

Any failure in 1–4: roll back Stratex only
(`cp -a .env.bak-rel047 .env`, restart, re-verify) and report — do not
leave Stratex running on flipped flags with a known auth regression.

### 6.3 State

As of this note: **prepared, not executed** — the Stratex flip is not
deployed and not production-verified until §6.1–§6.2 are run and reported.
