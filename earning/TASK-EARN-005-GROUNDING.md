# TASK-EARN-005 — Grounding checkpoint 1: which product is the $19 one?

**Task:** TASK-EARN-005 — sales page copy pack for the 19-dollar digital product
**Worker:** Muse 19 · **Branch:** `muse19/task-earn-005` · **Checkpoint:** 1 (grounding)
**Date:** 2026-11-24 ~13:21 IST · **Base:** main `8ca10eec` (board blob `48db36bb`, 18,752 lines)

## Ruling this checkpoint answers

Coordinator watch 7124945395 (run scheduled 12:37 IST, posted ~12:53 IST), **Ruling 1**:
"EARN-005: the claim STANDS (option b). … EARN-005 stays yours; start the copy work
now, do not wait." The 11:51 re-slot to the pool was written from a pre-claim read.
Claim: hub comment 7123360586 (~11:22 IST), branch `muse19/task-earn-005`.

## What was checked first-hand this run

1. **Board record TASK-EARN-005** (main `8ca10eec`, line 17679): title only —
   "EARN: sales page copy pack for the 19-dollar digital product". P3, owner muse_19.
   Acceptance: "Sales page copy (headline, benefits, FAQ, call to action) committed
   under earning/, ready for the owner to approve." Next action: "Write the sales page
   copy for the 19-dollar product; free-only, no paid promotion." Evidence cites only
   the coordinator watch 2026-11-23 ~23:10 IST (hub 7108903950), which names no product.
   **No product name, price page, or source file anywhere in the record.**
2. **`earning/` on main:** 4 packs + `products/` dir only —
   `TASK-EARN-002-EMAIL-SEQUENCES-PACK.md`, `TASK-EARN-006-RESUME-LINKEDIN-PACK.md`,
   `TASK-EARN-007-EMAIL-SEQUENCES-GIG-PACK.md`, `TASK-EARN-008-EMAIL-SEQUENCES-PACK-2.md`.
   Grep for `19` across all four: **0 matches**. No `$19`, no `19-dollar`.
3. **`earning/products/`:** one entry only — `lead-magnet-ebook/the-7-day-email-list-starter-kit.md`
   (TASK-EARN-004). Read in full: **"Price: Free"**, instant download, lead magnet.
   It is not the $19 product. Its "paid offer" mentions are generic ("priced small"),
   with no product and no $19.
4. **Repo-wide code search** (GitHub code search, main `8ca10eec`):
   - `$19`: 11 hits — all incidental, none a product: `Inference/docs/CORPUS_DISPOSITIONS.md`,
     `IntelX/intelx/registries/scouted_repos.json`, `Stratex/measurement/import_legacy_closes.py`,
     `Stratex/measurement/EXECUTION_AUDIT_RD010.md`, `Forge/app/templates/web_studio/domain_synthesizer.py`,
     `docs/archive/FRIDAY_DASHBOARD_TEST_REPORT.md`, and 5 test files. None under `earning/`.
   - `19-dollar`: **0 hits**. `19 USD`: **0 hits**. `nineteen dollars`: **0 hits**.
5. **Owner asked:** the $19-product question was put to Surendra ~12:20 IST
   (title, what it is, where it lives — or what it should be if it does not exist yet).
   At ~12:20 IST the follow-up told him to hold answering until the re-slot ruling
   landed. The ruling is now (b) — the hold is lifted — and **no answer has arrived
   yet** (main chat checked this run; newest turn is the 12:17 self-check delivery).

## Conclusion

**The $19 product cannot be identified from the board, the repo, or any coordinator
watch.** Writing sales-page copy now would mean inventing a product — headline,
benefits and FAQ for something that may not exist. That is exactly what the
12:20 question was asked to prevent, and the EARN-008 precedent in this lane is
to mark unverified facts [VERIFY], not to invent them.

## What unblocks the copy pack

One line from the owner: the product's title, what it is, and where it lives
(or what it should be, if it is to be created). The pack then follows the
acceptance exactly: headline, benefits, FAQ, call to action, committed under
`earning/` as `TASK-EARN-005-SALES-PAGE-COPY-PACK.md`, free-only, no paid promotion,
no invented claims — prices/delivery marked [VERIFY] where the brief does not cover them.

## Status

- Claim stands (ruling 1, watch 7124945395). Board flip AVAILABLE → CLAIMED rides
  in this work PR.
- Copy pack: **blocked on product identity**, not on effort. Grounding is the
  checkpoint-1 artifact; the draft follows as soon as the product is named.

— Muse 19
