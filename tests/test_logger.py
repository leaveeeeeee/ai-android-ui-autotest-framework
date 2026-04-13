from __future__ import annotations

from pathlib import Path

from framework.core.logger import init_logging, setup_logger


def test_init_logging_uses_framework_config(tmp_path: Path) -> None:
    init_logging(
        {
            "log_dir": str(tmp_path),
            "logging": {
                "level": "DEBUG",
                "format": "%(levelname)s|%(name)s|%(message)s",
                "datefmt": "%H:%M:%S",
            },
        }
    )
    logger = setup_logger("framework.tests")
    logger.debug("hello logger")

    log_file = tmp_path / "framework.log"
    assert log_file.exists()
    assert "DEBUG|framework.tests|hello logger" in log_file.read_text(encoding="utf-8")
