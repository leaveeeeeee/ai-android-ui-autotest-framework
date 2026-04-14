from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from framework.core.bounds import Bounds

StepEmitter = Callable[["StepSpec"], None]
_UNSET = object()


@dataclass
class StepSpec:
    """步骤记录输入模型。"""

    name: str
    detail: str = ""
    expected: str = ""
    actual: str = ""
    comparison: str = "PASS"
    status: str = "PASSED"
    logs: str = ""
    highlight_rect: Bounds | None = None
    capture: bool = True


class StepContext:
    """页面层步骤上下文。"""

    def __init__(self, *, spec: StepSpec, emitter: StepEmitter) -> None:
        self.spec = spec
        self._emitter = emitter

    def __enter__(self) -> "StepContext":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001
        if exc is not None:
            message = str(exc).strip()
            if not message:
                message = exc_type.__name__ if exc_type is not None else repr(exc)
            self.spec.status = "FAILED"
            self.spec.comparison = "FAIL"
            if not self.spec.actual:
                self.spec.actual = message
            if not self.spec.logs:
                self.spec.logs = message
            elif message and message not in self.spec.logs:
                self.spec.logs = f"{self.spec.logs}\n{message}"

        self._emitter(self.spec)
        return False

    def update(
        self,
        *,
        detail: str | object = _UNSET,
        expected: str | object = _UNSET,
        actual: str | object = _UNSET,
        comparison: str | object = _UNSET,
        status: str | object = _UNSET,
        logs: str | object = _UNSET,
        highlight_rect: Bounds | None | object = _UNSET,
        capture: bool | object = _UNSET,
    ) -> "StepContext":
        """在步骤执行过程中补充动态字段。"""

        updates = {
            "detail": detail,
            "expected": expected,
            "actual": actual,
            "comparison": comparison,
            "status": status,
            "logs": logs,
            "highlight_rect": highlight_rect,
            "capture": capture,
        }
        for field_name, value in updates.items():
            if value is not _UNSET:
                setattr(self.spec, field_name, value)
        return self
