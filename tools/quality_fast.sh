#!/bin/bash

set -euo pipefail

BASE_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "${BASE_DIR}"

if [[ ! -x .venv/bin/pre-commit ]]; then
  echo "The development environment is not ready: run 'uv sync --extra dev --extra plugins'."
  exit 2
fi

QUALITY_FILES=()
while IFS= read -r -d '' file; do
  QUALITY_FILES+=("${file}")
done < <(git ls-files --cached --others --exclude-standard -z)

if [[ ${#QUALITY_FILES[@]} -eq 0 ]]; then
  exit 0
fi

exec .venv/bin/pre-commit run \
  --hook-stage pre-commit \
  --files "${QUALITY_FILES[@]}"
