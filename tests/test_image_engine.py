from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from framework.core.exceptions import ImageMatchError
from framework.vision.image_engine import ImageEngine
from tests.fakes import FakeImageDriver


def test_image_engine_match_and_click(tmp_path: Path) -> None:
    screenshot = np.zeros((120, 120, 3), dtype=np.uint8)
    screenshot[30:50, 60:90] = (255, 255, 255)
    screenshot[35:45, 68:82] = (0, 0, 0)
    template = screenshot[30:50, 60:90].copy()

    screenshot_path = tmp_path / "screen.png"
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    template_path = template_dir / "login_button.png"
    cv2.imwrite(str(screenshot_path), screenshot)
    cv2.imwrite(str(template_path), template)

    driver = FakeImageDriver(screenshot_path)
    engine = ImageEngine(
        driver=driver,
        template_dir=template_dir,
        screenshot_dir=tmp_path / "shots",
        debug_dir=tmp_path / "debug",
        threshold=0.8,
    )

    result = engine.click("login_button")

    assert result.confidence >= 0.8
    assert result.center == (75, 40)
    assert driver.clicked_point == (75, 40)
    assert (tmp_path / "debug" / "run_case_image_match_001_login_button_debug.png").exists()


def test_image_engine_raises_when_confidence_too_low(tmp_path: Path) -> None:
    screenshot = np.zeros((80, 80, 3), dtype=np.uint8)
    screenshot[10:30, 10:30] = (255, 255, 255)
    screenshot[14:18, 14:18] = (0, 0, 0)
    template = np.zeros((20, 20, 3), dtype=np.uint8)
    template[:, :] = (255, 255, 255)
    template[0:4, 0:4] = (0, 0, 0)

    mismatched_screenshot = np.zeros((80, 80, 3), dtype=np.uint8)

    screenshot_path = tmp_path / "screen.png"
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    template_path = template_dir / "missing_button.png"
    cv2.imwrite(str(screenshot_path), mismatched_screenshot)
    cv2.imwrite(str(template_path), template)

    driver = FakeImageDriver(screenshot_path)
    engine = ImageEngine(
        driver=driver,
        template_dir=template_dir,
        screenshot_dir=tmp_path / "shots",
        debug_dir=tmp_path / "debug",
        threshold=1.1,
    )

    try:
        engine.match("missing_button")
    except ImageMatchError as exc:
        message = str(exc)
        assert "below threshold" in message
        assert str(template_path) in message
        assert "run_case_image_match_001_missing_button.png" in message
    else:
        raise AssertionError("Expected ImageMatchError when confidence is below threshold.")


def test_image_engine_uses_unique_artifact_names(tmp_path: Path) -> None:
    screenshot = np.zeros((60, 60, 3), dtype=np.uint8)
    screenshot[20:35, 10:25] = (255, 255, 255)
    screenshot[24:30, 14:20] = (0, 0, 0)
    template = screenshot[20:35, 10:25].copy()

    screenshot_path = tmp_path / "screen.png"
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    cv2.imwrite(str(screenshot_path), screenshot)
    cv2.imwrite(str(template_dir / "search_button.png"), template)

    driver = FakeImageDriver(screenshot_path)
    engine = ImageEngine(
        driver=driver,
        template_dir=template_dir,
        screenshot_dir=tmp_path / "shots",
        debug_dir=tmp_path / "debug",
        threshold=0.8,
    )

    first = engine.match("search_button", artifact_name="step_a")
    second = engine.match("search_button", artifact_name="step_b")

    assert first.screenshot_path != second.screenshot_path
    assert "run_case_image_match_001_step_a" in first.screenshot_path
    assert "run_case_image_match_002_step_b" in second.screenshot_path
    assert (tmp_path / "debug" / "run_case_image_match_001_step_a_debug.png").exists()
    assert (tmp_path / "debug" / "run_case_image_match_002_step_b_debug.png").exists()


def test_image_engine_matches_scaled_template(tmp_path: Path) -> None:
    screenshot = np.zeros((100, 100, 3), dtype=np.uint8)
    screenshot[30:55, 40:65] = (255, 255, 255)
    screenshot[36:49, 47:58] = (0, 0, 0)
    full_patch = screenshot[30:55, 40:65].copy()
    template = cv2.resize(full_patch, (20, 20), interpolation=cv2.INTER_LINEAR)

    screenshot_path = tmp_path / "screen.png"
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    template_path = template_dir / "scaled_button.png"
    cv2.imwrite(str(screenshot_path), screenshot)
    cv2.imwrite(str(template_path), template)

    driver = FakeImageDriver(screenshot_path)
    engine = ImageEngine(
        driver=driver,
        template_dir=template_dir,
        screenshot_dir=tmp_path / "shots",
        debug_dir=tmp_path / "debug",
        threshold=0.8,
        scales=[1.0, 1.25],
    )

    result = engine.match("scaled_button")

    assert result.scale == pytest.approx(1.25)
    assert result.center == (52, 42)
