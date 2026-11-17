# Halo — preserved aside (TASK-WEB-003, 2026-11-17)

The owner picked the ULTRON theme on 2026-11-17 and instructed that the
present theme — **Halo** (TASK-WEB-002) — be kept aside intact; he will
say later what to do with it. This directory is the preservation record.

Halo is preserved three ways:

1. **In place, unmodified.** Every Halo source file remains at its
   original path, byte-for-byte as of the PR base
   `c6b22f686cb39b4fe6f9d0c54aee2631247cf90c`. (The hashes below were
   first taken at `2ba83d5c70841403c2a6dccda1b4a470a5bf6b3a`; the
   `FRIDAY/ui` tree is identical at both commits —
   `5c40bc248ba43d2780e93deecb6a6dbfd7a50706` — so they hold at the
   PR base unchanged.)
   TASK-WEB-003 does not modify any of them. SHA-256 at base:

   | File | SHA-256 |
   | --- | --- |
   | `FRIDAY/ui/app/globals.css` | `05b7f2743759912ea19ba80e127883cd006b1e3c5092703d9d20219af5c3e575` |
   | `FRIDAY/ui/components/stage/Stage.tsx` | `b49b7dcbe37e2d1fe407ba3fb485be5012a4bbdc1ab0b669cb3632b3fb17dd3a` |
   | `FRIDAY/ui/components/stage/Halo.tsx` | `0a3c9ffc8fdf4fa7f4be9b42341f2706872451f6ded47f83a99d9c6a5a545669` |
   | `FRIDAY/ui/components/stage/Conversation.tsx` | `bb6856c3882158d3eeafdd21893938eb18303d077de181460d86cc3939d2be1a` |
   | `FRIDAY/ui/components/VoiceCall.tsx` | `c70449c0d03d056d9954823cbcc4e76ee2afb67ae50c2c5f0ea80809eef26775` |
   | `FRIDAY/ui/components/stage/WakeListener.tsx` | `03d6981a9ac55c7349aad3a5c33a185ba364470542b2499588f5622090791e79` |
   | `FRIDAY/ui/lib/wire.ts` | `0eb1d8786dc22130b9b362daeaa76cba4ccd603e9e303e4ac5ca444045a3b8ce` |

   The remaining Halo surfaces (all `components/stage/*Sheet.tsx`,
   `Veil.tsx`, `Sheet.tsx`, `Ambience.tsx`, `motion.tsx`, the reactbits
   components and `components/Orb.tsx`) are likewise untouched — the
   PR's file list is the proof: none of them appear in it.

2. **As a standalone copy.** `globals.halo.css` in this directory is a
   byte-identical copy of `FRIDAY/ui/app/globals.css` at the PR base
   (SHA-256 `05b7f2743759912ea19ba80e127883cd006b1e3c5092703d9d20219af5c3e575`).
   It is not imported by the app; it exists so Halo's stylesheet
   survives even a future edit of the live file.

3. **Still live.** Halo remains a selectable theme: open the app with
   `?theme=halo`, or use "Switch to Halo theme" in the ULTRON control
   panel (persisted as `friday.theme` in localStorage — see
   `FRIDAY/ui/lib/theme.ts`). Selecting it renders the original
   `Stage` with the original `globals.css`, exactly as before.

The only pre-existing files TASK-WEB-003 modifies are
`FRIDAY/ui/app/page.tsx` and `FRIDAY/ui/app/layout.tsx` (theme routing
and the ULTRON stylesheet import). Neither contains Halo presentation
code; Halo's own files above carry it all.
