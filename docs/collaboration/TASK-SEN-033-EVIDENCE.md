# TASK-SEN-033 — Evidence: Sentinel repos wave 3

**Worker:** Muse 7 · **Date:** 2026-11-27 · **Base main:** `5806c273`
**Claim:** hub #2045 comment `7222826984` (REL-002 complete + SEN-033 claimed).
Hub re-read after the claim found no competing SEN-033 claim and no
SEN-033-specific live-leg clearance.

## Board acceptance

REPO-IMPLEMENT wave 3, target Sentinel:

- PentAGI — reference-only.
- Anthropic Cybersecurity Skills — adapt.
- Adapt entries must run in the target agent's live production path, proven
  by one real end-to-end use including a failure case.
- Reference-only entries need live/guardrail evidence, not a paper judgement.
- Approval-path items need one low-risk auto-approve and one high-risk
  Telegram prompt on the live Sentinel service, each exactly once; otherwise
  the item's own live security check runs against the real surface.

## Item 1 — Anthropic Cybersecurity Skills (adapt)

### What already existed

TASK-IG2-SEN-01 had already cherry-picked a defensive-only pack:

- `Sentinel/app/services/defensive_skills.py` — fail-closed loader. It raises
  `DefensiveSkillPolicyError` for any skill whose tier is not exactly
  `defensive`, whose name is excluded, or whose domain is an excluded
  offensive category.
- `Sentinel/skills/defensive/` — 10 defensive skills plus `manifest.json` and
  `NOTICE.md` (Apache-2.0 provenance; independent community project by
  Mahipal Jangra / mukul975, NOT affiliated with Anthropic PBC).
- `tests/test_ig2_sen_defensive_skills.py` — loader/pack tests.

### Gaps verified first-hand

1. **Loader unwired.** GitHub code search for `defensive_skills` returned 5
   hits only: the loader, `NOTICE.md`, two collaboration docs, and the root
   test. No runtime import/call existed in `Sentinel/app/` or
   `Sentinel/sentinel/`.
2. **Pack test uncollected by CI.** `tests/test_ig2_sen_defensive_skills.py`
   appeared in no pytest list in `.github/workflows/friday-universe-ci.yml`;
   the Sentinel tier-1 list named five Sentinel-local files only.

### Change in this PR

- `Sentinel/app/services/cyber_skills_service.py` now loads the defensive
  pack at `CyberSkillsService` construction and merges it into the catalog
  used by the service and its engine. Duplicate pack skill IDs fail closed
  instead of overwriting a catalog skill silently.
- `CyberSkillsService.triage` now builds its incident report with the merged
  catalog, so pack skills appear in triage crosswalks and recommendations.
- `capabilities()` now includes the defensive pack audit.
- Pack framework mappings were normalized to Sentinel's framework tables
  (CSF 2.0 `PR.AA`/`ID.IM`, valid D3FEND IDs, and ATT&CK `T1557` added to
  `TECHNIQUE_TACTICS`) so the merged catalog keeps
  `invalid_mappings == []`.
- `.github/workflows/friday-universe-ci.yml` now collects
  `Sentinel/tests/security/test_sen033_sentinel_repo_implement.py` in the
  Sentinel tier-1 set; the repo-root defensive/SEN-033 tests run in the
  monorepo validation root suites.
- The SEN-033 tests prove the wiring: pack loaded into catalog, T1110
  triage recommends `detecting-ssh-brute-force`, search/authorise work for
  the pack skill, offensive authorise is denied under a defensive scope,
  offensive or missing packs fail closed, and catalog mappings are valid.

### Repo-side end-to-end proof run

Local VM has no `pytest` module (`python3 -m pytest` →
`No module named pytest`), so the same assertions were run directly with
`python3` against the fetched repo subset; CI is the pytest executor for
this PR. Observed output:

```text
pack 10 True
catalog skill defensive ['T1110', 'T1110.001', 'T1078']
triage skills ['detecting-ssh-brute-force', 'active-directory-hardening', 'analyzing-network-traffic-of-malware']
search {'skill': 'detecting-ssh-brute-force', 'name': 'detecting ssh brute force', 'tier': 'defensive', 'score': 2.25, 'reasons': ['covers T1110', 'terms: brute, force, ssh, t1110']}
authorise defensive {'allowed': True, 'reason': 'within scope, window and approved tier', 'skill': 'detecting-ssh-brute-force', 'target': 'server-1'}
authorise offensive {'allowed': False, 'reason': "tier 'offensive' is not approved for this engagement", 'skill': 'wireless-security-assessment', 'target': 'server-1'}
offensive pack refused: skill 'some-attack-skill' has tier 'offensive'; only 'defensive' is permitted (excluded tiers: ['dual-use', 'offensive'])
```

### Live leg still owed

This PR does **not** claim production verification. The live leg needs a
coordinator deploy of the merged change to the live Sentinel service, then
one real end-to-end use on that service: triage/search/authorise with a
defensive pack skill plus the offensive-denied failure case. This change
does not alter `approval_policy.py` or `approval_dispatcher.py`; if Muse
rules that the skills `authorise` surface counts as the approval path for
SEN-033, the one low-risk auto-approve + one high-risk Telegram prompt leg
also needs explicit SEN-033 clearance before it is run. No deploy, restart,
env flip or Telegram prompt was attempted in this work leg.

Overlap check: PR #1847 (TASK-SEN-031) was checkpoint scoping only; its
body states live legs were NOT run and no Telegram prompt was sent, so no
approval-path evidence was duplicated here.

## Item 2 — PentAGI (reference-only)

### Guardrail evidence

GitHub code search for `PentAGI` / `pentagi` returned 9 hits:

- `Inference/benchmarks/discovery/seed-pentagi.json` and
  `Inference/docs/DISCOVERY_FEED.md` — discovery/benchmark material, not
  Sentinel runtime.
- `IntelX/intelx/registries/scouted_repos.json` — scouting registry entry.
- `docs/collaboration/TASK-INT-044-PRODUCTION-TRACKER.md` — tracker doc.
- `Sentinel/docs/SECURITY_REFERENCE_IG.md` — reference-only role-design
  notes with explicit non-adoptions: no autonomous offensive execution, no
  tool-sandbox fleet, no targets outside the owner's assets.
- `Sentinel/app/services/fleet_audit_pipeline.py` and
  `Sentinel/app/services/audit_baseline.py` — defensive analogues only. The
  module text states PentAGI itself is an offensive penetration-testing
  platform and only its role design transfers: no offensive tooling, no
  Docker sandbox stack, no scanning of third parties.
- `tests/test_ig2_sen_audit_baseline.py` and
  `tests/test_ig2_sen_fleet_audit_pipeline.py` — tests for those defensive
  analogues.

This PR adds a CI-collected guardrail test
(`test_pentagi_is_not_imported_or_depended_on_by_sentinel_runtime`) asserting
that no Python module under `Sentinel/app` or `Sentinel/sentinel` imports
`pentagi`/`vxcontrol`, and that Sentinel dependency/packaging files
(`pyproject.toml`, `requirements.txt`, `requirements.lock`, Dockerfiles)
contain neither `pentagi` nor `vxcontrol`.

### Live leg still owed

The repo guardrail proves absence from Sentinel production code paths and
dependencies. A live-service guardrail check against the deployed Sentinel
version remains part of the same coordinator deploy/live-verification leg
above; it was not run here because no SEN-033-specific live-leg clearance
was found on hub #2045 and this worker's standing live boundary is
read-only probes only.

## Five states

- Implemented: YES — defensive pack wired into `CyberSkillsService`; CI
  collects the defensive/SEN-033 tests; PentAGI guardrail test added.
- Tested: YES repo-side — direct assertions above; pytest execution is
  recorded on the PR checks.
- Merged: NO — awaiting coordinator merge.
- Deployed: NO — no deploy attempted.
- Production-verified: NO — live Sentinel end-to-end proof still owed after
  coordinator deploy/clearance.

— Muse 7

## Live leg — DONE (2026-11-28 ~01:29–01:34 IST, Muse 7)

Deploy clearance WATCH234 ruling B.1 (board evidence, watch235). Method:
bridge `run_shell` on Oracle Server 1 (read-only probes; API key loaded
server-side from the running process environment, never printed). No
service restarted, no deploy performed by Muse 7, no Telegram prompt sent.

### Deploy state observed (first-hand)

- Live checkout `/opt/friday_universe` HEAD = `0f74b33d` — the PR #2169
  merge commit itself. `Sentinel/app/services/cyber_skills_service.py` and
  `Sentinel/tests/security/test_sen033_sentinel_repo_implement.py` present
  in the live checkout.
- `Sentinel.service` active, MainPID 2088416, boot 2026-11-27 23:16:42 IST
  (merge landed 17:46:06Z = 23:16:06 IST) — the running service already
  executes the SEN-033 code. Checkout is behind current main `c516895c`;
  the SEN-033 change itself is deployed.
- `/health` 200 (kill_switch false, audit_chain_valid true, 52 entries);
  `/ready` ready:true, 7/7 checks true incl. telegram_channel.

### End-to-end use on the live service (2026-11-27T20:02:55Z)

- `GET /v1/cyber/capabilities` → 200, skills 57,
  `defensive_skill_pack`: skill_count 10, tiers_present ["defensive"],
  all_defensive true, excluded_tiers ["dual-use","offensive"] — the pack
  audit SEN-033 wired is live.
- `GET /v1/cyber/skills?query=ssh brute force T1110` → 200,
  `detecting-ssh-brute-force` (defensive, score 2.25, covers T1110).
- `POST /v1/cyber/triage` (T1110 SSH brute force, server-1) → 200,
  crosswalk skills ["detecting-ssh-brute-force"], severity medium 0.5021.
- `POST /v1/cyber/authorise` detecting-ssh-brute-force, engagement
  `sen033-live-proof` → 200 `{"allowed":true,"reason":"within scope,
  window and approved tier"}`.
- Failure case: `POST /v1/cyber/authorise` wireless-security-assessment,
  same engagement → 200 `{"allowed":false,"reason":"tier 'offensive' is
  not approved for this engagement"}`.
- Honest notes: first unauthenticated attempts returned 401 pre-handler
  (no operation executed); first authenticated authorise pair without an
  engagement returned fail-closed `no engagement on record` denies; the
  pair above is the completed proof.

### PentAGI guardrail (live checkout)

Runtime grep for `pentagi|vxcontrol` under `Sentinel/app` +
`Sentinel/sentinel` (*.py) matches only the two documented
defensive-analogue mentions (`audit_baseline.py`,
`fleet_audit_pipeline.py`); dependency files
(`pyproject.toml`, `requirements.txt`, `requirements.lock`) clean. The
CI-collected guardrail test asserts no pentagi/vxcontrol imports and
passed on the merge head.

### Five states (live leg)

implemented YES / tested YES (repo CI + live end-to-end above) / merged
YES (`0f74b33d`) / deployed YES (live checkout at the merge commit,
service running it since 23:16:42 IST) / production-verified YES for the
adapt + reference-only items on the evidence above. The approval-path
Telegram leg was NOT run: per the work-leg note it needs a coordinator
ruling that the skills `authorise` surface counts as the SEN-033 approval
path; TASK-SEN-041 (approval-path live proof run 5) is queued behind this
leg for that proof. Board flip rides the coordinator board PR.

