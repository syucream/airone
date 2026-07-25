#!/bin/bash
#
# Reproducible cross-stack quality gate for local development and CI.
# Fast per-file checks belong in pre-commit; this script intentionally checks
# repository-wide contracts before a push or review.

set -euo pipefail

BASE_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "${BASE_DIR}"

run() {
  echo
  echo ">>> $*"
  "$@"
}

run uv lock --check
run uv run ruff check .
run uv run ruff format --check .
run uv run mypy .
run uv run lint-imports

echo
echo ">>> OpenAPI schema (zero warnings)"
DJANGO_CONFIGURATION=DRFSpectacularExcludeCustomView \
  uv run python manage.py spectacular --fail-on-warn >/dev/null

run npm run lint
run npm run test -- --runInBand
run npm run quality:bundle
