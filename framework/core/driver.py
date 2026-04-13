from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

from framework.core.defaults import setting_from_mapping
from framework.core.exceptions import DeviceConnectionError, ElementNotFoundError
from framework.core.locator import Locator
from framework.core.logger import init_logging, setup_logger
from framework.core.protocols import StepContextProvider, StepRecorder
from framework.core.waiter import Waiter
from framework.reporting.image_tools import annotate_click_region, create_diff_image


def _sanitize_artifact_name(value: str) -> str:
    """把任意名称转换成稳定、可做文件名的片段。"""
    normalized = re.sub(r"[^a-zA-Z0-9_]+", "_", value.strip()).strip("_").lower()
    return normalized or "artifact"


class DriverAdapter:
    """对 `uiautomator2` 的轻量封装。

    设计目标：
    - 给页面对象提供统一操作入口
    - 隔离上层业务代码与底层驱动实现
    - 在这里集中处理等待、点击兜底、输入兜底、步骤记录等横切逻辑
    """

    def __init__(
        self,
        serial: str,
        default_timeout: float = 10.0,
        retry_interval: float = 0.5,
        framework_config: dict[str, Any] | None = None,
    ) -> None:
        self.serial = serial
        init_logging(framework_config)
        self.logger = setup_logger()
        self.waiter = Waiter(timeout=default_timeout, interval=retry_interval)
        self.framework_config = framework_config or {}
        self.step_recorder: StepRecorder | None = None
        self.step_context_provider: StepContextProvider | None = None
        self._device = None
        self._runtime_context: dict[str, str] = {}
        self._artifact_sequence = 0
        self.click_retry_count = int(
            setting_from_mapping(self.framework_config, "click_retry_count")
        )
        self.click_retry_interval = float(
            self.framework_config.get(
                "click_retry_interval",
                setting_from_mapping(self.framework_config, "default_retry_interval"),
            )
        )

    @property
    def device(self) -> Any:
        if self._device is None:
            raise DeviceConnectionError(
                f"Device is not connected for serial {self.serial or 'default'}."
            )
        return self._device

    def connect(self) -> "DriverAdapter":
        """连接真实设备并返回当前 driver 实例。"""
        try:
            import uiautomator2 as u2

            self._device = u2.connect(self.serial) if self.serial else u2.connect()
            self.logger.info("Connected to device: %s", self.serial or "default")
            return self
        except Exception as exc:
            raise DeviceConnectionError(
                f"Failed to connect to device for serial {self.serial or 'default'}: {exc}"
            ) from exc

    def find(self, locator: Locator) -> Any:
        """查找元素。

        行为说明：
        - 先尝试主定位器
        - 主定位失败后按顺序尝试 fallback
        - 全部失败则抛出 `ElementNotFoundError`
        """
        element = self._find_once(locator)
        if element is not None:
            return element

        for fallback in locator.fallback:
            element = self._find_once(fallback)
            if element is not None:
                self.logger.warning(
                    "Primary locator '%s' failed; fallback '%s' matched.",
                    locator.name,
                    fallback.name,
                )
                return element

        attempted = [locator.describe(), *(fallback.describe() for fallback in locator.fallback)]
        raise ElementNotFoundError(
            "Unable to locate element. Attempted locators: " + " | ".join(attempted)
        )

    def click(self, locator: Locator) -> None:
        """点击元素。

        对 XPath/WebView 场景优先使用元素中心点点击，减少 `.click()` 在真机上的不稳定问题。
        """
        last_error: Exception | None = None
        attempts = max(1, self.click_retry_count)
        for attempt in range(1, attempts + 1):
            try:
                element = self.find(locator)
                if locator.strategy == "xpath":
                    bounds = self._extract_bounds(element)
                    if bounds is not None:
                        self._click_bounds_center(bounds)
                        return
                element.click()
                return
            except Exception as exc:
                last_error = exc
                if attempt == attempts:
                    break
                time.sleep(self.click_retry_interval)
        raise ElementNotFoundError(
            "Failed to click element after retries: "
            f"{locator.describe()}, retries={attempts}, interval={self.click_retry_interval}. "
            f"Last error: {last_error}"
        )

    def click_point(self, x: int, y: int) -> None:
        """按坐标点击屏幕。"""
        self.device.click(x, y)

    def set_text(self, locator: Locator, value: str) -> None:
        """向元素写入文本。

        针对 WebView/XPath 输入场景，这里会做多重兜底：
        1. 先尝试元素原生 `set_text`
        2. 再尝试 `device.send_keys(clear=False)`
        3. 再尝试 `device.send_keys(clear=True)`

        写入完成后，会通过页面层级再次确认文本是否已真正出现在页面中。
        """
        element = self.find(locator)
        if locator.strategy == "xpath":
            bounds = self._extract_bounds(element)
            if bounds is not None:
                self._click_bounds_center(bounds)
            else:
                element.click()

            last_error: Exception | None = None
            for writer in (
                lambda: self._set_text_on_element(element, value),
                lambda: self._send_keys(value, clear=False),
                lambda: self._send_keys(value, clear=True),
            ):
                try:
                    writer()
                except Exception as exc:
                    last_error = exc
                    continue

                if not value or self._page_contains_text(value):
                    return

            message = (
                "Failed to set text: "
                f"{locator.describe()}, value={value!r} was not observed in page source."
            )
            if last_error is not None:
                message = f"{message} Last error: {last_error}"
            raise ElementNotFoundError(message)

        element.set_text(value)

    def clear_text(self, locator: Locator) -> None:
        """清空输入框内容。"""
        element = self.find(locator)
        if hasattr(element, "clear_text"):
            element.clear_text()
            return
        if hasattr(element, "set_text"):
            element.set_text("")
            return
        raise ElementNotFoundError(f"Element does not support clear_text: {locator.describe()}")

    def exists(self, locator: Locator) -> bool:
        """判断元素是否存在。"""
        try:
            return self._find_once(locator) is not None
        except Exception:
            return False

    def send_keys(self, value: str, *, clear: bool = False) -> None:
        """直接调用设备级输入能力。

        这个方法主要用于“图片先点击，再设备级输入”的兜底场景。
        """
        self._send_keys(value, clear=clear)

    def screenshot(self, path: str | Path) -> str:
        """保存设备截图到指定路径。"""
        target = str(path)
        self.device.screenshot(target)
        return target

    def page_source(self) -> str:
        """导出当前页面层级 XML。"""
        return self.device.dump_hierarchy()

    def app_start(self, package: str, activity: str | None = None) -> None:
        """启动应用。"""
        self.device.app_start(package, activity=activity)

    def app_stop(self, package: str) -> None:
        """停止应用。"""
        self.device.app_stop(package)

    def press(self, key: str) -> None:
        """发送按键。"""
        self.device.press(key)

    def set_step_recorder(self, recorder: StepRecorder | None) -> None:
        """注入步骤记录器。通常在 pytest 生命周期中设置。"""
        self.step_recorder = recorder

    def set_step_context_provider(self, provider: StepContextProvider | None) -> None:
        """注入步骤上下文提供器，比如当前焦点窗口。"""
        self.step_context_provider = provider

    def set_runtime_context(self, **context: str) -> None:
        """设置当前用例的运行时上下文。

        运行时上下文会参与截图、页面层级、图像调试图的唯一命名。
        """
        self._runtime_context = {key: str(value) for key, value in context.items() if value}
        self._artifact_sequence = 0

    def clear_runtime_context(self) -> None:
        """清空运行时上下文。"""
        self._runtime_context = {}
        self._artifact_sequence = 0

    def build_artifact_name(self, base_name: str, *, category: str = "artifact") -> str:
        """生成唯一产物名。

        命名维度：
        - run_id
        - case_name
        - category
        - 全局序号
        - 业务语义名
        """
        self._artifact_sequence += 1
        parts = [
            self._runtime_context.get("run_id", ""),
            self._runtime_context.get("case_name", ""),
            _sanitize_artifact_name(category),
            f"{self._artifact_sequence:03d}",
            _sanitize_artifact_name(base_name),
        ]
        return "_".join(part for part in parts if part)

    def get_bounds(self, locator: Locator) -> tuple[int, int, int, int] | None:
        """获取元素边界框，常用于高亮截图中的操作区域。"""
        element = self.find(locator)
        return self._extract_bounds(element)

    def capture_state(self, name: str) -> tuple[str, str]:
        """采集当前状态。

        返回值：
        - 截图路径
        - 页面层级 XML 路径
        """
        screenshot_dir = Path(setting_from_mapping(self.framework_config, "screenshot_dir"))
        source_dir = Path(setting_from_mapping(self.framework_config, "page_source_dir"))
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        source_dir.mkdir(parents=True, exist_ok=True)

        safe_name = self.build_artifact_name(name, category="state")
        screenshot_path = screenshot_dir / f"{safe_name}.png"
        source_path = source_dir / f"{safe_name}.xml"
        self.screenshot(screenshot_path)
        source_path.write_text(self.page_source(), encoding="utf-8")
        return str(screenshot_path), str(source_path)

    def record_step(
        self,
        *,
        name: str,
        detail: str = "",
        expected: str = "",
        actual: str = "",
        comparison: str = "",
        status: str = "PASSED",
        logs: str = "",
        highlight_rect: tuple[int, int, int, int] | None = None,
        capture: bool = True,
    ) -> None:
        """记录一步执行过程。

        这一层会负责：
        - 生成步骤截图
        - 高亮点击区域
        - 生成前后差异图
        - 采集页面层级
        - 注入焦点窗口等上下文
        """
        if self.step_recorder is None:
            return

        started_at = time.perf_counter()
        screenshot_path = ""
        previous_screenshot_path = self.step_recorder.last_screenshot_path
        diff_path = ""
        source_path = ""
        focus_window = ""
        if self.step_context_provider is not None:
            try:
                context = self.step_context_provider() or {}
                focus_window = str(context.get("focus_window", "") or "")
            except Exception:
                focus_window = ""
        if capture:
            step_file_name = self.step_recorder.next_step_name(name)
            screenshot_path, source_path = self.capture_state(step_file_name)
            if highlight_rect is not None:
                annotate_click_region(screenshot_path, highlight_rect)
            if previous_screenshot_path:
                diff_path = str(
                    Path(screenshot_path).with_name(f"{Path(screenshot_path).stem}_diff.png")
                )
                create_diff_image(previous_screenshot_path, screenshot_path, diff_path)

        self.step_recorder.add_step(
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
            duration_ms=int((time.perf_counter() - started_at) * 1000),
        )

    def _find_once(self, locator: Locator) -> Any | None:
        """只执行一次底层定位，不处理 fallback。"""
        if locator.strategy == "image":
            return None
        if locator.strategy == "xpath":
            xpath_obj = self.device.xpath(locator.value)
            return self._wait_for_element(xpath_obj, locator)

        kwargs = locator.as_kwargs()
        if not kwargs:
            raise ElementNotFoundError(f"Unsupported locator strategy for {locator.describe()}")

        obj = self.device(**kwargs)
        return self._wait_for_element(obj, locator)

    def _wait_for_element(self, candidate: Any, locator: Locator) -> Any | None:
        """统一通过 `Waiter` 等待元素出现。"""

        timeout = locator.timeout or self.waiter.timeout
        try:
            return self.waiter.until(
                lambda: candidate if self._element_exists(candidate) else None,
                message=f"Locator timed out: {locator.describe()}, timeout={timeout}",
                timeout=timeout,
                interval=self.waiter.interval,
            )
        except TimeoutError:
            return None

    def _element_exists(self, candidate: Any) -> bool:
        """兼容不同底层对象的存在性判断。"""

        exists_attr = getattr(candidate, "exists", None)
        if callable(exists_attr):
            return bool(exists_attr())
        if exists_attr is not None:
            return bool(exists_attr)

        wait_method = getattr(candidate, "wait", None)
        if callable(wait_method):
            return bool(wait_method(timeout=0))
        return False

    def _extract_bounds(self, element: Any) -> tuple[int, int, int, int] | None:
        """尽量从不同元素对象结构中解析边界框。"""
        if element is None:
            return None

        info = getattr(element, "info", None)
        if isinstance(info, dict):
            bounds = info.get("bounds")
            normalized = self._normalize_bounds(bounds)
            if normalized is not None:
                return normalized

        bounds_attr = getattr(element, "bounds", None)
        if callable(bounds_attr):
            try:
                normalized = self._normalize_bounds(bounds_attr())
                if normalized is not None:
                    return normalized
            except Exception:
                pass
        elif bounds_attr is not None:
            normalized = self._normalize_bounds(bounds_attr)
            if normalized is not None:
                return normalized

        rect_attr = getattr(element, "rect", None)
        if rect_attr is not None:
            normalized = self._normalize_bounds(rect_attr)
            if normalized is not None:
                return normalized

        getter = getattr(element, "get", None)
        if callable(getter):
            try:
                nested = getter(timeout=0)
            except TypeError:
                try:
                    nested = getter()
                except Exception:
                    nested = None
            except Exception:
                nested = None
            if nested is not None and nested is not element:
                return self._extract_bounds(nested)

        return None

    def _normalize_bounds(self, bounds: Any) -> tuple[int, int, int, int] | None:
        """把不同格式的 bounds 统一转换成 `(left, top, right, bottom)`。"""
        if bounds is None:
            return None

        if isinstance(bounds, dict):
            keys = ("left", "top", "right", "bottom")
            if all(key in bounds for key in keys):
                return (
                    int(bounds["left"]),
                    int(bounds["top"]),
                    int(bounds["right"]),
                    int(bounds["bottom"]),
                )

        if isinstance(bounds, (list, tuple)) and len(bounds) == 4:
            return tuple(int(value) for value in bounds)  # type: ignore[return-value]

        if isinstance(bounds, str):
            match = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds)
            if match:
                left, top, right, bottom = match.groups()
                return int(left), int(top), int(right), int(bottom)

        return None

    def _click_bounds_center(self, bounds: tuple[int, int, int, int]) -> None:
        """点击边界框中心点。"""
        left, top, right, bottom = bounds
        self.click_point((left + right) // 2, (top + bottom) // 2)

    def _set_text_on_element(self, element: Any, value: str) -> None:
        """优先使用元素原生 `set_text` 能力写入文本。"""
        target = element
        getter = getattr(element, "get", None)
        if callable(getter):
            try:
                nested = getter(timeout=self.waiter.timeout)
            except TypeError:
                nested = getter()
            if nested is not None:
                target = nested

        setter = getattr(target, "set_text", None)
        if not callable(setter):
            raise ElementNotFoundError("Resolved element does not support set_text.")
        setter(value)

    def _send_keys(self, value: str, *, clear: bool) -> None:
        """调用设备级输入能力写入文本。"""
        try:
            self.device.send_keys(value, clear=clear)
        except TypeError:
            self.device.send_keys(value)

    def _page_contains_text(self, text: str) -> bool:
        """通过页面层级判断文本是否已经真实出现在页面中。"""
        return text.casefold() in self.page_source().casefold()
