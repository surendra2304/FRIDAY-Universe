# FRIDAY Universe — Fleet Upgrade Prompts (Superseded)

> **Superseded. Do not execute these prompts.**
>
> This file described a fleet-wide upgrade that targeted a self-managed PostgreSQL
> instance on a Dokploy host and a SQLite fallback in `/dev/shm`. Both were
> retired. Production persistence is **Oracle Autonomous Database only**, with one
> unprivileged login and schema per agent.
>
> The credentials that previously appeared in this file were for a PostgreSQL
> container that no longer exists; they have been removed from the working tree.
> If that instance ever existed with those values, treat them as compromised and
> rotate anything that reused them.
>
> Current sources of truth:
> - `AGENTS.md` — agent inventory, live entrypoints, verified readiness matrix
> - `DEPLOYMENT_GUIDE.md` — systemd + Caddy deployment on the two OCI VMs
> - `CREDENTIALS.md` — where credentials live (`/etc/friday-universe/`, never Git)
