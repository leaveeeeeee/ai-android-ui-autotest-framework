from __future__ import annotations

import time
from typing import Callable, TypeVar

T = TypeVar("T")


class Waiter:
    """通用等待与轮询工具。

    适用场景：
    - 页面加载存在延迟
    - UI 动画未结束
    - 元素需要重试才能稳定出现
    """

    def __init__(self, timeout: float = 10.0, interval: float = 0.5) -> None:
        self.timeout = timeout
        self.interval = interval

    def until(
        self,
        condition: Callable[[], T | None],
        message: str = "",
        *,
        timeout: float | None = None,
        interval: float | None = None,
        exception_cls: type[Exception] = TimeoutError,
    ) -> T:
        """持续轮询条件，直到成功或超时。

        `condition` 返回任意 truthy 值时立即结束，并返回该值。
        """
        effective_timeout = self.timeout if timeout is None else timeout
        effective_interval = self.interval if interval is None else interval
        deadline = time.monotonic() + effective_timeout
        last_result = None
        while time.monotonic() < deadline:
            last_result = condition()
            if last_result:
                return last_result
            time.sleep(effective_interval)
        raise exception_cls(message or "在超时时间内条件仍未满足。")

    def until_true(
        self,
        condition: Callable[[], bool],
        message: str = "",
        *,
        timeout: float | None = None,
        interval: float | None = None,
        exception_cls: type[Exception] = TimeoutError,
    ) -> None:
        """等待布尔条件为真。"""

        self.until(
            lambda: True if condition() else None,
            message=message,
            timeout=timeout,
            interval=interval,
            exception_cls=exception_cls,
        )
