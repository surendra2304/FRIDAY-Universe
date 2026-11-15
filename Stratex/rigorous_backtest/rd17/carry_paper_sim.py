#!/usr/bin/env python3
"""TASK-STR-RD-017 — funding-carry forward PAPER SIMULATION engine.

Runs the RD-009 `always_pos` book (long spot / short Binance USDT-M
perp, coin-quantity hedge, crypto30) FORWARD on live mainnet public
data, under the frozen declaration in declaration.json (same dir):
cross-margin portfolio simulation, perp leg at 1.0x, RD-009's cost
model, actual settled funding prints, hash-chained append-only ledger.

PAPER ONLY. No orders, no accounts, no API keys — public GET data.

Usage:
  carry_paper_sim.py poll   --state-dir DIR --transport rest|bridge
                            [--claim-comment ID]
  carry_paper_sim.py daemon --state-dir DIR --transport rest|bridge
                            --interval SECONDS [--claim-comment ID]
  carry_paper_sim.py report --state-dir DIR

State (all inside --state-dir):
  ledger.jsonl   the hash-chained append-only ledger (source of truth;
                 book state is rebuilt by replaying it on every start)
  bundles/       raw poll bundles, gzipped, SHA-256 named in MARK rows

Transports:
  rest    runs server_fetch.py (same dir) as a local subprocess — the
          durable deployment mode, for a host with direct Binance
          access (see README.md runbook).
  bridge  runs server_fetch.py on FRIDAY Server 2 via the bridge MCP
          (bridge_fetch.py) — the research-sandbox mode, used because
          the sandbox egress is geo-blocked by Binance. Same endpoints,
          same data; every data row records the transport.
"""
import argparse
import gzip
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent

# ---- frozen parameters (declaration.json is the authority; these are
# ---- its values, asserted against the file at start when present)
NOTIONAL = 1000.0            # one-leg notional per symbol, USDT (paper)
SPOT_FEE = 0.0010            # 0.10% per side
PERP_FEE = 0.0005            # 0.05% per side
SLIP = 0.0002                # 0.02% per leg-side
MMR = 0.01                   # flat maintenance-margin rate (declared)
MARGIN_REVIEW_EXCURSION = 0.25
DROP_FLIP_PCT = 0.05         # 5% of notional in rolling 30d
DROP_WINDOW_MS = 30 * 86400 * 1000
STOP_WINDOW_MS = 90 * 86400 * 1000
DAY_MS = 86400 * 1000

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
           "DOGEUSDT", "ADAUSDT", "LTCUSDT", "LINKUSDT", "DOTUSDT",
           "TRXUSDT", "AVAXUSDT", "NEARUSDT", "ATOMUSDT", "UNIUSDT",
           "ETCUSDT", "BCHUSDT", "FILUSDT", "APTUSDT", "ARBUSDT",
           "OPUSDT", "INJUSDT", "SUIUSDT", "XLMUSDT", "HBARUSDT",
           "ALGOUSDT", "VETUSDT", "SANDUSDT", "MANAUSDT", "AAVEUSDT"]


def utc_iso(ms):
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def utc_day(ms):
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime(
        "%Y-%m-%d")


# ---------------------------------------------------------------- IO --
def durable_write(path, data_bytes, mode="ab"):
    """Write with retries: the sandbox write-admission intermittently
    EPERMs for tens of seconds. Appends are single write() calls of one
    complete line; callers verify by read-back where it matters."""
    last = None
    deadline = time.time() + 180
    while time.time() < deadline:
        try:
            with open(path, mode) as f:
                f.write(data_bytes)
                f.flush()
                os.fsync(f.fileno())
            return
        except OSError as exc:  # noqa: PERF203
            last = exc
            time.sleep(2)
    raise RuntimeError(f"durable_write failed: {path}: {last}")


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True)


# ------------------------------------------------------------- Ledger --
class Ledger:
    def __init__(self, state_dir):
        self.dir = Path(state_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / "bundles").mkdir(exist_ok=True)
        self.path = self.dir / "ledger.jsonl"
        self.rows = []
        self.last_hash = "GENESIS"
        self.seq = 0
        if self.path.exists():
            for line in self.path.read_text().splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                expect = self._hash(row, with_hash=False)
                if row.get("row_hash") != expect:
                    raise RuntimeError(
                        f"ledger hash mismatch at seq {row.get('seq')}")
                if row.get("prev_hash") != self.last_hash:
                    raise RuntimeError(
                        f"ledger chain break at seq {row.get('seq')}")
                self.rows.append(row)
                self.last_hash = row["row_hash"]
                self.seq = row["seq"]

    @staticmethod
    def _hash(row, with_hash=True):
        body = {k: v for k, v in row.items() if k != "row_hash"}
        return hashlib.sha256(canonical(body).encode()).hexdigest()

    def append(self, row_type, ts_ms, payload, bundle_sha=None):
        row = {"seq": self.seq + 1, "ts_ms": int(ts_ms),
               "ts_utc": utc_iso(ts_ms), "type": row_type,
               "prev_hash": self.last_hash}
        row.update(payload)
        if bundle_sha:
            row["bundle_sha256"] = bundle_sha
        row["row_hash"] = self._hash(row)
        line = (json.dumps(row, sort_keys=True) + "\n").encode()
        # Verify-not-duplicate: if a previous append actually landed
        # despite an error, the seq on disk will already be ours.
        durable_write(self.path, line)
        tail = self.path.read_text().splitlines()[-1]
        landed = json.loads(tail)
        if landed.get("seq") != row["seq"] or \
                landed.get("row_hash") != row["row_hash"]:
            raise RuntimeError("ledger append did not land verifiably")
        self.rows.append(row)
        self.last_hash = row["row_hash"]
        self.seq = row["seq"]
        return row


# --------------------------------------------------------------- Book --
class Position:
    def __init__(self, sym):
        self.sym = sym
        self.status = "not_entered"     # open | closed | not_entered
        self.q = 0.0
        self.spot_entry = None
        self.mark_entry = None
        self.entry_ts = None
        self.entry_cost = 0.0           # 1x costs
        self.exit_cost = 0.0
        self.funding_cash = 0.0
        self.prints = []                # (funding_time_ms, rate)
        self.flip = []                  # (funding_time_ms, cashflow)
        self.max_adverse = 0.0          # max (mark/mark_entry - 1)
        self.review_fired = False
        self.realized = None            # segment PnL at close (1x)
        self.close_reason = None


class Book:
    def __init__(self):
        self.started = False
        self.ended = False
        self.end_reason = None
        self.start_ts = None
        self.capital = 0.0              # sum(N + M0) over entered
        self.cash = 0.0
        self.pos = {s: Position(s) for s in SYMBOLS}
        self.fees_total = 0.0           # 1x
        self.fees_total_2x = 0.0
        self.kill_trips = []
        self.book_review_armed = True
        self.mark_history = []          # (ts_ms, net_1x)
        self.f14 = {}                   # sym -> [(day, mean_rate)]
        self.turns_confirmed = []       # dicts
        self.turns_open = {}            # sym -> opening day
        self.last_snapshot_day = None

    # -- replay ------------------------------------------------------
    @classmethod
    def from_ledger(cls, ledger):
        book = cls()
        for row in ledger.rows:
            book.apply(row)
        return book

    def apply(self, row):
        t = row["type"]
        if t == "SIM_START":
            self.started = True
            self.start_ts = row["ts_ms"]
        elif t == "ENTRY":
            p = self.pos[row["symbol"]]
            p.status = "open"
            p.q = row["q"]
            p.spot_entry = row["spot_price"]
            p.mark_entry = row["mark_price"]
            p.entry_ts = row["ts_ms"]
            p.entry_cost = row["entry_cost"]
            self.capital += 2 * NOTIONAL
            self.cash += 2 * NOTIONAL - NOTIONAL - row["entry_cost"]
            self.fees_total += row["entry_cost"]
            self.fees_total_2x += 2 * row["entry_cost"]
        elif t == "FUNDING":
            p = self.pos[row["symbol"]]
            p.funding_cash += row["cashflow"]
            p.prints.append((row["funding_time_ms"], row["rate"]))
            p.flip.append((row["funding_time_ms"], row["cashflow"]))
            self.cash += row["cashflow"]
        elif t == "MARK":
            self.mark_history.append((row["ts_ms"], row["net_1x"]))
            for sym, d in row["symbols"].items():
                p = self.pos.get(sym)
                if p and d.get("max_adverse") is not None:
                    p.max_adverse = max(p.max_adverse, d["max_adverse"])
        elif t == "MARGIN_REVIEW":
            if row.get("symbol"):
                self.pos[row["symbol"]].review_fired = True
            else:
                self.book_review_armed = False
        elif t in ("SYMBOL_DROP", "CLOSE_ALL"):
            for c in row["closes"]:
                p = self.pos[c["symbol"]]
                p.status = "closed"
                p.exit_cost = c["exit_cost"]
                p.realized = c["segment_pnl"]
                p.close_reason = row["type"]
                self.cash += c["spot_proceeds"] + c["perp_pnl"] \
                    - c["exit_cost"]
                self.fees_total += c["exit_cost"]
                self.fees_total_2x += 2 * c["exit_cost"]
            if t == "SYMBOL_DROP":
                self.kill_trips.append(
                    {"type": t, "ts_ms": row["ts_ms"],
                     "symbol": row["closes"][0]["symbol"]})
        elif t == "REGIME_SNAPSHOT":
            self.last_snapshot_day = row["day"]
            for sym, mean_rate in row["f14"].items():
                self.f14.setdefault(sym, []).append((row["day"], mean_rate))
        elif t == "REGIME_TURN":
            self.turns_confirmed.append(
                {"symbol": row["symbol"], "opened_day": row["opened_day"],
                 "confirmed_day": row["day"]})
            self.turns_open.pop(row["symbol"], None)
        elif t == "REGIME_TURN_OPEN":
            self.turns_open[row["symbol"]] = row["opened_day"]
        elif t in ("KILL_STOP", "LIQUIDATION"):
            self.kill_trips.append({"type": t, "ts_ms": row["ts_ms"]})
        elif t == "SIM_END":
            self.ended = True
            self.end_reason = row.get("reason")

    # -- valuation ---------------------------------------------------
    def value(self, bundle_symbols):
        """Returns aggregates at a bundle's prices. Open positions only
        contribute spot value + perp uPnL; cash already holds realised
        proceeds, funding and fees."""
        spot_val = 0.0
        perp_upnl = 0.0
        mm = 0.0
        per = {}
        for sym, p in self.pos.items():
            if p.status != "open":
                continue
            d = bundle_symbols.get(sym) or {}
            spot = d.get("spot")
            mark = d.get("mark")
            if spot is None or mark is None:
                per[sym] = {"missing": True}
                continue
            sv = p.q * spot
            upnl = -p.q * (mark - p.mark_entry)
            basis = p.q * (spot - p.spot_entry) + upnl
            seg = basis + p.funding_cash - p.entry_cost
            spot_val += sv
            perp_upnl += upnl
            mm += p.q * mark * MMR
            adverse = mark / p.mark_entry - 1.0
            per[sym] = {
                "spot": spot, "mark": mark, "spot_value": sv,
                "perp_upnl": upnl, "basis": basis,
                "funding_cash": p.funding_cash, "segment_pnl": seg,
                "segment_pnl_2x": basis + p.funding_cash
                - 2 * p.entry_cost,
                "max_adverse": max(p.max_adverse, adverse),
                "adverse_now": adverse,
            }
        equity = self.cash + spot_val + perp_upnl
        net_1x = equity - self.capital
        # 2x shadow: same book, doubled fees (entry/exit) — fees_total_2x
        # replaces fees_total inside equity.
        equity_2x = equity + self.fees_total - self.fees_total_2x
        net_2x = equity_2x - self.capital
        return {"per": per, "spot_value": spot_val, "perp_upnl": perp_upnl,
                "equity": equity, "mm": mm,
                "margin_ratio": (equity / mm) if mm > 0 else None,
                "net_1x": net_1x, "net_2x": net_2x}

    def close_out(self, sym, bundle_symbols, ts_ms):
        """Hypothetical close of one open position at bundle prices.
        Returns the close record (does not mutate the book)."""
        p = self.pos[sym]
        d = bundle_symbols[sym]
        spot, mark = d["spot"], d["mark"]
        spot_proceeds = p.q * spot
        perp_pnl = -p.q * (mark - p.mark_entry)
        # RD-009 cost model is expressed on one-leg notional (its
        # declared approximation), so the exit charge is on NOTIONAL.
        exit_cost = NOTIONAL * ((SPOT_FEE + SLIP) + (PERP_FEE + SLIP))
        basis = p.q * (spot - p.spot_entry) + perp_pnl
        seg = basis + p.funding_cash - p.entry_cost - exit_cost
        return {"symbol": sym, "spot_price": spot, "mark_price": mark,
                "spot_proceeds": spot_proceeds, "perp_pnl": perp_pnl,
                "exit_cost": exit_cost, "segment_pnl": seg}


# ------------------------------------------------------------ Engine --
def declaration_hash():
    p = HERE / "declaration.json"
    if p.exists():
        return hashlib.sha256(p.read_bytes()).hexdigest()
    return None


def fetch_bundle(transport, since_map, state_dir):
    """Returns (bundle_dict, transport_tag). Raises on total failure."""
    spec = {"symbols": SYMBOLS, "since_ms": since_map}
    if transport == "rest":
        proc = subprocess.run(
            [sys.executable, str(HERE / "server_fetch.py")],
            input=json.dumps(spec), capture_output=True, text=True,
            timeout=180)
        out = proc.stdout
    elif transport == "bridge":
        import bridge_fetch
        out = bridge_fetch.fetch_bundle_text(spec, state_dir)
    else:
        raise ValueError(f"unknown transport {transport}")
    for line in out.splitlines():
        if line.startswith("RD17BUNDLE "):
            return json.loads(line[len("RD17BUNDLE "):]), transport \
                if transport == "rest" else "bridge-s1"
    raise RuntimeError("no RD17BUNDLE line in fetch output: "
                       + out[:400])


def archive_bundle(state_dir, bundle):
    raw = json.dumps(bundle, sort_keys=True).encode()
    sha = hashlib.sha256(raw).hexdigest()
    path = Path(state_dir) / "bundles" / f"{bundle['fetched_at_ms']}.json.gz"
    if not path.exists():
        durable_write(path, gzip.compress(raw), mode="wb")
    return sha


def entry_cost():
    return NOTIONAL * ((SPOT_FEE + SLIP) + (PERP_FEE + SLIP))


def poll(state_dir, transport, claim_comment=None):
    ledger = Ledger(state_dir)
    book = Book.from_ledger(ledger)
    if book.ended:
        return {"status": "ended", "reason": book.end_reason}
    since = {}
    for sym, p in book.pos.items():
        if p.status == "open":
            since[sym] = p.prints[-1][0] if p.prints else p.entry_ts
        elif book.started:
            since[sym] = book.start_ts
        else:
            # Book not open yet: pre-entry prints are never booked
            # (funding loop credits only fundingTime > entry_ts), so
            # fetching history is pure waste — with since=0 the fetcher
            # pulled 100 prints/symbol and a kline for each, which
            # timed out the bridge's 120s run_shell cap on the first
            # live poll (ledger seq 1, ERROR). Start from now; the next
            # poll re-fetches from entry_ts and catches any print that
            # lands between this fetch and the ENTRY booking.
            since[sym] = int(time.time() * 1000)
    try:
        bundle, tag = fetch_bundle(transport, since, state_dir)
    except Exception as exc:  # noqa: BLE001
        ledger.append("ERROR", int(time.time() * 1000),
                      {"stage": "fetch", "error": str(exc)[:500],
                       "transport": transport})
        return {"status": "fetch_error", "error": str(exc)[:300]}
    ts = bundle["fetched_at_ms"]
    bsym = bundle["symbols"]
    sha = archive_bundle(state_dir, bundle)

    # -- first poll: open the book ------------------------------------
    if not book.started:
        entered, not_entered = [], {}
        for sym in SYMBOLS:
            d = bsym.get(sym) or {}
            if d.get("spot") and d.get("mark"):
                entered.append(sym)
            else:
                not_entered[sym] = "missing spot or mark in start bundle"
        ledger.append("SIM_START", ts, {
            "declaration_sha256": declaration_hash(),
            "claim_comment": claim_comment,
            "transport": tag,
            "capital_per_symbol": 2 * NOTIONAL,
            "entered": entered, "not_entered": not_entered}, sha)
        for sym in entered:
            d = bsym[sym]
            q = NOTIONAL / d["spot"]
            ledger.append("ENTRY", ts, {
                "symbol": sym, "q": q, "spot_price": d["spot"],
                "mark_price": d["mark"], "entry_cost": entry_cost(),
                "transport": tag}, sha)
        book = Book.from_ledger(ledger)
        val = book.value(bsym)
        ledger.append("MARK", ts, {
            "transport": tag, "equity": val["equity"], "mm": val["mm"],
            "margin_ratio": val["margin_ratio"], "net_1x": val["net_1x"],
            "net_2x": val["net_2x"], "symbols": val["per"]}, sha)
        return {"status": "started", "entered": len(entered),
                "not_entered": not_entered}

    # -- funding prints ------------------------------------------------
    for sym in SYMBOLS:
        p = book.pos[sym]
        if p.status != "open":
            continue
        seen = {ft for ft, _ in p.prints}
        for pr in (bsym.get(sym) or {}).get("prints", []):
            ft = pr["funding_time_ms"]
            if ft <= p.entry_ts or ft in seen:
                continue
            mark_at = pr.get("mark_at_print")
            approx = mark_at is None
            if approx:
                mark_at = (bsym.get(sym) or {}).get("mark")
            if mark_at is None:
                ledger.append("ERROR", ts, {
                    "stage": "funding_mark", "symbol": sym,
                    "funding_time_ms": ft,
                    "error": "no mark available for print"}, sha)
                continue
            cashflow = p.q * mark_at * pr["rate"]  # short receives r>0
            ledger.append("FUNDING", ts, {
                "symbol": sym, "funding_time_ms": ft, "rate": pr["rate"],
                "mark_at_print": mark_at, "mark_approx": approx,
                "cashflow": cashflow, "transport": tag}, sha)
            p.funding_cash += cashflow
            p.prints.append((ft, pr["rate"]))
            p.flip.append((ft, cashflow))
            book.cash += cashflow
            seen.add(ft)

    # -- valuation ------------------------------------------------------
    val = book.value(bsym)
    ledger.append("MARK", ts, {
        "transport": tag, "equity": val["equity"], "mm": val["mm"],
        "margin_ratio": val["margin_ratio"], "net_1x": val["net_1x"],
        "net_2x": val["net_2x"], "symbols": val["per"]}, sha)
    book.mark_history.append((ts, val["net_1x"]))

    # -- liquidation (armed first: it is the account-level truth) ------
    if val["mm"] > 0 and val["equity"] <= val["mm"]:
        closes = [book.close_out(s, bsym, ts) for s in SYMBOLS
                  if book.pos[s].status == "open"
                  and (bsym.get(s) or {}).get("spot")]
        ledger.append("LIQUIDATION", ts, {
            "equity": val["equity"], "mm": val["mm"],
            "reason": "equity <= maintenance margin"}, sha)
        ledger.append("CLOSE_ALL", ts, {"closes": closes,
                                        "reason": "LIQUIDATION"}, sha)
        ledger.append("SIM_END", ts, {"reason": "LIQUIDATED"})
        return {"status": "liquidated"}

    # -- margin reviews ---------------------------------------------------
    for sym, d in val["per"].items():
        p = book.pos[sym]
        if d.get("max_adverse") is not None \
                and d["max_adverse"] >= MARGIN_REVIEW_EXCURSION \
                and not p.review_fired:
            ledger.append("MARGIN_REVIEW", ts, {
                "symbol": sym, "max_adverse": d["max_adverse"],
                "equity": val["equity"],
                "margin_ratio": val["margin_ratio"],
                "note": "25% adverse excursion at 1x cross: review "
                        "event per declaration (not a halt)"}, sha)
            p.review_fired = True
    open_m0 = NOTIONAL * sum(1 for p in book.pos.values()
                             if p.status == "open")
    if open_m0 > 0 and val["perp_upnl"] < -MARGIN_REVIEW_EXCURSION * open_m0 \
            and book.book_review_armed:
        ledger.append("MARGIN_REVIEW", ts, {
            "symbol": None, "perp_upnl": val["perp_upnl"],
            "equity": val["equity"], "margin_ratio": val["margin_ratio"],
            "note": "aggregate perp uPnL < -25% of initial perp margin"},
            sha)
        book.book_review_armed = False
    if open_m0 > 0 and val["perp_upnl"] >= -0.20 * open_m0:
        book.book_review_armed = True

    # -- symbol drop: flip cost > 5% of notional in rolling 30d ---------
    for sym in SYMBOLS:
        p = book.pos[sym]
        if p.status != "open":
            continue
        window = [cf for ft, cf in p.flip if ts - ft <= DROP_WINDOW_MS]
        if sum(window) < -DROP_FLIP_PCT * NOTIONAL:
            if (bsym.get(sym) or {}).get("spot"):
                close = book.close_out(sym, bsym, ts)
                ledger.append("SYMBOL_DROP", ts, {
                    "closes": [close], "flip_30d": sum(window),
                    "reason": "funding flip cost > 5% of notional in 30d"},
                    sha)
                p.status = "closed"

    # -- book stop: rolling-90d net < 0 (only once 90d exist) -----------
    if book.start_ts and ts - book.start_ts >= STOP_WINDOW_MS:
        past = [n for t0, n in book.mark_history
                if t0 <= ts - STOP_WINDOW_MS]
        if past and val["net_1x"] - past[-1] < 0:
            closes = [book.close_out(s, bsym, ts) for s in SYMBOLS
                      if book.pos[s].status == "open"
                      and (bsym.get(s) or {}).get("spot")]
            ledger.append("KILL_STOP", ts, {
                "rolling_90d_net": val["net_1x"] - past[-1]}, sha)
            ledger.append("CLOSE_ALL", ts, {"closes": closes,
                                            "reason": "KILL_STOP"}, sha)
            ledger.append("SIM_END", ts, {"reason": "STOPPED_KILL"})
            return {"status": "stopped_kill"}

    # -- daily regime snapshot -------------------------------------------
    today = utc_day(ts)
    if book.last_snapshot_day != today:
        f14 = {}
        for sym in SYMBOLS:
            p = book.pos[sym]
            if p.status != "open" and not p.prints:
                continue
            rates = [r for ft, r in p.prints
                     if ts - 14 * DAY_MS < ft <= ts]
            if rates:
                f14[sym] = sum(rates) / len(rates)
            elif book.f14.get(sym):
                f14[sym] = book.f14[sym][-1][1]
        if f14:
            ledger.append("REGIME_SNAPSHOT", ts, {"day": today, "f14": f14})
            prev = dict(book.f14)
            for sym, mean_rate in f14.items():
                prev.setdefault(sym, []).append((today, mean_rate))
            def _sign(v):
                return math.copysign(1, v) if v != 0 else 0
            confirmed_keys = {(t["symbol"], t["opened_day"])
                              for t in book.turns_confirmed}
            for sym, series in prev.items():
                if len(series) < 15:
                    continue
                sign_now = _sign(series[-1][1])
                if not sign_now:
                    continue
                # Baseline = the last ESTABLISHED (non-zero) sign at or
                # before the snapshot 14 earlier. A gradual F14 decay
                # passes through an exact 0.0 snapshot; sign(0) is no
                # regime, so the comparison is against the last real
                # sign (declaration interpretation, disclosed in the
                # README: zero-F14 snapshots carry no sign).
                sign_then = 0
                for _, v in reversed(series[:-14]):
                    if v != 0:
                        sign_then = _sign(v)
                        break
                if not sign_then or sign_then == sign_now:
                    continue
                # did the new sign persist the last 14 snapshots?
                last14 = [_sign(v) for _, v in series[-14:]]
                if all(s == sign_now for s in last14):
                    opened = series[-14][0]
                    if (sym, opened) in confirmed_keys:
                        continue
                    ledger.append("REGIME_TURN", ts, {
                        "symbol": sym, "day": today,
                        "opened_day": opened,
                        "f14_now": series[-1][1]})
                    book.turns_confirmed.append(
                        {"symbol": sym, "opened_day": opened,
                         "confirmed_day": today})
                    confirmed_keys.add((sym, opened))
            book.last_snapshot_day = today
            book.f14 = {k: v[-40:] for k, v in prev.items()}

    return {"status": "ok", "net_1x": val["net_1x"],
            "equity": val["equity"], "margin_ratio": val["margin_ratio"]}


# -------------------------------------------------------------- Report --
def report(state_dir):
    ledger = Ledger(state_dir)
    book = Book.from_ledger(ledger)
    out = {"rows": len(ledger.rows), "started": book.started,
           "ended": book.ended, "end_reason": book.end_reason,
           "start_ts": book.start_ts,
           "start_utc": utc_iso(book.start_ts) if book.start_ts else None,
           "kill_trips": book.kill_trips,
           "turns_confirmed": book.turns_confirmed}
    # T1: funding identity from archived bundles
    bundles_dir = Path(state_dir) / "bundles"
    funding_from_bundles = {}
    prints_seen = set()
    if bundles_dir.exists():
        entry_ts = book.start_ts or 0
        for gz in sorted(bundles_dir.glob("*.json.gz")):
            bundle = json.loads(gzip.decompress(gz.read_bytes()))
            for sym, d in bundle["symbols"].items():
                p = book.pos.get(sym)
                if not p:
                    continue
                for pr in d.get("prints", []):
                    key = (sym, pr["funding_time_ms"])
                    if pr["funding_time_ms"] <= entry_ts \
                            or key in prints_seen:
                        continue
                    prints_seen.add(key)
                    mark_at = pr.get("mark_at_print")
                    if mark_at is None:
                        continue  # approx rows cannot be recomputed
                    funding_from_bundles[sym] = \
                        funding_from_bundles.get(sym, 0.0) \
                        + p.q * mark_at * pr["rate"]
    funding_ledger = {s: p.funding_cash for s, p in book.pos.items()
                      if p.prints}
    t1 = {}
    for sym in set(funding_from_bundles) | set(funding_ledger):
        a = funding_from_bundles.get(sym, 0.0)
        b = funding_ledger.get(sym, 0.0)
        t1[sym] = {"bundles": a, "ledger": b, "diff": a - b}
    out["T1_funding_identity"] = t1
    # last mark aggregates
    marks = [r for r in ledger.rows if r["type"] == "MARK"]
    if marks:
        last = marks[-1]
        out["last_mark"] = {"ts_utc": last["ts_utc"],
                            "equity": last["equity"],
                            "net_1x": last["net_1x"],
                            "net_2x": last["net_2x"],
                            "margin_ratio": last["margin_ratio"]}
        # T2: decomposition identity at last mark
        t2 = {}
        for sym, d in last["symbols"].items():
            if "segment_pnl" not in d:
                continue
            expect = d["basis"] + d["funding_cash"] \
                - book.pos[sym].entry_cost
            t2[sym] = {"segment_pnl": d["segment_pnl"],
                       "components": expect,
                       "diff": d["segment_pnl"] - expect}
        out["T2_decomposition_identity"] = t2
    out["funding_rows"] = sum(1 for r in ledger.rows
                              if r["type"] == "FUNDING")
    out["positions"] = {
        s: {"status": p.status, "funding_cash": p.funding_cash,
            "prints": len(p.prints), "max_adverse": p.max_adverse,
            "realized": p.realized}
        for s, p in book.pos.items()}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["poll", "daemon", "report"])
    ap.add_argument("--state-dir", required=True)
    ap.add_argument("--transport", default="rest",
                    choices=["rest", "bridge"])
    ap.add_argument("--interval", type=int, default=900)
    ap.add_argument("--claim-comment", default=None)
    args = ap.parse_args()
    if args.cmd == "report":
        print(json.dumps(report(args.state_dir), indent=1, default=str))
        return
    if args.cmd == "poll":
        print(json.dumps(poll(args.state_dir, args.transport,
                              args.claim_comment), default=str))
        return
    # daemon
    while True:
        try:
            res = poll(args.state_dir, args.transport, args.claim_comment)
            print(f"[{utc_iso(int(time.time() * 1000))}] {res}",
                  flush=True)
            if res.get("status") in ("ended", "liquidated",
                                     "stopped_kill"):
                return
        except Exception as exc:  # noqa: BLE001
            print(f"daemon poll exception: {exc}", flush=True)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
