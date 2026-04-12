#!/usr/bin/env bash

set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python}"
TMP_TEST_DIR="${TMPDIR:-/tmp}/generated-tests"
TMP_PROMPT_DIR="${TMPDIR:-/tmp}/generated-prompts"

echo "[1/7] 检查依赖完整性"
"${PYTHON_BIN}" -m pip check

if command -v actionlint >/dev/null 2>&1; then
  echo "[2/7] 校验 GitHub workflow"
  actionlint
else
  echo "[2/7] 跳过 GitHub workflow 校验：未安装 actionlint"
fi

echo "[3/7] 检查代码格式"
"${PYTHON_BIN}" -m ruff format --check framework tests scripts

echo "[4/7] 检查 lint 规则"
"${PYTHON_BIN}" -m ruff check framework tests scripts

echo "[5/7] 编译核心目录"
"${PYTHON_BIN}" -m compileall framework tests scripts docs

echo "[6/7] 验证文本生成用例链路"
rm -rf "${TMP_TEST_DIR}" "${TMP_PROMPT_DIR}"
"${PYTHON_BIN}" scripts/generate_cases_from_excel.py \
  examples/case_inputs/test_cases_template.csv \
  --output-dir "${TMP_TEST_DIR}" \
  --prompt-dir "${TMP_PROMPT_DIR}"
"${PYTHON_BIN}" -m compileall "${TMP_TEST_DIR}"
"${PYTHON_BIN}" -m pytest --collect-only -q -c pytest.ini \
  "${TMP_TEST_DIR}/test_search_via_baidu_search_chatgpt.py"

echo "[7/7] 运行非真机测试"
"${PYTHON_BIN}" -m pytest tests -m "not device" -q -W error

echo "PR 门禁本地检查通过。"
