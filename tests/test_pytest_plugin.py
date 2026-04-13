from __future__ import annotations

import types

import pytest

from framework.pytest_plugin import pytest_collection_modifyitems


class DummyItem:
    def __init__(self, *, device: bool) -> None:
        self._device = device

    def get_closest_marker(self, name: str):
        if name == "device" and self._device:
            return object()
        return None


class DummyConfig:
    def __init__(self, workers) -> None:  # noqa: ANN001
        self.option = types.SimpleNamespace(numprocesses=workers)


def test_pytest_plugin_blocks_device_parallel_execution() -> None:
    with pytest.raises(pytest.UsageError):
        pytest_collection_modifyitems(DummyConfig("auto"), [DummyItem(device=True)])


def test_pytest_plugin_allows_parallel_non_device_collection() -> None:
    pytest_collection_modifyitems(DummyConfig("auto"), [DummyItem(device=False)])
