#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${1:-.}"

echo "[check] docker build"
docker build -t openenv-datapipeline "$REPO_DIR"

echo "[check] openenv validate"
openenv validate

echo "[pass] local prevalidation complete"
