from __future__ import annotations

from pathlib import Path

import pytest

from framework.core.config import ConfigManager
from framework.core.exceptions import DeviceConnectionError
from framework.device.adb import DeviceSnapshot
from framework.device.manager import DeviceManager
from tests.fakes import FakeAdb


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


def test_prepare_environment_error_includes_serial() -> None:
    config = ConfigManager(
        path=Path("config/test.yaml"),
        data={
            "device": {
                "serial": "SER123",
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
            keyboard_visible=False,
            screen_on=True,
        ),
        device_state="offline",
    )
    manager = StubDeviceManager(config, fake_adb)

    with pytest.raises(DeviceConnectionError) as exc_info:
        manager.prepare_test_environment()

    message = str(exc_info.value)
    assert "SER123" in message
    assert "offline" in message


def test_reset_to_baseline_uses_custom_home_packages() -> None:
    config = ConfigManager(
        path=Path("config/test.yaml"),
        data={
            "device": {
                "home_packages": ["com.vendor.home"],
                "reset_to_home_after_case": True,
            }
        },
    )
    fake_adb = FakeAdb(
        DeviceSnapshot(
            focus="mCurrentFocus=Window{1 u0 com.vendor.home/.Launcher}",
            package="com.vendor.home",
            activity=".Launcher",
            keyboard_visible=False,
            screen_on=True,
        )
    )
    manager = StubDeviceManager(config, fake_adb)

    details = manager.reset_to_baseline()

    assert "baseline_home=already_on_home" in details
    assert "start_home" not in fake_adb.calls


def test_prepare_environment_uses_custom_transient_packages() -> None:
    config = ConfigManager(
        path=Path("config/test.yaml"),
        data={
            "device": {
                "transient_packages": ["com.vendor.overlay"],
                "reset_to_home_after_case": True,
            }
        },
    )
    fake_adb = FakeAdb(
        DeviceSnapshot(
            focus="mCurrentFocus=Window{1 u0 com.vendor.overlay/.Overlay}",
            package="com.vendor.overlay",
            activity=".Overlay",
            keyboard_visible=False,
            screen_on=True,
        )
    )
    manager = StubDeviceManager(config, fake_adb)

    manager.prepare_test_environment()

    assert "close_system_dialogs" in fake_adb.calls
