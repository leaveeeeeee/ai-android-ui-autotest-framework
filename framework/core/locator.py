from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Locator:
    """统一定位器模型。

    用途：
    - 统一封装资源 ID、文本、XPath、描述等定位方式
    - 支持 fallback 定位器，提升真机稳定性
    - 为后续图像兜底保留统一入口
    """

    name: str
    strategy: str
    value: Any
    fallback: list["Locator"] = field(default_factory=list)
    allow_image_fallback: bool = False
    timeout: float | None = None
    image_template: str = ""
    image_region: tuple[int, int, int, int] | None = None
    image_threshold: float | None = None

    def as_kwargs(self) -> dict[str, Any]:
        """将当前定位器转换成 uiautomator2 可直接消费的参数。"""
        mapping = {
            "resource_id": {"resourceId": self.value},
            "text": {"text": self.value},
            "xpath": {"xpath": self.value},
            "class_name": {"className": self.value},
            "description": {"description": self.value},
        }
        return mapping.get(self.strategy, {})

    def image_fallback_config(self) -> dict[str, Any] | None:
        """返回图片兜底配置。

        设计说明：
        - 优先使用显式声明的 `image_template`
        - 为兼容旧代码，`allow_image_fallback=True` 但未声明模板时，
          仍回退到历史行为：使用 `locator.name` 作为模板名
        - 如果两者都没有，则说明该定位器不支持图片兜底
        """
        template = self.image_template.strip() or (self.name if self.allow_image_fallback else "")
        if not template:
            return None
        return {
            "template": template,
            "region": self.image_region,
            "threshold": self.image_threshold,
        }
