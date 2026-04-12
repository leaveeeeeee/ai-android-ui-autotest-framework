"""校验提交信息是否符合约定格式。"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

CONVENTIONAL_COMMIT_PATTERN = re.compile(
    r"^(build|chore|ci|docs|feat|fix|perf|refactor|revert|style|test)"
    r"(\([a-z0-9][a-z0-9._/-]*\))?!?: .+$"
)
MAX_SUBJECT_LENGTH = 72


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="校验提交信息或 PR 标题格式。")
    parser.add_argument(
        "message_file",
        nargs="?",
        help="git commit-msg hook 传入的提交信息文件路径。",
    )
    parser.add_argument(
        "--message",
        help="直接校验一段提交标题，常用于 CI 校验 PR 标题。",
    )
    return parser.parse_args()


def load_message(args: argparse.Namespace) -> tuple[str, bool]:
    """读取待校验内容，并返回是否需要校验正文空行。"""
    if args.message:
        return args.message.strip(), False

    if not args.message_file:
        raise SystemExit("请提供提交信息文件路径，或通过 --message 直接传入标题。")

    content = Path(args.message_file).read_text(encoding="utf-8").strip("\n")
    return content, True


def validate_message(message: str, require_blank_line: bool) -> list[str]:
    """返回所有校验失败原因。"""
    lines = message.splitlines()
    subject = lines[0].strip() if lines else ""
    errors: list[str] = []

    if not subject:
        errors.append("提交标题不能为空。")
        return errors

    if len(subject) > MAX_SUBJECT_LENGTH:
        errors.append(f"提交标题长度不能超过 {MAX_SUBJECT_LENGTH} 个字符。")

    if not CONVENTIONAL_COMMIT_PATTERN.match(subject):
        errors.append(
            "提交标题需符合 Conventional Commits，例如：`feat(report): add allure trend page`。"
        )

    if require_blank_line and len(lines) > 1 and lines[1].strip():
        errors.append("提交标题与正文之间需要空一行。")

    return errors


def main() -> int:
    """程序入口。"""
    args = parse_args()
    message, require_blank_line = load_message(args)
    errors = validate_message(message, require_blank_line=require_blank_line)
    if not errors:
        print("提交信息格式校验通过。")
        return 0

    print("提交信息格式不符合要求：", file=sys.stderr)
    for error in errors:
        print(f"- {error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
