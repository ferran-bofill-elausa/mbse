#!/usr/bin/env bash
set -e

echo "Open example model"

cd "$(dirname "$0")/../.."
exec env PYTHONPATH=src python -m mbse_web_viewer.server.hsm.hsm_server tests/reference_model/hsm/reference_hsm_model.json --open-browser
