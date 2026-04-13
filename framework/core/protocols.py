from __future__ import annotations

from typing import Any, Mapping, Protocol, runtime_checkable

StepContext = Mapping[str, Any]


@runtime_checkable
class StepContextProvider(Protocol):
    """为步骤记录提供补充上下文。"""

    def __call__(self) -> StepContext | None: ...


@runtime_checkable
class StepRecorder(Protocol):
    """步骤记录器最小契约。"""

    last_screenshot_path: str

    def next_step_name(self, name: str) -> str: ...

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
    ) -> dict[str, str | int]: ...
