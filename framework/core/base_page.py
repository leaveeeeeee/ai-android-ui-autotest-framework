from __future__ import annotations

from pathlib import Path

from framework.core.driver import DriverAdapter
from framework.core.exceptions import ElementNotFoundError
from framework.core.locator import Locator
from framework.core.logger import setup_logger
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
        self.image_engine = image_engine or ImageEngine(
            driver=driver,
            template_dir=driver.framework_config.get("image_template_dir", "assets/images"),
            screenshot_dir=driver.framework_config.get(
                "screenshot_dir", "artifacts/report_data/screenshots"
            ),
            debug_dir=driver.framework_config.get(
                "image_debug_dir", "artifacts/report_data/image_debug"
            ),
            threshold=float(driver.framework_config.get("image_match_threshold", 0.92)),
        )
        self.logger = setup_logger(self.__class__.__name__)

    def click(self, locator: Locator) -> None:
        """点击元素。

        如果元素允许图片兜底，普通定位失败后会自动尝试图像点击。
        """
        try:
            self.driver.click(locator)
        except ElementNotFoundError:
            if locator.allow_image_fallback:
                self.logger.warning("Falling back to image click for '%s'", locator.name)
                self.image_engine.click(locator.name)
                return
            raise

    def input_text(self, locator: Locator, value: str) -> None:
        """向输入框写入文本。"""
        self.driver.set_text(locator, value)

    def clear_text(self, locator: Locator) -> None:
        """清空输入框内容。"""
        self.driver.clear_text(locator)

    def is_visible(self, locator: Locator) -> bool:
        """判断元素当前是否可见。"""
        return self.driver.exists(locator)

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
        """记录一步执行步骤，并按需采集截图和页面层级。"""
        self.driver.record_step(
            name=name,
            detail=detail,
            expected=expected,
            actual=actual,
            comparison=comparison,
            status=status,
            logs=logs,
            highlight_rect=highlight_rect,
            capture=capture,
        )

    def save_failure_artifacts(self, case_name: str) -> tuple[str, str]:
        """保存失败现场。

        主要产物：
        - 失败截图
        - 页面层级 XML
        """
        screenshot_dir = Path(
            self.driver.framework_config.get("screenshot_dir", "artifacts/report_data/screenshots")
        )
        source_dir = Path(
            self.driver.framework_config.get("page_source_dir", "artifacts/report_data/page_source")
        )
        screenshot_path = screenshot_dir / f"{case_name}.png"
        source_path = source_dir / f"{case_name}.xml"
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.parent.mkdir(parents=True, exist_ok=True)

        self.driver.screenshot(screenshot_path)
        source_path.write_text(self.driver.page_source(), encoding="utf-8")
        return str(screenshot_path), str(source_path)
