#!/usr/bin/env bash
set -e

echo "Open example model"

cd "$(dirname "$0")/../.."
exec env PYTHONPATH=src python -m mbse_web_viewer.server.viewer_app tests/reference_model/project/reference_project.json --open-browser
