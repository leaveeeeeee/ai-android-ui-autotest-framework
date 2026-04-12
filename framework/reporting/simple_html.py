"""结构化 HTML 报告生成器。

这个模块负责把 pytest 执行结果整理成一套可浏览的静态报告页面：
- 总览页
- latest 最新报告
- runs 历史运行报告
- 单用例步骤详情页
"""

from __future__ import annotations

import html
import os
import shutil
import time
from pathlib import Path

import pytest

from framework.reporting.runtime_store import get_case_report_store


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
    run_id = time.strftime("%Y%m%d_%H%M%S")
    run_root = reports_root / "runs" / run_id
    run_root.mkdir(parents=True, exist_ok=True)

    config._framework_simple_html = {
        "path": target,
        "reports_root": reports_root,
        "run_root": run_root,
        "run_id": run_id,
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

    existing = next((row for row in html_state["rows"] if row["nodeid"] == item.nodeid), None)
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
        "steps": list(store.get("steps", [])),
    }

    if report.when == "teardown" and existing is not None:
        existing["postcheck"] = postcheck or existing.get("postcheck", "")
        existing["steps"] = list(store.get("steps", []))
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

    cases = [_build_case_bundle(run_root, row) for row in rows]
    suite_html = _render_suite_page(
        cases=cases,
        title="Android UI Framework Report",
        subtitle=f"Run ID: {html_state['run_id']}",
        duration=duration,
        exitstatus=exitstatus,
        case_link_prefix="cases",
        recent_runs=_recent_run_entries(
            reports_root, current_run_id=html_state["run_id"], relative_mode="run"
        ),
    )
    (run_root / "index.html").write_text(suite_html, encoding="utf-8")

    if latest_root.exists():
        shutil.rmtree(latest_root)
    shutil.copytree(run_root, latest_root)

    latest_cases = [_build_case_summary_for_latest(case) for case in cases]
    latest_html = _render_suite_page(
        cases=latest_cases,
        title="Android UI Framework Latest Report",
        subtitle=f"Latest run: {html_state['run_id']}",
        duration=duration,
        exitstatus=exitstatus,
        case_link_prefix="latest/cases",
        recent_runs=_recent_run_entries(
            reports_root, current_run_id=html_state["run_id"], relative_mode="root"
        ),
    )
    (reports_root / "index.html").write_text(latest_html, encoding="utf-8")
    html_state["path"].write_text(latest_html, encoding="utf-8")


def _build_case_bundle(run_root: Path, row: dict) -> dict:
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
        "screenshot_rel": _stage_asset(row.get("screenshot", ""), screenshot_dir, case_dir),
        "xml_rel": _stage_asset(row.get("xml", ""), source_dir, case_dir),
    }

    case_html = _render_case_page(staged_case)
    (case_dir / "index.html").write_text(case_html, encoding="utf-8")
    return staged_case


def _build_case_summary_for_latest(case: dict) -> dict:
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
    cases: list[dict],
    title: str,
    subtitle: str,
    duration: float,
    exitstatus: int,
    case_link_prefix: str,
    recent_runs: list[dict],
) -> str:
    total = len(cases)
    passed = sum(1 for case in cases if case["outcome"] == "PASSED")
    failed = sum(1 for case in cases if case["outcome"] == "FAILED")
    skipped = sum(1 for case in cases if case["outcome"] == "SKIPPED")
    success_rate = (passed / total * 100) if total else 0.0

    case_rows = []
    for case in cases:
        color = {
            "PASSED": "#166534",
            "FAILED": "#b91c1c",
            "SKIPPED": "#92400e",
        }.get(case["outcome"], "#374151")
        case_link = case.get("case_link") or f"{case_link_prefix}/{case['case_slug']}/index.html"
        case_rows.append(
            "<tr>"
            f"<td><a href='{html.escape(case_link)}'>{html.escape(case['nodeid'])}</a></td>"
            f"<td style='color:{color};font-weight:700'>{html.escape(case['outcome'])} ({html.escape(case['phase'])})</td>"
            f"<td>{html.escape(case['duration'])}</td>"
            f"<td>{len(case.get('steps', []))}</td>"
            f"<td><pre style='white-space:pre-wrap;max-width:480px'>{html.escape(_shorten(case.get('message', '')))}</pre></td>"
            "</tr>"
        )

    run_rows = []
    for run in recent_runs:
        run_rows.append(
            "<tr>"
            f"<td>{html.escape(run['run_id'])}</td>"
            f"<td><a href='{html.escape(run['href'])}'>打开</a></td>"
            "</tr>"
        )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 32px; color: #111827; background:#f8fafc; }}
    h1 {{ margin-bottom: 6px; }}
    .subtitle {{ color:#4b5563; margin-bottom:24px; }}
    .metrics {{ display:grid; grid-template-columns:repeat(5,minmax(140px,1fr)); gap:12px; margin-bottom:24px; }}
    .card {{ background:white; border:1px solid #dbe2ea; border-radius:14px; padding:16px; }}
    .metric-label {{ color:#6b7280; font-size:13px; }}
    .metric-value {{ font-size:24px; font-weight:700; margin-top:6px; }}
    table {{ width:100%; border-collapse: collapse; background:white; }}
    th, td {{ border: 1px solid #d1d5db; padding: 10px; text-align: left; vertical-align: top; }}
    th {{ background: #e5e7eb; }}
    .section {{ margin-top:28px; }}
  </style>
</head>
<body>
  <h1>{html.escape(title)}</h1>
  <div class="subtitle">{html.escape(subtitle)}</div>
  <div class="metrics">
    <div class="card"><div class="metric-label">总用例数</div><div class="metric-value">{total}</div></div>
    <div class="card"><div class="metric-label">通过</div><div class="metric-value">{passed}</div></div>
    <div class="card"><div class="metric-label">失败</div><div class="metric-value">{failed}</div></div>
    <div class="card"><div class="metric-label">跳过</div><div class="metric-value">{skipped}</div></div>
    <div class="card"><div class="metric-label">成功率</div><div class="metric-value">{success_rate:.1f}%</div></div>
    <div class="card"><div class="metric-label">总耗时 / Exit</div><div class="metric-value">{duration:.2f}s / {exitstatus}</div></div>
  </div>

  <div class="section">
    <h2>用例总览</h2>
    <table>
      <thead>
        <tr>
          <th>用例</th><th>结果</th><th>耗时</th><th>步骤数</th><th>失败摘要 / 环境信息</th>
        </tr>
      </thead>
      <tbody>
        {"".join(case_rows) or '<tr><td colspan="5">No cases recorded.</td></tr>'}
      </tbody>
    </table>
  </div>

  <div class="section">
    <h2>运行历史</h2>
    <table>
      <thead><tr><th>Run ID</th><th>详情</th></tr></thead>
      <tbody>{"".join(run_rows) or '<tr><td colspan="2">No historical runs.</td></tr>'}</tbody>
    </table>
  </div>
</body>
</html>
"""


def _render_case_page(case: dict) -> str:
    color = {
        "PASSED": "#166534",
        "FAILED": "#b91c1c",
        "SKIPPED": "#92400e",
    }.get(case["outcome"], "#374151")

    step_rows = []
    for step in case.get("steps", []):
        step_rows.append(
            "<tr>"
            f"<td>{step.get('index', '')}</td>"
            f"<td>{html.escape(str(step.get('name', '')))}</td>"
            f"<td style='color:{'#166534' if step.get('status') == 'PASSED' else '#b91c1c'};font-weight:700'>{html.escape(str(step.get('status', '')))}</td>"
            f"<td>{html.escape(str(step.get('expected', '')))}</td>"
            f"<td>{html.escape(str(step.get('actual', '')))}</td>"
            f"<td>{html.escape(str(step.get('comparison', '')))}</td>"
            f"<td><pre style='white-space:pre-wrap'>{html.escape(str(step.get('logs', '')))}</pre></td>"
            f"<td><pre style='white-space:pre-wrap'>{html.escape(str(step.get('focus_window', '')))}</pre></td>"
            f"<td>{_img_cell(step.get('previous_screenshot_rel', ''), '前一步截图')}</td>"
            f"<td>{_img_cell(step.get('screenshot_rel', ''), '当前步骤截图')}</td>"
            f"<td>{_img_cell(step.get('diff_rel', ''), '差异对比图')}</td>"
            f"<td>{_link_cell(step.get('source_rel', ''), '页面层级')}</td>"
            f"<td><pre style='white-space:pre-wrap'>{html.escape(str(step.get('detail', '')))}</pre></td>"
            "</tr>"
        )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>{html.escape(case["nodeid"])}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 24px; color: #111827; background:#f8fafc; }}
    .topbar {{ margin-bottom:24px; }}
    .summary {{ background:white; border:1px solid #dbe2ea; border-radius:14px; padding:16px; margin-bottom:20px; }}
    table {{ width:100%; border-collapse: collapse; background:white; }}
    th, td {{ border: 1px solid #d1d5db; padding: 10px; text-align: left; vertical-align: top; }}
    th {{ background: #e5e7eb; }}
    img {{ max-width:220px; border:1px solid #d1d5db; border-radius:8px; }}
  </style>
</head>
<body>
  <div class="topbar"><a href="../../index.html">返回套件总览</a></div>
  <h1>{html.escape(case["nodeid"])}</h1>
  <div class="summary">
    <div>结果: <span style="color:{color};font-weight:700">{html.escape(case["outcome"])} ({html.escape(case["phase"])})</span></div>
    <div>耗时: {html.escape(case["duration"])}</div>
    <div>步骤数: {len(case.get("steps", []))}</div>
    <div>基线定义: <code>{html.escape(str(case.get("baseline", "")) or "-")}</code></div>
  </div>
  <div class="summary">
    <h3>失败原因 / 环境信息</h3>
    <pre style='white-space:pre-wrap'>{html.escape(case.get("message", "")) or "-"}</pre>
  </div>
  <table>
    <thead>
      <tr>
        <th>#</th><th>步骤</th><th>状态</th><th>预期</th><th>实际</th><th>对比</th><th>步骤日志</th><th>当前焦点窗口</th><th>前一步截图</th><th>当前截图</th><th>差异图</th><th>页面层级</th><th>说明</th>
      </tr>
    </thead>
    <tbody>
      {"".join(step_rows) or '<tr><td colspan="13">No step rows recorded.</td></tr>'}
    </tbody>
  </table>
</body>
</html>
"""


def _img_cell(rel_path: str, alt: str) -> str:
    if not rel_path:
        return "-"
    return f'<a href="{html.escape(rel_path)}"><img src="{html.escape(rel_path)}" alt="{html.escape(alt)}" /></a>'


def _link_cell(rel_path: str, label: str) -> str:
    if not rel_path:
        return "-"
    return f'<a href="{html.escape(rel_path)}">{html.escape(label)}</a>'


def _slugify(value: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in value).strip("_").lower() or "case"


def _shorten(message: str, limit: int = 280) -> str:
    stripped = message.strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[: limit - 3] + "..."


def _recent_run_entries(reports_root: Path, current_run_id: str, relative_mode: str) -> list[dict]:
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
