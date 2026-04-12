#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REPORT_PATH="$ROOT_DIR/artifacts/reports/via_baidu_report.html"
REPORT_INDEX_PATH="$ROOT_DIR/artifacts/reports/index.html"
REPORT_LATEST_PATH="$ROOT_DIR/artifacts/reports/latest/index.html"
PYTEST_HTML_REPORT_PATH="$ROOT_DIR/artifacts/reports/via_baidu_pytest_html_report.html"
REPORT_DATA_DIR="$ROOT_DIR/artifacts/report_data"
ALLURE_RESULTS_DIR="$REPORT_DATA_DIR/allure-results"
PYTHON_BIN="/Volumes/SD Card/从入门到 recode/解释器/bin/python"

mkdir -p "$ROOT_DIR/artifacts/reports"
mkdir -p "$REPORT_DATA_DIR"
mkdir -p "$ALLURE_RESULTS_DIR"

if "$PYTHON_BIN" - <<'PY' >/dev/null 2>&1
import pytest_html
PY
then
  "$PYTHON_BIN" -m pytest \
    "$ROOT_DIR/tests/test_via_baidu_search.py" \
    -m "smoke and device" \
    --simple-html="$REPORT_PATH" \
    --html="$PYTEST_HTML_REPORT_PATH" \
    --self-contained-html \
    --alluredir="$ALLURE_RESULTS_DIR" \
    --clean-alluredir
else
  "$PYTHON_BIN" -m pytest \
    "$ROOT_DIR/tests/test_via_baidu_search.py" \
    -m "smoke and device" \
    --simple-html="$REPORT_PATH" \
    --alluredir="$ALLURE_RESULTS_DIR" \
    --clean-alluredir
fi

printf 'Report entry page: %s\n' "$REPORT_INDEX_PATH"
printf 'Latest structured report: %s\n' "$REPORT_LATEST_PATH"
printf 'Legacy report alias: %s\n' "$REPORT_PATH"
if [ -f "$PYTEST_HTML_REPORT_PATH" ]; then
  printf 'Pytest HTML report generated at: %s\n' "$PYTEST_HTML_REPORT_PATH"
fi
printf 'Allure results generated at: %s\n' "$ALLURE_RESULTS_DIR"
