from __future__ import annotations

import subprocess

from framework.device.adb import AdbClient


def test_adb_client_parses_focus_state_and_keyboard(monkeypatch):
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

    monkeypatch.setattr(subprocess, "run", fake_run)
    adb = AdbClient(serial="SER123")

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
