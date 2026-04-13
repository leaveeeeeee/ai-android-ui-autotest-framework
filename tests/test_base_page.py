from __future__ import annotations

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
