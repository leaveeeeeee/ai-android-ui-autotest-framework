from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from framework.core.exceptions import ConfigError


@dataclass
class ConfigManager:
    """负责读取与查询 YAML 配置。"""

    path: Path
    data: dict[str, Any]

    @classmethod
    def load(cls, path: str | Path = "config/config.yaml") -> "ConfigManager":
        """从指定路径加载配置文件。"""
        config_path = Path(path)
        if not config_path.exists():
            raise ConfigError(
                f"Config file not found: {config_path}. "
                "Copy config/config.yaml.example to config/config.yaml first."
            )

        with config_path.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file) or {}

        return cls(path=config_path, data=data)

    def get(self, dotted_key: str, default: Any = None) -> Any:
        """按 `a.b.c` 形式查询嵌套配置，不存在时返回默认值。"""
        current: Any = self.data
        for key in dotted_key.split("."):
            if not isinstance(current, dict) or key not in current:
                return default
            current = current[key]
        return current
