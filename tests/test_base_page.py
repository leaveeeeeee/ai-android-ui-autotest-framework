from __future__ import annotations

from framework.core.base_page import BasePage
from framework.core.exceptions import ElementNotFoundError
from framework.core.locator import Locator


class FakeDriver:
    def __init__(self) -> None:
        self.framework_config = {}
        self.sent_keys: list[tuple[str, bool]] = []

    def click(self, locator: Locator) -> None:
        raise ElementNotFoundError(locator.name)

    def set_text(self, locator: Locator, value: str) -> None:
        raise ElementNotFoundError(locator.name)

    def clear_text(self, locator: Locator) -> None:
        return None

    def exists(self, locator: Locator) -> bool:
        return False

    def send_keys(self, value: str, *, clear: bool = False) -> None:
        self.sent_keys.append((value, clear))

    def build_artifact_name(self, base_name: str, *, category: str = "artifact") -> str:
        return f"{category}_{base_name}"

    def screenshot(self, path) -> str:  # noqa: ANN001
        return str(path)

    def page_source(self) -> str:
        return "<hierarchy />"


class FakeImageEngine:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict]] = []

    def click(self, image_name: str, **kwargs) -> None:
        self.calls.append(("click", image_name, kwargs))

    def exists(self, image_name: str, **kwargs) -> bool:
        self.calls.append(("exists", image_name, kwargs))
        return True


def test_base_page_uses_explicit_image_template_for_fallbacks() -> None:
    driver = FakeDriver()
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
