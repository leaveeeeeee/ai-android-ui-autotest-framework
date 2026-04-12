from __future__ import annotations
"""pytest 公共入口。

主要职责：
- 注册框架自定义参数
- 初始化设备与页面 fixture
- 为真机用例挂接统一前后置
- 在失败时补充截图、页面层级和报告数据
"""

from pathlib import Path

import pytest

from framework.core.config import ConfigManager
from framework.device.manager import DeviceManager
from framework.pages.demo_page import DemoPage
from framework.pages.via_baidu_page import ViaBaiduPage
from framework.reporting.execution_trace import ExecutionTraceRecorder
from framework.reporting.allure_helper import attach_png as allure_attach_png
from framework.reporting.allure_helper import attach_text as allure_attach_text
from framework.reporting.allure_helper import attach_xml as allure_attach_xml
from framework.reporting.simple_html import pytest_addoption as reporting_pytest_addoption
from framework.reporting.simple_html import add_test_row as reporting_add_test_row
from framework.reporting.simple_html import pytest_configure as reporting_pytest_configure
from framework.reporting.simple_html import pytest_sessionfinish as reporting_pytest_sessionfinish

try:
    from pytest_html import extras as pytest_html_extras
except Exception:  # pragma: no cover - 运行环境可能未安装该可选依赖
    pytest_html_extras = None


def pytest_addoption(parser: pytest.Parser) -> None:
    """注册框架自定义命令行参数。"""
    reporting_pytest_addoption(parser)
    parser.addoption(
        "--config",
        action="store",
        default="config/config.yaml",
        help="指定框架配置文件路径，默认使用 config/config.yaml。",
    )


def pytest_configure(config: pytest.Config) -> None:
    """初始化报告插件。"""
    reporting_pytest_configure(config)


@pytest.fixture(scope="session")
def config(request: pytest.FixtureRequest) -> ConfigManager:
    """加载项目配置。"""
    config_path = request.config.getoption("--config")
    return ConfigManager.load(config_path)


@pytest.fixture(scope="session")
def device_manager(config: ConfigManager) -> DeviceManager:
    """构建设备管理器。"""
    return DeviceManager(config)


@pytest.fixture(scope="session")
def driver(device_manager: DeviceManager):
    """连接真机 driver。

    如果设备不可用，则直接跳过依赖真机的用例。
    """
    adapter = device_manager.build_driver()
    try:
        yield adapter.connect()
    except Exception as exc:
        pytest.skip(f"真机驱动不可用，已跳过：{exc}")


@pytest.fixture(scope="session")
def adb(device_manager: DeviceManager):
    """返回 ADB 客户端。"""
    return device_manager.adb()


@pytest.fixture()
def demo_page(driver) -> DemoPage:
    """示例页面对象 fixture。"""
    return DemoPage(driver)


@pytest.fixture()
def via_baidu_page(config: ConfigManager, driver, adb) -> ViaBaiduPage:
    """Via 百度搜索页面对象 fixture。

    在返回页面对象前，会先启动 Via 并打开目标 URL。
    """
    package = config.get("device.app_package", "mark.via")
    activity = config.get("device.app_activity", ".Shell")
    start_url = config.get("device.start_url", "https://www.baidu.com")
    adb.start_activity(package=package, activity=activity, data_uri=start_url)
    driver.record_step(
        name="启动业务应用",
        detail=f"启动应用 {package}/{activity} 并打开 {start_url}",
        expected="Via 浏览器打开百度首页。",
        actual=f"已发起启动：{package}/{activity}",
        comparison="PASS",
        logs=f"adb am start -n {package}/{activity} -d {start_url}",
    )
    return ViaBaiduPage(driver)


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
    recorder = ExecutionTraceRecorder(case_name)
    driver.set_step_recorder(recorder)
    driver.set_step_context_provider(lambda: {"focus_window": adb.current_focus()})
    request.node._framework_steps = recorder.steps

    try:
        precheck_lines = device_manager.prepare_test_environment()
        request.node._framework_precheck = "\n".join(precheck_lines)
        request.node._framework_baseline = str(device_manager.baseline_description())
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
        driver.record_step(
            name="环境前置检查",
            detail=str(exc),
            expected="设备可用，并恢复到统一初始页。",
            actual="环境检查失败。",
            comparison="FAIL",
            status="FAILED",
            logs=str(exc),
        )
        raise

    try:
        yield
    finally:
        try:
            postcheck_lines = device_manager.reset_to_baseline()
            request.node._framework_postcheck = "\n".join(postcheck_lines)
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


def _get_page_fixture(item: pytest.Item):
    """从当前用例上下文中取出已注入的页面对象。"""
    for fixture_name in ("demo_page", "via_baidu_page"):
        page = item.funcargs.get(fixture_name)
        if page is not None:
            return page
    return None


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
                Path(screenshot_path).read_bytes(),
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

    if report.failed:
        page = _get_page_fixture(item)
        if page is not None:
            case_name = item.nodeid.replace("/", "_").replace("::", "_")
            screenshot_path, source_path = page.save_failure_artifacts(case_name)
            item.add_report_section(report.when, "failure-artifacts", f"{screenshot_path}\n{source_path}")

        if failure_reason:
            item.add_report_section(report.when, "failure-reason", failure_reason)
            allure_attach_text("Failure Reason", failure_reason)

        precheck = getattr(item, "_framework_precheck", "")
        if precheck:
            item.add_report_section(report.when, "environment-precheck", precheck)

        if screenshot_path:
            allure_attach_png(screenshot_path, "Failure Screenshot")
        if source_path:
            allure_attach_xml(source_path, "Failure Page Source")

        _attach_pytest_html_extras(
            item=item,
            report=report,
            failure_reason=failure_reason,
            screenshot_path=screenshot_path,
            source_path=source_path,
        )

    reporting_add_test_row(item, call, report)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """pytest 结束时输出结构化 HTML 报告。"""
    reporting_pytest_sessionfinish(session, exitstatus)


@pytest.fixture(scope="session", autouse=True)
def ensure_artifact_dirs(config: ConfigManager) -> None:
    """提前创建运行所需目录，避免执行中才因路径缺失报错。"""
    for relative in (
        config.get("framework.screenshot_dir", "artifacts/report_data/screenshots"),
        config.get("framework.log_dir", "artifacts/report_data/logs"),
        config.get("framework.page_source_dir", "artifacts/report_data/page_source"),
        config.get("framework.report_dir", "artifacts/reports"),
        config.get("framework.allure_results_dir", "artifacts/report_data/allure-results"),
        config.get("framework.allure_report_dir", "artifacts/report_data/allure-report"),
        config.get("framework.ai_prompt_dir", "artifacts/report_data/ai-prompts"),
        config.get("framework.image_debug_dir", "artifacts/report_data/image_debug"),
        config.get("framework.image_template_dir", "assets/images"),
    ):
        Path(relative).mkdir(parents=True, exist_ok=True)
