from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from framework.core.config import ConfigManager
from framework.core.driver import DriverAdapter
from framework.core.exceptions import DeviceConnectionError
from framework.device.adb import AdbClient


@dataclass(slots=True)
class DeviceManager:
    """统一管理设备级前后置动作。"""

    config: ConfigManager

    def build_driver(self) -> DriverAdapter:
        """基于当前配置构建 `DriverAdapter`。"""
        serial = self.config.get("device.serial", "")
        timeout = float(self.config.get("framework.default_timeout", 10))
        interval = float(self.config.get("framework.default_retry_interval", 0.5))
        framework_config = self.config.get("framework", {}) or {}
        return DriverAdapter(
            serial=serial,
            default_timeout=timeout,
            retry_interval=interval,
            framework_config=framework_config,
        )

    def adb(self) -> AdbClient:
        """构建 ADB 客户端。"""
        return AdbClient(serial=self.config.get("device.serial", ""))

    def prepare_test_environment(self) -> list[str]:
        """执行用例前置检查并恢复基线环境。

        这一步通常在 `@pytest.mark.device` 用例开始前自动执行。
        """
        adb = self.adb()
        details: list[str] = []
        adb.wait_for_device()
        state = adb.get_state()
        if state != "device":
            raise DeviceConnectionError(f"ADB device state is '{state}', expected 'device'.")
        details.append(f"adb_state={state}")

        adb.wake_up()
        adb.unlock_screen()
        details.append("screen_awake=true")
        details.extend(self._exit_transient_state())

        package = self.config.get("device.app_package", "")
        if package:
            installed = adb.is_package_installed(package)
            if not installed:
                raise DeviceConnectionError(f"Required package is not installed: {package}")
            details.append(f"package_installed={package}")

        details.append(f"focus={adb.current_focus()}")
        self.reset_to_baseline()
        details.append("baseline_ready=true")
        return details

    def reset_to_baseline(self) -> list[str]:
        """执行用例后置恢复。

        默认行为：
        - 退出临时状态
        - 回桌面
        - 强停业务应用
        - 根据配置决定停在桌面还是重新进入基线页
        """
        adb = self.adb()
        details: list[str] = []

        baseline_package = self.config.get("device.baseline_package") or self.config.get(
            "device.app_package", ""
        )
        baseline_activity = self.config.get("device.baseline_activity") or self.config.get(
            "device.app_activity", ""
        )
        baseline_url = self.config.get("device.baseline_url") or self.config.get(
            "device.start_url", ""
        )
        reset_to_home = bool(self.config.get("device.reset_to_home_after_case", False))

        details.extend(self._exit_transient_state())
        adb.go_home()
        time.sleep(0.8)
        adb.press_back()
        time.sleep(0.5)
        details.append("pressed_home=true")
        details.append("back_after_home=true")

        if baseline_package:
            adb.force_stop(baseline_package)
            details.append(f"force_stopped={baseline_package}")

        if reset_to_home:
            details.append("baseline=system_home")
            return details

        if baseline_package and baseline_activity:
            adb.start_activity(
                package=baseline_package,
                activity=baseline_activity,
                data_uri=baseline_url or None,
            )
            details.append(
                f"baseline_started={baseline_package}/{baseline_activity}"
                + (f" url={baseline_url}" if baseline_url else "")
            )

        details.append(f"focus={adb.current_focus()}")
        return details

    def baseline_description(self) -> dict[str, Any]:
        """返回当前基线页定义，便于写入报告。"""
        return {
            "package": self.config.get("device.baseline_package")
            or self.config.get("device.app_package", ""),
            "activity": self.config.get("device.baseline_activity")
            or self.config.get("device.app_activity", ""),
            "url": self.config.get("device.baseline_url")
            or self.config.get("device.start_url", ""),
            "reset_to_home_after_case": bool(
                self.config.get("device.reset_to_home_after_case", False)
            ),
        }

    def _exit_transient_state(self) -> list[str]:
        """尽量退出弹窗、输入法、半打开页面等临时状态。"""
        adb = self.adb()
        details: list[str] = []
        for index in range(2):
            adb.press_back()
            time.sleep(0.3)
            details.append(f"pressed_back_{index + 1}=true")
        return details
