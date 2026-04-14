from __future__ import annotations

import re
from typing import Any

Bounds = tuple[int, int, int, int]


def normalize_bounds(bounds: Any) -> Bounds | None:
    """把不同格式的 bounds 统一转换成 `(left, top, right, bottom)`。"""

    if bounds is None:
        return None

    if isinstance(bounds, dict):
        keys = ("left", "top", "right", "bottom")
        if all(key in bounds for key in keys):
            return (
                int(bounds["left"]),
                int(bounds["top"]),
                int(bounds["right"]),
                int(bounds["bottom"]),
            )

    if isinstance(bounds, (list, tuple)) and len(bounds) == 4:
        return tuple(int(value) for value in bounds)  # type: ignore[return-value]

    if isinstance(bounds, str):
        match = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds)
        if match:
            left, top, right, bottom = match.groups()
            return int(left), int(top), int(right), int(bottom)

    return None


def extract_bounds(element: Any) -> Bounds | None:
    """尽量从不同元素对象结构中解析边界框。"""

    if element is None:
        return None

    info = getattr(element, "info", None)
    if isinstance(info, dict):
        normalized = normalize_bounds(info.get("bounds"))
        if normalized is not None:
            return normalized

    bounds_attr = getattr(element, "bounds", None)
    if callable(bounds_attr):
        try:
            normalized = normalize_bounds(bounds_attr())
            if normalized is not None:
                return normalized
        except Exception:
            pass
    elif bounds_attr is not None:
        normalized = normalize_bounds(bounds_attr)
        if normalized is not None:
            return normalized

    rect_attr = getattr(element, "rect", None)
    if rect_attr is not None:
        normalized = normalize_bounds(rect_attr)
        if normalized is not None:
            return normalized

    getter = getattr(element, "get", None)
    if callable(getter):
        try:
            nested = getter(timeout=0)
        except TypeError:
            try:
                nested = getter()
            except Exception:
                nested = None
        except Exception:
            nested = None
        if nested is not None and nested is not element:
            return extract_bounds(nested)

    return None
