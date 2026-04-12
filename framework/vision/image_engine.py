from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import cv2
import numpy as np

from framework.core.exceptions import ImageMatchError
from framework.core.logger import setup_logger

if TYPE_CHECKING:
    from framework.core.driver import DriverAdapter


@dataclass
class ImageMatchResult:
    """图像匹配结果。"""

    template_path: str
    screenshot_path: str
    confidence: float
    top_left: tuple[int, int]
    bottom_right: tuple[int, int]

    @property
    def center(self) -> tuple[int, int]:
        return (
            int((self.top_left[0] + self.bottom_right[0]) / 2),
            int((self.top_left[1] + self.bottom_right[1]) / 2),
        )


class ImageEngine:
    """基于 OpenCV 的模板匹配引擎。

    主要用途：
    - 在普通定位失败时做图像兜底
    - 输出匹配框、中心点、置信度
    - 生成调试图，便于排查误点和误识别
    """

    def __init__(
        self,
        driver: "DriverAdapter",
        template_dir: str | Path = "assets/images",
        screenshot_dir: str | Path = "artifacts/report_data/screenshots",
        debug_dir: str | Path = "artifacts/report_data/image_debug",
        threshold: float = 0.92,
    ) -> None:
        self.driver = driver
        self.template_dir = Path(template_dir)
        self.screenshot_dir = Path(screenshot_dir)
        self.debug_dir = Path(debug_dir)
        self.threshold = threshold
        self.logger = setup_logger(self.__class__.__name__)

    def click(
        self,
        image_name: str,
        threshold: float | None = None,
        region: tuple[int, int, int, int] | None = None,
    ) -> ImageMatchResult:
        """匹配模板并点击匹配区域中心。"""
        match_result = self.match(image_name=image_name, threshold=threshold, region=region)
        center_x, center_y = match_result.center
        self.driver.click_point(center_x, center_y)
        self.logger.info(
            "Clicked image '%s' at (%s, %s) with confidence %.4f",
            image_name,
            center_x,
            center_y,
            match_result.confidence,
        )
        return match_result

    def exists(
        self,
        image_name: str,
        threshold: float | None = None,
        region: tuple[int, int, int, int] | None = None,
    ) -> bool:
        """判断模板是否存在于当前页面。"""
        try:
            self.match(image_name=image_name, threshold=threshold, region=region)
            return True
        except ImageMatchError:
            return False

    def match(
        self,
        image_name: str,
        threshold: float | None = None,
        region: tuple[int, int, int, int] | None = None,
    ) -> ImageMatchResult:
        """执行一次模板匹配并返回详细结果。"""
        effective_threshold = self.threshold if threshold is None else threshold
        template_path = self._resolve_template_path(image_name)
        screenshot_path = self._capture_screenshot(image_name)

        screenshot = cv2.imread(str(screenshot_path), cv2.IMREAD_COLOR)
        template = cv2.imread(str(template_path), cv2.IMREAD_COLOR)
        if screenshot is None:
            raise ImageMatchError(f"Failed to load screenshot for matching: {screenshot_path}")
        if template is None:
            raise ImageMatchError(f"Failed to load image template: {template_path}")

        crop, offset = self._crop_region(screenshot, region)
        if template.shape[0] > crop.shape[0] or template.shape[1] > crop.shape[1]:
            raise ImageMatchError(
                f"Template '{template_path.name}' is larger than the search area."
            )

        method = self._select_match_method(template)
        result = cv2.matchTemplate(crop, template, method)
        min_confidence, max_confidence, min_location, max_location = cv2.minMaxLoc(result)
        confidence, match_location = self._normalize_confidence(
            method=method,
            min_confidence=min_confidence,
            max_confidence=max_confidence,
            min_location=min_location,
            max_location=max_location,
        )
        top_left = (match_location[0] + offset[0], match_location[1] + offset[1])
        bottom_right = (
            top_left[0] + template.shape[1],
            top_left[1] + template.shape[0],
        )

        match_result = ImageMatchResult(
            template_path=str(template_path),
            screenshot_path=str(screenshot_path),
            confidence=float(confidence),
            top_left=top_left,
            bottom_right=bottom_right,
        )
        self._write_debug_image(screenshot, match_result, template_path.name)

        if match_result.confidence < effective_threshold:
            raise ImageMatchError(
                "Image match confidence below threshold: "
                f"{match_result.confidence:.4f} < {effective_threshold:.4f} "
                f"for template '{template_path.name}'"
            )

        self.logger.info(
            "Matched image '%s' with confidence %.4f at %s",
            template_path.name,
            match_result.confidence,
            match_result.center,
        )
        return match_result

    def _select_match_method(self, template: np.ndarray) -> int:
        """根据模板内容选择更合适的匹配算法。"""
        grayscale_template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        if float(np.std(grayscale_template)) < 1e-6:
            return cv2.TM_SQDIFF_NORMED
        return cv2.TM_CCOEFF_NORMED

    def _normalize_confidence(
        self,
        method: int,
        min_confidence: float,
        max_confidence: float,
        min_location: tuple[int, int],
        max_location: tuple[int, int],
    ) -> tuple[float, tuple[int, int]]:
        """把不同算法返回值统一折算为“分数 + 命中位置”。"""
        if method == cv2.TM_SQDIFF_NORMED:
            return 1.0 - float(min_confidence), min_location
        return float(max_confidence), max_location

    def _resolve_template_path(self, image_name: str) -> Path:
        """根据模板名解析真实模板路径。"""
        candidate = Path(image_name)
        candidates = (
            [candidate]
            if candidate.suffix
            else [
                candidate.with_suffix(".png"),
                candidate.with_suffix(".jpg"),
            ]
        )

        for template in candidates:
            full_path = template if template.is_absolute() else self.template_dir / template
            if full_path.exists():
                return full_path

        raise ImageMatchError(
            f"Image template '{image_name}' not found under {self.template_dir.resolve()}"
        )

    def _capture_screenshot(self, image_name: str) -> Path:
        """先截图，再作为图像匹配输入。"""
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = self.screenshot_dir / f"{Path(image_name).stem}_latest.png"
        self.driver.screenshot(screenshot_path)
        return screenshot_path

    def _crop_region(
        self,
        image: np.ndarray,
        region: tuple[int, int, int, int] | None,
    ) -> tuple[np.ndarray, tuple[int, int]]:
        """在局部区域内裁剪匹配范围，提高速度和稳定性。"""
        if region is None:
            return image, (0, 0)

        left, top, right, bottom = region
        if left < 0 or top < 0 or right <= left or bottom <= top:
            raise ImageMatchError(f"Invalid region: {region}")

        height, width = image.shape[:2]
        bounded_left = max(0, min(left, width))
        bounded_top = max(0, min(top, height))
        bounded_right = max(0, min(right, width))
        bounded_bottom = max(0, min(bottom, height))
        if bounded_right <= bounded_left or bounded_bottom <= bounded_top:
            raise ImageMatchError(f"Region is outside the screenshot bounds: {region}")

        return (
            image[bounded_top:bounded_bottom, bounded_left:bounded_right],
            (bounded_left, bounded_top),
        )

    def _write_debug_image(
        self,
        screenshot: np.ndarray,
        match_result: ImageMatchResult,
        template_name: str,
    ) -> None:
        """输出带命中框和分数标注的调试图。"""
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        debug_image = screenshot.copy()
        cv2.rectangle(
            debug_image,
            match_result.top_left,
            match_result.bottom_right,
            color=(0, 255, 0),
            thickness=2,
        )
        center_x, center_y = match_result.center
        cv2.circle(debug_image, (center_x, center_y), 6, color=(0, 0, 255), thickness=-1)
        label = f"{template_name}: {match_result.confidence:.3f}"
        text_origin = (match_result.top_left[0], max(match_result.top_left[1] - 10, 20))
        cv2.putText(
            debug_image,
            label,
            text_origin,
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2,
            cv2.LINE_AA,
        )
        target_path = self.debug_dir / f"{Path(template_name).stem}_debug.png"
        cv2.imwrite(str(target_path), debug_image)
