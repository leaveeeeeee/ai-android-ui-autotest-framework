from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import yaml

from framework.core.exceptions import ConfigError

DEFAULT_LOCAL_CONFIG_PATH = Path("config/config.local.yaml")
DEFAULT_EXAMPLE_CONFIG_PATH = Path("config/config.example.yaml")
LEGACY_CONFIG_PATH = Path("config/config.yaml")
CI_CONFIG_PATH = Path("config/config.ci.yaml")


def _to_float(value: str) -> float:
    return float(value)


ENV_OVERRIDES: dict[str, tuple[str, Callable[[str], Any]]] = {
    "ANDROID_SERIAL": ("device.serial", str),
    "APP_PACKAGE": ("device.app_package", str),
    "APP_ACTIVITY": ("device.app_activity", str),
    "BASELINE_URL": ("device.baseline_url", str),
    "REPORTS_ROOT": ("framework.report_dir", str),
    "IMAGE_THRESHOLD": ("framework.image_match_threshold", _to_float),
}


@dataclass
class ConfigManager:
    """负责读取与查询 YAML 配置。"""

    path: Path
    data: dict[str, Any]

    @classmethod
    def load(cls, path: str | Path | None = None) -> "ConfigManager":
        """从指定路径加载配置文件。"""
        config_path = _resolve_config_path(path)
        if not config_path.exists():
            raise ConfigError(
                f"Config file not found: {config_path}. "
                "Copy config/config.example.yaml to config/config.local.yaml first, "
                "or pass --config with an existing file."
            )

        with config_path.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file) or {}

        _apply_env_overrides(data)
        _validate_config(data)
        return cls(path=config_path, data=data)

    def get(self, dotted_key: str, default: Any = None) -> Any:
        """按 `a.b.c` 形式查询嵌套配置，不存在时返回默认值。"""
        current: Any = self.data
        for key in dotted_key.split("."):
            if not isinstance(current, dict) or key not in current:
                return default
            current = current[key]
        return current


def _resolve_config_path(path: str | Path | None) -> Path:
    if path:
        requested = Path(path)
        if requested.exists():
            return requested
        if requested == DEFAULT_LOCAL_CONFIG_PATH:
            return _default_config_path()
        return requested
    return _default_config_path()


def _default_config_path() -> Path:
    candidates = [DEFAULT_LOCAL_CONFIG_PATH]
    if os.getenv("CI"):
        candidates.append(CI_CONFIG_PATH)
    candidates.extend([LEGACY_CONFIG_PATH, DEFAULT_EXAMPLE_CONFIG_PATH])
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return DEFAULT_LOCAL_CONFIG_PATH


def _apply_env_overrides(data: dict[str, Any]) -> None:
    for env_name, (dotted_key, caster) in ENV_OVERRIDES.items():
        raw_value = os.getenv(env_name)
        if raw_value is None or raw_value == "":
            continue
        try:
            value = caster(raw_value)
        except (TypeError, ValueError) as exc:
            raise ConfigError(
                f"Invalid value for {env_name}: {raw_value!r} cannot override {dotted_key}."
            ) from exc
        _set_dotted(data, dotted_key, value)


def _set_dotted(data: dict[str, Any], dotted_key: str, value: Any) -> None:
    current = data
    parts = dotted_key.split(".")
    for key in parts[:-1]:
        next_value = current.setdefault(key, {})
        if not isinstance(next_value, dict):
            next_value = {}
            current[key] = next_value
        current = next_value
    current[parts[-1]] = value


def _get_dotted(data: dict[str, Any], dotted_key: str) -> Any:
    current: Any = data
    for key in dotted_key.split("."):
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def _validate_config(data: dict[str, Any]) -> None:
    threshold = _get_dotted(data, "framework.image_match_threshold")
    if threshold is not None:
        threshold_value = _validate_float("framework.image_match_threshold", threshold)
        if not 0 <= threshold_value <= 1:
            raise ConfigError("framework.image_match_threshold must be between 0 and 1.")

    positive_number_keys = (
        "framework.default_timeout",
        "framework.default_retry_interval",
        "framework.click_retry_interval",
        "device.implicitly_wait",
        "device.new_command_timeout",
    )
    for dotted_key in positive_number_keys:
        value = _get_dotted(data, dotted_key)
        if value is not None:
            number = _validate_float(dotted_key, value)
            if number <= 0:
                raise ConfigError(f"{dotted_key} must be greater than 0.")

    capture_policy = str(_get_dotted(data, "reporting.capture_policy") or "normal")
    if capture_policy not in {"debug", "normal", "failure_or_marked", "ci"}:
        raise ConfigError(
            "reporting.capture_policy must be debug, normal, failure_or_marked, or ci."
        )

    history_retention = _get_dotted(data, "reporting.history_retention")
    if history_retention is not None:
        try:
            retention_value = int(history_retention)
        except (TypeError, ValueError) as exc:
            raise ConfigError("reporting.history_retention must be an integer.") from exc
        if retention_value <= 0:
            raise ConfigError("reporting.history_retention must be greater than 0.")


def _validate_float(dotted_key: str, value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{dotted_key} must be numeric.") from exc
