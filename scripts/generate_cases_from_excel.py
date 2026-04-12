from __future__ import annotations
"""从结构化文本生成 pytest 用例与 AI 提示词。"""

import argparse
import csv
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from framework.generator.models import TextCaseSpec
from framework.generator.renderer import render_ai_prompt, render_test_case


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="根据 Excel 或 CSV 测试文本生成 pytest 用例。")
    parser.add_argument("input_file", help="输入文件路径，支持 .xlsx 和 .csv。")
    parser.add_argument(
        "--output-dir",
        default="tests/generated",
        help="生成的 pytest 文件输出目录。",
    )
    parser.add_argument(
        "--prompt-dir",
        default="artifacts/report_data/ai-prompts",
        help="当用例信息不完整时，AI 提示词输出目录。",
    )
    return parser.parse_args()


def load_rows(input_path: Path) -> list[dict[str, str]]:
    """读取 CSV 或 XLSX 中的测试文本。"""
    if input_path.suffix.lower() == ".csv":
        with input_path.open("r", encoding="utf-8-sig", newline="") as file:
            return list(csv.DictReader(file))

    if input_path.suffix.lower() == ".xlsx":
        try:
            from openpyxl import load_workbook
        except ImportError as exc:  # pragma: no cover - 运行环境可能未安装 openpyxl
            raise SystemExit(
                "读取 .xlsx 需要 openpyxl，请先安装项目依赖。"
            ) from exc

        workbook = load_workbook(input_path)
        sheet = workbook.active
        rows = list(sheet.iter_rows(values_only=True))
        if not rows:
            return []
        headers = [str(cell or "").strip() for cell in rows[0]]
        return [
            {
                headers[index]: "" if value is None else str(value)
                for index, value in enumerate(row)
                if index < len(headers) and headers[index]
            }
            for row in rows[1:]
        ]

    raise SystemExit("目前只支持 .xlsx 和 .csv 两种输入格式。")


def main() -> int:
    """执行文本转用例主流程。"""
    args = parse_args()
    input_path = Path(args.input_file)
    output_dir = Path(args.output_dir)
    prompt_dir = Path(args.prompt_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    prompt_dir.mkdir(parents=True, exist_ok=True)

    rows = load_rows(input_path)
    generated = 0
    prompts = 0
    for row in rows:
        spec = TextCaseSpec.from_mapping(row)
        target_file = output_dir / spec.file_name
        target_file.write_text(render_test_case(spec), encoding="utf-8")
        generated += 1

        if not spec.has_executable_calls:
            prompt_file = prompt_dir / f"{spec.case_id}.md"
            prompt_file.write_text(render_ai_prompt(spec), encoding="utf-8")
            prompts += 1

    print(f"已生成 pytest 文件数：{generated}")
    print(f"已生成 AI 提示词数：{prompts}")
    print(f"用例输出目录：{output_dir.resolve()}")
    print(f"提示词输出目录：{prompt_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
