from __future__ import annotations

from typing import TYPE_CHECKING

from framework.core.defaults import setting_from_mapping
from framework.vision.image_engine import ImageEngine

if TYPE_CHECKING:
    from framework.core.driver import DriverAdapter


def build_image_engine(driver: "DriverAdapter") -> ImageEngine:
    """基于 driver 配置构建页面层使用的 `ImageEngine`。"""

    return ImageEngine(
        driver=driver,
        template_dir=setting_from_mapping(driver.framework_config, "image_template_dir"),
        screenshot_dir=setting_from_mapping(driver.framework_config, "screenshot_dir"),
        debug_dir=setting_from_mapping(driver.framework_config, "image_debug_dir"),
        threshold=float(setting_from_mapping(driver.framework_config, "image_match_threshold")),
        scales=setting_from_mapping(driver.framework_config, "image_match_scales"),
    )
