"use client";

import { X } from "lucide-react";
import { useEffect, useRef, type ReactNode } from "react";
import { ScrollProgress } from "./motion";

/* ================================================================
   The sheet — the one way anything beyond the stage appears.
   A layer rises over the dimmed room; the stage underneath is
   never unmounted, so a live call and the conversation carry on
   while the owner looks at something else. Tap the dark, press
   Escape, or swipe the sheet down and it sinks back.
   ================================================================ */

export function Sheet({
  title,
  kicker,
  onClose,
  children,
}: {
  title: string;
  kicker: string;
  onClose: () => void;
  children: ReactNode;
}) {
  const touchStartY = useRef<number | null>(null);
  const bodyRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="sheet-backdrop" role="presentation" onClick={onClose}>
      <section
        className="sheet"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
        onTouchStart={(e) => {
          touchStartY.current = e.touches[0]?.clientY ?? null;
        }}
        onTouchEnd={(e) => {
          const start = touchStartY.current;
          touchStartY.current = null;
          if (start === null) return;
          const end = e.changedTouches[0]?.clientY ?? start;
          if (end - start > 90) onClose();
        }}
      >
        <header className="sheet-head">
          <div>
            <p className="sheet-kicker">{kicker}</p>
            <h2 className="sheet-title">{title}</h2>
          </div>
          <button type="button" className="sheet-close" onClick={onClose} aria-label={`Close ${title}`}>
            <X size={18} aria-hidden="true" />
          </button>
        </header>
        <ScrollProgress scrollerRef={bodyRef} />
        <div className="sheet-body" ref={bodyRef}>
          {children}
        </div>
      </section>
    </div>
  );
}
