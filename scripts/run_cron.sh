#!/usr/bin/env bash
# ==============================================================================
# Linux / macOS Cron Runner for LinkedIn Daily Bot
# ==============================================================================

set -euo pipefail

# Get script parent directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_DIR}"

# Locate Python in venv or fallback to system python
if [ -f "${PROJECT_DIR}/venv/bin/python" ]; then
    PYTHON_BIN="${PROJECT_DIR}/venv/bin/python"
else
    PYTHON_BIN="$(which python3 || which python)"
fi

echo "=========================================================="
echo "Running LinkedIn Daily Bot via cron: $(date)"
echo "Directory: ${PROJECT_DIR}"
echo "Python:    ${PYTHON_BIN}"
echo "=========================================================="

# Run main pipeline and append output to cron.log
"${PYTHON_BIN}" main.py >> "${PROJECT_DIR}/cron.log" 2>&1
