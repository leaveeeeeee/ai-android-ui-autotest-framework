from __future__ import annotations

from framework.pages.via_baidu_page import ViaBaiduPage
from tests.fakes import FakeImageEngine


class FakeViaDriver:
    def __init__(self, *, search_visible: bool) -> None:
        self.framework_config = {}
        self.search_visible = search_visible
        self.recorded_steps = []
        self.bounds_requests: list[str] = []
        self.clicks: list[str] = []
        self.set_text_calls: list[tuple[str, str]] = []
        self.exists_calls: list[str] = []
        self.result_visible = False

    def record_step(self, spec) -> None:  # noqa: ANN001
        self.recorded_steps.append(spec)

    def exists(self, locator) -> bool:  # noqa: ANN001
        self.exists_calls.append(locator.name)
        if locator.name == "baidu_search_input":
            return self.search_visible
        if locator.name.startswith("result_keyword_"):
            return self.result_visible
        return True

    def get_bounds(self, locator) -> tuple[int, int, int, int] | None:  # noqa: ANN001
        self.bounds_requests.append(locator.name)
        return (10, 20, 110, 60)

    def click(self, locator) -> None:  # noqa: ANN001
        self.clicks.append(locator.name)

    def set_text(self, locator, value: str) -> None:  # noqa: ANN001
        self.set_text_calls.append((locator.name, value))


def test_via_baidu_search_uses_step_context_names_when_search_box_is_visible() -> None:
    driver = FakeViaDriver(search_visible=True)
    page = ViaBaiduPage(driver=driver, image_engine=FakeImageEngine())

    page.search("chatgpt")

    assert [step.name for step in driver.recorded_steps] == [
        "检查首页搜索框",
        "点击搜索框",
        "输入搜索词",
        "点击搜索按钮",
    ]
    assert [step.status for step in driver.recorded_steps] == [
        "PASSED",
        "PASSED",
        "PASSED",
        "PASSED",
    ]
    assert driver.set_text_calls == [("baidu_search_input", "chatgpt")]
    assert driver.clicks == ["baidu_search_input", "baidu_search_button"]


def test_via_baidu_search_adds_open_panel_step_when_search_box_is_hidden() -> None:
    driver = FakeViaDriver(search_visible=False)
    page = ViaBaiduPage(driver=driver, image_engine=FakeImageEngine())

    page.search("chatgpt")

    assert [step.name for step in driver.recorded_steps] == [
        "检查首页搜索框",
        "打开搜索面板",
        "点击搜索框",
        "输入搜索词",
        "点击搜索按钮",
    ]
    assert driver.clicks[0] == "top_address_bar"
