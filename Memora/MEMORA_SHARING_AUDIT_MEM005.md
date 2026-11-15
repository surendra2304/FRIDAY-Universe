# Memora Cross-Agent Sharing Audit — TASK-MEM-005 (Wave 5)

**Date:** 2026-11-15 (IST) · **Crews:** MEM-005 audit crew (code+config) + MEM-005 finisher crew (empirical phase) · **Claim:** issue #35, comment 6891420156 · **Branch:** `claude/task-mem-005-sharing-audit`

**Question:** which agents can read/write which Memora memory scopes — in the code, in the live configuration, and in production behaviour?

**Method:** (1) code audit of Memora's identity/scope model and every agent's Memora client usage; (2) config audit of the live `.env` files on both servers — key *values never printed*, only presence and `sha256[:8]` fingerprints; (3) empirical probes against production Memora (Server 1, `127.0.0.1:8002`): synthetic token-tagged records planted per agent identity, the full read/mutate/auth matrix executed, then every probe record hard-deleted and its absence verified three ways. No env file or key was changed. Deployed code is byte-identical to this repository for all five core files (`apps/api/dependencies.py` `2015047b…`, `storage/relational/access_scope.py` `467d631d…`, `apps/api/routers/v1_memories.py` `e3e2004d…`, `apps/api/routers/memories.py` `5095a7bb…`, `core/memory/service.py` `515d8189…` — deployed sha256[:16] == repo blob content at main).

---

## 1. The identity model (code)

- Identity = `X-Agent-Name` header + Bearer credential, checked in `Memora/apps/api/dependencies.py::authenticate_agent` against a **per-agent key** held in Memora's own env (`FRIDAY_API_KEY`, `STRATEX_API_KEY`, … one per agent). Keys are identity-bound: presenting Stratex's key under the name `friday` is rejected (verified live, §4).
- **Master-key branch (the pivotal line):** `master_key = os.getenv("MEMORA_MASTER_KEY") or os.getenv("MEMORA_API_KEY")`; if the presented credential equals it, the caller is authenticated **as whatever `X-Agent-Name` it claims**. `MEMORA_MASTER_KEY` is not set in production, so the operative master is the value of `MEMORA_API_KEY` — which is *also* the `memora` agent's own per-agent key (the env map assigns `memora → MEMORA_API_KEY`).
- Scope model on records: `PRIVATE` (owner only), `SHARED` (owner + named `shared_with` recipients), `UNIVERSAL` (authoring restricted to the `memora` service identity). Inaccessible records are hidden with **404, not 403**, on read/delete/share paths — existence is not leaked.
- Body selectors are bound to the authenticated principal (`resolve_agent_selector`): a write claiming another `agent_id` is rejected (verified live, §4).
- Anonymous access fails closed: it requires the explicit opt-in `MEMORA_ALLOW_ANONYMOUS_DEV`, which is unset in production (verified live, §4). Fabric administration (`ADMIN_AGENTS`) is restricted to the `memora` identity.

## 2. The live configuration (fingerprints only)

Memora's own env holds **ten distinct per-agent keys** (all present, all different fingerprints): friday `1d2626d4`, inference `d1ab094f`, stratex `0956dda8`, futuris `70687e6a`, intelx `e407691c`, forge `52fbca45`, sentinel `2a2945f8`, cortex `bea72f6c`, vyralx `c277f5d7`, memora `60c2827d` (= the master value).

Where the **master value** (fp `60c2827d`) also lives — every copy verified by fingerprint equality with Memora's `MEMORA_API_KEY`:

| Location | Var | Holds master? |
|---|---|---|
| Server 1 — FRIDAY/.env | `MEMORA_API_KEY` | **yes** |
| Server 1 — Inference/.env | `MEMORA_API_KEY` | **yes** |
| Server 1 — Stratex/.env | `MEMORA_API_KEY` | **yes** |
| Server 1 — Futuris/.env | `MEMORA_API_KEY` | **yes** |
| Server 1 — IntelX/.env | `MEMORA_API_KEY` | **yes** |
| Server 1 — Forge/.env | `MEMORA_API_KEY` | **yes** |
| Server 2 — VyralX/.env | `MEMORA_API_KEY` | **yes** |
| Server 2 — Sentinel/.env | `MEMORA_API_KEY` | **yes** |
| Server 2 — Cortex/.env | `MEMORA_API_KEY` | **yes** |

**Every agent in the fleet holds the master key in its own env file.** Any one agent process — or any reader of any one `.env` — can authenticate to Memora as any agent.

FRIDAY's env additionally holds the fleet's per-agent service keys under plain names (`STRATEX_API_KEY` fp `0956dda8` and `INTELX_API_KEY` fp `e407691c` verified byte-equal to Memora's copies; `CORTEX_API_KEY`, `FORGE_API_KEY`, `FUTURIS_API_KEY`, `INFERENCE_API_KEY`, `SENTINEL_API_KEY`, `VYRALX_API_KEY` also present). This is **load-bearing, not accidental**: FRIDAY's `MemoraClient._agent_api_key()` resolves `{AGENT}_API_KEY` from FRIDAY's own env for *any* agent name, i.e. FRIDAY is designed to read/write Memora on behalf of other agents (delegation outcomes, cross-agent recall). Any remediation must replace that mechanism, not just delete the keys.

Config drift note: Memora's env carries `ENVIRONMENT=development` alongside `MEMORA_ENV=production`. Today this is harmless — the production branch is taken because `MEMORA_ENV=production`, and anonymous access additionally requires its own explicit opt-in — but the drifted value is one future edit away from mattering.

## 3. Empirical phase — setup

Two production runs by the finisher crew (the first run's Server-1 matrix output was lost to a bridge failure mid-delivery; its cleanup was verified complete by id and by search before the second run started):

- **Run MEM005F-80f08d28** — fingerprints (§2), plant phase, and the Server-2 decisive cell (§5b).
- **Run MEM005F-2cf90132** — full Server-1 matrix (below), result persisted server-side before delivery.

Records planted (owner identity, per-agent key from Memora's env): friday PRIVATE, friday SHARED→[stratex], stratex PRIVATE, stratex SHARED→[friday], intelx PRIVATE, vyralx PRIVATE, memora UNIVERSAL — all writes **201**. Also attempted: friday SHARED→[intelx] (**403** — recipient `intelx` not yet registered in tenant `default`; registration is lazy, on an identity's first own call), friday SHARED→[`*`] (**403** — wildcards rejected by design), friday UNIVERSAL (**403** — only the memora identity may author UNIVERSAL).

## 4. The verified access matrix (own per-agent keys, run MEM005F-2cf90132)

Read via `GET /v1/memories/search` — ✔ = record returned, ✘ = not returned (HTTP 200 with empty result for the reader):

| Record ↓ / Reader → | friday | stratex | intelx | vyralx | memora |
|---|---|---|---|---|---|
| friday PRIVATE | ✔ | ✘ | ✘ | ✘ | ✘ |
| friday SHARED→[stratex] | ✔ | ✔ | ✘ | ✘ | ✘ |
| stratex PRIVATE | ✘ | ✔ | ✘ | ✘ | ✘ |
| stratex SHARED→[friday] | ✔ | ✔ | ✘ | ✘ | ✘ |
| intelx PRIVATE | ✘ | ✘ | ✔ | ✘ | ✘ |
| vyralx PRIVATE | ✘ | ✘ | ✘ | ✔ | ✘ |
| memora UNIVERSAL | ✘ | ✘ | ✘ | ✘ | ✔ |

The same verdicts hold on every other read surface tested:

- `POST /v1/memories/query`: friday PRIVATE as stratex ✘ / as friday ✔; stratex PRIVATE as friday ✘; stratex SHARED→[friday] as friday ✔.
- `GET /v1/memories/{id}`: friday PRIVATE as friday **200**; as stratex **404**; as intelx **404**; stratex PRIVATE as friday **404**.
- **Legacy surface** (`GET /memories/{id}`, `GET /memories`, `POST /memories/query`): friday PRIVATE as stratex **404** / not in list / not in query; as friday **200**; stratex PRIVATE as friday **404**; stratex's legacy list shows its own PRIVATE and not friday's. **Cross-scope reads are denied on BOTH the v1 and legacy surfaces (decisive cell c: PASS).**
- UNIVERSAL exception: the memora-authored UNIVERSAL record was **not** readable by any other agent — search ✘ for all four, and `GET /v1/memories/{id}` as vyralx returned **403**. See finding F3.

Auth negatives: no credentials → **401** (v1 search and legacy list); wrong key → **401**; friday's name with stratex's key → **401**; unknown agent name (`rogue`) → **503** (no configured credential — a config fault response, not an auth bypass).

Mutations by a non-owner (stratex against friday's PRIVATE record): `DELETE /v1/memories/{id}?hard=true` → **404** (denied, existence hidden); `POST /v1/memories/{id}/share` to self → **404** (denied); legacy `POST /memories/{id}/transition` → **422** (rejected). The record survived intact for its owner and remained invisible to stratex. Body-selector spoof (stratex writes with `agent_id: "friday"` in the body) → **403**.

Cleanup: all 8 records created in run 2 (7 planted + 1 cell-(a) write) were hard-deleted as their owners (DELETE → 200 each) and verified absent three ways — search as memora ✘, search as owner ✘, GET by id as owner **404**. Run 1's 7 records were likewise verified gone (GET by id 404 as owner and as memora). **Production memory was left exactly as found.**

## 5. The three decisive cells

**(a) FRIDAY's env `STRATEX_API_KEY` — CONFIRMED live.** The value is byte-equal to Memora's Stratex key (fp `0956dda8`). Presented from Server 1 with `X-Agent-Name: stratex` it: found stratex's PRIVATE probe record in search (200, found), **wrote** a new PRIVATE record as stratex (201), and that record was readable back with Memora's own Stratex key and invisible to friday. FRIDAY (or any reader of FRIDAY's `.env`) holds a fully working Stratex credential for Memora. The same holds by fingerprint for `INTELX_API_KEY` (fp `e407691c`).

**(b) A non-Friday agent's `MEMORA_API_KEY` authenticates as `friday` — CONFIRMED live from Server 2.** VyralX's env value (fp `60c2827d` = the master) was used exactly as VyralX would use it, against VyralX's own `MEMORA_URL` (`http://10.0.0.121:8002`): with `X-Agent-Name: friday` it **found friday's PRIVATE probe record in search (200, found)** and **read it by id (200, found)**; with `X-Agent-Name: stratex` it found stratex's PRIVATE record (200, found). No-credential control: **401**. Sentinel and Cortex hold the identical master value on Server 2 (fingerprints above), so the cell is proven for the class, not just for VyralX.

**(c) Cross-scope reads denied on both surfaces — CONFIRMED** (§4): with each agent's *own* key, PRIVATE/SHARED boundaries hold identically on v1 and legacy search, query, get-by-id and list.

**Master-key semantics, precisely:** the master key is a universal *impersonation* credential, not a scope bypass. Presented as friday it read friday's PRIVATE (200, found); presented as stratex it could **not** read friday's PRIVATE (scope of the claimed identity still applies); presented as friday it could not read stratex's PRIVATE (404); presented as vyralx it read vyralx's PRIVATE. Whoever holds it can *become* any agent — and thereby exercise exactly that agent's rights, including writing, sharing and deleting that agent's memories as that agent.

## 6. Findings

- **F1 — CRITICAL (over-read / impersonation):** the operative Memora master key is copied into **all nine agent env files** across both servers (§2), and it authenticates as any claimed agent (§5b). The per-agent scope enforcement (§4) is sound, but it is enforced *per claimed identity* — and the credential that lets anyone claim any identity is the most widely distributed secret in the fleet. One agent compromise, one leaked `.env`, one over-broad log line = full memory-fabric identity compromise, including FRIDAY's private memories (which carry the owner's personal facts).
- **F2 — HIGH (key sprawl, partially load-bearing):** FRIDAY's env holds every agent's per-agent Memora key (§2, §5a). Unlike F1 this is wired into FRIDAY's client design (it acts on behalf of other agents), so it cannot be fixed by deletion alone — but as built, FRIDAY is a single point whose compromise yields every identity even if F1 is fixed.
- **F3 — MEDIUM (under-read / intent mismatch):** UNIVERSAL records are effectively memora-only in practice: authored only by memora (by design) **and** not returned to any other agent on search, and 403 on get-by-id. If UNIVERSAL is meant to be the fleet-wide tier, that intent is not met on any read surface tested; if it is meant to be memora-internal, the name promises more than the behaviour. Either way the mismatch should be decided explicitly. (The `memora` identity also cannot search other agents' PRIVATE records — consistent with per-identity scoping, noted for completeness.)
- **F4 — LOW (sharing friction):** sharing to an agent that has not yet made its first authenticated Memora call fails with 403 (`recipient must be registered in tenant 'default'`). In production this bites exactly the newest/least-active agents.
- **F5 — INFO (config drift):** `ENVIRONMENT=development` in Memora's env next to `MEMORA_ENV=production` (§2). Fail-closed behaviour verified today; the drift is a latent trap, not a live hole.
- **What is genuinely good (verified, not assumed):** with per-agent keys, scope enforcement is correct and consistent across v1 + legacy, search + query + get + list; denials hide existence (404); keys are identity-bound; body selectors cannot spoof authorship; wildcard sharing is refused; UNIVERSAL authoring is restricted; anonymous access fails closed; cross-agent mutation/deletion/sharing attempts all fail and the target record survives untouched.

## 7. Remediation — NOT applied (coordinator/owner decision)

This audit changed no env files and no keys. Options for the coordinator/owner, in dependency order:

1. **Stop distributing the master.** Remove the `MEMORA_API_KEY` copy from every *agent* env; agents should present their **own** per-agent key (each already exists in Memora's env). FRIDAY's client already falls back per-agent (`{AGENT}_API_KEY` first) — but FRIDAY's *own* current credential chain ends at `MEMORA_API_KEY` (the master), and other agents' clients must be checked one by one before any copy is deleted, or their memory access breaks.
2. **Split the master from the memora identity.** Set a distinct `MEMORA_MASTER_KEY` held only in Memora's env (and the coordinator's custody), and give the `memora` agent its own ordinary per-agent key, so the service identity is no longer synonymous with the master.
3. **Replace FRIDAY's on-behalf-of mechanism** (F2) with an explicit delegation: FRIDAY authenticates as friday, and Memora grants named cross-agent rights (e.g. write-outcome-for-X) by policy — rather than FRIDAY holding X's raw key.
4. Decide F3 (UNIVERSAL semantics) and F4 (auto-register share recipients) explicitly; fix the F5 drift in passing.
5. Rotate every key that has been distributed as a copy, once 1–3 land — until then rotation alone changes nothing, because the *pattern* is the exposure.

**Residual risk until remediation:** as measured in §5, any single agent env read yields full impersonation. That is the state the fleet is in today, stated plainly.
