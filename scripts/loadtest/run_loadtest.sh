#!/usr/bin/env bash
set -euo pipefail

# Runs the k6 load test against an existing deployed API.
# Saves artifacts into loadtest_artifacts/.
#
# Usage:
#   ./scripts/loadtest/run_loadtest.sh https://your-domain.com
#
# Or:
#   BASE_URL=https://your-domain.com ./scripts/loadtest/run_loadtest.sh

ARTIFACT_DIR="${ARTIFACT_DIR:-loadtest_artifacts}"
BASE_URL="${1:-${BASE_URL:-}}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
LOADTEST_FILE="${SCRIPT_DIR}/loadtest.js"

mkdir -p "${PROJECT_ROOT}/${ARTIFACT_DIR}"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="${PROJECT_ROOT}/${ARTIFACT_DIR}/k6_run_${TIMESTAMP}.log"
SUMMARY_JSON="${PROJECT_ROOT}/${ARTIFACT_DIR}/k6_summary_${TIMESTAMP}.json"
INSTALL_NOTES="${PROJECT_ROOT}/${ARTIFACT_DIR}/k6_install_notes.txt"

if [[ -z "${BASE_URL}" ]]; then
  echo "ERROR: No base URL provided."
  echo ""
  echo "Provide it as either:"
  echo "  ./scripts/loadtest/run_loadtest.sh https://your-domain.com"
  echo "or:"
  echo "  BASE_URL=https://your-domain.com ./scripts/loadtest/run_loadtest.sh"
  exit 1
fi

cat > "${INSTALL_NOTES}" <<'EOF'
k6 installation notes (no Docker)

Debian / Ubuntu:
  sudo apt-get update
  sudo apt-get install -y gnupg ca-certificates
  curl -fsSL https://dl.k6.io/key.gpg | sudo gpg --dearmor -o /usr/share/keyrings/k6-archive-keyring.gpg
  echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | \
    sudo tee /etc/apt/sources.list.d/k6.list >/dev/null
  sudo apt-get update
  sudo apt-get install -y k6

Verify install:
  k6 version
EOF

echo "Saved k6 install notes to: ${INSTALL_NOTES}"

if ! command -v k6 >/dev/null 2>&1; then
  echo "ERROR: k6 is not installed or not in PATH."
  echo "See install notes in: ${INSTALL_NOTES}"
  exit 1
fi

if [[ ! -f "${LOADTEST_FILE}" ]]; then
  echo "ERROR: load test script not found at ${LOADTEST_FILE}"
  exit 1
fi

echo "Starting load test..."
echo "Base URL: ${BASE_URL}"
echo "Artifacts dir: ${PROJECT_ROOT}/${ARTIFACT_DIR}"
echo "Log file: ${LOG_FILE}"
echo "Summary JSON: ${SUMMARY_JSON}"
echo ""

BASE_URL="${BASE_URL}" \
k6 run \
  --summary-export "${SUMMARY_JSON}" \
  "${LOADTEST_FILE}" 2>&1 | tee "${LOG_FILE}"

echo ""
echo "Load test complete."
echo "Artifacts saved:"
echo "  ${LOG_FILE}"
echo "  ${SUMMARY_JSON}"