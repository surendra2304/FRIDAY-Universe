"use client";

import { Loader2, MessageSquareText, Send } from "lucide-react";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { ChatMessage, requestJson } from "@/lib/api";

/* ============================================================
   FRIDAY chat — talks to the friend-persona /api/chat pipeline
   (the same engine that routes to the 10-agent fleet).
   ============================================================ */

const CHIPS = [
  "How's the fleet?",
  "What do you remember?",
  "Portfolio status",
  "Macro news",
];

export function ChatPanel({ prefill }: { prefill?: { text: string; seq: number } }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [hydrated, setHydrated] = useState(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    setHydrated(true);
  }, []);

  /* Conversation-memory fix 2026-11-13: the server has persisted history
     (/api/v1/conversation/history, logged by every command), but the panel
     started EMPTY on every page load — the owner relaoded to a blank chat and
     concluded FRIDAY has no memory. Hydrate the last session's exchanges on
     mount. Failure is silent and normal: a fresh install simply has nothing
     to restore, and the chat starts empty as before. */
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
        }>("/api/v1/conversation/history?limit=30");
        if (cancelled || !res.entries?.length) return;
        const restored: ChatMessage[] = [];
        for (const e of [...res.entries].reverse()) {
          const at = e.timestamp ? new Date(e.timestamp).getTime() : Date.now();
          if (e.user_input?.trim()) restored.push({ role: "user", text: e.user_input, at });
          if (e.friday_reply?.trim()) restored.push({ role: "friday", text: e.friday_reply, at });
        }
        if (restored.length) setMessages(restored.slice(-60));
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
    setMessages((current) => [...current, { role: "user", text: clean, at: Date.now() }]);
    try {
      const result = await requestJson<{ reply?: string; mode?: string }>("/api/chat", {
        method: "POST",
        body: JSON.stringify({ message: clean }),
      });
      const answer = result.reply || result.mode || "FRIDAY accepted the message.";
      setMessages((current) => [...current, { role: "friday", text: answer, at: Date.now() }]);
    } catch (error) {
      const reason = error instanceof Error ? error.message : "FRIDAY could not be reached.";
      setMessages((current) => [...current, { role: "friday", text: reason, at: Date.now(), error: true }]);
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
      </div>

      <div className="chat-body">
        <div className="chat-scroll" ref={scrollRef}>
          {messages.length === 0 ? (
            <div className="chat-empty">
              <h4 className="chat-empty-title">How can I help, Boss?</h4>
              <p style={{ margin: 0, fontSize: 13.5, maxWidth: 380 }}>
                Talk or type below — commands, questions, fleet dispatch. Try a starter
                if you&apos;re not sure where to begin.
              </p>
              {/* Theme fix 2026-11-13 (VLM review): starter chips used to sit in a
                  separate row pinned above the input, leaving a dead band between
                  the centered greeting and the bottom controls. One centered unit:
                  greeting + starters together. */}
              <div className="chat-chips chat-chips-empty">
                <span className="chips-label">Try:</span>
                {CHIPS.map((chip) => (
                  <button key={chip} className="chip" onClick={() => void send(chip)}>
                    {chip}
                  </button>
                ))}
              </div>
            </div>
          ) : (
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
          )}
          {busy && (
            <div className="typing-row panel" style={{ padding: "13px 18px" }}>
              <span className="typing-dot" />
              <span className="typing-dot" />
              <span className="typing-dot" />
            </div>
          )}
        </div>

        <form className="chat-input-row" onSubmit={onSubmit}>
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
