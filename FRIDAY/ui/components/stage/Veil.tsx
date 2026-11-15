"use client";

import { Search } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

/* ================================================================
   The veil — the single door to everything off-stage.
   One searchable list of commands; nothing in this room is
   reached any other way. Type to narrow, arrows to move, Enter
   to go, Escape to fall back to the stage. The list is short on
   purpose: a room you can hold in your head beats a menu you
   have to explore.
   ================================================================ */

export interface VeilCommand {
  id: string;
  label: string;
  hint: string;
  keys: string;
  run: () => void;
}

export function Veil({ commands, onClose }: { commands: VeilCommand[]; onClose: () => void }) {
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return commands;
    return commands.filter((c) => `${c.label} ${c.hint} ${c.keys}`.toLowerCase().includes(q));
  }, [commands, query]);

  const choose = (command: VeilCommand | undefined) => {
    if (!command) return;
    onClose();
    command.run();
  };

  return (
    <div className="veil-backdrop" role="presentation" onClick={onClose}>
      <div
        className="veil"
        role="dialog"
        aria-modal="true"
        aria-label="Everything else"
        onClick={(e) => e.stopPropagation()}
      >
        <label className="veil-search">
          <Search size={17} aria-hidden="true" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setActive(0);
            }}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setActive((a) => Math.min(a + 1, visible.length - 1));
              } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setActive((a) => Math.max(a - 1, 0));
              } else if (e.key === "Enter") {
                e.preventDefault();
                choose(visible[active]);
              } else if (e.key === "Escape") {
                e.preventDefault();
                onClose();
              }
            }}
            placeholder="Where to?"
            aria-label="Search everything the room can show"
          />
        </label>

        <ul className="veil-list">
          {visible.map((command, idx) => (
            <li key={command.id}>
              <button
                type="button"
                className={`veil-item ${idx === active ? "is-active" : ""}`}
                onMouseEnter={() => setActive(idx)}
                onClick={() => choose(command)}
              >
                <span className="veil-item-label">{command.label}</span>
                <span className="veil-item-hint">{command.hint}</span>
              </button>
            </li>
          ))}
          {visible.length === 0 && <li className="veil-empty">Nothing in the room matches that.</li>}
        </ul>

        <p className="veil-foot">Escape returns to the stage — the call and the conversation stay alive underneath.</p>
      </div>
    </div>
  );
}
