from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from typing import Sequence


@dataclass
class DeviceSnapshot:
    """设备当前前台状态快照。"""

    focus: str
    package: str = ""
    activity: str = ""
    keyboard_visible: bool = False
    screen_on: bool = True


class AdbClient:
    """ADB 辅助类。

    这层负责设备级动作，例如：
    - 回桌面
    - 按键事件
    - 启动 Activity
    - 查询焦点窗口
    - 检查应用是否安装
    """

    def __init__(self, serial: str = "") -> None:
        self.serial = serial

    def _base_cmd(self) -> list[str]:
        """拼接基础 adb 命令。"""
        cmd = ["adb"]
        if self.serial:
            cmd.extend(["-s", self.serial])
        return cmd

    def shell(self, command: str, check: bool = True) -> str:
        """执行 `adb shell` 命令并返回标准输出。"""
        result = subprocess.run(
            [*self._base_cmd(), "shell", command],
            capture_output=True,
            text=True,
            check=check,
        )
        return result.stdout.strip()

    def devices(self) -> str:
        """查看当前 adb 识别到的设备列表。"""
        result = subprocess.run(
            ["adb", "devices"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    def wait_for_device(self) -> str:
        """阻塞等待设备上线。"""
        result = subprocess.run(
            [*self._base_cmd(), "wait-for-device"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    def get_state(self) -> str:
        """获取设备状态，常见返回值为 `device`。"""
        result = subprocess.run(
            [*self._base_cmd(), "get-state"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    def start_activity(
        self,
        package: str,
        activity: str,
        data_uri: str | None = None,
        extra_args: Sequence[str] | None = None,
    ) -> str:
        """启动指定 Activity，可选传入 URL。"""
        cmd = [*self._base_cmd(), "shell", "am", "start", "-n", f"{package}/{activity}"]
        if data_uri:
            cmd.extend(["-d", data_uri])
        if extra_args:
            cmd.extend(extra_args)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    def force_stop(self, package: str) -> str:
        """强行停止应用。"""
        return self.shell(f"am force-stop {package}")

    def press_keyevent(self, keycode: int) -> str:
        """发送 Android keyevent。"""
        return self.shell(f"input keyevent {keycode}")

    def go_home(self) -> str:
        """回到桌面。"""
        return self.press_keyevent(3)

    def press_back(self) -> str:
        """执行返回操作。"""
        return self.press_keyevent(4)

    def wake_up(self) -> str:
        """点亮屏幕。"""
        return self.press_keyevent(224)

    def unlock_screen(self) -> str:
        """尝试关闭锁屏遮罩。"""
        self.shell("wm dismiss-keyguard")
        return "dismiss-keyguard"

    def start_home(self) -> str:
        """通过显式 HOME Intent 回到桌面。"""
        return self.shell(
            "am start -W -a android.intent.action.MAIN -c android.intent.category.HOME"
        )

    def close_system_dialogs(self) -> str:
        """关闭系统级弹窗、通知栏、最近任务等临时层。"""
        return self.shell("am broadcast -a android.intent.action.CLOSE_SYSTEM_DIALOGS", check=False)

    def current_focus(self) -> str:
        """获取当前焦点窗口信息。

        报告里会把这个值展示出来，便于排查步骤执行时页面是否切对了。
        """
        return self.current_focus_state().focus

    def current_focus_state(self) -> DeviceSnapshot:
        """返回结构化前台状态。"""
        output = self.shell("dumpsys window windows", check=False)
        focus_lines = [
            line.strip()
            for line in output.splitlines()
            if any(
                keyword in line
                for keyword in (
                    "mCurrentFocus",
                    "mFocusedApp",
                    "mResumeActivity",
                    "imeInputTarget",
                    "imeLayeringTarget",
                )
            )
        ]
        focus = " | ".join(focus_lines) if focus_lines else "unknown"
        package = ""
        activity = ""
        match = re.search(r"([A-Za-z0-9._]+)/([A-Za-z0-9.$_/-]+)", focus)
        if match:
            package, activity = match.groups()
        return DeviceSnapshot(
            focus=focus,
            package=package,
            activity=activity,
            keyboard_visible=self.is_keyboard_visible(window_output=output),
            screen_on=self.screen_is_on(),
        )

    def screen_is_on(self) -> bool:
        """判断屏幕是否处于点亮态。"""
        output = self.shell("dumpsys power", check=False)
        normalized = output.casefold()
        if "display power: state=off" in normalized or "mwakefulness=asleep" in normalized:
            return False
        if "display power: state=on" in normalized or "mwakefulness=awake" in normalized:
            return True
        return True

    def is_keyboard_visible(self, window_output: str | None = None) -> bool:
        """判断输入法面板是否正在显示。

        真机经验：
        - `dumpsys input_method` 里的 `mIsInputViewShown=true` 在部分 MIUI 设备上会残留
        - 真正更可靠的是看 WindowManager 中 InputMethod 窗口是否可见
        """
        output = window_output or self.shell("dumpsys window windows", check=False)
        match = re.search(
            r"Window #\d+ Window\{[^}]+ InputMethod\}:(.*?)(?:\n  Window #\d+ |\Z)",
            output,
            re.S,
        )
        if match is None:
            return False

        block = match.group(1).casefold()
        if "isvisible=true" in block:
            return True
        return (
            "mhasurface=true isreadyfordisplay()=true" in block and "mviewvisibility=0x0" in block
        )

    def is_package_installed(self, package: str) -> bool:
        """判断指定应用是否已安装。"""
        return bool(self.shell(f"pm path {package}"))
