#!/usr/bin/env bash
# TASK-FRD-005 — run one voice acceptance pass against production FRIDAY.
#
# Runs ON Server 1 (it uses the loopback token endpoint and the
# FRIDAY-Voice journal). The harness files may live in the repo
# checkout (/opt/friday_universe/FRIDAY/voice_acceptance) or be staged
# in /tmp/frd005/harness — set HARNESS_HOME accordingly. All run
# artefacts land in /tmp/frd005/runs/<run-id>/ and are never written
# into the repo tree.
#
#   HARNESS_HOME=/tmp/frd005/harness bash run_acceptance.sh
#
# Exit code is the scorer's: 0 PASS, 1 FAIL, 3 UNVERIFIED,
# 2 infrastructure failure (participant could not complete the call).
set -u
HARNESS_HOME="${HARNESS_HOME:-$(cd "$(dirname "$0")" && pwd)}"
WORK_DIR="${WORK_DIR:-/tmp/frd005}"
VENV_PY="${VENV_PY:-/opt/friday_universe/venv/bin/python}"
RUN_ID="$(date +%Y%m%d-%H%M%S)"
ROOM="friday-frd005-${RUN_ID}"
RUN_DIR="${WORK_DIR}/runs/${RUN_ID}"
mkdir -p "${RUN_DIR}" "${WORK_DIR}/utterances"

echo "== TASK-FRD-005 voice acceptance run ${RUN_ID} =="
echo "room: ${ROOM}"
echo "host context: $(date '+%Y-%m-%d %H:%M:%S %Z') | $(uptime)"
systemctl is-active FRIDAY-Voice || { echo "FATAL: FRIDAY-Voice not active"; exit 2; }
"${VENV_PY}" -c "import livekit, httpx, edge_tts" \
  || { echo "FATAL: fleet venv lacks livekit/httpx/edge_tts"; exit 2; }
"${VENV_PY}" -c "import av" 2>/dev/null || command -v ffmpeg >/dev/null \
  || { echo "FATAL: need PyAV or an ffmpeg binary for mp3 decoding"; exit 2; }

echo "-- utterances --"
"${VENV_PY}" "${HARNESS_HOME}/make_utterances.py" \
  --battery "${HARNESS_HOME}/battery.json" \
  --out-dir "${WORK_DIR}/utterances" || exit 2
cp "${WORK_DIR}/utterances/utterances_manifest.json" "${RUN_DIR}/" 2>/dev/null || true

START_HUMAN="$(date '+%Y-%m-%d %H:%M:%S')"
echo "-- call (start ${START_HUMAN}) --"
"${VENV_PY}" "${HARNESS_HOME}/participant.py" \
  --room "${ROOM}" \
  --battery "${HARNESS_HOME}/battery.json" \
  --utter-dir "${WORK_DIR}/utterances" \
  --out-dir "${RUN_DIR}"
PART_RC=$?
if [ "${PART_RC}" -ne 0 ]; then
  echo "participant failed with rc=${PART_RC}; no scoring attempted"
  exit 2
fi
sleep 3  # let the worker flush its final journal lines + status file

echo "-- evidence --"
journalctl -u FRIDAY-Voice.service --since "${START_HUMAN}" -o cat --no-pager \
  > "${RUN_DIR}/journal.txt" 2>/dev/null
cp /opt/friday_universe/FRIDAY/data/voice_worker_status.json \
  "${RUN_DIR}/status.json" 2>/dev/null || echo "status file missing"

"${VENV_PY}" "${HARNESS_HOME}/score.py" \
  --timeline "${RUN_DIR}/${ROOM}_timeline.json" \
  --journal "${RUN_DIR}/journal.txt" \
  --status "${RUN_DIR}/status.json" \
  --battery "${HARNESS_HOME}/battery.json" \
  --out-json "${RUN_DIR}/results.json" \
  --out-md "${RUN_DIR}/results.md"
SCORE_RC=$?
echo "-- results (${RUN_DIR}/results.md) --"
cat "${RUN_DIR}/results.md"
exit "${SCORE_RC}"
