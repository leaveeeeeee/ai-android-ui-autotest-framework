from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from framework.core.config import ConfigManager
from framework.core.defaults import default_value
from framework.core.driver import DriverAdapter
from framework.core.logger import init_logging
from framework.core.steps import StepSpec
from framework.device.adb import AdbClient
from framework.device.manager import DeviceManager
from framework.pages.demo_page import DemoPage
from framework.pages.via_baidu_page import ViaBaiduPage
from framework.testing.page_registry import register_page_object
from framework.vision.factory import build_image_engine


@pytest.fixture(scope="session")
def config(request: pytest.FixtureRequest) -> ConfigManager:
    """加载项目配置。"""

    config_path = request.config.getoption("--config")
    manager = ConfigManager.load(config_path)
    init_logging(manager.get("framework", {}) or {})
    return manager


@pytest.fixture(scope="session")
def device_manager(config: ConfigManager) -> DeviceManager:
    """构建设备管理器。"""

    return DeviceManager(config)


@pytest.fixture(scope="session")
def driver(device_manager: DeviceManager) -> Iterator[DriverAdapter]:
    """连接真机 driver。"""

    adapter = device_manager.build_driver()
    try:
        yield adapter.connect()
    except Exception as exc:
        pytest.skip(f"真机驱动不可用，已跳过：{exc}")


@pytest.fixture(scope="session")
def adb(device_manager: DeviceManager) -> AdbClient:
    """返回 ADB 客户端。"""

    return device_manager.adb()


@pytest.fixture()
def demo_page(request: pytest.FixtureRequest, driver: DriverAdapter) -> DemoPage:
    """示例页面对象 fixture。"""

    return register_page_object(request, DemoPage(driver, image_engine=build_image_engine(driver)))


@pytest.fixture()
def via_baidu_page(
    request: pytest.FixtureRequest,
    config: ConfigManager,
    driver: DriverAdapter,
    adb: AdbClient,
) -> ViaBaiduPage:
    """Via 百度搜索页面对象 fixture。"""

    package = config.get("device.app_package", "mark.via")
    activity = config.get("device.app_activity", ".Shell")
    start_url = config.get("device.start_url", "https://www.baidu.com")
    adb.start_activity(package=package, activity=activity, data_uri=start_url)
    driver.record_step(
        StepSpec(
            name="启动业务应用",
            detail=f"启动应用 {package}/{activity} 并打开 {start_url}",
            expected="Via 浏览器打开百度首页。",
            actual=f"已发起启动：{package}/{activity}",
            comparison="PASS",
            logs=f"adb am start -n {package}/{activity} -d {start_url}",
            capture=False,
        )
    )
    return register_page_object(
        request,
        ViaBaiduPage(driver, image_engine=build_image_engine(driver)),
    )


@pytest.fixture(scope="session", autouse=True)
def ensure_artifact_dirs(config: ConfigManager) -> None:
    """提前创建运行所需目录，避免执行中才因路径缺失报错。"""

    for relative in (
        config.get("framework.screenshot_dir", default_value("framework.screenshot_dir")),
        config.get("framework.log_dir", default_value("framework.log_dir")),
        config.get("framework.page_source_dir", default_value("framework.page_source_dir")),
        config.get("framework.report_dir", default_value("framework.report_dir")),
        config.get("framework.allure_results_dir", default_value("framework.allure_results_dir")),
        config.get("framework.allure_report_dir", default_value("framework.allure_report_dir")),
        config.get("framework.ai_prompt_dir", default_value("framework.ai_prompt_dir")),
        config.get("framework.image_debug_dir", default_value("framework.image_debug_dir")),
        config.get("framework.image_template_dir", default_value("framework.image_template_dir")),
    ):
        Path(relative).mkdir(parents=True, exist_ok=True)
