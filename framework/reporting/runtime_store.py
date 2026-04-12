from __future__ import annotations

from typing import Any

import pytest

CASE_REPORT_KEY: pytest.StashKey[dict[str, Any]] = pytest.StashKey()


def get_case_report_store(item: pytest.Item) -> dict[str, Any]:
    """获取当前用例的结构化报告缓存。"""
    try:
        return item.stash[CASE_REPORT_KEY]
    except KeyError:
        store = {
            "steps": [],
            "baseline": "",
            "environment": {
                "precheck": "",
                "postcheck": "",
            },
            "failure": {
                "reason": "",
                "screenshot": "",
                "xml": "",
                "phase": "",
            },
        }
        item.stash[CASE_REPORT_KEY] = store
        return store
