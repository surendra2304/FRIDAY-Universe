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
SERVER1_SERVICES=(FRIDAY Inference Memora Stratex Futuris IntelX Forge Stratex-Daemon)
SERVER2_SERVICES=(VyralX Sentinel Cortex VyralX-Daemon)
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

affected_for() {
  local -n svc_arr=$1
  local out=()
  for svc in "${svc_arr[@]}"; do
    if echo "$CHANGED_FOLDERS" | grep -qw "$svc" || echo "$CHANGED_FOLDERS" | grep -Eqw "mesh|deploy|scripts"; then
      systemctl list-unit-files 2>/dev/null | grep -qw "${svc}.service" && out+=("$svc")
    fi
  done
  echo "${out[@]:-}"
}

if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files 2>/dev/null | grep -qw "VyralX.service"; then
  FLEET_SERVICES=(SERVER2_SERVICES[@])
  AFFECTED=$(affected_for SERVER2_SERVICES)
else
  AFFECTED=$(affected_for SERVER1_SERVICES)
fi

if $DRY_RUN; then
  echo "DRY-RUN rollback $CURRENT -> $TARGET_RESOLVED"
  echo "would restart: ${AFFECTED:-<none>}"
  git diff --stat "$CURRENT" "$TARGET_RESOLVED" | tail -5
  exit 0
fi

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
