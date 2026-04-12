from __future__ import annotations

from pathlib import Path

from framework.core.driver import DriverAdapter


class FakeDevice:
    def screenshot(self, path: str) -> None:
        Path(path).write_bytes(b"fake-png")

    def dump_hierarchy(self) -> str:
        return "<hierarchy />"


def test_driver_capture_state_uses_runtime_context_for_unique_artifacts(tmp_path: Path) -> None:
    driver = DriverAdapter(
        serial="",
        framework_config={
            "screenshot_dir": str(tmp_path / "screenshots"),
            "page_source_dir": str(tmp_path / "page_source"),
        },
    )
    driver._device = FakeDevice()
    driver.set_runtime_context(run_id="20260412_101500", case_name="tests_case_demo")

    first_shot, first_xml = driver.capture_state("打开搜索框")
    second_shot, second_xml = driver.capture_state("打开搜索框")

    assert first_shot != second_shot
    assert first_xml != second_xml
    assert "20260412_101500" in first_shot
    assert "tests_case_demo" in first_shot
    assert Path(first_shot).exists()
    assert Path(second_xml).exists()
