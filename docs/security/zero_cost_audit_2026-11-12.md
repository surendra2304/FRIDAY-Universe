# $0-Cost Audit — H10 (2026-11-12)

**Auditor:** ZAI Agent 1 (batch 9b) · **Cadence:** quarterly (owner directive)
**Automated tool:** `python3 scripts/zero_cost_audit.py` — 9/9 checks PASSED

## 1. Compute (Oracle Cloud)

| Item | Verdict | Evidence |
|---|---|---|
| Sniper instance shape | $0 | `FRIDAY/scripts/oracle_retry.py` only launches `VM.Standard.A1.Flex` (Always Free eligible) |
| Sniper launch configs | $0 | 4 configs, worst case 2 OCPU / 12 GB — inside the 4 OCPU / 24 GB A1 free allowance |
| Sniper live-resize path | $0 | In-place upgrade targets 2 OCPU / 12 GB only |
| Boot volume | $0 | 50 GB (free block-storage total is 200 GB across ALL volumes — see manual check) |
| Existing VMs | $0 | Both run within Always Free shapes (sandbox VM + future ARM capture); no VM.Standard.E2/Flex x86 paid launches exist anywhere in the repo |

## 2. GitHub

| Item | Verdict | Evidence |
|---|---|---|
| Repo visibility | $0 | `surendra2304/FRIDAY-Universe` is **public** → Actions minutes unlimited and free |
| Sniper runner time | $0 | The 24/7 hourly sniper (up to 6h runs) would be ~43,000 min/month — free only because the repo is public. **Invariant: keep the repo public, or the sniper becomes a real bill.** The audit script FAILs if the repo turns private. |
| Paid SDKs in workflows | $0 | No aws/gcp/azure/stripe/twilio/pinecone/algolia/pusher references in any workflow |

## 3. AI providers

| Item | Verdict | Evidence |
|---|---|---|
| Default provider | $0 | `llm_provider=gemini`, model `gemini-3.6-flash` (free tier) |
| OpenAI fallback | $0 unless enabled | `openai_provider.py` defaults to `gpt-4o-mini` (PAID) but is never the default provider — cost only if the owner deliberately sets an OpenAI key and switches providers |
| Rate-limit guard | tracked | F3 (usage dashboard + rate-limit guard) remains on the checklist |

## 4. Trading (Stratex)

| Item | Verdict | Evidence |
|---|---|---|
| Live-money path | blocked | `validate_environment_safety()` is a PERMANENT invariant: any `LIVE_TRADING/ENABLE_LIVE/REAL_MONEY/...=TRUE` env var raises `SecurityConfigurationError`; only Binance demo/paper endpoints allowlisted |
| Capital risk | demo only | Demo account (owner reset 2026-11-11 for a clean P&L baseline) |

## 5. Everything else

DuckDNS (free) · Telegram Bot API (free) · self-hosted Docker/Traefik/Redis on the
free VMs (no OCI managed LB / object storage / NAT gateway in any compose file or
deploy doc) · GitHub-hosted git (free) · no other cloud SDKs in the tree.

## 6. Owner manual checklist (OCI console, ~5 minutes, quarterly)

The script cannot see inside the OCI tenancy. Once a quarter, confirm in the
Oracle Cloud console:

- [ ] Billing & Cost Management → last invoice / current spend = **$0.00**
- [ ] Compute → total boot volumes across ALL instances ≤ 200 GB
      (2 VMs × 50 GB = 100 GB today; a third 50 GB VM still fits)
- [ ] Networking → no Load Balancer, no NAT Gateway (DuckDNS + direct ports only)
- [ ] Object Storage → within 20 GB / 50K requests (should be zero usage)
- [ ] Egress < 10 TB/month (Settings → Usage; telemetry-level usage today)

**Next scheduled re-run:** 2027-02-12 (`python3 scripts/zero_cost_audit.py` + this console checklist)
