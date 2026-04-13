from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

DEFAULT_HOME_PACKAGES = [
    "com.miui.home",
    "com.android.launcher",
    "com.android.launcher3",
    "com.google.android.apps.nexuslauncher",
]

DEFAULT_TRANSIENT_PACKAGES = [
    "com.android.systemui",
    "com.android.permissioncontroller",
    "com.google.android.permissioncontroller",
    "com.miui.securitycenter",
    "com.miui.guardprovider",
]

DEFAULT_IMAGE_MATCH_SCALES = [0.67, 0.75, 0.875, 1.0, 1.125, 1.25, 1.33]

DEFAULT_CONFIG: dict[str, Any] = {
    "framework": {
        "screenshot_dir": "artifacts/report_data/screenshots",
        "log_dir": "artifacts/report_data/logs",
        "page_source_dir": "artifacts/report_data/page_source",
        "report_dir": "artifacts/reports",
        "allure_results_dir": "artifacts/report_data/allure-results",
        "allure_report_dir": "artifacts/report_data/allure-report",
        "ai_prompt_dir": "artifacts/report_data/ai-prompts",
        "image_template_dir": "assets/images",
        "image_debug_dir": "artifacts/report_data/image_debug",
        "image_match_threshold": 0.92,
        "image_match_scales": DEFAULT_IMAGE_MATCH_SCALES,
        "default_timeout": 10.0,
        "default_retry_interval": 0.5,
        "click_retry_count": 2,
        "click_retry_interval": 0.5,
        "logging": {
            "level": "INFO",
            "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "device": {
        "home_packages": DEFAULT_HOME_PACKAGES,
        "transient_packages": DEFAULT_TRANSIENT_PACKAGES,
    },
}


def default_value(dotted_key: str) -> Any:
    """读取框架默认配置。"""

    candidates = [dotted_key]
    if not dotted_key.startswith("framework.") and not dotted_key.startswith("device."):
        if "." in dotted_key:
            candidates.extend([f"framework.{dotted_key}", f"device.{dotted_key}"])
        else:
            candidates.extend([f"framework.{dotted_key}", f"device.{dotted_key}"])

    for candidate in candidates:
        current: Any = DEFAULT_CONFIG
        for key in candidate.split("."):
            if not isinstance(current, dict) or key not in current:
                break
            current = current[key]
        else:
            return deepcopy(current)
    raise KeyError(dotted_key)


def setting_from_mapping(config: Mapping[str, Any] | None, dotted_key: str) -> Any:
    """从映射读取配置，缺失时回退到默认值。"""

    current: Any = config or {}
    for key in dotted_key.split("."):
        if not isinstance(current, Mapping) or key not in current:
            return default_value(dotted_key)
        current = current[key]
    return deepcopy(current)
