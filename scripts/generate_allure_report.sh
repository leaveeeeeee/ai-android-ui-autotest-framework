#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RESULTS_DIR="$ROOT_DIR/artifacts/report_data/allure-results"
REPORT_DIR="$ROOT_DIR/artifacts/report_data/allure-report"

if ! command -v allure >/dev/null 2>&1; then
  printf 'Allure CLI not found. Results are available at: %s\n' "$RESULTS_DIR"
  exit 0
fi

allure generate "$RESULTS_DIR" -o "$REPORT_DIR" --clean
printf 'Allure HTML report generated at: %s\n' "$REPORT_DIR"
