from __future__ import annotations

from _pytest.stash import Stash

from framework.reporting.runtime_store import get_case_report_store
from framework.reporting.simple_html import add_test_row


class DummyConfig:
    def __init__(self) -> None:
        self._framework_simple_html = {"rows": []}


class DummyItem:
    def __init__(self) -> None:
        self.config = DummyConfig()
        self.nodeid = "tests/test_demo.py::test_case"
        self.stash = Stash()


class DummyReport:
    def __init__(self, when: str = "call") -> None:
        self.when = when
        self.failed = when == "call"
        self.outcome = "failed" if self.failed else "passed"
        self.duration = 1.23
        self.longreprtext = ""
        self.sections: list[tuple[str, str]] = []


class DummyCall:
    excinfo = None


def test_simple_html_prefers_structured_runtime_store_over_sections() -> None:
    item = DummyItem()
    store = get_case_report_store(item)
    store["steps"] = [{"index": 1, "name": "点击搜索", "status": "PASSED"}]
    store["baseline"] = "{'package': 'mark.via'}"
    store["environment"]["precheck"] = "before_prepare.focus=mark.via/.Shell"
    store["environment"]["postcheck"] = "after_reset.focus=com.miui.home/.launcher.Launcher"
    store["failure"] = {
        "reason": "搜索按钮未出现",
        "screenshot": "/tmp/failure.png",
        "xml": "/tmp/failure.xml",
        "phase": "call",
    }

    add_test_row(item, DummyCall(), DummyReport())

    row = item.config._framework_simple_html["rows"][0]
    assert row["screenshot"] == "/tmp/failure.png"
    assert row["xml"] == "/tmp/failure.xml"
    assert row["steps"] == [{"index": 1, "name": "点击搜索", "status": "PASSED"}]
    assert "搜索按钮未出现" in row["message"]
    assert "[Environment Precheck]" in row["message"]
    assert "[Environment Reset]" in row["message"]
