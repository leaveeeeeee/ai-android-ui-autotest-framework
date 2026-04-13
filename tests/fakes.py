from __future__ import annotations

from pathlib import Path

import cv2

from framework.core.exceptions import ElementNotFoundError
from framework.core.locator import Locator
from framework.device.adb import DeviceSnapshot


class FakePageDriver:
    def __init__(
        self,
        *,
        framework_config: dict | None = None,
        click_error: Exception | None = None,
        set_text_error: Exception | None = None,
        visible: bool = False,
    ) -> None:
        self.framework_config = framework_config or {}
        self.click_error = click_error
        self.set_text_error = set_text_error
        self.visible = visible
        self.sent_keys: list[tuple[str, bool]] = []

    def click(self, locator: Locator) -> None:
        if self.click_error is not None:
            raise self.click_error

    def set_text(self, locator: Locator, value: str) -> None:
        if self.set_text_error is not None:
            raise self.set_text_error

    def clear_text(self, locator: Locator) -> None:
        return None

    def exists(self, locator: Locator) -> bool:
        return self.visible

    def send_keys(self, value: str, *, clear: bool = False) -> None:
        self.sent_keys.append((value, clear))

    def build_artifact_name(self, base_name: str, *, category: str = "artifact") -> str:
        return f"{category}_{base_name}"

    def screenshot(self, path: str | Path) -> str:
        return str(path)

    def page_source(self) -> str:
        return "<hierarchy />"


class FakeImageEngine:
    def __init__(self, *, exists_result: bool = True) -> None:
        self.exists_result = exists_result
        self.calls: list[tuple[str, str, dict]] = []

    def click(self, image_name: str, **kwargs) -> None:
        self.calls.append(("click", image_name, kwargs))

    def exists(self, image_name: str, **kwargs) -> bool:
        self.calls.append(("exists", image_name, kwargs))
        return self.exists_result


class FakeCaptureDevice:
    def screenshot(self, path: str) -> None:
        Path(path).write_bytes(b"fake-png")

    def dump_hierarchy(self) -> str:
        return "<hierarchy />"


class FakeSelector:
    def __init__(self, matched: bool = False, click_error: Exception | None = None) -> None:
        self.matched = matched
        self.click_error = click_error
        self.wait_calls: list[float] = []
        self.click_calls = 0

    @property
    def exists(self) -> bool:
        return self.matched

    def wait(self, timeout: float) -> bool:
        self.wait_calls.append(timeout)
        return self.matched

    def click(self) -> None:
        self.click_calls += 1
        if self.click_error is not None:
            raise self.click_error


class FakeAdb:
    def __init__(self, state: DeviceSnapshot, *, device_state: str = "device") -> None:
        self.state = state
        self.device_state = device_state
        self.calls: list[str] = []

    def wait_for_device(self) -> str:
        self.calls.append("wait_for_device")
        return ""

    def get_state(self) -> str:
        self.calls.append("get_state")
        return self.device_state

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


class FakeStepRecorder:
    def __init__(self) -> None:
        self.last_screenshot_path = ""
        self.records: list[dict[str, object]] = []

    def next_step_name(self, name: str) -> str:
        return name

    def add_step(self, **kwargs):
        self.records.append(kwargs)
        return kwargs


class FakeImageDriver:
    def __init__(self, screenshot_source: Path) -> None:
        self.screenshot_source = screenshot_source
        self.clicked_point: tuple[int, int] | None = None
        self.sequence = 0

    def screenshot(self, path: str | Path) -> str:
        image = cv2.imread(str(self.screenshot_source), cv2.IMREAD_COLOR)
        cv2.imwrite(str(path), image)
        return str(path)

    def click_point(self, x: int, y: int) -> None:
        self.clicked_point = (x, y)

    def build_artifact_name(self, base_name: str, *, category: str = "artifact") -> str:
        self.sequence += 1
        return f"run_case_{category}_{self.sequence:03d}_{base_name}"


def not_found(locator: Locator) -> ElementNotFoundError:
    return ElementNotFoundError(locator.name)
