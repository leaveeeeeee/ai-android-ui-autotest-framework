from __future__ import annotations

from pathlib import Path

from framework.core.config import ConfigManager
from framework.device.adb import DeviceSnapshot
from framework.device.manager import DeviceManager


class FakeAdb:
    def __init__(self, state: DeviceSnapshot) -> None:
        self.state = state
        self.calls: list[str] = []

    def wait_for_device(self) -> str:
        self.calls.append("wait_for_device")
        return ""

    def get_state(self) -> str:
        self.calls.append("get_state")
        return "device"

    def current_focus_state(self) -> DeviceSnapshot:
        return DeviceSnapshot(
            focus=self.state.focus,
            package=self.state.package,
            activity=self.state.activity,
            keyboard_visible=self.state.keyboard_visible,
            screen_on=self.state.screen_on,
        )

    def current_focus(self) -> str:
        return self.state.focus

    def screen_is_on(self) -> bool:
        return self.state.screen_on

    def is_keyboard_visible(self) -> bool:
        return self.state.keyboard_visible

    def wake_up(self) -> str:
        self.calls.append("wake_up")
        self.state.screen_on = True
        return ""

    def unlock_screen(self) -> str:
        self.calls.append("unlock_screen")
        return ""

    def press_back(self) -> str:
        self.calls.append("press_back")
        self.state.keyboard_visible = False
        return ""

    def close_system_dialogs(self) -> str:
        self.calls.append("close_system_dialogs")
        self.state.package = "com.miui.home"
        self.state.activity = ".launcher.Launcher"
        self.state.focus = "mCurrentFocus=Window{1 u0 com.miui.home/.launcher.Launcher}"
        self.state.keyboard_visible = False
        return ""

    def start_home(self) -> str:
        self.calls.append("start_home")
        self.state.package = "com.miui.home"
        self.state.activity = ".launcher.Launcher"
        self.state.focus = "mCurrentFocus=Window{1 u0 com.miui.home/.launcher.Launcher}"
        self.state.keyboard_visible = False
        self.state.screen_on = True
        return ""

    def force_stop(self, package: str) -> str:
        self.calls.append(f"force_stop:{package}")
        self.start_home()
        return ""

    def start_activity(self, package: str, activity: str, data_uri: str | None = None) -> str:
        self.calls.append(f"start_activity:{package}/{activity}:{data_uri or ''}")
        self.state.package = package
        self.state.activity = activity
        self.state.focus = f"mCurrentFocus=Window{{1 u0 {package}/{activity}}}"
        self.state.keyboard_visible = False
        self.state.screen_on = True
        return ""

    def is_package_installed(self, package: str) -> bool:
        self.calls.append(f"is_package_installed:{package}")
        return True


class StubDeviceManager(DeviceManager):
    def __init__(self, config: ConfigManager, fake_adb: FakeAdb) -> None:
        super().__init__(config)
        self._fake_adb = fake_adb

    def adb(self) -> FakeAdb:
        return self._fake_adb


def test_prepare_environment_is_state_driven() -> None:
    config = ConfigManager(
        path=Path("config/test.yaml"),
        data={
            "device": {
                "app_package": "mark.via",
                "app_activity": ".Shell",
                "baseline_package": "mark.via",
                "baseline_activity": ".Shell",
                "baseline_url": "https://www.baidu.com",
                "reset_to_home_after_case": True,
            },
            "framework": {
                "default_timeout": 5,
                "default_retry_interval": 0.1,
            },
        },
    )
    fake_adb = FakeAdb(
        DeviceSnapshot(
            focus="mCurrentFocus=Window{1 u0 mark.via/.Shell}",
            package="mark.via",
            activity=".Shell",
            keyboard_visible=True,
            screen_on=False,
        )
    )
    manager = StubDeviceManager(config, fake_adb)

    details = manager.prepare_test_environment()

    assert "wake_up" in fake_adb.calls
    assert "press_back" in fake_adb.calls
    assert "start_home" in fake_adb.calls
    assert any(line == "baseline_ready=true" for line in details)
    assert any("after_prepare.package=com.miui.home" == line for line in details)


def test_reset_to_baseline_relaunches_app_when_not_resetting_home() -> None:
    config = ConfigManager(
        path=Path("config/test.yaml"),
        data={
            "device": {
                "baseline_package": "mark.via",
                "baseline_activity": ".Shell",
                "baseline_url": "https://www.baidu.com",
                "reset_to_home_after_case": False,
            },
            "framework": {
                "default_timeout": 5,
                "default_retry_interval": 0.1,
            },
        },
    )
    fake_adb = FakeAdb(
        DeviceSnapshot(
            focus="mCurrentFocus=Window{1 u0 com.miui.home/.launcher.Launcher}",
            package="com.miui.home",
            activity=".launcher.Launcher",
            keyboard_visible=False,
            screen_on=True,
        )
    )
    manager = StubDeviceManager(config, fake_adb)

    details = manager.reset_to_baseline()

    assert "force_stop:mark.via" in fake_adb.calls
    assert "start_activity:mark.via/.Shell:https://www.baidu.com" in fake_adb.calls
    assert any("after_reset.package=mark.via" == line for line in details)
