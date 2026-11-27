"use client";

/* TASK-WEB-008 — the implementation moved to the kit.
   `stage/motion.tsx` is now a re-export of
   `components/kit/ScrollPlaybook.tsx` so existing imports
   (`FleetSheet`, `TourSheet`, `Sheet`) keep working with zero
   behaviour change. The kit is the single implementation. */
export {
  Parallax,
  Reveal,
  ScrollProgress,
  usePrefersReducedMotion,
} from "@/components/kit/ScrollPlaybook";
