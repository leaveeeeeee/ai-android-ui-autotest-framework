#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "[1/2] 安装开发依赖"
"${PYTHON_BIN}" -m pip install .[dev]

echo "[2/2] 安装 git hooks"
"${PYTHON_BIN}" -m pre_commit install --hook-type pre-commit --hook-type commit-msg --hook-type pre-push

echo "git hooks 安装完成。"
echo "如果你有固定解释器，建议这样执行："
echo "PYTHON_BIN=\"/你的/python\" ${PROJECT_ROOT}/scripts/install_git_hooks.sh"
