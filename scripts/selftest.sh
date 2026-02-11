#!/bin/bash
# Self-test wrapper script for open-webui-offline-mini MVP
# This script runs the Python selftest using the project venv when available.

set -e

cd "$(dirname "$0")/.."

echo "Running open-webui-offline-mini MVP selftest..."

PYTHON="python3"
if [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
fi

"$PYTHON" scripts/selftest.py "$@"
