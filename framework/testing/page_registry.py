from __future__ import annotations

from typing import Any

import pytest

PAGE_OBJECTS_KEY: pytest.StashKey[list[Any]] = pytest.StashKey()


def register_page_object(request: pytest.FixtureRequest, page: Any) -> Any:
    """把页面对象登记到当前用例上下文。"""

    try:
        pages = request.node.stash[PAGE_OBJECTS_KEY]
    except KeyError:
        pages = []
        request.node.stash[PAGE_OBJECTS_KEY] = pages
    pages.append(page)
    return page


def get_latest_page_object(item: pytest.Item) -> Any | None:
    """返回当前用例最近注册的页面对象。"""

    try:
        pages = item.stash[PAGE_OBJECTS_KEY]
    except KeyError:
        return None
    return pages[-1] if pages else None
