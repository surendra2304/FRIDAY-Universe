import { ThemeRoot } from "@/components/ThemeRoot";

/* TASK-WEB-003 — the app is still one stage; only its theme is
   chosen now. ThemeRoot renders the ULTRON command dashboard by
   default (the owner's 2026-11-17 pick). The preserved Halo stage
   lives at its own route, /halo (TASK-WEB-005-FIX-01); it is not
   selected here. See components/ThemeRoot.tsx. */
export default function Home() {
  return <ThemeRoot />;
}
