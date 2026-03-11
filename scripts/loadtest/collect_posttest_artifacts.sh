#!/usr/bin/env bash
set -euo pipefail

# Collects service status and recent logs after a load test.
# Saves artifacts into loadtest_artifacts/.
#
# Intended services:
#   - wimbac
#   - nginx
#   - influxdb
#
# Usage:
#   ./scripts/loadtest/collect_posttest_artifacts.sh
#
# Optional:
#   LOG_WINDOW_MINUTES=30 ./scripts/loadtest/collect_posttest_artifacts.sh

ARTIFACT_DIR="${ARTIFACT_DIR:-loadtest_artifacts}"
LOG_WINDOW_MINUTES="${LOG_WINDOW_MINUTES:-30}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
OUT_DIR="${PROJECT_ROOT}/${ARTIFACT_DIR}"

mkdir -p "${OUT_DIR}"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
SINCE_ARG="${LOG_WINDOW_MINUTES} minutes ago"

STATUS_WIMBAC="${OUT_DIR}/systemctl_wimbac_${TIMESTAMP}.txt"
STATUS_NGINX="${OUT_DIR}/systemctl_nginx_${TIMESTAMP}.txt"
STATUS_INFLUX="${OUT_DIR}/systemctl_influxdb_${TIMESTAMP}.txt"

JOURNAL_WIMBAC="${OUT_DIR}/journal_wimbac_${TIMESTAMP}.log"
JOURNAL_NGINX="${OUT_DIR}/journal_nginx_${TIMESTAMP}.log"
JOURNAL_INFLUX="${OUT_DIR}/journal_influxdb_${TIMESTAMP}.log"

echo "Collecting post-test artifacts into ${OUT_DIR}"
echo "Journal window: last ${LOG_WINDOW_MINUTES} minutes"
echo ""

sudo systemctl status wimbac --no-pager > "${STATUS_WIMBAC}" 2>&1 || true
sudo systemctl status nginx --no-pager > "${STATUS_NGINX}" 2>&1 || true
sudo systemctl status influxdb --no-pager > "${STATUS_INFLUX}" 2>&1 || true

sudo journalctl -u wimbac --since "${SINCE_ARG}" --no-pager > "${JOURNAL_WIMBAC}" 2>&1 || true
sudo journalctl -u nginx --since "${SINCE_ARG}" --no-pager > "${JOURNAL_NGINX}" 2>&1 || true
sudo journalctl -u influxdb --since "${SINCE_ARG}" --no-pager > "${JOURNAL_INFLUX}" 2>&1 || true

echo "Saved:"
echo "  ${STATUS_WIMBAC}"
echo "  ${STATUS_NGINX}"
echo "  ${STATUS_INFLUX}"
echo "  ${JOURNAL_WIMBAC}"
echo "  ${JOURNAL_NGINX}"
echo "  ${JOURNAL_INFLUX}"