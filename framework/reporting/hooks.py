from __future__ import annotations

import base64
from pathlib import Path

import pytest

from framework.device.manager import DeviceManager
from framework.reporting.allure_helper import attach_png as allure_attach_png
from framework.reporting.allure_helper import attach_text as allure_attach_text
from framework.reporting.allure_helper import attach_xml as allure_attach_xml
from framework.reporting.execution_trace import ExecutionTraceRecorder
from framework.reporting.runtime_store import get_case_report_store
from framework.reporting.simple_html import add_test_row as reporting_add_test_row
from framework.reporting.simple_html import get_simple_html_run_id
from framework.reporting.simple_html import pytest_sessionfinish as reporting_pytest_sessionfinish
from framework.testing.page_registry import get_latest_page_object

try:
    from pytest_html import extras as pytest_html_extras
except Exception:  # pragma: no cover - 运行环境可能未安装该可选依赖
    pytest_html_extras = None


@pytest.fixture(autouse=True)
def manage_device_case_lifecycle(
    request: pytest.FixtureRequest,
    device_manager: DeviceManager,
):
    """给真机用例统一挂接前后置。"""

    if request.node.get_closest_marker("device") is None:
        yield
        return

    driver = request.getfixturevalue("driver")
    adb = request.getfixturevalue("adb")
    case_name = request.node.nodeid.replace("/", "_").replace("::", "_")
    run_id = get_simple_html_run_id(request.config)
    recorder = ExecutionTraceRecorder(case_name, run_id=run_id)
    store = get_case_report_store(request.node)
    store["steps"] = recorder.steps
    driver.set_step_recorder(recorder)
    driver.set_step_context_provider(lambda: {"focus_window": adb.current_focus()})
    driver.set_runtime_context(run_id=run_id, case_name=case_name)
    request.node._framework_steps = recorder.steps

    try:
        precheck_lines = device_manager.prepare_test_environment()
        request.node._framework_precheck = "\n".join(precheck_lines)
        request.node._framework_baseline = str(device_manager.baseline_description())
        store["environment"]["precheck"] = request.node._framework_precheck
        store["baseline"] = request.node._framework_baseline
        allure_attach_text("Environment Precheck", request.node._framework_precheck)
        allure_attach_text("Baseline", request.node._framework_baseline)
        driver.record_step(
            name="环境前置检查",
            detail=request.node._framework_precheck,
            expected="设备可用，并恢复到统一初始页。",
            actual="环境检查通过，设备已恢复到基线页。",
            comparison="PASS",
            logs=request.node._framework_precheck,
        )
    except Exception as exc:
        request.node._framework_precheck = str(exc)
        store["environment"]["precheck"] = request.node._framework_precheck
        driver.record_step(
            name="环境前置检查",
            detail=str(exc),
            expected="设备可用，并恢复到统一初始页。",
            actual="环境检查失败。",
            comparison="FAIL",
            status="FAILED",
            logs=str(exc),
        )
        driver.set_step_recorder(None)
        driver.set_step_context_provider(None)
        driver.clear_runtime_context()
        raise

    try:
        yield
    finally:
        try:
            postcheck_lines = device_manager.reset_to_baseline()
            request.node._framework_postcheck = "\n".join(postcheck_lines)
            store["environment"]["postcheck"] = request.node._framework_postcheck
            allure_attach_text("Environment Reset", request.node._framework_postcheck)
            driver.record_step(
                name="环境后置恢复",
                detail=request.node._framework_postcheck,
                expected="设备返回桌面或统一基线页。",
                actual="后置恢复完成。",
                comparison="PASS",
                logs=request.node._framework_postcheck,
            )
        except Exception as exc:
            request.node._framework_postcheck = str(exc)
            store["environment"]["postcheck"] = request.node._framework_postcheck
            allure_attach_text("Environment Reset", request.node._framework_postcheck)
            driver.record_step(
                name="环境后置恢复",
                detail=str(exc),
                expected="设备返回桌面或统一基线页。",
                actual="后置恢复失败。",
                comparison="FAIL",
                status="FAILED",
                logs=str(exc),
            )
            raise
        finally:
            driver.set_step_recorder(None)
            driver.set_step_context_provider(None)
            driver.clear_runtime_context()


def _attach_pytest_html_extras(
    item: pytest.Item,
    report: pytest.TestReport,
    failure_reason: str,
    screenshot_path: str | None,
    source_path: str | None,
) -> None:
    """把失败信息补充进 pytest-html 附件。"""

    if pytest_html_extras is None:
        return

    extras = getattr(report, "extras", [])
    if failure_reason:
        extras.append(pytest_html_extras.text(failure_reason, name="Failure Reason"))
    if screenshot_path and Path(screenshot_path).exists():
        extras.append(
            pytest_html_extras.png(
                base64.b64encode(Path(screenshot_path).read_bytes()).decode("utf-8"),
                name="Failure Screenshot",
            )
        )
    if source_path and Path(source_path).exists():
        extras.append(
            pytest_html_extras.text(
                Path(source_path).read_text(encoding="utf-8", errors="ignore"),
                name="Page Source",
            )
        )

    precheck = getattr(item, "_framework_precheck", "")
    if precheck:
        extras.append(pytest_html_extras.text(precheck, name="Environment Precheck"))
    report.extras = extras


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    """在每个阶段结束后收集失败现场与报告数据。"""

    outcome = yield
    report = outcome.get_result()
    failure_reason = report.longreprtext.strip() if report.failed else ""
    screenshot_path: str | None = None
    source_path: str | None = None
    store = get_case_report_store(item)

    if report.failed:
        page = get_latest_page_object(item)
        if page is not None:
            case_name = item.nodeid.replace("/", "_").replace("::", "_")
            screenshot_path, source_path = page.save_failure_artifacts(case_name)

        if failure_reason:
            allure_attach_text("Failure Reason", failure_reason)

        if screenshot_path:
            allure_attach_png(screenshot_path, "Failure Screenshot")
        if source_path:
            allure_attach_xml(source_path, "Failure Page Source")

        store["failure"] = {
            "reason": failure_reason,
            "screenshot": screenshot_path or "",
            "xml": source_path or "",
            "phase": report.when,
        }

        _attach_pytest_html_extras(
            item=item,
            report=report,
            failure_reason=failure_reason,
            screenshot_path=screenshot_path,
            source_path=source_path,
        )
    elif report.when == "call":
        store["failure"] = {
            "reason": "",
            "screenshot": "",
            "xml": "",
            "phase": report.when,
        }

    reporting_add_test_row(item, call, report)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """pytest 结束时输出结构化 HTML 报告。"""

    reporting_pytest_sessionfinish(session, exitstatus)
