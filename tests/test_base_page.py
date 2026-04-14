from __future__ import annotations

import pytest

from framework.core.base_page import BasePage
from framework.core.locator import Locator
from tests.fakes import FakeImageEngine, FakePageDriver, not_found


def test_base_page_uses_explicit_image_template_for_fallbacks() -> None:
    driver = FakePageDriver(
        click_error=not_found(
            Locator(name="renamed_login_button", strategy="resource_id", value="demo:id/login")
        ),
        set_text_error=not_found(
            Locator(name="renamed_login_button", strategy="resource_id", value="demo:id/login")
        ),
        visible=False,
    )
    image_engine = FakeImageEngine()
    page = BasePage(driver=driver, image_engine=image_engine)
    locator = Locator(
        name="renamed_login_button",
        strategy="resource_id",
        value="demo:id/login",
        allow_image_fallback=True,
        image_template="stable_login_button",
        image_region=(10, 20, 200, 300),
        image_threshold=0.88,
    )

    page.click(locator)
    page.input_text(locator, "chatgpt")
    visible = page.is_visible(locator)

    assert visible is True
    assert driver.sent_keys == [("chatgpt", True)]
    assert image_engine.calls == [
        (
            "click",
            "stable_login_button",
            {
                "threshold": 0.88,
                "region": (10, 20, 200, 300),
                "artifact_name": "renamed_login_button_click",
            },
        ),
        (
            "click",
            "stable_login_button",
            {
                "threshold": 0.88,
                "region": (10, 20, 200, 300),
                "artifact_name": "renamed_login_button_input",
            },
        ),
        (
            "exists",
            "stable_login_button",
            {
                "threshold": 0.88,
                "region": (10, 20, 200, 300),
                "artifact_name": "renamed_login_button_visible",
            },
        ),
    ]


def test_base_page_builds_image_engine_via_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    built_engine = FakeImageEngine()
    driver = FakePageDriver(framework_config={"image_template_dir": "artifacts/templates"})

    monkeypatch.setattr("framework.core.base_page.build_image_engine", lambda current: built_engine)

    page = BasePage(driver=driver)

    assert page.image_engine is built_engine


def test_base_page_step_records_success_after_context_exit() -> None:
    driver = FakePageDriver()
    page = BasePage(driver=driver, image_engine=FakeImageEngine())

    with page.step("点击搜索框", expected="输入框可编辑", detail="聚焦搜索输入框") as step:
        step.update(actual="已点击搜索框", logs="action=click locator=search_input")

    assert len(driver.recorded_steps) == 1
    recorded = driver.recorded_steps[0]
    assert recorded.name == "点击搜索框"
    assert recorded.status == "PASSED"
    assert recorded.comparison == "PASS"
    assert recorded.actual == "已点击搜索框"
    assert recorded.logs == "action=click locator=search_input"


def test_base_page_step_records_failure_and_reraises() -> None:
    driver = FakePageDriver()
    page = BasePage(driver=driver, image_engine=FakeImageEngine())

    with pytest.raises(RuntimeError, match="tap failed"):
        with page.step("点击搜索按钮", expected="进入结果页") as step:
            step.update(detail="点击百度搜索按钮")
            raise RuntimeError("tap failed")

    assert len(driver.recorded_steps) == 1
    recorded = driver.recorded_steps[0]
    assert recorded.name == "点击搜索按钮"
    assert recorded.status == "FAILED"
    assert recorded.comparison == "FAIL"
    assert recorded.actual == "tap failed"
    assert recorded.logs == "tap failed"
