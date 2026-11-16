import type { Metadata } from "next";
import Link from "next/link";
import { GlassStartPage } from "@/components/GlassStartPage";

export const metadata: Metadata = {
  title: "FRIDAY — Start",
  description: "The glass start page: search, weather, to-dos, notes and a map, on one calm page.",
};

/* TASK-IG2-WEB-07 (wiring) — the glass start page gets the standalone
   route its component was built for ("a caller renders it as a
   standalone start page, e.g. a browser new-tab target or a /start
   route"). The live stage at / is untouched; point a browser's
   new-tab or home page here and this is what opens. The way back is
   one quiet link in the corner — the page itself is the component's
   own, unchanged. */
export default function StartPage() {
  return (
    <main>
      <GlassStartPage />
      <Link
        href="/"
        style={{
          position: "fixed",
          left: 16,
          bottom: 16,
          zIndex: 50,
          fontFamily: "var(--font-mono)",
          fontSize: 12,
          letterSpacing: "0.08em",
          color: "var(--dim)",
          background: "rgba(10, 14, 29, 0.55)",
          border: "1px solid var(--hair)",
          borderRadius: 999,
          padding: "7px 13px",
          textDecoration: "none",
          backdropFilter: "blur(12px)",
          WebkitBackdropFilter: "blur(12px)",
        }}
      >
        ← FRIDAY
      </Link>
    </main>
  );
}
