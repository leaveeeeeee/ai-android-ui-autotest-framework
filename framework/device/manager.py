from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from framework.core.config import ConfigManager
from framework.core.defaults import default_value
from framework.core.driver import DriverAdapter
from framework.core.exceptions import DeviceConnectionError
from framework.core.logger import init_logging
from framework.core.waiter import Waiter
from framework.device.adb import AdbClient, DeviceSnapshot


@dataclass
class DeviceManager:
    """统一管理设备级前后置动作。"""

    config: ConfigManager
    waiter: Waiter = field(init=False, repr=False)
    _adb_client: AdbClient | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        init_logging(self.config.get("framework", {}) or {})
        timeout = float(
            self.config.get("framework.default_timeout", default_value("framework.default_timeout"))
        )
        interval = float(
            self.config.get(
                "framework.default_retry_interval",
                default_value("framework.default_retry_interval"),
            )
        )
        self.waiter = Waiter(timeout=timeout, interval=interval)

    @property
    def serial(self) -> str:
        """返回当前配置的设备序列号。"""

        return str(self.config.get("device.serial", "") or "")

    def build_driver(self) -> DriverAdapter:
        """基于当前配置构建 `DriverAdapter`。"""
        framework_config = self.config.get("framework", {}) or {}
        return DriverAdapter(
            serial=self.serial,
            default_timeout=self.waiter.timeout,
            retry_interval=self.waiter.interval,
            framework_config=framework_config,
        )

    def adb(self) -> AdbClient:
        """构建 ADB 客户端。"""
        if self._adb_client is None:
            self._adb_client = AdbClient(serial=self.serial)
        return self._adb_client

    def prepare_test_environment(self) -> list[str]:
        """执行用例前置检查并恢复基线环境。"""
        adb = self.adb()
        details: list[str] = []
        adb.wait_for_device()
        state = adb.get_state()
        if state != "device":
            raise DeviceConnectionError(
                "ADB device state is "
                f"{state!r} for serial {self.serial or 'default'}, expected 'device'."
            )
        details.append(f"adb_state={state}")

        before_snapshot = adb.current_focus_state()
        details.extend(self._snapshot_lines("before_prepare", before_snapshot))
        details.extend(self._ensure_interactive(adb))
        details.extend(self._stabilize_foreground(adb))

        package = self.config.get("device.app_package", "")
        if package:
            installed = adb.is_package_installed(package)
            if not installed:
                raise DeviceConnectionError(
                    "Required package is not installed: "
                    f"package={package}, serial={self.serial or 'default'}"
                )
            details.append(f"package_installed={package}")

        details.extend(self.reset_to_baseline())
        after_snapshot = adb.current_focus_state()
        details.extend(self._snapshot_lines("after_prepare", after_snapshot))
        details.append("baseline_ready=true")
        return details

    def reset_to_baseline(self) -> list[str]:
        """执行用例后置恢复。"""
        adb = self.adb()
        details: list[str] = []
        details.extend(self._snapshot_lines("before_reset", adb.current_focus_state()))
        details.extend(self._ensure_interactive(adb))
        details.extend(self._stabilize_foreground(adb))
        details.extend(self._ensure_home(adb))

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

        if baseline_package:
            adb.force_stop(baseline_package)
            details.append(f"force_stopped={baseline_package}")
            details.extend(self._ensure_home(adb))

        if reset_to_home:
            details.append("baseline=system_home")
            details.extend(self._snapshot_lines("after_reset", adb.current_focus_state()))
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
            self.waiter.until_true(
                lambda: self._is_target_focus(
                    adb.current_focus_state(),
                    package=baseline_package,
                    activity=baseline_activity,
                ),
                message=(
                    "Failed to reach configured baseline page: "
                    f"{baseline_package}/{baseline_activity} "
                    f"for serial {self.serial or 'default'}"
                ),
                timeout=8.0,
                interval=0.3,
                exception_cls=DeviceConnectionError,
            )

        details.extend(self._snapshot_lines("after_reset", adb.current_focus_state()))
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

    def _ensure_interactive(self, adb: AdbClient) -> list[str]:
        """确保设备处于可交互状态。"""
        details: list[str] = []
        snapshot = adb.current_focus_state()
        if not snapshot.screen_on:
            adb.wake_up()
            self.waiter.until_true(
                adb.screen_is_on,
                message=f"Failed to wake screen for serial {self.serial or 'default'}.",
                timeout=5.0,
                interval=0.2,
                exception_cls=DeviceConnectionError,
            )
            details.append("screen_awake=true")
        else:
            details.append("screen_awake=already_on")

        adb.unlock_screen()
        details.append("keyguard_dismiss_requested=true")
        return details

    def _stabilize_foreground(self, adb: AdbClient, max_rounds: int = 6) -> list[str]:
        """按设备当前状态逐步收敛前台环境。"""
        details: list[str] = []
        for index in range(max_rounds):
            snapshot = adb.current_focus_state()
            details.extend(self._snapshot_lines(f"stabilize_{index + 1}", snapshot))
            if snapshot.keyboard_visible:
                adb.press_back()
                details.append("dismiss_keyboard=back")
                self.waiter.until_true(
                    lambda: not adb.is_keyboard_visible(),
                    message=f"Failed to dismiss keyboard for serial {self.serial or 'default'}.",
                    timeout=2.0,
                    interval=0.2,
                    exception_cls=DeviceConnectionError,
                )
                continue

            if self._is_transient_package(snapshot.package):
                adb.close_system_dialogs()
                details.append(f"close_system_dialogs={snapshot.package or 'unknown'}")
                self.waiter.until_true(
                    lambda: not self._is_transient_package(adb.current_focus_state().package),
                    message=(
                        "Failed to close system transient layer "
                        f"for serial {self.serial or 'default'}."
                    ),
                    timeout=2.0,
                    interval=0.2,
                    exception_cls=DeviceConnectionError,
                )
                continue

            break
        return details

    def _ensure_home(self, adb: AdbClient) -> list[str]:
        """确保当前设备已经回到桌面稳态。"""
        details: list[str] = []
        snapshot = adb.current_focus_state()
        if self._is_home_focus(snapshot):
            details.append("baseline_home=already_on_home")
            return details

        adb.start_home()
        details.append("home_intent_sent=true")
        self.waiter.until_true(
            lambda: self._is_home_focus(adb.current_focus_state()),
            message=f"Failed to return to launcher home for serial {self.serial or 'default'}.",
            timeout=5.0,
            interval=0.3,
            exception_cls=DeviceConnectionError,
        )
        details.extend(self._snapshot_lines("home_ready", adb.current_focus_state()))
        return details

    def _snapshot_lines(self, prefix: str, snapshot: DeviceSnapshot) -> list[str]:
        """把结构化状态展开成报告可消费的文本明细。"""
        return [
            f"{prefix}.focus={snapshot.focus}",
            f"{prefix}.package={snapshot.package or 'unknown'}",
            f"{prefix}.activity={snapshot.activity or 'unknown'}",
            f"{prefix}.keyboard_visible={snapshot.keyboard_visible}",
            f"{prefix}.screen_on={snapshot.screen_on}",
        ]

    def _is_home_focus(self, snapshot: DeviceSnapshot) -> bool:
        """判断当前焦点是否已经是桌面。"""
        home_packages = set(
            self.config.get("device.home_packages", default_value("device.home_packages"))
        )
        return snapshot.package in home_packages and not snapshot.keyboard_visible

    def _is_transient_package(self, package: str) -> bool:
        """判断当前前台是否为系统临时层。"""
        transient_packages = set(
            self.config.get("device.transient_packages", default_value("device.transient_packages"))
        )
        return package in transient_packages

    def _is_target_focus(
        self,
        snapshot: DeviceSnapshot,
        *,
        package: str,
        activity: str,
    ) -> bool:
        """判断当前焦点是否已到达目标基线页。"""
        if snapshot.package != package:
            return False
        activity_suffix = activity.split("/")[-1]
        if not activity_suffix:
            return True
        return snapshot.activity.endswith(activity_suffix)
