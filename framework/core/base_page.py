from __future__ import annotations

from pathlib import Path

from framework.core.defaults import setting_from_mapping
from framework.core.driver import DriverAdapter, UiActionResult
from framework.core.exceptions import ElementNotFoundError
from framework.core.locator import Locator
from framework.core.logger import setup_logger
from framework.core.steps import StepContext, StepSpec
from framework.vision.factory import build_image_engine
from framework.vision.image_engine import ImageEngine


class BasePage:
    """页面对象基类。

    页面对象建议只表达业务语义，比如：
    - `search()`
    - `login()`
    - `assert_home_loaded()`

    不建议在测试用例里直接散落底层 driver 调用。
    """

    def __init__(self, driver: DriverAdapter, image_engine: ImageEngine | None = None) -> None:
        self.driver = driver
        self.image_engine = image_engine or build_image_engine(driver)
        self.logger = setup_logger(self.__class__.__name__)

    def click(self, locator: Locator) -> UiActionResult:
        """点击元素。

        如果元素允许图片兜底，普通定位失败后会自动尝试图像点击。
        """
        try:
            return self.driver.click(locator)
        except ElementNotFoundError:
            fallback_result = self._click_with_image_fallback(locator)
            if fallback_result is not None:
                return fallback_result
            raise

    def input_text(self, locator: Locator, value: str) -> UiActionResult:
        """向输入框写入文本。"""
        try:
            return self.driver.set_text(locator, value)
        except ElementNotFoundError:
            fallback = locator.image_fallback_config()
            if fallback is None:
                raise
            self.logger.warning("使用图片兜底聚焦输入框：%s", locator.name)
            self.image_engine.click(
                fallback["template"],
                threshold=fallback["threshold"],
                region=fallback["region"],
                artifact_name=f"{locator.name}_input",
            )
            self.driver.send_keys(value, clear=True)
            return UiActionResult(
                locator_name=locator.name,
                strategy="image",
                bounds=fallback["region"],
                used_fallback=True,
            )

    def clear_text(self, locator: Locator) -> None:
        """清空输入框内容。"""
        self.driver.clear_text(locator)

    def is_visible(self, locator: Locator) -> bool:
        """判断元素当前是否可见。"""
        if self.driver.exists(locator):
            return True

        fallback = locator.image_fallback_config()
        if fallback is None:
            return False
        self.logger.info("普通定位未命中，使用图片兜底检查可见性：%s", locator.name)
        return self.image_engine.exists(
            fallback["template"],
            threshold=fallback["threshold"],
            region=fallback["region"],
            artifact_name=f"{locator.name}_visible",
        )

    def record_step(self, spec: StepSpec) -> None:
        """记录一步执行步骤，并按需采集截图和页面层级。"""
        self.driver.record_step(spec)

    def step(
        self,
        name: str,
        *,
        expected: str = "",
        detail: str = "",
        capture: bool = True,
        comparison: str = "PASS",
    ) -> StepContext:
        """构建页面层步骤上下文。"""

        return StepContext(
            spec=StepSpec(
                name=name,
                expected=expected,
                detail=detail,
                capture=capture,
                comparison=comparison,
            ),
            emitter=self.record_step,
        )

    def save_failure_artifacts(self, case_name: str) -> tuple[str, str]:
        """保存失败现场。

        主要产物：
        - 失败截图
        - 页面层级 XML
        """
        screenshot_dir = Path(setting_from_mapping(self.driver.framework_config, "screenshot_dir"))
        source_dir = Path(setting_from_mapping(self.driver.framework_config, "page_source_dir"))
        artifact_name = self.driver.build_artifact_name(case_name, category="failure")
        screenshot_path = screenshot_dir / f"{artifact_name}.png"
        source_path = source_dir / f"{artifact_name}.xml"
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.parent.mkdir(parents=True, exist_ok=True)

        self.driver.screenshot(screenshot_path)
        source_path.write_text(self.driver.page_source(), encoding="utf-8")
        return str(screenshot_path), str(source_path)

    def _click_with_image_fallback(self, locator: Locator) -> UiActionResult | None:
        """按显式图片兜底契约执行点击。"""
        fallback = locator.image_fallback_config()
        if fallback is None:
            return None
        self.logger.warning("普通定位失败，改用图片兜底点击：%s", locator.name)
        self.image_engine.click(
            fallback["template"],
            threshold=fallback["threshold"],
            region=fallback["region"],
            artifact_name=f"{locator.name}_click",
        )
        return UiActionResult(
            locator_name=locator.name,
            strategy="image",
            bounds=fallback["region"],
            used_fallback=True,
        )
