# FRIDAY Universe — Engineering Handoff (Superseded)

> **This document is superseded and retained only as a historical record.**
>
> It described a planned migration to PostgreSQL 18 deployed through Dokploy and
> Docker Swarm. That plan was abandoned. Production is **systemd + Caddy on two
> OCI VMs** with **Oracle Autonomous Database only** — there is no PostgreSQL,
> no SQLite, no Docker Swarm and no Traefik in the running system.
>
> For the current architecture and verified state, read:
> - `AGENTS.md` — agent inventory, live entrypoints, verified readiness matrix
> - `DEPLOYMENT_GUIDE.md` — how the system is actually deployed and operated
> - `CREDENTIALS.md` — where credentials live (never in this repository)
> - `docs/` — design system, animation and QA references
>
> Nothing in this file should be used to plan or operate the system.
