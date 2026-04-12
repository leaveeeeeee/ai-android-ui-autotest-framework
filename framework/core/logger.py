from __future__ import annotations

import logging
from pathlib import Path


def setup_logger(
    name: str = "framework",
    log_dir: str = "artifacts/report_data/logs",
) -> logging.Logger:
    """创建框架统一日志对象。

    使用说明：
    - 同时输出到终端和文件
    - 日志文件默认写入 `artifacts/report_data/logs`
    - 同名 logger 会复用已有 handler，避免重复打印
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    Path(log_dir).mkdir(parents=True, exist_ok=True)
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(Path(log_dir) / f"{name}.log", encoding="utf-8")
    file_handler.setFormatter(formatter)

    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)
    logger.propagate = False
    return logger
