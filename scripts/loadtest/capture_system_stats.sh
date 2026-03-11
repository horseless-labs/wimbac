#!/usr/bin/env bash
set -euo pipefail

# Captures periodic system snapshots during a load test.
# Appends data every 10 seconds to loadtest_artifacts/system_stats.log
#
# Usage:
#   ./scripts/loadtest/capture_system_stats.sh
#
# Stop with Ctrl+C.

ARTIFACT_DIR="${ARTIFACT_DIR:-loadtest_artifacts}"
INTERVAL_SECONDS="${INTERVAL_SECONDS:-10}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
OUT_DIR="${PROJECT_ROOT}/${ARTIFACT_DIR}"
OUT_FILE="${OUT_DIR}/system_stats.log"

mkdir -p "${OUT_DIR}"

echo "Writing system snapshots to ${OUT_FILE}"
echo "Sampling interval: ${INTERVAL_SECONDS}s"
echo "Press Ctrl+C to stop."
echo ""

cleanup() {
  echo "" | tee -a "${OUT_FILE}"
  echo "[$(date -Is)] capture_system_stats stopped" | tee -a "${OUT_FILE}"
  exit 0
}

trap cleanup INT TERM

echo "[$(date -Is)] capture_system_stats started" | tee -a "${OUT_FILE}"

while true; do
  {
    echo "============================================================"
    echo "TIMESTAMP: $(date -Is)"
    echo ""

    echo "[UPTIME]"
    uptime
    echo ""

    echo "[MEMORY USAGE]"
    free -h
    echo ""

    echo "[TOP CPU PROCESSES]"
    ps -eo pid,ppid,cmd,%mem,%cpu --sort=-%cpu | head -n 15
    echo ""

    echo "[GUNICORN PROCESSES]"
    pgrep -a gunicorn || echo "No gunicorn processes found"
    echo ""

    echo "[INFLUXDB PROCESS]"
    pgrep -a influxd || pgrep -a influxdb || echo "No InfluxDB process found"
    echo ""

    echo "[SOCKET INFO FOR PORTS 8000, 80, 443]"
    if command -v ss >/dev/null 2>&1; then
      ss -ltnp | awk 'NR==1 || /:8000 |:80 |:443 / || /:8000$|:80$|:443$/'
    else
      echo "ss command not found"
    fi
    echo ""

    echo "[LOAD AVERAGE / VMSTAT]"
    if command -v vmstat >/dev/null 2>&1; then
      vmstat 1 3
    else
      echo "vmstat command not found"
    fi
    echo ""

    echo "[DISK USAGE]"
    df -h
    echo ""
  } >> "${OUT_FILE}" 2>&1

  sleep "${INTERVAL_SECONDS}"
done