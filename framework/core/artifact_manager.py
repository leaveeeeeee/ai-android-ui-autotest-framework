from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable, Mapping

from framework.core.defaults import setting_from_mapping


def _sanitize_artifact_name(value: str) -> str:
    """把任意名称转换成稳定、可做文件名的片段。"""

    normalized = re.sub(r"[^a-zA-Z0-9_]+", "_", value.strip()).strip("_").lower()
    return normalized or "artifact"


class ArtifactManager:
    """统一管理运行时上下文、产物命名和状态采集。"""

    def __init__(self, framework_config: Mapping[str, Any] | None = None) -> None:
        self.framework_config = framework_config or {}
        self._runtime_context: dict[str, str] = {}
        self._artifact_sequence = 0

    def set_runtime_context(self, **context: str) -> None:
        """设置当前用例的运行时上下文。"""

        self._runtime_context = {key: str(value) for key, value in context.items() if value}
        self._artifact_sequence = 0

    def clear_runtime_context(self) -> None:
        """清空运行时上下文。"""

        self._runtime_context = {}
        self._artifact_sequence = 0

    def build_artifact_name(self, base_name: str, *, category: str = "artifact") -> str:
        """生成唯一产物名。"""

        self._artifact_sequence += 1
        parts = [
            self._runtime_context.get("run_id", ""),
            self._runtime_context.get("case_name", ""),
            _sanitize_artifact_name(category),
            f"{self._artifact_sequence:03d}",
            _sanitize_artifact_name(base_name),
        ]
        return "_".join(part for part in parts if part)

    def capture_state(
        self,
        *,
        name: str,
        screenshotter: Callable[[str | Path], str],
        page_source_provider: Callable[[], str] | None,
        include_page_source: bool = True,
    ) -> tuple[str, str]:
        """采集当前截图和页面层级。"""

        screenshot_dir = Path(setting_from_mapping(self.framework_config, "screenshot_dir"))
        source_dir = Path(setting_from_mapping(self.framework_config, "page_source_dir"))
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        if include_page_source:
            source_dir.mkdir(parents=True, exist_ok=True)

        safe_name = self.build_artifact_name(name, category="state")
        screenshot_path = screenshot_dir / f"{safe_name}.png"
        source_path = source_dir / f"{safe_name}.xml"
        screenshotter(screenshot_path)
        _resize_screenshot_if_needed(
            screenshot_path,
            max_width=int(setting_from_mapping(self.framework_config, "max_screenshot_width")),
        )
        if include_page_source and page_source_provider is not None:
            source_path.write_text(page_source_provider(), encoding="utf-8")
            return str(screenshot_path), str(source_path)
        return str(screenshot_path), ""


def _resize_screenshot_if_needed(path: Path, *, max_width: int) -> None:
    if max_width <= 0:
        return

    try:
        from PIL import Image

        with Image.open(path) as image:
            if image.width <= max_width:
                return
            ratio = max_width / image.width
            height = max(1, int(image.height * ratio))
            resized = image.resize((max_width, height))
            resized.save(path)
    except Exception:
        return
