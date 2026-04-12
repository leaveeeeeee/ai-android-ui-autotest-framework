from __future__ import annotations

from pathlib import Path

try:
    import allure
except Exception:  # pragma: no cover - 本地环境可能未安装 allure 依赖
    allure = None


def enabled() -> bool:
    """判断当前环境是否可用 Allure。"""
    return allure is not None


def attach_text(name: str, content: str) -> None:
    """向 Allure 报告附加文本内容。"""
    if not enabled() or not content:
        return
    allure.attach(content, name=name, attachment_type=allure.attachment_type.TEXT)


def attach_file(path: str | Path, name: str, attachment_type=None) -> None:
    """向 Allure 报告附加文件。"""
    if not enabled():
        return
    file_path = Path(path)
    if not file_path.exists():
        return
    allure.attach.file(str(file_path), name=name, attachment_type=attachment_type)


def attach_png(path: str | Path, name: str) -> None:
    """向 Allure 报告附加 PNG 图片。"""
    if not enabled():
        return
    attach_file(path, name=name, attachment_type=allure.attachment_type.PNG)


def attach_xml(path: str | Path, name: str) -> None:
    """向 Allure 报告附加 XML 文件。"""
    if not enabled():
        return
    attach_file(path, name=name, attachment_type=allure.attachment_type.XML)
