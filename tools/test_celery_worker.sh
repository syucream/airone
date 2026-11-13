#!/usr/bin/env bash
# Run fault tests against disposable, invocation-local MySQL and RabbitMQ.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
REPO_ROOT="$PWD"
if [ "$#" -gt 1 ]; then
    echo "Usage: tools/test_celery_worker.sh [TestClass[.test_method]]" >&2
    exit 2
fi
PY=(python3)
mkdir -p "$REPO_ROOT/.artifacts/celery-worker"
RUN_DIR=$(mktemp -d "$REPO_ROOT/.artifacts/celery-worker/run-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXX")
PROJECT="pagoda-worker-$(basename "$RUN_DIR" | tr '[:upper:]' '[:lower:]')"
COMPOSE_FILE="$REPO_ROOT/tools/celery_worker/compose.yml"
if [ -n "${PAGODA_WORKER_SUBNET:-}" ]; then
    # Reject YAML metacharacters; Docker validates the actual CIDR and overlap.
    if ! [[ "$PAGODA_WORKER_SUBNET" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+/[0-9]+$ ]]; then
        echo "PAGODA_WORKER_SUBNET must be an IPv4 CIDR" >&2
        exit 2
    fi
    SUBNET_COMPOSE="$RUN_DIR/compose-with-subnet.yml"
    cat "$COMPOSE_FILE" >"$SUBNET_COMPOSE"
    printf '\nnetworks:\n  default:\n    ipam:\n      config:\n        - subnet: %s\n' "$PAGODA_WORKER_SUBNET" >>"$SUBNET_COMPOSE"
    COMPOSE_FILE="$SUBNET_COMPOSE"
fi
COMPOSE=(docker compose --profile tests --env-file /dev/null -p "$PROJECT" -f "$COMPOSE_FILE")
# Do not let a caller's database, broker, or eager-mode settings reach the tests.
while IFS= read -r variable; do
    case "$variable" in
        AIRONE_*|CELERY_*|DJANGO_*|DD_*|ENABLED_PLUGINS) unset "$variable" ;;
    esac
done < <(compgen -e)
export DJANGO_SETTINGS_MODULE=tools.celery_worker.settings
export DJANGO_CONFIGURATION=WorkerTest
export ENABLED_PLUGINS='' DD_TRACE_ENABLED=false
export PAGODA_WORKER_TEST=1 PAGODA_LITE=0 AIRONE_CELERY_EAGER=0
export PAGODA_WORKER_TEST_DIR="$RUN_DIR"
export PAGODA_WORKER_SOURCE_DIR="$REPO_ROOT"
export PAGODA_WORKER_COMPOSE_PROJECT="$PROJECT"
export PAGODA_WORKER_COMPOSE_FILE="$COMPOSE_FILE"

# Allow the harness to clean up workers that run in their own process sessions.
bounded() {
    "${PY[@]}" "$REPO_ROOT/tools/celery_worker/timeout.py" "$@"
}

cleanup() {
    local result="$?"
    trap - EXIT INT TERM
    set +e
    bounded 30 "${COMPOSE[@]}" logs --no-color >"$RUN_DIR/services.log" 2>&1
    bounded 45 "${COMPOSE[@]}" down --volumes --remove-orphans --timeout 10 >>"$RUN_DIR/setup.log" 2>&1
    local cleanup_result="$?"
    if [ "$result" -eq 0 ] && [ "$cleanup_result" -ne 0 ]; then
        result="$cleanup_result"
    fi
    printf '{"exit_code": %s, "cleanup_exit_code": %s}\n' "$result" "$cleanup_result" >"$RUN_DIR/launcher-result.json"
    echo "Worker test artifacts: $RUN_DIR"
    exit "$result"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

echo "Worker test artifacts: $RUN_DIR"
echo "Starting disposable services ($PROJECT)"
bounded 360 "${COMPOSE[@]}" up -d --wait --wait-timeout 180 mysql rabbitmq 2>&1 | tee "$RUN_DIR/setup.log"
echo "Building the Linux worker test image"
bounded 900 "${COMPOSE[@]}" build runner 2>&1 | tee "$RUN_DIR/build.log"
TARGET=tools.celery_worker.test_worker
if [ -n "${1:-}" ]; then
    case "$1" in
        tools.celery_worker.test_worker*) TARGET="$1" ;;
        *) TARGET="$TARGET.$1" ;;
    esac
fi
bounded 900 "${PY[@]}" "$REPO_ROOT/tools/celery_worker/control.py" "$TARGET" 2>&1 | tee "$RUN_DIR/tests.log"
