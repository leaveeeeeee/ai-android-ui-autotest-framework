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


def test_init_logging_switches_output_when_config_changes(tmp_path: Path) -> None:
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"

    init_logging({"log_dir": str(first_dir)})
    setup_logger("framework.tests").info("first message")

    init_logging({"log_dir": str(second_dir)})
    setup_logger("framework.tests").info("second message")

    assert "first message" in (first_dir / "framework.log").read_text(encoding="utf-8")
    assert "second message" in (second_dir / "framework.log").read_text(encoding="utf-8")
