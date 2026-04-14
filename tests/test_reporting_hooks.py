from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from framework.core.steps import StepSpec
from framework.device.adb import DeviceSnapshot
from framework.reporting import hooks as reporting_hooks
from framework.reporting.runtime_store import get_case_report_store
from tests.fakes import FakeAdb


class DummyConfig:
    def __init__(self, *, run_id: str = "run_001") -> None:
        self._framework_simple_html = {"run_id": run_id, "rows": []}


class DummyNode:
    def __init__(
        self,
        *,
        nodeid: str = "tests/test_demo.py::test_device_case",
        config: DummyConfig | None = None,
        is_device: bool = True,
    ) -> None:
        self.nodeid = nodeid
        self.config = config or DummyConfig()
        self.stash: dict[object, object] = {}
        self._is_device = is_device

    def get_closest_marker(self, name: str) -> object | None:
        if name == "device" and self._is_device:
            return object()
        return None


class DummyRequest:
    def __init__(self, node: DummyNode, fixtures: dict[str, object]) -> None:
        self.node = node
        self.config = node.config
        self._fixtures = fixtures

    def getfixturevalue(self, name: str) -> object:
        return self._fixtures[name]


class FakeLifecycleDriver:
    def __init__(self) -> None:
        self.recorded_steps: list[dict[str, object]] = []
        self.recorders: list[object | None] = []
        self.providers: list[object | None] = []
        self.runtime_contexts: list[dict[str, str]] = []
        self.clear_runtime_context_calls = 0

    def set_step_recorder(self, recorder) -> None:  # noqa: ANN001
        self.recorders.append(recorder)

    def set_step_context_provider(self, provider) -> None:  # noqa: ANN001
        self.providers.append(provider)

    def set_runtime_context(self, **context: str) -> None:
        self.runtime_contexts.append(context)

    def clear_runtime_context(self) -> None:
        self.clear_runtime_context_calls += 1

    def record_step(self, spec: StepSpec) -> None:
        self.recorded_steps.append(spec.__dict__.copy())


class FakeDeviceManager:
    def __init__(
        self,
        *,
        precheck_lines: list[str] | None = None,
        postcheck_lines: list[str] | None = None,
        teardown_error: Exception | None = None,
    ) -> None:
        self.precheck_lines = precheck_lines or ["adb ready", "baseline restored"]
        self.postcheck_lines = postcheck_lines or ["reset complete"]
        self.teardown_error = teardown_error

    def prepare_test_environment(self) -> list[str]:
        return self.precheck_lines

    def baseline_description(self) -> str:
        return "Via home baseline"

    def reset_to_baseline(self) -> list[str]:
        if self.teardown_error is not None:
            raise self.teardown_error
        return self.postcheck_lines


class FakeOutcome:
    def __init__(self, report) -> None:  # noqa: ANN001
        self.report = report

    def get_result(self):  # noqa: ANN201
        return self.report


class FakeExtras:
    @staticmethod
    def text(content: str, name: str) -> tuple[str, str, str]:
        return ("text", name, content)

    @staticmethod
    def png(content: str, name: str) -> tuple[str, str, str]:
        return ("png", name, content)


class FakePage:
    def __init__(self, screenshot_path: Path, source_path: Path) -> None:
        self.screenshot_path = screenshot_path
        self.source_path = source_path
        self.saved_cases: list[str] = []

    def save_failure_artifacts(self, case_name: str) -> tuple[str, str]:
        self.saved_cases.append(case_name)
        return str(self.screenshot_path), str(self.source_path)


def _drain_fixture(generator) -> None:  # noqa: ANN001
    with pytest.raises(StopIteration):
        next(generator)


def test_manage_device_case_lifecycle_writes_store_and_cleans_up(monkeypatch) -> None:
    allure_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        reporting_hooks,
        "allure_attach_text",
        lambda name, content: allure_calls.append((name, content)),
    )

    node = DummyNode()
    driver = FakeLifecycleDriver()
    adb = FakeAdb(DeviceSnapshot(focus="Window{1 u0 mark.via/.Shell}", package="mark.via"))
    request = DummyRequest(node, {"driver": driver, "adb": adb})
    device_manager = FakeDeviceManager()

    lifecycle = reporting_hooks.manage_device_case_lifecycle.__wrapped__(request, device_manager)
    next(lifecycle)

    store = get_case_report_store(node)
    assert store["environment"]["precheck"] == "adb ready\nbaseline restored"
    assert store["baseline"] == "Via home baseline"
    assert node._framework_steps is store["steps"]
    assert driver.runtime_contexts == [
        {"run_id": "run_001", "case_name": "tests_test_demo.py_test_device_case"}
    ]
    assert callable(driver.providers[0])
    assert driver.providers[0]() == {"focus_window": "Window{1 u0 mark.via/.Shell}"}
    assert driver.recorded_steps[0]["name"] == "环境前置检查"
    assert allure_calls[:2] == [
        ("Environment Precheck", "adb ready\nbaseline restored"),
        ("Baseline", "Via home baseline"),
    ]

    _drain_fixture(lifecycle)

    assert store["environment"]["postcheck"] == "reset complete"
    assert driver.recorded_steps[-1]["name"] == "环境后置恢复"
    assert driver.recorders[-1] is None
    assert driver.providers[-1] is None
    assert driver.clear_runtime_context_calls == 1
    assert allure_calls[-1] == ("Environment Reset", "reset complete")


def test_manage_device_case_lifecycle_propagates_teardown_failure(monkeypatch) -> None:
    monkeypatch.setattr(reporting_hooks, "allure_attach_text", lambda *args, **kwargs: None)

    node = DummyNode()
    driver = FakeLifecycleDriver()
    adb = FakeAdb(DeviceSnapshot(focus="Window{1 u0 mark.via/.Shell}", package="mark.via"))
    request = DummyRequest(node, {"driver": driver, "adb": adb})
    device_manager = FakeDeviceManager(teardown_error=RuntimeError("reset failed"))

    lifecycle = reporting_hooks.manage_device_case_lifecycle.__wrapped__(request, device_manager)
    next(lifecycle)

    with pytest.raises(RuntimeError, match="reset failed"):
        next(lifecycle)

    store = get_case_report_store(node)
    assert store["environment"]["postcheck"] == "reset failed"
    assert driver.recorded_steps[-1]["status"] == "FAILED"
    assert driver.recorders[-1] is None
    assert driver.providers[-1] is None
    assert driver.clear_runtime_context_calls == 1


def test_pytest_runtest_makereport_collects_failure_artifacts(monkeypatch, tmp_path: Path) -> None:
    allure_calls: list[tuple[str, str]] = []
    add_row_calls: list[tuple[object, object, object]] = []
    screenshot_path = tmp_path / "failure.png"
    source_path = tmp_path / "failure.xml"
    screenshot_path.write_bytes(b"fake-png")
    source_path.write_text("<hierarchy />", encoding="utf-8")

    node = DummyNode(is_device=False)
    node._framework_precheck = "adb ready"
    page = FakePage(screenshot_path, source_path)
    store = get_case_report_store(node)
    store["steps"] = [{"name": "step", "duration_ms": 12}]

    monkeypatch.setattr(reporting_hooks, "get_latest_page_object", lambda item: page)
    monkeypatch.setattr(
        reporting_hooks,
        "allure_attach_text",
        lambda name, content: allure_calls.append((name, content)),
    )
    monkeypatch.setattr(
        reporting_hooks,
        "allure_attach_png",
        lambda path, name: allure_calls.append((name, str(path))),
    )
    monkeypatch.setattr(
        reporting_hooks,
        "allure_attach_xml",
        lambda path, name: allure_calls.append((name, str(path))),
    )
    monkeypatch.setattr(reporting_hooks, "pytest_html_extras", FakeExtras())
    monkeypatch.setattr(
        reporting_hooks,
        "reporting_add_test_row",
        lambda item, call, report: add_row_calls.append((item, call, report)),
    )

    report = SimpleNamespace(
        failed=True,
        when="call",
        longreprtext="AssertionError: expected result",
        extras=[],
        outcome="failed",
        duration=1.23,
    )
    call = SimpleNamespace(excinfo=SimpleNamespace(value=AssertionError("expected result")))

    hook = reporting_hooks.pytest_runtest_makereport(node, call)
    next(hook)
    with pytest.raises(StopIteration):
        hook.send(FakeOutcome(report))

    failure = store["failure"]
    assert failure["reason"] == "AssertionError: expected result"
    assert failure["screenshot"] == str(screenshot_path)
    assert failure["xml"] == str(source_path)
    assert failure["phase"] == "call"
    assert page.saved_cases == ["tests_test_demo.py_test_device_case"]
    assert ("Failure Reason", "AssertionError: expected result") in allure_calls
    assert ("Failure Screenshot", str(screenshot_path)) in allure_calls
    assert ("Failure Page Source", str(source_path)) in allure_calls
    assert ("text", "Failure Reason", "AssertionError: expected result") in report.extras
    assert ("text", "Environment Precheck", "adb ready") in report.extras
    assert any(extra[:2] == ("png", "Failure Screenshot") for extra in report.extras)
    assert any(extra[:2] == ("text", "Page Source") for extra in report.extras)
    assert add_row_calls == [(node, call, report)]
