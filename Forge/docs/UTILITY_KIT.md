# Fleet Utility Kit — free third-party utilities (TASK-FRG-033)

Curated reference of free utilities the fleet uses, with the free tier verified live at the time of entry — the verified facts, not the reels' claims. Each entry records its source item, what the free tier actually gives, its limits, and a one-time live test-use. Free-only rule applies: no paid tier is ever required for the fleet's use.

## 1. Sejda — free online PDF editing

- **Site:** https://www.sejda.com
- **Source:** forge package G-05, item DcJFRqqDIIA (sejda.com free online PDF editing).
- **What it is:** browser-based PDF tools (merge, split, compress, edit, convert, sign, watermark, OCR, and more) plus a Desktop app.
- **Free tier — verified live 2026-11-25 (sejda.com/pricing, first-hand):** $0 forever, **no signup required**. Page and hourly limits, limited file uploads, tool-specific limits.
- **Paid (for comparison, same page):** Week Pass $5 per user for 7 days; Monthly $7.50 per user per month; Annual $63 per user per year. Paid adds unlimited documents with no page or hourly limits, OCR up to 100 pages, up to 21 minutes per task, files up to 500 MB, processing multiple files at once, email support.
- **Usage notes:**
  - Browser tools upload the file to Sejda's servers for processing; for sensitive PDFs use Sejda Desktop instead — it processes documents on the local computer without uploading them.
  - The free tier suits occasional small jobs; the hourly task cap is the binding limit, so batch work belongs on a paid pass or the Desktop app.
  - No account, no card, no install for the free web tools.
- **Test-use — DONE 2026-11-25 (live browser, 21:24–22:44 IST):** merged the real 2-page test PDF (uploaded twice) into a 4-page PDF at sejda.com/merge-pdf. Verified two ways: Sejda's results viewer showed "1 / 4" with thumbnails 1–4, and the downloaded file (frg033-sejda-test_merged.pdf, 860 bytes) reads Pages: 4 via pdfinfo. No signup, no payment, no account; upload approval granted (allow_always).

## 2. ToffeeShare — peer-to-peer file transfer, nothing uploaded

- **Site:** https://toffeeshare.com
- **Source:** intelx package X-04, item DaXwbFrDEuX (ToffeeShare: peer-to-peer file sharing without uploading).
- **What it is:** free P2P file sharing from the Netherlands. Files go straight from the sender's device to the receiver's; nothing is stored online.
- **Free tier — verified live 2026-11-25 (toffeeshare.com + /faq, first-hand):** free, no signup, no account, **no file-size limit**. WebRTC peer-to-peer, end-to-end encrypted (DTLS 1.3). Close the browser tab to stop sharing; files stay available only as long as the sender's tab stays open. The service reports 50+ TB transferred per month.
- **Limits and caveats (same pages):**
  - No folder sending — zip the folder first (their own blog explains how).
  - Both peers must stay online for the whole transfer; if the sender closes the tab or the PC sleeps, the transfer stops (resumes ~5–10 s after wake).
  - Speed is bound by the slower of sender upload / receiver download; expect roughly 10–100 Mbit/s, occasionally up to 300 Mbit/s; same-network transfers are fastest.
  - Firefox or Chrome recommended. Safari cannot stream to disk, so Safari downloads cap at roughly 4 GB. Internet Explorer does not work at all.
- **Usage notes:**
  - Drag a file in, share the link, receiver downloads — good for large one-off transfers that must never sit on a third-party server.
  - Never use it for files the receiver must fetch later: there is no persistence, no link that outlives the sender's tab.
  - No account means no audit trail; confirm receipt with the receiver out of band for anything that matters.
- **Test-use — PARTIAL 2026-11-26 (live browser, 17:55–18:05 IST, two environments):** upload WORKED (direct drop onto the area; the "Click to browse or drag files here" button did nothing, no picker — same as 2026-11-25); share links generated in both environments (https://toffeeshare.com/c/ek--whaSRr, https://toffeeshare.com/c/CA9tIWcoRz, https://toffeeshare.com/c/n9XsoqUsRw); receiver reached /receive, "Connected to the sender", file listed correctly — signalling works. DOWNLOAD FAILED: 5 attempts across 3 links, all stuck at "0% Connecting.." (Env 1: 60s, 90s, 45s+; Env 2: 90s, 45s), 0 bytes transferred; the WebRTC data channel never establishes in this browser environment (Env 1 showed the fallback-relay notice, no bytes followed). Transfer NOT verified and NOT claimed. No signup, no payment, no account. First attempt 2026-11-25 FAILED outright (file selection never worked; uploads interrupted before reaching the browser). Remaining route: retry in a device browser.

## How entries get added

An entry needs: the source item, the free tier verified live at build time (limits, file-size caps, sign-up needs — quoted from the provider's own pages, not the reel), and one live test-use on a real file. Paid tiers are recorded for comparison only; the fleet never depends on one.
