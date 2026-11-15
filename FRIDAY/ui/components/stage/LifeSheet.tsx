"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

/* ================================================================
   Life in weeks, summoned (TASK-IG-WEB-02).

   Source idea (IG reference corpus, DTjp4aaE_bT): a life
   calendar — every week of a life as one dot in a grid — plus
   the 365-day dot calendar the same reel shows for planning
   a year.

   Two modes, one canvas (a 52 × 90 grid is ~4,700 dots; they
   are painted, not DOM nodes):
     · Life in weeks — 52 dots per row, 90 rows. Lived weeks
       glow, the current week breathes, the rest wait faint.
     · Year in days — the current year as a GitHub-style grid,
       one dot per day, weeks as columns.

   Privacy by construction: the birth date and the milestone
   marks are the owner's own data, so they live in this
   browser's localStorage and nowhere else. Nothing is sent
   to the backend; this layer makes no network calls at all.
   ================================================================ */

const YEARS = 90;
const WEEKS_PER_YEAR = 52;
const TOTAL_WEEKS = YEARS * WEEKS_PER_YEAR;
const DAY_MS = 86_400_000;
const WEEK_MS = 7 * DAY_MS;

const DOB_KEY = "friday.life.dob";
const MARKS_KEY = "friday.life.marks";

interface Mark {
  date: string; // YYYY-MM-DD
  label: string;
}

function parseLocalDate(value: string): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return null;
  const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  return Number.isNaN(date.getTime()) ? null : date;
}

function startOfDay(date: Date): Date {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  return d;
}

function formatDate(date: Date): string {
  return date.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

function loadMarks(): Mark[] {
  try {
    const raw = window.localStorage.getItem(MARKS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as Mark[];
    return Array.isArray(parsed) ? parsed.filter((m) => m && m.date && m.label) : [];
  } catch {
    return [];
  }
}

interface Dot {
  x: number;
  y: number;
  r: number;
  index: number;
}

export function LifeSheet() {
  const [dob, setDob] = useState<string>("");
  const [marks, setMarks] = useState<Mark[]>([]);
  const [mode, setMode] = useState<"weeks" | "year">("weeks");
  const [hover, setHover] = useState<string>("");
  const [pulse, setPulse] = useState(false);
  const [markDate, setMarkDate] = useState("");
  const [markLabel, setMarkLabel] = useState("");

  const wrapRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const dotsRef = useRef<Dot[]>([]);

  /* Stored values only exist after mount (localStorage + the
     owner's motion preference), same probe pattern as Halo. */
  const [reducedMotion, setReducedMotion] = useState(false);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDob(window.localStorage.getItem(DOB_KEY) ?? "");
    setMarks(loadMarks());
    setReducedMotion(window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  }, []);

  /* The current week breathes — a slow pulse, off entirely
     under reduced motion (a steady ring marks it instead). */
  useEffect(() => {
    if (reducedMotion) return;
    const timer = window.setInterval(() => setPulse((p) => !p), 700);
    return () => window.clearInterval(timer);
  }, [reducedMotion]);

  const today = useMemo(() => startOfDay(new Date()), []);
  const dobDate = useMemo(() => (dob ? parseLocalDate(dob) : null), [dob]);

  const weeksLived = useMemo(() => {
    if (!dobDate) return 0;
    return Math.max(0, Math.floor((today.getTime() - startOfDay(dobDate).getTime()) / WEEK_MS));
  }, [dobDate, today]);

  const yearStart = useMemo(() => new Date(today.getFullYear(), 0, 1), [today]);
  const dayOfYear = Math.floor((today.getTime() - yearStart.getTime()) / DAY_MS); // 0-based
  const daysInYear = Math.round(
    (new Date(today.getFullYear() + 1, 0, 1).getTime() - yearStart.getTime()) / DAY_MS,
  );

  const markWeeks = useMemo(() => {
    if (!dobDate) return new Map<number, string>();
    const map = new Map<number, string>();
    for (const mark of marks) {
      const date = parseLocalDate(mark.date);
      if (!date) continue;
      const idx = Math.floor((startOfDay(date).getTime() - startOfDay(dobDate).getTime()) / WEEK_MS);
      if (idx >= 0 && idx < TOTAL_WEEKS) map.set(idx, mark.label);
    }
    return map;
  }, [marks, dobDate]);

  const markDays = useMemo(() => {
    const map = new Map<number, string>();
    for (const mark of marks) {
      const date = parseLocalDate(mark.date);
      if (!date || date.getFullYear() !== today.getFullYear()) continue;
      const idx = Math.floor((startOfDay(date).getTime() - yearStart.getTime()) / DAY_MS);
      if (idx >= 0 && idx < daysInYear) map.set(idx, mark.label);
    }
    return map;
  }, [marks, today, yearStart, daysInYear]);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const styles = window.getComputedStyle(document.documentElement);
    const livedColor = styles.getPropertyValue("--glow-a").trim() || "#38bdf8";
    const nowColor = styles.getPropertyValue("--glow-c").trim() || "#a855f7";
    const markColor = styles.getPropertyValue("--warn").trim() || "#fbbf24";

    const width = wrap.clientWidth;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);

    let cols: number;
    let rows: number;
    let count: number;
    if (mode === "weeks") {
      cols = WEEKS_PER_YEAR;
      rows = YEARS;
      count = TOTAL_WEEKS;
    } else {
      const offset = (yearStart.getDay() + 6) % 7; // Monday-first
      cols = Math.ceil((offset + daysInYear) / 7);
      rows = 7;
      count = daysInYear;
    }
    const cell = width / cols;
    const height = Math.ceil(cell * rows);
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);

    const dots: Dot[] = [];
    const radius = Math.max(1.4, cell * 0.31);
    for (let i = 0; i < count; i++) {
      let col: number;
      let row: number;
      let state: "lived" | "now" | "future";
      let marked: string | undefined;
      if (mode === "weeks") {
        col = i % WEEKS_PER_YEAR;
        row = Math.floor(i / WEEKS_PER_YEAR);
        state = i < weeksLived ? "lived" : i === weeksLived ? "now" : "future";
        marked = markWeeks.get(i);
      } else {
        const offset = (yearStart.getDay() + 6) % 7;
        col = Math.floor((offset + i) / 7);
        row = (offset + i) % 7;
        state = i < dayOfYear ? "lived" : i === dayOfYear ? "now" : "future";
        marked = markDays.get(i);
      }
      const x = col * cell + cell / 2;
      const y = row * cell + cell / 2;
      dots.push({ x, y, r: radius, index: i });

      ctx.beginPath();
      if (state === "lived") {
        ctx.fillStyle = livedColor;
        ctx.globalAlpha = 0.85;
        ctx.arc(x, y, radius, 0, Math.PI * 2);
        ctx.fill();
      } else if (state === "now") {
        ctx.globalAlpha = 1;
        ctx.fillStyle = nowColor;
        const r = reducedMotion ? radius : radius * (pulse ? 1.25 : 0.95);
        ctx.arc(x, y, r, 0, Math.PI * 2);
        ctx.fill();
        ctx.beginPath();
        ctx.strokeStyle = nowColor;
        ctx.globalAlpha = 0.55;
        ctx.lineWidth = 1;
        ctx.arc(x, y, radius * 1.9, 0, Math.PI * 2);
        ctx.stroke();
      } else {
        ctx.fillStyle = "#8ea0c9";
        ctx.globalAlpha = 0.22;
        ctx.arc(x, y, radius, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.globalAlpha = 1;
      if (marked) {
        ctx.beginPath();
        ctx.strokeStyle = markColor;
        ctx.lineWidth = 1.4;
        ctx.arc(x, y, radius * 1.85, 0, Math.PI * 2);
        ctx.stroke();
      }
    }
    dotsRef.current = dots;
  }, [mode, weeksLived, dayOfYear, daysInYear, yearStart, markWeeks, markDays, pulse, reducedMotion]);

  useEffect(() => {
    draw();
    const wrap = wrapRef.current;
    if (!wrap || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(() => draw());
    ro.observe(wrap);
    return () => ro.disconnect();
  }, [draw]);

  const onHover = (event: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    const dot = dotsRef.current.find((d) => Math.abs(d.x - x) <= d.r * 2.2 && Math.abs(d.y - y) <= d.r * 2.2);
    if (!dot) {
      setHover("");
      return;
    }
    if (mode === "weeks") {
      if (!dobDate) return;
      const start = new Date(startOfDay(dobDate).getTime() + dot.index * WEEK_MS);
      const label = markWeeks.get(dot.index);
      setHover(
        `Week ${dot.index + 1} of ${TOTAL_WEEKS} · begins ${formatDate(start)}` +
          (dot.index === weeksLived ? " · you are here" : "") +
          (label ? ` · marked: ${label}` : ""),
      );
    } else {
      const date = new Date(yearStart.getTime() + dot.index * DAY_MS);
      const label = markDays.get(dot.index);
      setHover(
        `Day ${dot.index + 1} of ${daysInYear} · ${formatDate(date)}` +
          (dot.index === dayOfYear ? " · today" : "") +
          (label ? ` · marked: ${label}` : ""),
      );
    }
  };

  const saveDob = (value: string) => {
    setDob(value);
    if (value) window.localStorage.setItem(DOB_KEY, value);
    else window.localStorage.removeItem(DOB_KEY);
  };

  const saveMarks = (next: Mark[]) => {
    setMarks(next);
    window.localStorage.setItem(MARKS_KEY, JSON.stringify(next));
  };

  const addMark = () => {
    if (!markDate || !markLabel.trim()) return;
    saveMarks([...marks, { date: markDate, label: markLabel.trim() }].sort((a, b) => a.date.localeCompare(b.date)));
    setMarkDate("");
    setMarkLabel("");
  };

  const weeksShown = Math.min(weeksLived, TOTAL_WEEKS);
  const percent = dobDate ? ((weeksShown / TOTAL_WEEKS) * 100).toFixed(1) : null;

  return (
    <div className="life">
      <div className="life-modes" role="tablist" aria-label="Grid mode">
        <button
          type="button"
          role="tab"
          aria-selected={mode === "weeks"}
          className={`life-chip ${mode === "weeks" ? "is-on" : ""}`}
          onClick={() => setMode("weeks")}
        >
          Life in weeks
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mode === "year"}
          className={`life-chip ${mode === "year" ? "is-on" : ""}`}
          onClick={() => setMode("year")}
        >
          Year in days
        </button>
      </div>

      {!dobDate && mode === "weeks" ? (
        <div className="life-setup">
          <p className="sheet-note">
            Every week of a 90-year life is one dot — 4,680 of them. Tell the grid when the count
            started and it will show where you stand. Your birth date is stored only in this
            browser (localStorage); it is never sent anywhere.
          </p>
          <label className="life-field">
            <span>Birth date</span>
            <input type="date" value={dob} onChange={(e) => saveDob(e.target.value)} aria-label="Your birth date" />
          </label>
        </div>
      ) : (
        <>
          <p className="sheet-summary life-stats">
            {mode === "weeks" ? (
              <>
                <span>
                  <b>{weeksShown.toLocaleString("en-IN")}</b> weeks lived
                </span>
                <span>
                  <b>{(TOTAL_WEEKS - weeksShown).toLocaleString("en-IN")}</b> on the grid ahead
                </span>
                <span>
                  <b>{percent}%</b> of the grid
                </span>
              </>
            ) : (
              <>
                <span>
                  <b>{dayOfYear + 1}</b> of {daysInYear} days
                </span>
                <span>
                  <b>{daysInYear - dayOfYear - 1}</b> days left in {today.getFullYear()}
                </span>
                <span>
                  <b>{(((dayOfYear + 1) / daysInYear) * 100).toFixed(1)}%</b> of the year
                </span>
              </>
            )}
          </p>

          <div className="life-canvas-wrap" ref={wrapRef}>
            <canvas
              ref={canvasRef}
              className="life-canvas"
              role="img"
              aria-label={
                mode === "weeks"
                  ? `Life in weeks: ${weeksShown} of ${TOTAL_WEEKS} weeks lived`
                  : `Year in days: day ${dayOfYear + 1} of ${daysInYear}`
              }
              onMouseMove={onHover}
              onMouseLeave={() => setHover("")}
            />
          </div>
          <p className="life-readout" aria-live="polite">
            {hover || (mode === "weeks" ? "Hover a dot — each one is a week." : "Hover a dot — each one is a day.")}
          </p>

          <div className="life-legend" aria-hidden="true">
            <span>
              <i className="life-dot is-lived" /> lived
            </span>
            <span>
              <i className="life-dot is-now" /> {mode === "weeks" ? "this week" : "today"}
            </span>
            <span>
              <i className="life-dot is-future" /> ahead
            </span>
            <span>
              <i className="life-dot is-marked" /> marked
            </span>
          </div>

          <div className="life-marks">
            <p className="life-marks-head">Mark a date</p>
            <div className="life-mark-form">
              <input type="date" value={markDate} onChange={(e) => setMarkDate(e.target.value)} aria-label="Mark date" />
              <input
                type="text"
                value={markLabel}
                onChange={(e) => setMarkLabel(e.target.value)}
                placeholder="What happens then?"
                aria-label="Mark label"
                maxLength={60}
              />
              <button type="button" className="life-btn" onClick={addMark}>
                Mark it
              </button>
            </div>
            {marks.length > 0 && (
              <ul className="life-mark-list">
                {marks.map((mark, idx) => (
                  <li key={`${mark.date}-${idx}`}>
                    <span className="life-mark-date">{formatDate(parseLocalDate(mark.date) ?? new Date())}</span>
                    <span className="life-mark-label">{mark.label}</span>
                    <button
                      type="button"
                      className="life-mark-remove"
                      onClick={() => saveMarks(marks.filter((_, i) => i !== idx))}
                      aria-label={`Remove mark ${mark.label}`}
                    >
                      ×
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {mode === "weeks" && (
              <label className="life-field life-field-inline">
                <span>Birth date</span>
                <input type="date" value={dob} onChange={(e) => saveDob(e.target.value)} aria-label="Your birth date" />
              </label>
            )}
          </div>
        </>
      )}
    </div>
  );
}
