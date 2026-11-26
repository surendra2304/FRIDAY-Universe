import type { Metadata } from "next";
import Link from "next/link";
import { Stage } from "@/components/stage/Stage";

export const metadata: Metadata = {
  title: "FRIDAY — Halo",
  description:
    "The Halo stage: one room, one voice, one conversation — the living light at the centre, with the fleet, the chronicle and the sheets one summon away.",
};

/* TASK-WEB-005-FIX-01 — the Halo stage gets the standalone route its
   component was built for. The owner's WEB-003 pick stands: the live
   home route (/) still renders the ULTRON stage unconditionally, and
   nothing here changes it. Halo mounts at /halo instead — its own
   route, its own export (out/halo/index.html), served at
   /friday/halo/ by the FRIDAY service and at the bare-domain /halo
   by the Server 2 gateway rewrite. The way back is one quiet link
   in the corner — the page itself is the stage's own, unchanged. */
export default function HaloPage() {
  return (
    <>
      <Stage />
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
        ← ULTRON
      </Link>
    </>
  );
}
