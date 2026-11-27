"use client";

import { useEffect, useRef, useState } from "react";
import { usePrefersReducedMotion } from "./ScrollPlaybook";

/* ================================================================
   ScrollVideo — scroll-driven video (TASK-WEB-008, NEW).

   Source idea (board acceptance, F-39 item Dc8xeYzoOLh): a
   video whose playback is driven by scroll — the GSAP
   ScrollTrigger scrub pattern, rebuilt on the stack the house
   already has (rAF-throttled scroll reads, direct DOM writes,
   no new dependency).

   The video sits pinned (sticky) while its wrapper scrolls
   through `scrubPx` pixels; the scroll fraction becomes the
   playback fraction. No autoplay, no loop, no sound: the video
   is muted and paused, and only `currentTime` moves.

   Reduced motion is a hard rule (playbook): under
   `prefers-reduced-motion: reduce` the scrub never engages and
   the first frame stands, with a caption that says so.

   Honest states, no invented frames: before metadata loads the
   poster (or a blank frame) shows; if the video fails to load,
   an explicit error line replaces the scrub, never a fake
   poster or a generated stand-in.
   ================================================================ */

export interface ScrollVideoProps {
  /** Video URL. Caller-supplied; the kit fetches nothing itself. */
  src: string;
  /** Poster frame shown before metadata loads. */
  poster?: string;
  /** Caption under the video. */
  caption?: string;
  /** Accessible label for the video region. */
  label?: string;
  /** Pixels of scroll travel the scrub maps over. Defaults to 1200. */
  scrubPx?: number;
}

export function ScrollVideo({
  src,
  poster,
  caption,
  label = "Scroll-driven video",
  scrubPx = 1200,
}: ScrollVideoProps) {
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);
  const reduced = usePrefersReducedMotion();

  useEffect(() => {
    const wrap = wrapRef.current;
    const video = videoRef.current;
    if (!wrap || !video || reduced || !ready) return;

    let raf = 0;
    const update = () => {
      raf = 0;
      const duration = video.duration;
      if (!duration || !Number.isFinite(duration)) return;
      const rect = wrap.getBoundingClientRect();
      const travel = Math.max(1, rect.height - window.innerHeight);
      const fraction = Math.min(1, Math.max(0, -rect.top / travel));
      const target = fraction * duration;
      if (Math.abs(video.currentTime - target) > 0.04) {
        video.currentTime = target;
      }
    };
    const onScroll = () => {
      if (!raf) raf = window.requestAnimationFrame(update);
    };
    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      if (raf) window.cancelAnimationFrame(raf);
    };
  }, [ready, reduced]);

  return (
    <figure
      aria-label={label}
      style={{ margin: 0 }}
    >
      <div
        ref={wrapRef}
        style={{ height: `calc(100vh + ${scrubPx}px)`, position: "relative" }}
      >
        <div
          style={{
            position: "sticky",
            top: 0,
            height: "100vh",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            overflow: "hidden",
            background: "#05070f",
          }}
        >
          {failed ? (
            <p className="sheet-note" role="alert">
              The video at this address didn&apos;t load — nothing is shown in
              its place.
            </p>
          ) : (
            <video
              ref={videoRef}
              src={src}
              poster={poster}
              muted
              playsInline
              preload="metadata"
              aria-label={label}
              onLoadedMetadata={() => setReady(true)}
              onError={() => setFailed(true)}
              style={{
                maxWidth: "100%",
                maxHeight: "100vh",
                width: "auto",
                height: "auto",
                display: "block",
              }}
            />
          )}
        </div>
      </div>
      <figcaption
        className="sheet-note"
        style={{ textAlign: "center", paddingTop: 8 }}
      >
        {failed
          ? "Video unavailable."
          : reduced
            ? `${caption ?? "Scroll-driven video."} Reduced motion is on — scrubbing is off, first frame shown.`
            : `${caption ?? "Scroll-driven video."} Scroll to scrub through it.`}
      </figcaption>
    </figure>
  );
}
