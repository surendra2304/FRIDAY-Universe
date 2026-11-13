"use client";

import { Eraser, Loader2, MessageSquareText, Send } from "lucide-react";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { ChatMessage, requestJson } from "@/lib/api";

/* ============================================================
   FRIDAY chat — talks to the friend-persona /api/chat pipeline
   (the same engine that routes to the 10-agent fleet).

   Chat-length fix (2026-11-13, owner directive "why is the chat
   that much long"): the transcript used to grow without bound —
   an hour of commands produced a wall of bubbles. Now the panel
   keeps only the last MAX_RENDERED exchanges in view, restores
   at most the last session tail, and has an explicit Clear
   button. The full history stays on the server (Memora) — only
   the rendered transcript is capped.
   ============================================================ */

const CHIPS = [
  "How's the fleet?",
  "What do you remember?",
  "Portfolio status",
  "Macro news",
];

/** Hard cap on rendered bubbles (most recent win). */
const MAX_RENDERED = 40;
/** Restored-from-history tail — enough context, never a wall. */
const RESTORE_LIMIT = 12;

function appendCapped(current: ChatMessage[], next: ChatMessage[]): ChatMessage[] {
  return [...current, ...next].slice(-MAX_RENDERED);
}

export function ChatPanel({ prefill }: { prefill?: { text: string; seq: number } }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [hydrated, setHydrated] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    setHydrated(true);
  }, []);

  /* Conversation-memory fix 2026-11-13: the server has persisted history
     (/api/v1/conversation/history, logged by every command), but the panel
     started EMPTY on every page load — the owner reloaded to a blank chat and
     concluded FRIDAY has no memory. Hydrate the last session's exchanges on
     mount. Round 2 (2026-11-13, owner directive): restore at most the last
     20 messages — a full 60-message wall (mostly one-line failures) read as
     a broken product on first paint. A divider marks it as restored context
     so the fresh session reads clean. Failure is silent and normal: a fresh
     install simply has nothing to restore. Round 3 (2026-11-13,
     owner directive): restore only a short tail — chat must read
     like a console, not an archive. */
  const [restoredCount, setRestoredCount] = useState(0);
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await requestJson<{
          entries?: Array<{
            user_input?: string;
            friday_reply?: string;
            timestamp?: string;
          }>;
        }>("/api/v1/conversation/history?limit=" + RESTORE_LIMIT);
        if (cancelled || !res.entries?.length) return;
        const restored: ChatMessage[] = [];
        for (const e of [...res.entries].reverse()) {
          const at = e.timestamp ? new Date(e.timestamp).getTime() : Date.now();
          if (e.user_input?.trim()) restored.push({ role: "user", text: e.user_input, at });
          if (e.friday_reply?.trim()) restored.push({ role: "friday", text: e.friday_reply, at });
        }
        const capped = restored.slice(-RESTORE_LIMIT);
        if (capped.length) {
          setMessages(capped);
          setRestoredCount(capped.length);
        }
      } catch {
        /* history unavailable → fresh chat, not an error surface */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  /* external prefill (e.g. "Ask" on a Fleet card): focus the input in
     place — never scrollIntoView, which used to yank the page (owner
     directive 2026-11-11: no scroll jumps, ever). */
  useEffect(() => {
    if (!prefill || prefill.seq === 0) return;
    setInput((current) => (current.trim() ? current : prefill.text));
    requestAnimationFrame(() => inputRef.current?.focus());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prefill?.seq]);

  const scrollToEnd = useCallback(() => {
    requestAnimationFrame(() => {
      const el = scrollRef.current;
      if (el) el.scrollTop = el.scrollHeight;
    });
  }, []);

  useEffect(() => {
    scrollToEnd();
  }, [messages, busy, scrollToEnd]);

  async function send(text: string) {
    const clean = text.trim();
    if (!clean || busy) return;
    setBusy(true);
    setInput("");
    setMessages((current) => appendCapped(current, [{ role: "user", text: clean, at: Date.now() }]));
    try {
      const result = await requestJson<{ reply?: string; mode?: string; metadata?: { proactive_notice?: string | null } }>("/api/chat", {
        method: "POST",
        body: JSON.stringify({ message: clean }),
      });
      const answer = result.reply || result.mode || "FRIDAY accepted the message.";
      setMessages((current) => appendCapped(current, [{ role: "friday", text: answer, at: Date.now() }]));
      /* Server pollution fix (2026-11-13): monitor alerts no longer arrive
         glued to the answer text — they ride in metadata and render here as
         a dismissible banner, so the answer itself stays clean. */
      setNotice(result.metadata?.proactive_notice ?? null);
    } catch (error) {
      const reason = error instanceof Error ? error.message : "FRIDAY could not be reached.";
      setMessages((current) => appendCapped(current, [{ role: "friday", text: reason, at: Date.now(), error: true }]));
    } finally {
      setBusy(false);
    }
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void send(input);
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void send(input);
    }
  }

  return (
    <div className="panel" id="chat">
      <div className="panel-head">
        <div className="panel-title">
          <div className="title-icon cyan">
            <MessageSquareText size={17} />
          </div>
          <div>
            <h3>Console</h3>
            <span className="subtitle">Commands, questions, fleet dispatch — same brain as the phone line</span>
          </div>
        </div>
        <button
          className="mini-btn chat-clear"
          onClick={() => {
            setMessages([]);
            setRestoredCount(0);
            setNotice(null);
          }}
          disabled={messages.length === 0}
          title="Clear the transcript — full history stays in FRIDAY's memory"
          aria-label="Clear chat transcript"
        >
          <Eraser size={13} /> Clear
        </button>
      </div>

      <div className="chat-body">
        {notice && (
          <div className="onboarding-hint" style={{ margin: "12px 18px 0" }} role="status">
            <span style={{ lineHeight: 1.45, whiteSpace: "pre-wrap" }}>{notice}</span>
            <button className="onboarding-dismiss" onClick={() => setNotice(null)} aria-label="Dismiss notice">
              dismiss
            </button>
          </div>
        )}
        <div className="chat-scroll" ref={scrollRef}>
          {restoredCount > 0 && (
            <div className="session-divider" aria-label="Restored conversation history">
              last session · {restoredCount} messages
            </div>
          )}
          {messages.length === 0 && (
            <div className="chat-empty">
              <h4 className="chat-empty-title">How can I help, Boss?</h4>
              <p style={{ margin: 0, fontSize: 13.5, maxWidth: 380 }}>
                Talk or type below — commands, questions, fleet dispatch.
              </p>
            </div>
          )}
          {messages.length > 0 &&
            messages.map((m, i) => (
              <div
                key={i}
                className={
                  m.role === "user"
                    ? "bubble user"
                    : m.error
                      ? "bubble friday error"
                      : "bubble friday"
                }
              >
                {m.text}
                <div className="bubble-meta">
                  {m.role === "user" ? "You" : "FRIDAY"} ·{" "}
                  {hydrated ? new Date(m.at).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" }) : ""}
                </div>
              </div>
            ))
          }
          {busy && (
            <div className="typing-row panel" style={{ padding: "13px 18px" }}>
              <span className="typing-dot" />
              <span className="typing-dot" />
              <span className="typing-dot" />
            </div>
          )}
        </div>

        <form className="chat-input-row" onSubmit={onSubmit}>
          {messages.length === 0 && (
            <div className="chat-chips chat-chips-anchor">
              <span className="chips-label">Try:</span>
              {CHIPS.map((chip) => (
                <button type="button" key={chip} className="chip" onClick={() => void send(chip)}>
                  {chip}
                </button>
              ))}
            </div>
          )}
          <textarea
            ref={inputRef}
            className="chat-input"
            rows={1}
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Message FRIDAY…"
            aria-label="Message FRIDAY"
            disabled={busy}
          />
          <button className="send-btn" type="submit" disabled={busy || !input.trim()} aria-label="Send message">
            {busy ? <Loader2 size={17} className="spin" /> : <Send size={17} />}
          </button>
        </form>
      </div>
    </div>
  );
}
