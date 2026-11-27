import type { Metadata } from "next";
import Link from "next/link";
import { KitDemo } from "./KitDemo";

export const metadata: Metadata = {
  title: "FRIDAY — UI kit",
  description:
    "The FRIDAY UI kit demo: scroll-driven video, scroll playbook, showcase rows, map interface and the glass start page.",
};

/* TASK-WEB-008 — the kit demo route. The interactive demo lives in
   KitDemo (client); this page is the server shell, same shape as
   the /start route. The live stage at / is untouched. */
export default function KitPage() {
  return (
    <main>
      <KitDemo />
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
