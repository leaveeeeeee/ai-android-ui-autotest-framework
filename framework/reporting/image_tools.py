from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def annotate_click_region(
    screenshot_path: str | Path,
    rect: tuple[int, int, int, int],
    color: tuple[int, int, int] = (0, 0, 255),
) -> None:
    """在截图上用红框标出操作区域。"""
    image = cv2.imread(str(screenshot_path), cv2.IMREAD_COLOR)
    if image is None:
        return

    left, top, right, bottom = rect
    cv2.rectangle(image, (left, top), (right, bottom), color=color, thickness=3)
    center = ((left + right) // 2, (top + bottom) // 2)
    cv2.circle(image, center, 8, color, thickness=-1)
    cv2.imwrite(str(screenshot_path), image)


def create_diff_image(
    before_path: str | Path,
    after_path: str | Path,
    diff_path: str | Path,
) -> None:
    """生成前后截图差异图。

    有明显变化时会标出变化区域；
    若变化不明显，则回退成前后图并排展示。
    """
    before = cv2.imread(str(before_path), cv2.IMREAD_COLOR)
    after = cv2.imread(str(after_path), cv2.IMREAD_COLOR)
    if before is None or after is None:
        return
    if before.shape != after.shape:
        return

    diff = cv2.absdiff(before, after)
    gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    _, threshold = cv2.threshold(gray, 25, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(threshold, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    output = after.copy()
    changed = False
    for contour in contours:
        if cv2.contourArea(contour) < 150:
            continue
        x, y, width, height = cv2.boundingRect(contour)
        cv2.rectangle(output, (x, y), (x + width, y + height), (0, 255, 255), 3)
        changed = True

    if not changed:
        output = np.hstack((before, after))
    cv2.imwrite(str(diff_path), output)
