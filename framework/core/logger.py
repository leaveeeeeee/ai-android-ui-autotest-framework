from __future__ import annotations

import logging
from logging.config import dictConfig
from pathlib import Path
from typing import Any, Mapping

from framework.core.defaults import setting_from_mapping

_CURRENT_SIGNATURE: tuple[str, str, str, str] | None = None


def init_logging(framework_config: Mapping[str, Any] | None = None) -> None:
    """集中初始化日志系统。"""

    global _CURRENT_SIGNATURE

    log_dir = str(setting_from_mapping(framework_config, "log_dir"))
    level = str(setting_from_mapping(framework_config, "logging.level")).upper()
    fmt = str(setting_from_mapping(framework_config, "logging.format"))
    datefmt = str(setting_from_mapping(framework_config, "logging.datefmt"))
    signature = (log_dir, level, fmt, datefmt)
    if _CURRENT_SIGNATURE == signature:
        return

    Path(log_dir).mkdir(parents=True, exist_ok=True)
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "framework": {
                    "format": fmt,
                    "datefmt": datefmt,
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "framework",
                    "level": level,
                },
                "file": {
                    "class": "logging.FileHandler",
                    "filename": str(Path(log_dir) / "framework.log"),
                    "encoding": "utf-8",
                    "formatter": "framework",
                    "level": level,
                },
            },
            "root": {
                "handlers": ["console", "file"],
                "level": level,
            },
        }
    )
    _CURRENT_SIGNATURE = signature


def setup_logger(
    name: str = "framework",
) -> logging.Logger:
    """创建框架统一日志对象。

    使用说明：
    - 同时输出到终端和文件
    - 日志配置统一由 `init_logging()` 初始化
    - 同名 logger 会复用 root handlers，避免重复打印
    """
    if _CURRENT_SIGNATURE is None:
        init_logging()
    return logging.getLogger(name)
