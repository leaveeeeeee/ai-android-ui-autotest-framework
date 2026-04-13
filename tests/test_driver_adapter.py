from __future__ import annotations

from pathlib import Path

import pytest

from framework.core.driver import DriverAdapter
from framework.core.exceptions import ElementNotFoundError
from framework.core.locator import Locator
from tests.fakes import FakeCaptureDevice, FakeSelector, FakeStepRecorder


class FakeLookupDevice(FakeCaptureDevice):
    def __init__(self, selector: FakeSelector | None = None) -> None:
        self.selector = selector or FakeSelector(matched=False)

    def __call__(self, **kwargs):
        self.kwargs = kwargs
        return self.selector


class FlakyClickDevice(FakeCaptureDevice):
    def __init__(self) -> None:
        self.selector = FakeSelector(matched=True, click_error=RuntimeError("tap failed"))
        self.calls = 0

    def __call__(self, **kwargs):
        self.calls += 1
        if self.calls >= 2:
            self.selector.click_error = None
        return self.selector


def test_driver_capture_state_uses_runtime_context_for_unique_artifacts(tmp_path: Path) -> None:
    driver = DriverAdapter(
        serial="",
        framework_config={
            "screenshot_dir": str(tmp_path / "screenshots"),
            "page_source_dir": str(tmp_path / "page_source"),
        },
    )
    driver._device = FakeCaptureDevice()
    driver.set_runtime_context(run_id="20260412_101500", case_name="tests_case_demo")

    first_shot, first_xml = driver.capture_state("打开搜索框")
    second_shot, second_xml = driver.capture_state("打开搜索框")

    assert first_shot != second_shot
    assert first_xml != second_xml
    assert "20260412_101500" in first_shot
    assert "tests_case_demo" in first_shot
    assert Path(first_shot).exists()
    assert Path(second_xml).exists()


def test_driver_find_error_includes_locator_context() -> None:
    driver = DriverAdapter(serial="SER123")
    driver._device = FakeLookupDevice()
    locator = Locator(
        name="search_input",
        strategy="resource_id",
        value="demo:id/search",
        timeout=3.5,
        fallback=[Locator(name="search_hint", strategy="text", value="Search")],
    )

    with pytest.raises(ElementNotFoundError) as exc_info:
        driver.find(locator)

    message = str(exc_info.value)
    assert "search_input" in message
    assert "resource_id" in message
    assert "demo:id/search" in message
    assert "timeout=3.5" in message
    assert "search_hint" in message


def test_driver_click_retries_until_success() -> None:
    driver = DriverAdapter(
        serial="SER123",
        framework_config={
            "click_retry_count": 2,
            "click_retry_interval": 0.0,
        },
    )
    device = FlakyClickDevice()
    driver._device = device

    driver.click(Locator(name="search_button", strategy="resource_id", value="demo:id/search"))

    assert device.calls == 2
    assert device.selector.click_calls == 2


def test_driver_record_step_includes_duration() -> None:
    driver = DriverAdapter(serial="SER123")
    recorder = FakeStepRecorder()
    driver.set_step_recorder(recorder)

    driver.record_step(name="打开搜索框", detail="detail", capture=False)

    assert recorder.records
    assert isinstance(recorder.records[0]["duration_ms"], int)
