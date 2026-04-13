from __future__ import annotations

import pytest

from framework.pytest_fixtures import (
    adb,
    config,
    demo_page,
    device_manager,
    driver,
    ensure_artifact_dirs,
    via_baidu_page,
)
from framework.reporting.hooks import (
    manage_device_case_lifecycle,
    pytest_runtest_makereport,
    pytest_sessionfinish,
)
from framework.reporting.simple_html import pytest_addoption as reporting_pytest_addoption
from framework.reporting.simple_html import pytest_configure as reporting_pytest_configure

__all__ = [
    "adb",
    "config",
    "demo_page",
    "device_manager",
    "driver",
    "ensure_artifact_dirs",
    "manage_device_case_lifecycle",
    "pytest_collection_modifyitems",
    "pytest_addoption",
    "pytest_configure",
    "pytest_runtest_makereport",
    "pytest_sessionfinish",
    "via_baidu_page",
]


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


def _is_parallel_requested(config: pytest.Config) -> bool:
    """判断是否显式启用了并行 worker。"""

    workers = getattr(config.option, "numprocesses", None)
    if workers in (None, 0, "0", "no"):
        return False
    if isinstance(workers, str):
        return workers == "auto" or workers.isdigit() and int(workers) > 1
    return bool(workers) and int(workers) > 1


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """阻止 `device` 用例在 xdist 下并行执行。"""

    if not _is_parallel_requested(config):
        return
    if not any(item.get_closest_marker("device") for item in items):
        return
    raise pytest.UsageError(
        "Device tests do not support pytest-xdist parallel execution. "
        "Run device cases without -n/--numprocesses."
    )
