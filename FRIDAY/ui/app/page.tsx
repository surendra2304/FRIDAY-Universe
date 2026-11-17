import { ThemeRoot } from "@/components/ThemeRoot";

/* TASK-WEB-003 — the app is still one stage; only its theme is
   chosen now. ThemeRoot renders the ULTRON command dashboard by
   default (the owner's 2026-11-17 pick) and the preserved Halo
   stage when Halo is selected. See components/ThemeRoot.tsx. */
export default function Home() {
  return <ThemeRoot />;
}
