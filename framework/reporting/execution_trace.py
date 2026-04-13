from __future__ import annotations

import re
from dataclasses import asdict, dataclass


def _slugify(value: str) -> str:
    """把名称转换成适合做文件名的安全字符串。"""
    normalized = re.sub(r"[^a-zA-Z0-9_]+", "_", value.strip()).strip("_").lower()
    return normalized or "step"


@dataclass
class ExecutionStep:
    """单个执行步骤的数据结构。"""

    index: int
    name: str
    status: str
    detail: str
    expected: str
    actual: str
    comparison: str
    logs: str = ""
    focus_window: str = ""
    screenshot_path: str = ""
    previous_screenshot_path: str = ""
    diff_path: str = ""
    source_path: str = ""
    duration_ms: int = 0

    def as_dict(self) -> dict[str, str | int]:
        """转换成可写入报告的数据字典。"""
        return asdict(self)


class ExecutionTraceRecorder:
    """步骤记录器。

    用途：
    - 为当前测试用例维护步骤列表
    - 生成统一命名的步骤文件名
    - 记录最近一张截图，便于生成前后差异图
    """

    def __init__(self, case_name: str, run_id: str = "") -> None:
        self.run_id = _slugify(run_id)
        self.case_name = _slugify(case_name)
        self.steps: list[dict[str, str | int]] = []
        self.last_screenshot_path: str = ""

    def next_step_name(self, name: str) -> str:
        """生成下一步对应的文件名前缀。"""
        index = len(self.steps) + 1
        parts = [self.run_id, self.case_name, f"{index:02d}", _slugify(name)]
        return "_".join(part for part in parts if part)

    def add_step(
        self,
        *,
        name: str,
        status: str = "PASSED",
        detail: str = "",
        expected: str = "",
        actual: str = "",
        comparison: str = "",
        logs: str = "",
        focus_window: str = "",
        screenshot_path: str = "",
        previous_screenshot_path: str = "",
        diff_path: str = "",
        source_path: str = "",
        duration_ms: int = 0,
    ) -> dict[str, str | int]:
        """追加一步执行记录。"""
        step = ExecutionStep(
            index=len(self.steps) + 1,
            name=name,
            status=status,
            detail=detail,
            expected=expected,
            actual=actual,
            comparison=comparison,
            logs=logs,
            focus_window=focus_window,
            screenshot_path=screenshot_path,
            previous_screenshot_path=previous_screenshot_path,
            diff_path=diff_path,
            source_path=source_path,
            duration_ms=duration_ms,
        ).as_dict()
        self.steps.append(step)
        if screenshot_path:
            self.last_screenshot_path = screenshot_path
        return step
