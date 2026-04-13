from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from typing import Sequence

from framework.core.defaults import default_value

WINDOW_FOCUS_KEYWORDS = (
    "mCurrentFocus",
    "mFocusedApp",
    "mResumeActivity",
    "imeInputTarget",
    "imeLayeringTarget",
)


def extract_focus_lines(window_output: str) -> list[str]:
    """从 `dumpsys window windows` 中提取焦点相关行。"""

    return [
        line.strip()
        for line in window_output.splitlines()
        if any(keyword in line for keyword in WINDOW_FOCUS_KEYWORDS)
    ]


def parse_screen_is_on(power_output: str) -> bool:
    """从 `dumpsys power` 输出中判断屏幕是否点亮。"""

    normalized = power_output.casefold()
    if "display power: state=off" in normalized or "mwakefulness=asleep" in normalized:
        return False
    if "display power: state=on" in normalized or "mwakefulness=awake" in normalized:
        return True
    return True


def parse_keyboard_visible(window_output: str) -> bool:
    """从 WindowManager 输出中判断输入法面板是否显示。"""

    match = re.search(
        r"Window #\d+ Window\{[^}]+ InputMethod\}:(.*?)(?:\n  Window #\d+ |\Z)",
        window_output,
        re.S,
    )
    if match is None:
        return False

    block = match.group(1).casefold()
    # MIUI 机型上偶尔会残留 `isVisible=true`，但输入法窗口已经 `mHasSurface=false`
    # 或 `mViewVisibility=0x8`。只有窗口真正具备 surface 且可见时，才认为键盘展开。
    return "mhassurface=true isreadyfordisplay()=true" in block and "mviewvisibility=0x0" in block


def parse_focus_state(window_output: str, power_output: str) -> "DeviceSnapshot":
    """把 dumpsys 原始输出解析为结构化设备快照。"""

    focus_lines = extract_focus_lines(window_output)
    focus = " | ".join(focus_lines) if focus_lines else "unknown"
    package, activity = _pick_primary_focus_target(focus_lines)
    return DeviceSnapshot(
        focus=focus,
        package=package,
        activity=activity,
        keyboard_visible=parse_keyboard_visible(window_output),
        screen_on=parse_screen_is_on(power_output),
    )


@dataclass
class DeviceSnapshot:
    """设备当前前台状态快照。"""

    focus: str
    package: str = ""
    activity: str = ""
    keyboard_visible: bool = False
    screen_on: bool = True


def _pick_primary_focus_target(focus_lines: list[str]) -> tuple[str, str]:
    """在多条焦点候选中挑选最能代表业务前台的目标。"""

    transient_packages = set(default_value("device.transient_packages"))
    candidates: list[tuple[str, str]] = []
    for line in focus_lines:
        match = re.search(r"([A-Za-z0-9._]+)/([A-Za-z0-9.$_/-]+)", line)
        if match:
            candidates.append(match.groups())

    if not candidates:
        return "", ""

    first_package, first_activity = candidates[0]
    if first_package not in transient_packages:
        return first_package, first_activity

    for package, activity in candidates[1:]:
        if package not in transient_packages:
            return package, activity

    return first_package, first_activity


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
        window_output = self.shell("dumpsys window windows", check=False)
        power_output = self.shell("dumpsys power", check=False)
        return parse_focus_state(window_output=window_output, power_output=power_output)

    def screen_is_on(self) -> bool:
        """判断屏幕是否处于点亮态。"""
        return parse_screen_is_on(self.shell("dumpsys power", check=False))

    def is_keyboard_visible(self, window_output: str | None = None) -> bool:
        """判断输入法面板是否正在显示。

        真机经验：
        - `dumpsys input_method` 里的 `mIsInputViewShown=true` 在部分 MIUI 设备上会残留
        - 真正更可靠的是看 WindowManager 中 InputMethod 窗口是否可见
        """
        output = window_output or self.shell("dumpsys window windows", check=False)
        return parse_keyboard_visible(output)

    def is_package_installed(self, package: str) -> bool:
        """判断指定应用是否已安装。"""
        return bool(self.shell(f"pm path {package}"))
