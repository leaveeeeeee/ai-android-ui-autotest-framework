from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping

from framework.core.defaults import default_value
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

    def __init__(
        self,
        artifact_manager: "ArtifactManager",
        *,
        reporting_config: Mapping[str, Any] | None = None,
    ) -> None:
        self.artifact_manager = artifact_manager
        self.reporting_config = reporting_config or {}
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

        if not self._should_capture(spec):
            return result

        step_file_name = recorder.next_step_name(spec.name)
        screenshot_path, source_path = self.artifact_manager.capture_state(
            name=step_file_name,
            screenshotter=screenshotter,
            page_source_provider=page_source_provider,
            include_page_source=self._should_capture_page_source(spec),
        )
        result.screenshot_path = screenshot_path
        result.source_path = source_path

        if spec.highlight_rect is not None:
            annotate_click_region(screenshot_path, spec.highlight_rect)
        if result.previous_screenshot_path and self._should_capture_diff(spec):
            diff_path = Path(screenshot_path).with_name(f"{Path(screenshot_path).stem}_diff.png")
            create_diff_image(result.previous_screenshot_path, screenshot_path, str(diff_path))
            result.diff_path = str(diff_path)
        return result

    def _setting(self, key: str) -> Any:
        return self.reporting_config.get(key, default_value(f"reporting.{key}"))

    def _should_capture(self, spec: StepSpec) -> bool:
        policy = str(self._setting("capture_policy")).lower()
        failed = spec.status.upper() == "FAILED" or spec.comparison.upper() == "FAIL"
        if policy == "debug":
            return True
        if policy in {"normal", "failure_or_marked", "ci"}:
            return bool(spec.capture or failed)
        return bool(spec.capture)

    def _should_capture_page_source(self, spec: StepSpec) -> bool:
        mode = str(self._setting("capture_page_source")).lower()
        failed = spec.status.upper() == "FAILED" or spec.comparison.upper() == "FAIL"
        if mode in {"always", "debug"}:
            return True
        if mode in {"never", "false", "off"}:
            return False
        return failed

    def _should_capture_diff(self, spec: StepSpec) -> bool:
        mode = str(self._setting("capture_diff")).lower()
        failed = spec.status.upper() == "FAILED" or spec.comparison.upper() == "FAIL"
        if mode in {"always", "debug"}:
            return True
        if mode in {"never", "false", "off"}:
            return False
        if mode == "on_failure":
            return failed
        return bool(spec.capture)
