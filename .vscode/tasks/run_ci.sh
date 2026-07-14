#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

PYTHON=".venv/bin/python"

if [ ! -x "$PYTHON" ]; then
  python -m venv .venv
fi

if ! command -v dot >/dev/null; then
  echo "Graphviz is required: install it and ensure 'dot' is on PATH."
  exit 1
fi

"$PYTHON" -m pip install -e ".[test]" build
"$PYTHON" -m ruff check .
"$PYTHON" -m pytest
"$PYTHON" -m build
