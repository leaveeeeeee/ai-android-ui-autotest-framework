from __future__ import annotations

from pathlib import Path

import pytest

from framework.core.config import ConfigManager
from framework.core.exceptions import ConfigError


def test_config_manager_applies_environment_overrides(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
device:
  serial: old
  app_package: old.package
  app_activity: .Old
  baseline_url: https://old.example
framework:
  report_dir: artifacts/reports
  image_match_threshold: 0.9
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("ANDROID_SERIAL", "SER123")
    monkeypatch.setenv("APP_PACKAGE", "mark.via")
    monkeypatch.setenv("APP_ACTIVITY", ".Shell")
    monkeypatch.setenv("BASELINE_URL", "https://www.baidu.com")
    monkeypatch.setenv("REPORTS_ROOT", "/tmp/reports")
    monkeypatch.setenv("IMAGE_THRESHOLD", "0.88")

    config = ConfigManager.load(config_path)

    assert config.get("device.serial") == "SER123"
    assert config.get("device.app_package") == "mark.via"
    assert config.get("device.app_activity") == ".Shell"
    assert config.get("device.baseline_url") == "https://www.baidu.com"
    assert config.get("framework.report_dir") == "/tmp/reports"
    assert config.get("framework.image_match_threshold") == 0.88


def test_config_manager_rejects_invalid_environment_override(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("framework: {}\n", encoding="utf-8")
    monkeypatch.setenv("IMAGE_THRESHOLD", "not-a-float")

    with pytest.raises(ConfigError):
        ConfigManager.load(config_path)


def test_config_manager_validates_threshold_range(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
framework:
  image_match_threshold: 1.5
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="image_match_threshold"):
        ConfigManager.load(config_path)


def test_config_manager_validates_reporting_policy(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
reporting:
  capture_policy: everything
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="capture_policy"):
        ConfigManager.load(config_path)
