# TASK-FRG-023 — EVALUATION: Antigravity remote-SSH mode as a fleet dev workflow

**Task:** Forge: evaluate Antigravity remote-SSH mode as a fleet dev workflow.
**Source:** CLASSIFICATION-2026-11-24.md section 1, item 13 (watch record Df_5HRok_uH, @_aidailyhacks Google Antigravity SSH). **Priority:** P2. **Worker:** Muse TP9.
**Claim:** hub #1483 comment 7164985301 (2026-11-25 ~20:00 IST). **Branch:** `musetp9/task-frg-023`.
**Evaluation date:** 2026-11-25. **Antigravity version evaluated:** App v2.33.0+ ("Connect over SSH", shipped 2026-11-17).

## Verdict: RECOMMENDED for fleet dev, with conditions

Antigravity's Connect over SSH does what the task asks: agents, projects,
Git worktrees and terminals run on the remote Linux host and keep running
with the laptop closed. Every fleet server already meets the host
requirements (Ubuntu LTS, glibc ≥ 2.26, forwarding effectively allowed).
The conditions are a supervised trial on FRIDAY-Server first, a
`sshd -T` confirmation of the effective forwarding setting, and two
fleet rules (no double-running fleet agents from Antigravity; no
credentials pasted into Antigravity) — see §5.

## 1. What the official docs say (read first-hand)

Primary source: **https://antigravity.google/docs/ssh/** ("Connect over SSH",
Google Antigravity Docs, read 2026-11-25). Corroborated by the v2.33.0
changelog ("Connect over SSH and GitHub pull request integration",
2026-11-17) and independent coverage (alphasignal.ai, enjoy.dev,
thenewway.ai — all consistent with the docs).

> "Antigravity sets up its remote server automatically over OpenSSH so
> your projects, agents, Git worktrees, terminals, and customizations run
> directly on the host, and running agents keep working even if you close
> the window or put your laptop to sleep."

Capability mapping against the task's acceptance:

| Task requirement | Docs evidence |
|---|---|
| Agents run on the remote Linux machine | "Where agents run: Your remote Linux machine" (remote-options table); "Agent tools, shell commands, the Linux terminal sandbox, permissions, and side-panel terminals run on the host" |
| Projects / Git worktrees on the host | "Projects and worktrees: browse the remote filesystem and run agents in Local mode or New worktree mode" |
| Terminals on the host | Side-panel terminals run on the host; server installed at `~/.antigravity-hub-server/` |
| Keeps running with the laptop closed | "Close window: Closes and disconnects SSH. Keep running on `<host>`; reconnect anytime." / "Sleep or network drop: Retries automatically, or click Reconnect. Keep running and reattach when back online." / Stop only via explicit **Stop SSH Server…** |
| No manual host setup | "Host setup: None (automatic over OpenSSH)" — the App installs its server itself |
| Uses existing SSH config | Reads `~/.ssh/config`, `ssh-agent`, `ProxyJump`, OpenSSH keys; `--ssh-host=<destination>` CLI launch |

Remote options compared (docs table): **Connect over SSH** (agents on your
Linux machine, App client, no host setup) vs **Remote Control** (agents on
your own desktop/server, browser client, install + sign-in) vs **Remote
Agents** (Google-managed environment, Pro/Ultra). For fleet dev — where
the fleet already owns the servers — Connect over SSH is the right option:
no new Google-hosted dependency, no plan gate (the changelog lists no plan
limit for SSH; Remote Agents is Pro/Ultra).

## 2. Requirements vs the fleet (checked live, read-only)

Checked 2026-11-25 via the Friday Bridge (read-only `read_text`):
`/etc/os-release` on all 6 servers; `/etc/ssh/sshd_config` on all 6;
`/etc/ssh/sshd_config.d/60-cloudimg-settings.conf` on servers 1 and 3.

| Server | OS (live) | glibc | `AllowTcpForwarding` |
|---|---|---|---|
| 1 — Oracle S1 | Ubuntu 22.04.5 LTS | 2.35 (distro) | Commented out in main config → OpenSSH default `yes`; cloudimg drop-in sets only `PasswordAuthentication no` |
| 2 — Oracle S2 | Ubuntu 22.04.5 LTS | 2.35 | Commented out → default `yes` (drop-in not yet checked) |
| 3 — FRIDAY-Server | Ubuntu 24.04.5 LTS | 2.39 | Commented out → default `yes`; cloudimg drop-in sets only `PasswordAuthentication no` |
| 4 — Stratex-Server | Ubuntu 24.04.5 LTS | 2.39 | Commented out → default `yes` (drop-in not yet checked) |
| 5 — VyralX-Server | Ubuntu 24.04.5 LTS | 2.39 | Commented out → default `yes` (drop-in not yet checked) |
| 6 — IntelX-Server | Ubuntu 24.04.5 LTS | 2.39 | Commented out → default `yes` (drop-in not yet checked) |

Docs requirement: 64-bit Linux (`x86_64`/`arm64`) with glibc 2.26+
(Ubuntu 18.04+, Debian 10+, RHEL 8+). **All 6 servers pass on OS/glibc.**
Architecture is recorded as x86_64 per the cloud instance types — it was
not directly verified through the read-only tools, and must be confirmed
at trial time (`uname -m`).

## 3. Setup gotchas (from the full watch, confirmed in the docs)

1. **`AllowTcpForwarding yes` (or `local`) — on the host AND any
   `ProxyJump` host.** Docs Requirements + error code
   `FORWARDING_PROHIBITED`: "Port forwarding disabled. Set
   `AllowTcpForwarding yes` (or `local`) in `sshd_config` on the host and
   any jump host." The fleet's jump-host path (if any) needs the same
   setting — a host that forwards fine directly can still fail through a
   jump host that forbids it. Live check: all 6 servers leave it at the
   OpenSSH default (`yes`); the **effective** value still needs
   `sshd -T` at trial time (drop-ins checked only on servers 1 and 3).
2. **glibc-only — Alpine/musl fails.** Docs Requirements + error code
   `UNSUPPORTED_HOST`: "Host isn't 64-bit Linux (`x86_64`/`arm64`) with
   `glibc` 2.26+, or uses `musl` (such as Alpine)." macOS and Windows
   hosts are also unsupported. Consequence for the fleet: Antigravity can
   target the six servers, but **not** a slim Alpine container — any
   container-based dev host must be glibc-based (Debian/Ubuntu slim).
3. **Outbound HTTPS + writable, executable `$HOME`.** The server needs
   outbound HTTPS and `$HOME` must be writable and executable
   (`~/.antigravity-hub-server/` for the server, `~/.gemini/` for agent
   data). `INSTALL_FAILED` otherwise (also: `gzip` present if
   `curl`/`wget` absent; `~/.bashrc` silent on non-interactive shells).
4. **Shell startup has a 10s timeout.** The server loads the environment
   from `$SHELL -l -i` (10s timeout). Slow prompts break startup — skip
   them when `ANTIGRAVITY_RESOLVING_ENVIRONMENT=1` is set, guard
   `exec zsh` with `[ -t 0 ]`.
5. **SSH overrides.** Antigravity overrides `ForwardAgent=no`,
   `ForwardX11=no`, `ControlMaster=no`, `ControlPath=none`,
   `RemoteCommand=none`, `ServerAliveInterval=15`,
   `ServerAliveCountMax=3` on its `ssh` command line. Multiplexed
   ControlMaster sockets and agent forwarding in `~/.ssh/config` are
   ignored for its connections.
6. **Skills/config come from the host, not the laptop.** In an SSH
   window, skills, rules, hooks, MCP servers and plugins load from
   `~/.gemini/` and project folders **on the host**. A skill that exists
   only on the laptop is invisible in the remote window. Fleet implication:
   the fleet's shared prompts/skills must live on the host (or in the
   repo under `.agents/skills/`) to be visible.
7. **Shared `$HOME` across hosts is unsupported.** Error
   `SHARED_HOME_UNSUPPORTED`: two hosts sharing one networked `$HOME`
   cannot both run the server (Take Over moves it, stopping agents
   there). Not a fleet issue today (each server has its own `$HOME`).
8. **Local-only features differ in an SSH window.** Side-panel browser
   hidden (links open in the local browser); `/browser` attaches to
   Chrome on the **remote** host; voice mode prompts per session, camera
   and screen access stay disabled; "Open in IDE / Reveal in Finder"
   hidden.

## 4. Fleet-specific notes

- **Tailscale:** Antigravity uses plain OpenSSH + `~/.ssh/config`, so a
  Tailscale IP/hostname works as a `Host` entry exactly like any other
  host. No Tailscale-specific setup is documented or needed.
- **Exactly one copy of an agent runs at a time.** Antigravity's hub
  server is per-user and separate from the fleet's systemd supervision.
  Starting a fleet agent from an Antigravity terminal on the same host
  would double-run it. Trial rule: use Antigravity for editing,
  reviewing and running *disposable* commands — never start a fleet
  agent service from it until Muse rules otherwise.
- **Credentials.** OAuth sign-in saves credentials on the host
  (`~/.gemini`). The fleet's credentials live in ONE file, Server 2
  `/opt/friday_universe/CREDENTIALS.md` — never paste its contents into
  Antigravity, its config, or a chat. Antigravity's own OAuth token is a
  separate credential on the host.
- **No paid tier needed for SSH.** The docs/changelog list no plan limit
  for Connect over SSH (unlike Remote Agents, Pro/Ultra). Free-only rule
  is not breached by the trial.

## 5. Trial plan (what a live trial must do)

1. Install Antigravity App v2.33.0+ on the owner's laptop; confirm
   `ssh` in `PATH`.
2. On FRIDAY-Server (trial host): run `sshd -T | grep -i allowtcpforwarding`
   to confirm the effective value; confirm `uname -m` (x86_64) and
   `ldd --version` (glibc ≥ 2.26); confirm outbound HTTPS.
3. Add a `Host` entry for FRIDAY-Server in `~/.ssh/config`; verify plain
   `ssh <host>` works first.
4. Connect from the App (sidebar → SSH Host…); open
   `/opt/friday_universe`; run one disposable command in the remote
   terminal; start one background agent task; close the laptop lid /
   close the window; reconnect and confirm the agent kept running.
5. Record the outcome (including any failure) as evidence; if the trial
   passes, extend to Oracle Server 1/2 next (Memora/Forge/Cortex hosts).

## 6. What was NOT verified live

- No Antigravity install and no live SSH session from the IDE were run
  in this evaluation (no desktop app in this worker VM; live-fleet
  changes need Muse clearance). The verdict rests on the official docs
  read first-hand + the read-only host checks above.
- Architecture (x86_64 vs arm64) not directly verified; effective
  `AllowTcpForwarding` not proven with `sshd -T`; sshd drop-ins checked
  only on servers 1 and 3; outbound HTTPS from the hosts not tested.
- The source video (Df_5HRok_uH, @_aidailyhacks) was not re-watched;
  its gotchas are the ones the docs confirm (items 1–2 above).

## Sources

- Google Antigravity Docs, "Connect over SSH": https://antigravity.google/docs/ssh/ (read 2026-11-25)
- Antigravity changelog, v2.33.0 "Connect over SSH and GitHub pull request integration" (2026-11-17), via enjoy.dev / alphasignal.ai coverage
- Fleet host facts: Friday Bridge read-only `read_text` on servers 1–6, 2026-11-25 (`/etc/os-release`, `/etc/ssh/sshd_config`, cloudimg drop-in on 1 and 3)
