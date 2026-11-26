# TASK-WEB-005-FIX-01 — EVIDENCE — 2026-11-27 ~02:25–03:00 IST — Muse TP1

Claim: hub #1483 comment 7202161226 (2026-11-27 ~01:25 IST; board assignment
WATCH180 §4 + Burn Enforcer 01:00 §C). Branch: musetp1/task-web-005-fix-01,
re-based onto current main `cd94db08` this run (claim-only branch, zero
commits of its own — ref moved 93628618 → cd94db08, verified by read-back).
Task: mount Halo at /halo on the live gateway (coordinator ruling in
principle, WATCH178). Board on main `cd94db08` verified first-hand this run:
FIX-01 AVAILABLE / owner muse_tp1 / branch null / pr null, P2; WEB-005
MERGED (PR #2009, merge `eb72a46a`); WEB-007 AVAILABLE / owner muse_tp1;
FRD-062 AVAILABLE / owner muse_tp1.

## Verdict: IMPLEMENTED (repo leg) — live leg DEPLOY-GATED, filed below

| State | Standing |
|---|---|
| Implemented | YES — route + gateway record in this PR |
| Tested | PARTIAL — local build NOT run this run (see §4); PR CI is the build gate |
| Merged | NO — work PR open, awaiting peer verification / coordinator merge |
| Deployed | NO — deploy leg is G2-gated; exact command list filed in §5 |
| Production-verified | NO — the live check in §5 is owed after the deploy leg |

Decision recorded: MOUNT, not retire. The board acceptance names the mount
("Mount Halo at /halo on the live gateway"), WATCH180 ruled it in principle,
and the owner's WEB-003 pick is untouched — the home route (/) still renders
the ULTRON stage unconditionally. The retire alternative is not taken.

## 1. Scope — code (verified first-hand on main `cd94db08`)

- `FRIDAY/ui/app/page.tsx` renders ThemeRoot; `FRIDAY/ui/components/
  ThemeRoot.tsx` (TASK-WEB-003, amended 2026-11-17) renders UltronStage
  UNCONDITIONALLY. Owner's 2026-11-17 pick: ULTRON is the only theme.
- The Halo stage is `FRIDAY/ui/components/stage/Stage.tsx` (TASK-WEB-002):
  the halo + rim lights + Conversation + veil (Cmd/Ctrl-K, "Everything
  else" summon pill, wordmark) + eleven sheets — fleet, chronicle, pulse,
  life, galaxy, showcase, tour, city, editorial, rank, orb. Present on
  main, mounted nowhere since WEB-003. All of its imports verified present
  this run: every sheet file, Veil, Sheet, WakeListener, reactbits
  Orb/SplitText/Magnet, `lucide-react` in package.json dependencies.
- The app is a static export (`FRIDAY/ui/next.config.ts`: `output:
  "export"`, `basePath: "/friday"`, `trailingSlash: true`). A new route
  `app/halo/page.tsx` exports to `out/halo/index.html`, served at
  `/friday/halo/`. The root layout (`app/layout.tsx`) already loads
  `globals.css` + `ultron.css`, so the Halo stage's styles ride along.
- Route pattern follows the proven `/start` route (`app/start/page.tsx`,
  TASK-IG2-WEB-07): a page component + one quiet fixed back-link. The halo
  page does NOT wrap Stage in a second `<main>` — Stage renders its own
  `<main class="stage">`. The back-link points at `/`, which Next resolves
  to `/friday/` under the basePath — the live Ultron home.

## 2. Scope — gateway (verified first-hand via bridge, read-only)

- Public ingress `https://friday-universe.duckdns.org`; Caddy on Oracle
  Server 2 reverse-proxies the FRIDAY service on FRIDAY-Server
  (15.134.130.145:10000). Live `/etc/caddy/Caddyfile` read this run:
  `handle_path /friday*` → FRIDAY-Server; a catch-all `handle` → the same
  service; no `/halo` handle exists.
- The FRIDAY service (`FRIDAY.service`, active running, :10000, pid 63565)
  mounts the export twice (`FRIDAY/src/friday/api/server.py:6632-6637`):
  `/friday` → StaticFiles(out, html=True) and `/` →
  _APIAwareStaticFiles(out, html=False). `_UI_EXPORT_DIR` is the checkout's
  `FRIDAY/ui/out`.
- Consequence, verified by reading the mount code: once `out/halo/
  index.html` exists in the FRIDAY-Server checkout, `/friday/halo/` serves
  it (200) through the existing `/friday*` handle — no service restart is
  needed, StaticFiles reads from disk per request. The bare-domain `/halo`
  does NOT work without a gateway rewrite: the `/` mount has html=False,
  so `/halo` (a directory) 404s and a browser gets the Ultron shell with a
  404 status. The rewrite in §3 is therefore required, not optional.
- The halo page's own assets are `/friday/_next/…` (basePath) and already
  pass through the existing `/friday*` handle; only the page request
  itself needs the rewrite.

## 3. Implementation — this PR

- `FRIDAY/ui/app/halo/page.tsx` (new): renders `<Stage />` with metadata
  title "FRIDAY — Halo" and a fixed back-link "← ULTRON" to `/`.
- `FRIDAY/ui/app/page.tsx`: comment updated — Halo lives at `/halo`, it
  is not "selected" here. No behaviour change; `/` still renders Ultron.
- `FRIDAY/ui/components/ultron/UltronStage.tsx`: one comment line updated
  ("one switch away" → "one route away, at /halo"). No behaviour change.
- `deploy/Caddyfile`: new `handle /halo*` before the catch-all `handle`,
  rewriting `*` to `/friday/halo/` and proxying to the FRIDAY service
  (S1-mirror upstream 127.0.0.1:10000, as the rest of the file). This is
  the versioned record of the mapping; the Server 2 live-file port is
  part of the deploy leg in §5. Precedent: TASK-IG2-WEB-04-FIX-01 (repo
  Caddyfile change → S2 live-file port).
- No `WORK_BOARD.yaml` hunk in this PR (board flips are coordinator-only,
  ruling 7200564540 §3; WATCH182 §2b). The FIX-01 flip rides in the next
  coordinator board PR.
- `FRIDAY/ui/out/` is NOT refreshed in this PR: it is rebuilt at deploy
  (§5 step 4) and refreshed in bulk on main (last at merge 37e030c7).

## 4. Tests — what ran and what did not

- Local build NOT run this run: no `npm ci` / `npm run build` was executed
  here, so no local export was produced and `out/halo/index.html` is not
  in this PR. Stated plainly rather than claimed.
- Build gate is PR CI: `.github/workflows/voice-startup-regressions.yml`
  runs `npm ci` + `npm run build` in `FRIDAY/ui` (with
  NEXT_TELEMETRY_DISABLED=1) on the PR. A green CI run proves the route
  compiles and exports; a red one blocks the merge. The route mirrors the
  proven `/start` pattern and every import it pulls in was verified
  present on main (§1), so the expected CI outcome is green.
- Repo validator: `scripts/validate_collaboration.py` run on this branch
  before push — result recorded in the PR body at open time (re-check on
  read-back; if it reports anything, it is named there, not hidden).

## 5. Live leg — DEPLOY-GATED (G2 not cleared, WATCH181 §2e)

The live leg runs under standing clearance 7200564540 (WATCH182 §2d —
"run them or release the task"), but the deploy itself is a server change:
G2 deploy is NOT cleared and server moves are banned, so the steps below
are FILED for coordinator-side execution (same fallback as WATCH183 §2b
for TP6's S2 route), not executed by this run. Muse: execute or rule.

Preconditions found read-only this run (deploy must account for them):
- FRIDAY-Server checkout `/opt/friday_universe` is at `5b245ffd`
  (2026-11-24) with LOCAL modifications to `FRIDAY/ui/out/404.html`,
  `FRIDAY/ui/out/404/index.html`, `FRIDAY/ui/out/__next.__PAGE__.txt`,
  `FRIDAY/ui/out/__next._full.txt`, `FRIDAY/ui/out/__next._tree.txt`.
  A plain `git pull` may conflict on those files — discard them first
  (step 2); the rebuild in step 4 regenerates them from source.
- The FRIDAY service needs NO restart for static-export changes
  (StaticFiles reads from disk); restart only if the live check in step 7
  still serves the old tree.

Deploy command list (exact, in order):
1. FRIDAY-Server (server 3): `git -C /opt/friday_universe status --short
   FRIDAY/ui/out/` — expect the local modifications above, nothing else.
2. FRIDAY-Server: `git -C /opt/friday_universe checkout --
   FRIDAY/ui/out/` — discard the live-only out/ edits so the pull is clean.
3. FRIDAY-Server: `git -C /opt/friday_universe pull origin main` — expect
   the FIX-01 merge commit at HEAD (or use the fleet's usual pull method).
4. FRIDAY-Server: `cd /opt/friday_universe/FRIDAY/ui &&
   NEXT_TELEMETRY_DISABLED=1 npm ci --no-audit --no-fund && npm run build`
   — verify node exists on the server first; if absent, build on a machine
   with node and copy the whole rebuilt `out/` tree in instead (a partial
   copy of only `out/halo/` is NOT enough — the route's hashed chunks are
   new files).
5. FRIDAY-Server: `ls /opt/friday_universe/FRIDAY/ui/out/halo/index.html`
   — must exist; `grep -c 'class="stage"'` on it — must be ≥ 1.
6. Server 2: back up the live Caddyfile (`cp /etc/caddy/Caddyfile
   /etc/caddy/Caddyfile.bak-20261127`), insert the `/halo` handle from §3
   BEFORE the catch-all `handle`, with the S2 upstream
   `15.134.130.145:10000` (not the file's 127.0.0.1:10000), then `caddy
   validate --config /etc/caddy/Caddyfile` and `caddy reload` (or the
   `oracle_caddy_reload` bridge tool).
7. Live check (real browser, no sign-in, desktop): GET
   `https://friday-universe.duckdns.org/halo` → 200, Halo stage markup
   (class "stage", wordmark FRIDAY, summon pill "Everything else");
   Ctrl+K → veil lists Editorial / Rank / Orb; open each sheet once —
   that is the live proof for WEB-005's three unverified items
   (IG-WEB-08, IG2-WEB-02, IG2-WEB-03). GET `/friday/halo/` → 200, same
   page. GET `/` → still the Ultron stage, unchanged. Record status codes
   + screenshots in this doc as a follow-up commit, or as a hub post
   linked here. Slow-network leg: owed on re-verification (browser
   tooling here provides no throttling; the decisive checks above are
   viewport-independent).

## 6. Queue and next

Queue stands: FIX-01 (head, this PR) → WEB-007 (pre-staged) → FRD-062.
On merge of this PR, the next driver run pulls WEB-007 — it is gated on
the same FIX-01 ruling only in the sense that its Toprank/Orb legs need
the Halo sheets reachable, which this mount provides.

## 7. Sources

- Hub: claim 7202161226; status 7203199773; WATCH182 7202475247 (+
  follow-up 7202524826); WATCH183 7203117194; MAXIMUM BURN 7202080409.
- Code on main `cd94db08`: `FRIDAY/ui/app/page.tsx`,
  `FRIDAY/ui/components/ThemeRoot.tsx`,
  `FRIDAY/ui/components/stage/Stage.tsx`,
  `FRIDAY/ui/components/ultron/UltronStage.tsx`,
  `FRIDAY/ui/next.config.ts`, `FRIDAY/ui/app/start/page.tsx`,
  `deploy/Caddyfile`, `.github/workflows/voice-startup-regressions.yml`.
- Live (bridge read-only, 2026-11-27 ~02:40–02:55 IST): Server 2
  `/etc/caddy/Caddyfile` (full file); Server 3 `FRIDAY/src/friday/api/
  server.py:6580-6650, 6247`; `FRIDAY.service` active running, :10000
  listening (pid 63565); checkout `5b245ffd` + local out/ modifications.

— Muse TP1
