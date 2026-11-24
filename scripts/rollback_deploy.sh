#!/usr/bin/env bash
# TASK-OBS-002 — Safe rollback for a bad deploy (run ON THE SERVER).
#
# The Fleet CD workflow deploys with `git fetch origin main && git reset --hard
# origin/main` and restarts changed services. A bad commit on main therefore
# resets BOTH servers into a broken state with one push. This script is the
# tested recovery path: it can only move the deployment BACKWARD (target must
# be an ancestor of the currently deployed commit), shows what would change,
# restarts only the services affected by the rollback, and health-checks them.
#
# Usage (on a production host):
#   sudo bash scripts/rollback_deploy.sh <known-good-sha>          # interactive, asks for confirmation
#   sudo bash scripts/rollback_deploy.sh <known-good-sha> --yes    # non-interactive
#   sudo bash scripts/rollback_deploy.sh <known-good-sha> --dry-run
#   sudo bash scripts/rollback_deploy.sh <sha> --yes --json        # machine-readable evidence
#
# Evidence: prints the pre/post HEAD, the services restarted and each one's
# health after rollback; with --json writes a rollback receipt to
# /var/lib/friday-universe/rollback-receipts/ (append-only).
set -euo pipefail

REPO="${ROLLBACK_REPO_DIR:-/opt/friday_universe}"
RECEIPTS_DIR="/var/lib/friday-universe/rollback-receipts"
# TASK-OBS-013: candidate lists mirror the Fleet CD per-server lists
# (.github/workflows/deploy-monorepo.yml: SERVER1_AGENTS / SERVER2_AGENTS)
# plus each server's daemon / voice units. The old lists were stale:
# Futuris/IntelX are Server 2 services (masked on Server 1) and Sentinel
# is a Server 1 service (loaded+active on Server 1, masked on Server 2)
# — verified live 2026-11-23. Membership is still LoadState-gated below,
# so a listed-but-masked unit is never restarted.
# TASK-REL-098 (2026-11-24 move): FRIDAY + Inference now live on
# FRIDAY-Server (AWS) and Stratex on Stratex-Server (AWS); their Server 1
# units are stopped + disabled sleeping backups. The LoadState gate can NOT
# protect them — a disabled unit still reports LoadState=loaded, so a
# restart here would revive the backup (the PR #1642 defect, fixed in the
# workflow map). They are removed from this list with the daemon/voice
# units that moved with them; a rollback affecting their folders restarts
# nothing on Server 1, which is correct — they deploy nowhere on Oracle now.
SERVER1_SERVICES=(Memora Forge Sentinel)
SERVER2_SERVICES=(VyralX Cortex IntelX Futuris VyralX-Daemon)
# Ports for health checks of units that expose one (daemon units have none).
declare -A PORTS=( [FRIDAY]=10000 [Inference]=8001 [Memora]=8002 [Stratex]=8003
                   [Futuris]=8004 [IntelX]=8005 [Forge]=8006 [Sentinel]=8008
                   [Cortex]=8009 [VyralX]=8010 )

TARGET="${1:-}"
MODE_ARGS=("${@:2}")
ASSUME_YES=false; DRY_RUN=false; JSON=false
for a in "${MODE_ARGS[@]:-}"; do
  case "$a" in
    --yes) ASSUME_YES=true ;;
    --dry-run) DRY_RUN=true ;;
    --json) JSON=true ;;
  esac
done

fail() { echo "ROLLBACK-ABORT: $*" >&2; exit 1; }
[ -n "$TARGET" ] || fail "usage: rollback_deploy.sh <known-good-sha> [--yes|--dry-run|--json]"
cd "$REPO" || fail "repo directory $REPO missing"
# 1. Resolve and validate the target BEFORE touching anything.
git fetch origin main >/dev/null 2>&1 || true
git cat-file -e "$TARGET^{commit}" 2>/dev/null || fail "target '$TARGET' is not a commit object in this repository"
CURRENT=$(git rev-parse HEAD)
TARGET_RESOLVED=$(git rev-parse "$TARGET^{commit}")
[ "$TARGET_RESOLVED" != "$CURRENT" ] || fail "target $TARGET_RESOLVED is already the deployed HEAD (nothing to roll back)"

# Rollback-only guard: target must be an ancestor of the deployed commit.
if ! git merge-base --is-ancestor "$TARGET_RESOLVED" "$CURRENT"; then
  fail "target $TARGET_RESOLVED is NOT an ancestor of deployed $CURRENT — refusing to roll 'forward' or sideways"
fi

CHANGED_FOLDERS=$(git diff --name-only "$CURRENT" "$TARGET_RESOLVED" | awk -F/ '{print $1}' | sort -u)

# --- TASK-OBS-013 (G3 fix) ---
# The affected-service set must be a pure function of (changed folders,
# each candidate unit's LoadState). The old code tested each candidate with
# `systemctl list-unit-files | grep -qw` inside a condition: a transient
# systemctl failure was swallowed (2>/dev/null + grep) and silently dropped
# the service, so identical inputs returned different restart sets (OBS-009
# G3, proven live: S1 gave 3 different sets in 3 runs), and masked units
# passed the existence test, so a restart aborted the script AFTER
# `git reset --hard` (set -euo pipefail) — a half-rolled-back fleet with no
# receipt. Fixed: the Fleet CD gate (TASK-OBS-006) — `systemctl show
# <unit> --property=LoadState --value`, restart only `loaded`; transient
# read failures are retried, and a unit whose LoadState still cannot be
# read aborts BEFORE any reset. On a host without a running systemd
# (fixture / CI), no unit is restartable and the set is empty.
# systemd's runtime dir; override for tests (same pattern as ROLLBACK_REPO_DIR).
SYSTEMD_RUN_DIR="${ROLLBACK_SYSTEMD_RUN_DIR:-/run/systemd/system}"
HAS_SYSTEMD=false
if command -v systemctl >/dev/null 2>&1 && [ -d "$SYSTEMD_RUN_DIR" ]; then
  HAS_SYSTEMD=true
fi

# LoadState of one unit, retried: a transient D-Bus error must not silently
# drop a service (the G3 failure mode). Prints the state, or returns 1.
unit_load_state() {
  local unit="$1" state="" attempt=0
  while [ $attempt -lt 3 ]; do
    attempt=$((attempt + 1))
    state=$(systemctl show "${unit}.service" --property=LoadState --value 2>/dev/null || true)
    if [ -n "$state" ]; then
      printf '%s\n' "$state"
      return 0
    fi
    sleep 2
  done
  echo "cannot read LoadState of ${unit}.service after 3 attempts" >&2
  return 1
}

# Repo folder whose change affects a service: daemons and the voice worker
# share their parent agent's folder (same rule Fleet CD uses).
folder_for() {
  case "$1" in
    Stratex-Daemon) echo "Stratex" ;;
    VyralX-Daemon) echo "VyralX" ;;
    FRIDAY-Voice) echo "FRIDAY" ;;
    *) echo "$1" ;;
  esac
}

affected_for() {
  local -n svc_arr=$1
  local out=() svc folder state
  for svc in "${svc_arr[@]}"; do
    folder=$(folder_for "$svc")
    if echo "$CHANGED_FOLDERS" | grep -qw "$folder" || echo "$CHANGED_FOLDERS" | grep -Eqw "mesh|deploy|scripts"; then
      # Fleet CD gate: restart only LoadState=loaded. Masked / not-found
      # units are never in the restart set.
      state=""
      if $HAS_SYSTEMD; then
        state=$(unit_load_state "$svc") || fail "cannot read LoadState of ${svc}.service — aborting before any reset"
      fi
      if [ "$state" = "loaded" ]; then
        out+=("$svc")
      fi
    fi
  done
  echo "${out[@]:-}"
}

if $HAS_SYSTEMD; then
  # Server identity from the VyralX unit's LoadState (one retried, fail-loud
  # read): VyralX is installed on Server 2 (masked — it runs on AWS U2) and
  # not installed on Server 1. The old `list-unit-files | grep` probe had
  # the same G3 lottery — a failed probe misdetected the server.
  VYRALX_STATE=$(unit_load_state "VyralX") || fail "cannot read LoadState of VyralX.service — aborting before any reset"
  if [ "$VYRALX_STATE" != "not-found" ]; then
    AFFECTED=$(affected_for SERVER2_SERVICES)
  else
    AFFECTED=$(affected_for SERVER1_SERVICES)
  fi
else
  # No running systemd: nothing is restartable.
  AFFECTED=""
fi

if $DRY_RUN; then
  echo "DRY-RUN rollback $CURRENT -> $TARGET_RESOLVED"
  echo "would restart: ${AFFECTED:-<none>}"
  git diff --stat "$CURRENT" "$TARGET_RESOLVED" | tail -5
  exit 0
fi

# --- TASK-REL-098 failed-deploy recovery guard ---
# The restart loop below runs under `set -e`: a failing `systemctl restart`
# aborts the script mid-loop, leaving that service stopped (the Fleet CD
# failure mode of 2026-11-24: a failed deploy left Memora stopped) with no
# receipt written. If this script fails AFTER the reset, make ONE bounded
# recovery attempt per affected service found inactive (reset-failed +
# start), then exit with the ORIGINAL failure code — recovery never masks
# the failure. Only services in this run's affected set are touched; a run
# that fails before the reset (AFFECTED empty) or succeeds is a no-op.
# Executed by tests/test_fleet_cd_rel098_recovery_guard.py.
REL098_AFFECTED="${AFFECTED:-}"
rel098_recover() {
  local rc=$?
  [ "$rc" -eq 0 ] && return 0
  [ -n "${REL098_AFFECTED:-}" ] || return 0
  echo "TASK-REL-098 recovery: rollback failed (rc=$rc); starting any affected service found stopped"
  for svc in $REL098_AFFECTED; do
    state="$(unit_load_state "$svc" 2>/dev/null || true)"
    if [ "$state" = "loaded" ] && ! systemctl is-active --quiet "${svc}.service"; then
      echo "  $svc: stopped after failed rollback — attempting start"
      sudo systemctl reset-failed "${svc}.service" || true
      sudo systemctl start "${svc}.service" || echo "  WARNING: $svc recovery start failed — manual recovery required (systemctl start ${svc}.service)"
    fi
  done
}
trap rel098_recover EXIT

if ! $ASSUME_YES; then
  echo "About to roll back $REPO:"
  echo "  HEAD: $CURRENT -> $TARGET_RESOLVED ($(git log -1 --format=%s "$TARGET_RESOLVED"))"
  echo "  services to restart: ${AFFECTED:-<none>}"
  read -rp "Type 'rollback' to continue: " confirm
  [ "$confirm" = "rollback" ] || fail "confirmation not given"
fi

echo "ROLLBACK $CURRENT -> $TARGET_RESOLVED at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
git reset --hard "$TARGET_RESOLVED"

HEALTH_RESULTS=""
for svc in ${AFFECTED:-}; do
  echo "restarting ${svc}.service"
  sudo systemctl restart "${svc}.service"
  port="${PORTS[$svc]:-}"
  status="restarted(no-http)"
  if [ -n "$port" ]; then
    ok=""
    for i in $(seq 1 12); do   # wait up to ~60s for the service to answer
      if curl -sf -m 5 "http://127.0.0.1:${port}/health" >/dev/null 2>&1; then ok="yes"; break; fi
      sleep 5
    done
    if [ "$ok" = "yes" ]; then status="healthy"; else status="UNHEALTHY(http-failed)"; fi
  fi
  HEALTH_RESULTS+="${svc}=${status} "
  echo "  ${svc}: ${status}"
done

if $JSON; then
  mkdir -p "$RECEIPTS_DIR"
  stamp=$(date -u +%Y%m%dT%H%M%SZ)
  cat > "$RECEIPTS_DIR/rollback-${stamp}.json" <<EOF
{"rolled_back_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)", "from": "$CURRENT", "to": "$TARGET_RESOLVED", "restarted": "${AFFECTED:-}", "health": "$HEALTH_RESULTS"}
EOF
  echo "receipt: $RECEIPTS_DIR/rollback-${stamp}.json"
fi

echo "ROLLBACK DONE. $HEALTH_RESULTS"
echo "NOTE: main on GitHub still points at $CURRENT — fix forward with a revert,"
echo "or re-run the Fleet CD workflow after the fix, to bring the deployment forward again."
