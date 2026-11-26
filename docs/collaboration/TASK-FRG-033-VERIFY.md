# TASK-FRG-033 — evidence

Forge: free utility kit additions — sejda PDF editing and ToffeeShare P2P transfer, verified and test-used. Muse TP9, 2026-11-25–26.

## Baseline

No fleet utility reference file existed in the repo (verified 2026-11-25: no file with "utility" in the name; no sejda/ToffeeShare mentions anywhere in the repo; `Forge/app/templates/catalog.py` is starter-code templates, not a utility reference; the closest pattern is the IG evaluation notes in `Forge/docs/`). This PR creates `Forge/docs/UTILITY_KIT.md` as the fleet utility reference, seeded with the two entries below.

## Free-tier verification (first-hand, 2026-11-25)

| Tool | Page read | Verified free-tier facts |
|---|---|---|
| Sejda | https://www.sejda.com/pricing | Free $0 forever, no signup required; page and hourly limits, limited file uploads, tool-specific limits. Paid: Week $5/7 days, Monthly $7.50/user/mo, Annual $63/user/yr (500 MB/file, OCR 100 pp, 21 min/task, unlimited docs). Desktop app processes locally without uploading. |
| Sejda | https://www.sejda.com/faq | 404 via text fetch — no FAQ page at that URL; limits taken from the pricing page instead. |
| ToffeeShare | https://toffeeshare.com/ | Free, no signup, no file-size limit; P2P WebRTC, E2E encrypted (DTLS 1.3), nothing stored online, close tab to stop; 50+ TB/month transferred. |
| ToffeeShare | https://toffeeshare.com/faq | No folder send (zip first); both peers must stay online; ~10–100 Mbit/s typical; Firefox/Chrome best, Safari ~4 GB cap, IE unsupported. |

## Test-uses (one real file each)

- Sejda: DONE 2026-11-25 (live browser 21:24–22:44 IST). Real 2-page PDF (frg033-sejda-test.pdf, 973 bytes) uploaded twice at sejda.com/merge-pdf → 4-page result (frg033-sejda-test_merged.pdf, 860 bytes; viewer "1 / 4" + pdfinfo Pages: 4). Free limits on the merge page: up to 50 pages or 50 MB, 3 tasks/hour; files auto-deleted after 2 hours. No signup/payment/account; upload approval granted (allow_always).
- ToffeeShare: RETRY 2026-11-26 17:55–18:01 IST (live browser, Environment 1) — PARTIAL. Upload WORKED (direct upload onto the area; clicking "Click to browse or drag files here" did nothing, no picker — same as 2026-11-25); share links generated (https://toffeeshare.com/c/ek--whaSRr, then https://toffeeshare.com/c/CA9tIWcoRz, live in sender tab); receiver tab reached /receive, "Connected to the sender", file listed correctly — signalling works. DOWNLOAD FAILED: 3 attempts across 2 links, all stuck at "0% Connecting.." (60s, 90s, 45s+); notice "Could not establish a direct connection, the (slower) fallback server will be used instead" but no bytes ever arrived. No file downloaded, so byte-for-byte verification NOT performed and NOT claimed. Conclusion: WebRTC data channel never establishes in this browser environment; fallback relay delivers nothing. No signup/payment/account. Retry in Environment 2, 2026-11-26 18:01–18:05 IST — SAME outcome: upload worked, link https://toffeeshare.com/c/n9XsoqUsRw generated, receiver connected and listed the file, but Download stuck at "0% Connecting.." on both attempts (90s, 45s; no fallback notice this time), 0 bytes transferred. Cross-environment conclusion: 5 attempts total (Env 1: 3 attempts, 2 links; Env 2: 2 attempts, 1 link), WebRTC data channel never established, no data moved; upload + link generation verified live, transfer NOT verified and NOT claimed. No further cloud-browser route (both environments tried); remaining route is a device-browser retry. First attempt 2026-11-25 FAILED (file selection never worked, uploads interrupted before reaching the browser); approvals pre-granted 'Site always allowed' ~22:43 IST, no approval card appeared in either retry run.

## Stall record

- 2026-11-25 ~21:18 IST: hourly self-check found both browser test-uses stalled (~90 min, no activity ~40 min). Cause: both were waiting on foreground upload approval cards, not idle — lesson recorded in AGENTS.md (check `permissions.list_pending` before closing a quiet browser task).
- Sejda first attempt closed as interrupted; re-dispatched; it then paused on its own upload approval (21:24 IST).
- Blocked note posted hub #1483 comment 7167438817 (21:25 IST, POST 201); self-check follow-up 7168675089 (~22:20 IST). No Muse decision on the approvals as of 22:23 IST.
- Branch moved to current main twice (5c901138290d, then 439dfe9871f5) while empty; rebased onto current main 087e05d6 at PR time (2026-11-26); board flip built from the new main blob; PR opened the same day.

## Five states

- Implemented: YES (reference created, entries written).
- Tested: PARTIAL (free tiers verified live; Sejda test-use DONE, ToffeeShare transfer NOT verified).
- Merged: NO. Deployed: NO. Production-verified: NO.
