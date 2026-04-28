from __future__ import annotations

import os
from pathlib import Path

from _pytest.stash import Stash

from framework.reporting.runtime_store import get_case_report_store
from framework.reporting.simple_html import (
    ASSETS_DIR,
    _build_case_bundle,
    _build_run_id,
    _prune_old_runs,
    _recent_run_entries,
    _render_case_page,
    add_test_row,
)


class DummyConfig:
    def __init__(self) -> None:
        self._framework_simple_html = {"rows": []}


class DummyItem:
    def __init__(self) -> None:
        self.config = DummyConfig()
        self.nodeid = "tests/test_demo.py::test_case"
        self.stash = Stash()


class DummyReport:
    def __init__(self, when: str = "call", *, failed: bool | None = None) -> None:
        self.when = when
        self.failed = when == "call" if failed is None else failed
        self.outcome = "failed" if self.failed else "passed"
        self.duration = 1.23
        self.longreprtext = ""
        self.sections: list[tuple[str, str]] = []


class DummyCall:
    excinfo = None


def test_simple_html_prefers_structured_runtime_store_over_sections() -> None:
    item = DummyItem()
    store = get_case_report_store(item)
    store["steps"] = [{"index": 1, "name": "点击搜索", "status": "PASSED"}]
    store["baseline"] = "{'package': 'mark.via'}"
    store["environment"]["precheck"] = "before_prepare.focus=mark.via/.Shell"
    store["environment"]["postcheck"] = "after_reset.focus=com.miui.home/.launcher.Launcher"
    store["failure"] = {
        "reason": "搜索按钮未出现",
        "screenshot": "/tmp/failure.png",
        "xml": "/tmp/failure.xml",
        "phase": "call",
    }

    add_test_row(item, DummyCall(), DummyReport())

    row = item.config._framework_simple_html["rows"][0]
    assert row["screenshot"] == "/tmp/failure.png"
    assert row["xml"] == "/tmp/failure.xml"
    assert row["steps"] == [{"index": 1, "name": "点击搜索", "status": "PASSED"}]
    assert "搜索按钮未出现" in row["message"]
    assert "[Environment Precheck]" in row["message"]
    assert "[Environment Reset]" in row["message"]


def test_simple_html_case_template_renders_duration_and_stylesheet() -> None:
    html = _render_case_page(
        {
            "nodeid": "tests/test_demo.py::test_case",
            "outcome": "PASSED",
            "phase": "call",
            "duration": "1.23s",
            "step_duration_label": "125ms",
            "baseline": "{'package': 'mark.via'}",
            "message": "ok",
            "steps": [
                {
                    "index": 1,
                    "name": "点击搜索",
                    "status": "PASSED",
                    "duration_label": "125ms",
                    "expected": "ok",
                    "actual": "ok",
                    "comparison": "PASS",
                    "logs": "",
                    "focus_window": "",
                    "previous_screenshot_rel": "",
                    "screenshot_rel": "",
                    "diff_rel": "",
                    "source_rel": "",
                    "detail": "",
                }
            ],
        },
        stylesheet_href="../../report.css",
    )

    assert "../../report.css" in html
    assert "125ms" in html


def test_add_test_row_merges_call_and_teardown_details() -> None:
    item = DummyItem()
    store = get_case_report_store(item)
    store["baseline"] = "{'package': 'mark.via'}"
    store["environment"]["precheck"] = "adb ready"
    store["steps"] = [
        {"index": 1, "name": "点击搜索", "status": "PASSED", "duration_ms": 80},
        {"index": 2, "name": "校验结果", "status": "FAILED", "duration_ms": 120},
    ]
    store["failure"] = {
        "reason": "结果页未加载",
        "screenshot": "/tmp/failure.png",
        "xml": "/tmp/failure.xml",
        "phase": "call",
    }

    add_test_row(item, DummyCall(), DummyReport("call", failed=True))

    store["environment"]["postcheck"] = "reset complete"
    add_test_row(item, DummyCall(), DummyReport("teardown", failed=False))

    rows = item.config._framework_simple_html["rows"]
    assert len(rows) == 1
    row = rows[0]
    assert row["phase"] == "call"
    assert row["baseline"] == "{'package': 'mark.via'}"
    assert row["postcheck"] == "reset complete"
    assert row["step_duration_ms"] == 200
    assert "[Environment Precheck]" in row["message"]
    assert "[Environment Reset]" in row["message"]


def test_build_case_bundle_stages_assets_and_uses_relative_paths(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    failure_png = source_root / "failure.png"
    failure_xml = source_root / "failure.xml"
    step_png = source_root / "step.png"
    previous_png = source_root / "previous.png"
    diff_png = source_root / "diff.png"
    source_xml = source_root / "step.xml"
    for path in (failure_png, step_png, previous_png, diff_png):
        path.write_bytes(b"png")
    for path in (failure_xml, source_xml):
        path.write_text("<hierarchy />", encoding="utf-8")

    run_root = tmp_path / "reports" / "runs" / "run_001"
    row = {
        "nodeid": "tests/test_demo.py::test_case",
        "outcome": "FAILED",
        "phase": "call",
        "duration": "1.23s",
        "message": "failure",
        "screenshot": str(failure_png),
        "xml": str(failure_xml),
        "precheck": "adb ready",
        "postcheck": "reset complete",
        "baseline": "{'package': 'mark.via'}",
        "steps": [
            {
                "index": 1,
                "name": "点击搜索",
                "status": "PASSED",
                "expected": "ok",
                "actual": "ok",
                "comparison": "PASS",
                "logs": "",
                "focus_window": "",
                "detail": "",
                "duration_ms": 125,
                "screenshot_path": str(step_png),
                "previous_screenshot_path": str(previous_png),
                "diff_path": str(diff_png),
                "source_path": str(source_xml),
            }
        ],
        "step_duration_ms": 125,
    }

    case = _build_case_bundle(run_root, row)

    case_dir = run_root / "cases" / "tests_test_demo_py__test_case"
    assert (case_dir / "index.html").exists()
    assert (case_dir / case["screenshot_rel"]).exists()
    assert (case_dir / case["xml_rel"]).exists()
    staged_step = case["steps"][0]
    assert staged_step["duration_label"] == "125ms"
    assert (case_dir / staged_step["screenshot_rel"]).exists()
    assert (case_dir / staged_step["previous_screenshot_rel"]).exists()
    assert (case_dir / staged_step["diff_rel"]).exists()
    assert (case_dir / staged_step["source_rel"]).exists()


def test_recent_run_entries_sort_desc_and_truncate_to_ten(tmp_path: Path) -> None:
    reports_root = tmp_path / "reports"
    runs_root = reports_root / "runs"
    runs_root.mkdir(parents=True)
    run_ids = [f"20260412_1015{index:02d}" for index in range(12)]
    for run_id in run_ids:
        (runs_root / run_id).mkdir()

    entries = _recent_run_entries(
        reports_root,
        current_run_id="20260412_101511",
        relative_mode="run",
    )

    assert len(entries) == 10
    assert entries[0] == {"run_id": "20260412_101511", "href": "index.html"}
    assert entries[-1]["run_id"] == "20260412_101502"
    assert entries[1]["href"] == "../20260412_101510/index.html"


def test_report_css_includes_responsive_breakpoints() -> None:
    css = (ASSETS_DIR / "report.css").read_text(encoding="utf-8")

    assert "@media (max-width: 1080px)" in css
    assert "@media (max-width: 720px)" in css


def test_build_run_id_prefers_github_run_id(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("GITHUB_RUN_ID", "123456789")

    assert _build_run_id() == "123456789"


def test_build_run_id_uses_microseconds_and_suffix(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.delenv("GITHUB_RUN_ID", raising=False)

    run_id = _build_run_id()

    assert len(run_id.split("_")) == 4
    assert len(run_id.rsplit("_", 1)[-1]) == 8


def test_prune_old_runs_keeps_recent_runs_and_current(tmp_path: Path) -> None:
    reports_root = tmp_path / "reports"
    runs_root = reports_root / "runs"
    runs_root.mkdir(parents=True)
    for index in range(5):
        run_dir = runs_root / f"run_{index}"
        run_dir.mkdir()
        os.utime(run_dir, (100 + index, 100 + index))

    current = runs_root / "current"
    current.mkdir()
    os.utime(current, (1, 1))
    _prune_old_runs(reports_root, current_run_id="current", keep=2)

    remaining = {path.name for path in runs_root.iterdir()}
    assert remaining == {"current", "run_4"}
