#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEFAULT_PYTHON=""

has_required_modules() {
  local candidate="$1"
  "${candidate}" -c "import pre_commit, pytest" >/dev/null 2>&1
}

if [[ -x "${PROJECT_ROOT}/.venv/bin/python" ]] && has_required_modules "${PROJECT_ROOT}/.venv/bin/python"; then
  DEFAULT_PYTHON="${PROJECT_ROOT}/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1 && has_required_modules "$(command -v python3)"; then
  DEFAULT_PYTHON="$(command -v python3)"
else
  DEFAULT_PYTHON="python"
fi

PYTHON_BIN="${PYTHON_BIN:-${DEFAULT_PYTHON}}"
TMP_TEST_DIR="${TMPDIR:-/tmp}/generated-tests"
TMP_PROMPT_DIR="${TMPDIR:-/tmp}/generated-prompts"
PRE_COMMIT_HOME="${PRE_COMMIT_HOME:-${TMPDIR:-/tmp}/pre-commit-cache}"

export PRE_COMMIT_HOME

echo "[1/8] 检查依赖完整性"
"${PYTHON_BIN}" -m pip check

if command -v actionlint >/dev/null 2>&1; then
  echo "[2/8] 校验 GitHub workflow"
  actionlint
else
  echo "[2/8] 跳过 GitHub workflow 校验：未安装 actionlint"
fi

echo "[3/8] 校验 pre-commit 配置"
"${PYTHON_BIN}" -m pre_commit validate-config

echo "[4/8] 执行 pre-commit 全量检查"
"${PYTHON_BIN}" -m pre_commit run --all-files --show-diff-on-failure

echo "[5/8] 编译核心目录"
"${PYTHON_BIN}" -m compileall framework tests scripts docs

echo "[6/8] 验证文本生成用例链路"
rm -rf "${TMP_TEST_DIR}" "${TMP_PROMPT_DIR}"
"${PYTHON_BIN}" scripts/generate_cases_from_excel.py \
  examples/case_inputs/test_cases_template.csv \
  --output-dir "${TMP_TEST_DIR}" \
  --prompt-dir "${TMP_PROMPT_DIR}"
"${PYTHON_BIN}" -m compileall "${TMP_TEST_DIR}"
"${PYTHON_BIN}" -m pytest --collect-only -q -c pyproject.toml \
  "${TMP_TEST_DIR}/test_search_via_baidu_search_chatgpt.py"

echo "[7/8] 运行非真机测试"
"${PYTHON_BIN}" -m pytest tests -m "not device" -q -W error

echo "[8/8] 校验最新提交标题格式"
"${PYTHON_BIN}" scripts/check_commit_message.py --message "$(git log -1 --pretty=%s)"

echo "PR 门禁本地检查通过。"
