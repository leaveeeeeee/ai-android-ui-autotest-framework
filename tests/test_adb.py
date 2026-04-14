from __future__ import annotations

import subprocess

from framework.device.adb import AdbClient, parse_focus_state, parse_keyboard_visible


def test_adb_client_parses_focus_state_and_keyboard() -> None:
    recorded_commands: list[list[str]] = []

    def fake_run(cmd, capture_output, text, check):  # noqa: ANN001
        recorded_commands.append(cmd)
        if cmd[-1] == "dumpsys window windows":
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout=(
                    "mCurrentFocus=Window{1 u0 mark.via/.Shell}\n"
                    "mFocusedApp=AppWindowToken{ mark.via/.Shell }\n"
                    "Window #3 Window{99 u0 InputMethod}:\n"
                    "  mViewVisibility=0x0\n"
                    "  mHasSurface=true isReadyForDisplay()=true\n"
                    "  isVisible=true\n"
                ),
                stderr="",
            )
        if cmd[-1] == "dumpsys power":
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout="Display Power: state=ON\nmWakefulness=Awake\n",
                stderr="",
            )
        return subprocess.CompletedProcess(cmd, 0, stdout="Starting: Intent\n", stderr="")

    adb = AdbClient(serial="SER123", runner=fake_run)

    snapshot = adb.current_focus_state()
    result = adb.start_activity("mark.via", ".Shell", data_uri="https://www.baidu.com")

    assert snapshot.package == "mark.via"
    assert snapshot.activity == ".Shell"
    assert snapshot.keyboard_visible is True
    assert snapshot.screen_on is True
    assert result == "Starting: Intent"
    assert recorded_commands[-1] == [
        "adb",
        "-s",
        "SER123",
        "shell",
        "am",
        "start",
        "-n",
        "mark.via/.Shell",
        "-d",
        "https://www.baidu.com",
    ]


def test_adb_client_runner_injection_covers_wait_and_shell_commands() -> None:
    recorded_commands: list[tuple[list[str], bool]] = []

    def fake_run(cmd, capture_output, text, check):  # noqa: ANN001
        recorded_commands.append((cmd, check))
        return subprocess.CompletedProcess(cmd, 0, stdout="device\n", stderr="")

    adb = AdbClient(serial="SER456", runner=fake_run)

    assert adb.wait_for_device() == "device"
    assert adb.get_state() == "device"
    assert adb.shell("input keyevent 3", check=False) == "device"

    assert recorded_commands == [
        (["adb", "-s", "SER456", "wait-for-device"], True),
        (["adb", "-s", "SER456", "get-state"], True),
        (["adb", "-s", "SER456", "shell", "input keyevent 3"], False),
    ]


def test_parse_focus_state_is_pure_and_reusable() -> None:
    snapshot = parse_focus_state(
        window_output=(
            "mCurrentFocus=Window{1 u0 mark.via/.Shell}\n"
            "mFocusedApp=AppWindowToken{ mark.via/.Shell }\n"
            "Window #3 Window{99 u0 InputMethod}:\n"
            "  mViewVisibility=0x0\n"
            "  mHasSurface=true isReadyForDisplay()=true\n"
            "  isVisible=true\n"
        ),
        power_output="Display Power: state=OFF\nmWakefulness=Asleep\n",
    )

    assert snapshot.package == "mark.via"
    assert snapshot.activity == ".Shell"
    assert snapshot.keyboard_visible is True
    assert snapshot.screen_on is False


def test_parse_keyboard_visible_ignores_hidden_ime_with_stale_visible_flag() -> None:
    assert (
        parse_keyboard_visible(
            (
                "Window #16 Window{9846559 u0 InputMethod}:\n"
                "  mViewVisibility=0x8\n"
                "  mHasSurface=false isReadyForDisplay()=false\n"
                "  isVisible=true\n"
            )
        )
        is False
    )


def test_parse_focus_state_prefers_resumed_app_when_system_overlay_is_foreground() -> None:
    snapshot = parse_focus_state(
        window_output=(
            "mCurrentFocus=Window{42 u0 com.android.systemui/.shade.NotificationPanelView}\n"
            "mFocusedApp=AppWindowToken{ mark.via/.Shell }\n"
            "mResumeActivity: ActivityRecord{5d2 mark.via/.Shell t12}\n"
            "imeInputTarget=Window{15 u0 mark.via/.Shell}\n"
        ),
        power_output="Display Power: state=ON\nmWakefulness=Awake\n",
    )

    assert snapshot.package == "mark.via"
    assert snapshot.activity == ".Shell"
    assert snapshot.screen_on is True
