"""结构化 HTML 报告生成器。"""

from __future__ import annotations

import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from jinja2 import Environment, FileSystemLoader, select_autoescape

from framework.core.defaults import default_value
from framework.reporting.runtime_store import get_case_report_store

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
ASSETS_DIR = Path(__file__).resolve().parent / "assets"
CSS_FILE_NAME = "report.css"


def pytest_addoption(parser: pytest.Parser) -> None:
    """注册自定义命令行参数。"""

    group = parser.getgroup("framework-reporting")
    group.addoption(
        "--simple-html",
        action="store",
        default="",
        help="输出结构化 HTML 报告，参数值为报告入口文件路径。",
    )


def pytest_configure(config: pytest.Config) -> None:
    """在 pytest 启动时初始化报告上下文。"""

    report_path = config.getoption("--simple-html")
    if not report_path:
        return

    target = Path(report_path).resolve()
    reports_root = target.parent
    run_id = _build_run_id()
    run_root = reports_root / "runs" / run_id
    run_root.mkdir(parents=True, exist_ok=True)
    reporting_config = _load_reporting_config(config)

    config._framework_simple_html = {
        "path": target,
        "reports_root": reports_root,
        "run_root": run_root,
        "run_id": run_id,
        "history_retention": int(
            reporting_config.get(
                "history_retention",
                default_value("reporting.history_retention"),
            )
        ),
        "started_at": time.time(),
        "rows": [],
    }


def get_simple_html_run_id(config: pytest.Config) -> str:
    """返回当前 pytest 会话的报告 run_id。"""

    state = getattr(config, "_framework_simple_html", None) or {}
    return str(state.get("run_id", ""))


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    outcome = yield
    report = outcome.get_result()
    add_test_row(item, call, report)


def add_test_row(item: pytest.Item, call: pytest.CallInfo, report: pytest.TestReport) -> None:
    """把单次 setup/call/teardown 结果整理进报告缓存。"""

    html_state = getattr(item.config, "_framework_simple_html", None)
    if html_state is None:
        return
    if report.when == "setup" and not report.failed:
        return
    if report.when not in {"setup", "call", "teardown"}:
        return

    store = get_case_report_store(item)
    failure = store.get("failure", {})
    environment = store.get("environment", {})
    screenshot_path = str(failure.get("screenshot", "") or "")
    xml_path = str(failure.get("xml", "") or "")
    precheck = str(environment.get("precheck", "") or "")
    postcheck = str(environment.get("postcheck", "") or "")

    failure_message = str(failure.get("reason", "") or "")
    if report.failed and not failure_message:
        failure_message = (
            report.longreprtext or str(call.excinfo.value) if call.excinfo else ""
        ).strip()
    detail_blocks = [failure_message] if failure_message else []
    if precheck:
        detail_blocks.append(f"[Environment Precheck]\n{precheck}")
    if postcheck:
        detail_blocks.append(f"[Environment Reset]\n{postcheck}")

    steps = list(store.get("steps", []))
    payload = {
        "nodeid": item.nodeid,
        "outcome": report.outcome.upper(),
        "duration": f"{report.duration:.2f}s",
        "message": "\n\n".join(detail_blocks),
        "screenshot": screenshot_path,
        "xml": xml_path,
        "precheck": precheck,
        "postcheck": postcheck,
        "baseline": str(store.get("baseline", "") or ""),
        "phase": report.when,
        "steps": steps,
        "step_duration_ms": sum(int(step.get("duration_ms", 0) or 0) for step in steps),
    }

    existing = next((row for row in html_state["rows"] if row["nodeid"] == item.nodeid), None)
    if report.when == "teardown" and existing is not None:
        existing["postcheck"] = postcheck or existing.get("postcheck", "")
        existing["steps"] = steps
        existing["step_duration_ms"] = payload["step_duration_ms"]
        existing["baseline"] = str(store.get("baseline", "") or existing.get("baseline", ""))
        if postcheck:
            message_parts = [
                existing.get("message", "").strip(),
                f"[Environment Reset]\n{postcheck}",
            ]
            existing["message"] = "\n\n".join(part for part in message_parts if part)
        if report.failed:
            existing["outcome"] = report.outcome.upper()
            existing["phase"] = report.when
            existing["duration"] = f"{report.duration:.2f}s"
            if screenshot_path:
                existing["screenshot"] = screenshot_path
            if xml_path:
                existing["xml"] = xml_path
        return

    if existing is None:
        html_state["rows"].append(payload)
    else:
        existing.update(payload)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """在测试会话结束时输出总览页、latest 页面和历史归档。"""

    html_state = getattr(session.config, "_framework_simple_html", None)
    if html_state is None:
        return

    reports_root: Path = html_state["reports_root"]
    run_root: Path = html_state["run_root"]
    latest_root = reports_root / "latest"
    rows = html_state["rows"]
    duration = time.time() - html_state["started_at"]

    _write_report_css(run_root / CSS_FILE_NAME)
    cases = [_build_case_bundle(run_root, row) for row in rows]
    suite_html = _render_suite_page(
        cases=cases,
        title="Android UI Framework Report",
        subtitle=f"Run ID: {html_state['run_id']}",
        duration=duration,
        exitstatus=exitstatus,
        recent_runs=_recent_run_entries(
            reports_root, current_run_id=html_state["run_id"], relative_mode="run"
        ),
        stylesheet_href=CSS_FILE_NAME,
    )
    (run_root / "index.html").write_text(suite_html, encoding="utf-8")

    if latest_root.exists():
        shutil.rmtree(latest_root)
    shutil.copytree(run_root, latest_root)

    _write_report_css(reports_root / CSS_FILE_NAME)
    latest_cases = [_build_case_summary_for_latest(case) for case in cases]
    latest_html = _render_suite_page(
        cases=latest_cases,
        title="Android UI Framework Latest Report",
        subtitle=f"Latest run: {html_state['run_id']}",
        duration=duration,
        exitstatus=exitstatus,
        recent_runs=_recent_run_entries(
            reports_root, current_run_id=html_state["run_id"], relative_mode="root"
        ),
        stylesheet_href=CSS_FILE_NAME,
    )
    (reports_root / "index.html").write_text(latest_html, encoding="utf-8")
    html_state["path"].write_text(latest_html, encoding="utf-8")
    _prune_old_runs(
        reports_root,
        current_run_id=html_state["run_id"],
        keep=int(html_state.get("history_retention", default_value("reporting.history_retention"))),
    )


def _build_case_bundle(run_root: Path, row: dict[str, Any]) -> dict[str, Any]:
    case_slug = _slugify(str(row["nodeid"]))
    case_dir = run_root / "cases" / case_slug
    screenshot_dir = case_dir / "screenshots"
    source_dir = case_dir / "page_source"
    diff_dir = case_dir / "diffs"
    for directory in (screenshot_dir, source_dir, diff_dir):
        directory.mkdir(parents=True, exist_ok=True)

    staged_steps = []
    for step in row.get("steps", []):
        staged_steps.append(
            {
                **step,
                "duration_label": _duration_label(int(step.get("duration_ms", 0) or 0)),
                "screenshot_rel": _stage_asset(
                    step.get("screenshot_path", ""), screenshot_dir, case_dir
                ),
                "previous_screenshot_rel": _stage_asset(
                    step.get("previous_screenshot_path", ""), screenshot_dir, case_dir
                ),
                "diff_rel": _stage_asset(step.get("diff_path", ""), diff_dir, case_dir),
                "source_rel": _stage_asset(step.get("source_path", ""), source_dir, case_dir),
            }
        )

    staged_case = {
        **row,
        "case_slug": case_slug,
        "case_dir": case_dir,
        "steps": staged_steps,
        "step_duration_label": _duration_label(int(row.get("step_duration_ms", 0) or 0)),
        "screenshot_rel": _stage_asset(row.get("screenshot", ""), screenshot_dir, case_dir),
        "xml_rel": _stage_asset(row.get("xml", ""), source_dir, case_dir),
    }

    case_html = _render_case_page(staged_case, stylesheet_href="../../report.css")
    (case_dir / "index.html").write_text(case_html, encoding="utf-8")
    return staged_case


def _build_case_summary_for_latest(case: dict[str, Any]) -> dict[str, Any]:
    latest_case = dict(case)
    latest_case["case_link"] = f"latest/cases/{case['case_slug']}/index.html"
    return latest_case


def _stage_asset(source: str, destination_dir: Path, case_dir: Path) -> str:
    if not source:
        return ""

    source_path = Path(source)
    if not source_path.exists():
        return ""

    destination_dir.mkdir(parents=True, exist_ok=True)
    target = destination_dir / source_path.name
    shutil.copy2(source_path, target)
    return os.path.relpath(target, case_dir)


def _render_suite_page(
    *,
    cases: list[dict[str, Any]],
    title: str,
    subtitle: str,
    duration: float,
    exitstatus: int,
    recent_runs: list[dict[str, str]],
    stylesheet_href: str,
) -> str:
    total = len(cases)
    passed = sum(1 for case in cases if case["outcome"] == "PASSED")
    failed = sum(1 for case in cases if case["outcome"] == "FAILED")
    skipped = sum(1 for case in cases if case["outcome"] == "SKIPPED")
    success_rate = (passed / total * 100) if total else 0.0

    return _render_template(
        "suite.html.j2",
        title=title,
        subtitle=subtitle,
        duration=f"{duration:.2f}s",
        exitstatus=exitstatus,
        stylesheet_href=stylesheet_href,
        metrics={
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "success_rate": f"{success_rate:.1f}%",
        },
        cases=cases,
        recent_runs=recent_runs,
    )


def _render_case_page(case: dict[str, Any], *, stylesheet_href: str) -> str:
    return _render_template(
        "case.html.j2",
        case=case,
        stylesheet_href=stylesheet_href,
    )


def _render_template(template_name: str, **context: Any) -> str:
    env = Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=select_autoescape(("html", "xml")),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    return env.get_template(template_name).render(**context)


def _write_report_css(target: Path) -> None:
    target.write_text((ASSETS_DIR / CSS_FILE_NAME).read_text(encoding="utf-8"), encoding="utf-8")


def _duration_label(duration_ms: int) -> str:
    if duration_ms <= 0:
        return "-"
    if duration_ms >= 1000:
        return f"{duration_ms / 1000:.2f}s"
    return f"{duration_ms}ms"


def _slugify(value: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in value).strip("_").lower() or "case"


def _build_run_id() -> str:
    github_run_id = os.getenv("GITHUB_RUN_ID")
    if github_run_id:
        return github_run_id
    return f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}_{uuid4().hex[:8]}"


def _load_reporting_config(config: pytest.Config) -> dict[str, Any]:
    try:
        from framework.core.config import ConfigManager

        config_path = config.getoption("--config")
        manager = ConfigManager.load(config_path)
        reporting_config = manager.get("reporting", {}) or {}
        return dict(reporting_config)
    except Exception:
        return {}


def _prune_old_runs(reports_root: Path, *, current_run_id: str, keep: int) -> None:
    if keep <= 0:
        return

    runs_root = reports_root / "runs"
    if not runs_root.exists():
        return

    run_dirs = sorted(
        (path for path in runs_root.iterdir() if path.is_dir()),
        key=lambda path: (path.stat().st_mtime_ns, path.name),
        reverse=True,
    )
    keep_names: list[str] = []
    if (runs_root / current_run_id).exists():
        keep_names.append(current_run_id)
    for run_dir in run_dirs:
        if len(keep_names) >= keep:
            break
        if run_dir.name in keep_names:
            continue
        keep_names.append(run_dir.name)
    keep_name_set = set(keep_names)
    for run_dir in run_dirs:
        if run_dir.name in keep_name_set:
            continue
        shutil.rmtree(run_dir)


def _recent_run_entries(
    reports_root: Path, current_run_id: str, relative_mode: str
) -> list[dict[str, str]]:
    runs_root = reports_root / "runs"
    if not runs_root.exists():
        return []

    entries = []
    for run_dir in sorted((path for path in runs_root.iterdir() if path.is_dir()), reverse=True)[
        :10
    ]:
        if relative_mode == "run":
            href = (
                "index.html" if run_dir.name == current_run_id else f"../{run_dir.name}/index.html"
            )
        else:
            href = f"runs/{run_dir.name}/index.html"
        entries.append(
            {
                "run_id": run_dir.name,
                "href": href,
            }
        )
    return entries
