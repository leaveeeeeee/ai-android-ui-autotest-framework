from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from framework.core.protocols import StepContextProvider, StepRecorder
from framework.core.steps import StepSpec
from framework.reporting.image_tools import annotate_click_region, create_diff_image

if TYPE_CHECKING:
    from framework.core.artifact_manager import ArtifactManager


@dataclass
class StepCaptureResult:
    """单步采集结果。"""

    focus_window: str = ""
    previous_screenshot_path: str = ""
    screenshot_path: str = ""
    diff_path: str = ""
    source_path: str = ""


class StepCaptureService:
    """为 `record_step()` 收集上下文、截图和差异图。"""

    def __init__(self, artifact_manager: "ArtifactManager") -> None:
        self.artifact_manager = artifact_manager
        self.context_provider: StepContextProvider | None = None

    def set_context_provider(self, provider: StepContextProvider | None) -> None:
        """更新步骤上下文提供器。"""

        self.context_provider = provider

    def collect(
        self,
        *,
        recorder: StepRecorder,
        spec: StepSpec,
        screenshotter,
        page_source_provider,
    ) -> StepCaptureResult:
        """采集步骤上下文，并按需生成截图和差异图。"""

        result = StepCaptureResult(previous_screenshot_path=recorder.last_screenshot_path)
        if self.context_provider is not None:
            try:
                context = self.context_provider() or {}
                result.focus_window = str(context.get("focus_window", "") or "")
            except Exception:
                result.focus_window = ""

        if not spec.capture:
            return result

        step_file_name = recorder.next_step_name(spec.name)
        screenshot_path, source_path = self.artifact_manager.capture_state(
            name=step_file_name,
            screenshotter=screenshotter,
            page_source_provider=page_source_provider,
        )
        result.screenshot_path = screenshot_path
        result.source_path = source_path

        if spec.highlight_rect is not None:
            annotate_click_region(screenshot_path, spec.highlight_rect)
        if result.previous_screenshot_path:
            diff_path = Path(screenshot_path).with_name(f"{Path(screenshot_path).stem}_diff.png")
            create_diff_image(result.previous_screenshot_path, screenshot_path, str(diff_path))
            result.diff_path = str(diff_path)
        return result
