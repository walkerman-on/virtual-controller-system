#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="$ROOT_DIR/load-test/results"
mkdir -p "$OUT_DIR"

COMPOSE_CMD=(docker compose -f docker-compose.yml -f docker-compose.loadtest.yml)

run_test() {
  local name="$1"
  local controllers="$2"
  local cycle_ms="$3"
  local duration_sec="$4"

  local ts
  ts="$(date +%Y%m%d_%H%M%S)"
  local report_file="/app/results/${name}_${ts}.json"
  local log_file="$OUT_DIR/${name}_${ts}.log"

  echo "=== ${name} ==="
  echo "controllers=${controllers} cycle_ms=${cycle_ms} duration_sec=${duration_sec} FULL_PID_CYCLE=true"
  docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" \
    opcua-server digital-twin-db analytics-service pid-controller-primary pid-controller-backup \
    | tee -a "$log_file" || true

  "${COMPOSE_CMD[@]}" run --rm \
    -e CONTROLLERS="${controllers}" \
    -e CYCLE_MS="${cycle_ms}" \
    -e DURATION_SEC="${duration_sec}" \
    -e WRITE_ENABLED="false" \
    -e FULL_PID_CYCLE="true" \
    -e RESULT_FILE="${report_file}" \
    load-generator | tee -a "$log_file"

  docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" \
    opcua-server digital-twin-db analytics-service pid-controller-primary pid-controller-backup \
    | tee -a "$log_file" || true
  echo
}

echo ">>> Ensure base system is running: docker compose up -d"
docker compose up -d

echo ">>> Build load-generator (подхватывает изменения load-test/)"
"${COMPOSE_CMD[@]}" build load-generator

run_test "baseline" 10 1000 180
run_test "workload" 30 500 300
run_test "spike" 50 200 180
python3 "$ROOT_DIR/load-test/generate_report.py"
echo "Reports: $OUT_DIR"
echo "Readable report: $OUT_DIR/LOAD_TEST_REPORT.md"
