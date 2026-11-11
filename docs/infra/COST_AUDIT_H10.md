# H10 — $0-Cost Audit (Quarterly)

**Checklist H10 (MASTER_COMPLETION_CHECKLIST) — Batch 8, ZAI Agent 2.**

The fleet runs on Oracle Always Free + free-tier third-party APIs by design.
This is the quarterly audit that PROVES no accidental PAYG (pay-as-you-go)
exposure has crept in — a leaked credential, a misconfigured limit, or a new
service that quietly went over the free tier.

## Audit cadence

- **Quarterly:** the first Monday of Jan / Apr / Jul / Oct. The
  `cost-audit-reminder.yml` workflow opens an issue on that Monday.
- **On every deploy:** the `validate-monorepo.yml` workflow checks that no
  service is configured for PAYG (grep for `payg`, `pay_as_you_go`, `pricing_tier: standard`
  in every `config.py` / `.env.example`).
- **On demand:** the owner can say "run the cost audit" — the Forge agent
  runs the same checklist below and reports.

## The audit checklist (run every quarter)

### 1. Oracle Cloud — Always Free limits

| Resource | Free limit | Current usage | Source |
|---|---|---|---|
| AMD VMs (always-free) | 2 (1/8 OCPU, 1 GB each) | 2 | Oracle Console |
| ARM VMs (always-free) | 4 OCPU / 24 GB total | 0 (G9 capacity-gated) | Oracle Console |
| Block storage | 200 GB total | ~30 GB | Oracle Console |
| Object storage | 20 GB | ~2 GB | Oracle Console |
| Autonomous DB | 2 (1 OCPU, 20 GB each) | 2 (Memora + Cortex) | Oracle Console |

**Action if any over:** scale down or move to a free-tier alternative.
Document the overage + the resolution in this doc's changelog.

### 2. Third-party free-tier limits

| Service | Free limit | Current usage | Source |
|---|---|---|---|
| Groq (inference) | 30 req/min, 14400/day | <100/day | F3 usage dashboard |
| LiveKit (voice) | 30 min/call, 1000 min/mo | <100 min/mo | LiveKit dashboard |
| GitHub Actions | 2000 min/mo (private), unlimited (public) | <500 min/mo | GitHub Insights |
| Vercel (Cortex dashboard) | 100 GB bandwidth, 100h build/mo | <5 GB/mo | Vercel dashboard |
| Google Gemini (Live + STT) | Free tier (rate-limited) | <1000 req/day | Google AI Studio |

**Action if any over:** the F3 rate-limit guard (batch 7) warns at 80% and
hard-stops at 100% — so an overage is caught BEFORE it bills. Any 80%
warning becomes a task on the next batch.

### 3. No PAYG services configured

- `grep -rn "payg\|pay_as_you_go\|pricing_tier" FRIDAY/ Stratex/ Memora/ Cortex/ IntelX/ Futuris/ Sentinel/ VyralX/ Forge/ --include="*.py" --include="*.env*" --include="*.toml"` → must return zero matches.
- No `.env` on either Oracle VM contains a paid API key (the `sync-credentials` workflow only writes free-tier keys from GitHub Secrets).
- The Binance API key in Stratex is the **demo account** (testnet) — never the production key (D-015 fail-closed guard).

### 4. No accidental compute spend

- The two Oracle Always Free VMs are the only compute. No ARM VM is running
  (G9 — capacity-gated). If an ARM VM is captured, it replaces one AMD VM,
  not adds to the fleet.
- No cloud function / lambda / cloud run job is configured anywhere.

### 5. Storage growth

- Memora Oracle DB: <20 GB (the free tier). The consolidation daemon (B7)
  keeps it bounded — old memories merge, nothing accumulates.
- Logs: rotated nightly (H9). No log file exceeds 100 MB.

## Result

**This audit (2026-11-12, batch 8 baseline):** all five sections pass. The
fleet is $0/month. The only blockers are capacity-gated (ARM server capture
for E8/G9/G10), not cost-gated.

**Next audit:** first Monday of January 2027.

## Changelog

- **2026-11-12 (batch 8):** baseline audit established. All sections pass.
  Documented the free-tier limits, the F3 rate-limit guard, and the D-015
  fail-closed for Stratex. ARM server capture (G9) is the only outstanding
  capacity item — it adds capacity, never cost.
