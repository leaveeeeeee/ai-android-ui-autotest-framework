from __future__ import annotations

import html
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
REPORT_DIR = ARTIFACTS_DIR / "reports"
REPORT_DATA_DIR = ARTIFACTS_DIR / "report_data"
SCREENSHOT_DIR = REPORT_DATA_DIR / "screenshots"
XML_DIR = REPORT_DATA_DIR / "page_source"

SERIAL = "5b06a7fa"
PACKAGE = "mark.via"
ACTIVITY = ".Shell"
START_URL = "https://www.baidu.com"
KEYWORD = "chatgpt"


@dataclass
class StepResult:
    name: str
    passed: bool
    detail: str
    screenshot: Optional[Path] = None
    xml_path: Optional[Path] = None


@dataclass
class TestReport:
    title: str
    started_at: float = field(default_factory=time.time)
    steps: list[StepResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(step.passed for step in self.steps)

    @property
    def duration_seconds(self) -> float:
        return time.time() - self.started_at

    def add(self, step: StepResult) -> None:
        self.steps.append(step)


def run_adb(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    cmd = ["adb", "-s", SERIAL, *args]
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def shell(command: str, check: bool = True) -> str:
    result = run_adb("shell", command, check=check)
    return result.stdout.strip()


def tap(x: int, y: int) -> None:
    shell(f"input tap {x} {y}")


def input_text(value: str) -> None:
    escaped = value.replace(" ", "%s")
    shell(f"input text {escaped}")


def start_via_with_baidu() -> str:
    result = shell(f"am start -n {PACKAGE}/{ACTIVITY} -d {START_URL}")
    return result


def dump_hierarchy(name: str) -> tuple[ET.Element, Path]:
    remote_path = f"/sdcard/{name}.xml"
    shell(f"uiautomator dump {remote_path}")
    xml_text = shell(f"cat {remote_path}")
    local_path = XML_DIR / f"{name}.xml"
    local_path.write_text(xml_text, encoding="utf-8")
    return ET.fromstring(xml_text), local_path


def screenshot(name: str) -> Path:
    remote_path = f"/sdcard/{name}.png"
    local_path = SCREENSHOT_DIR / f"{name}.png"
    run_adb("shell", "screencap", "-p", remote_path)
    png_bytes = run_adb("exec-out", "cat", remote_path).stdout.encode("latin1", errors="ignore")
    local_path.write_bytes(png_bytes)
    return local_path


def iter_nodes(root: ET.Element) -> Iterable[ET.Element]:
    for node in root.iter("node"):
        yield node


def parse_bounds(bounds: str) -> tuple[int, int, int, int]:
    left_top, right_bottom = bounds.split("][")
    left, top = left_top.replace("[", "").split(",")
    right, bottom = right_bottom.replace("]", "").split(",")
    return int(left), int(top), int(right), int(bottom)


def center_of(node: ET.Element) -> tuple[int, int]:
    left, top, right, bottom = parse_bounds(node.attrib["bounds"])
    return (left + right) // 2, (top + bottom) // 2


def find_node(
    root: ET.Element,
    *,
    resource_id: str | None = None,
    text_value: str | None = None,
    content_desc: str | None = None,
) -> Optional[ET.Element]:
    for node in iter_nodes(root):
        if resource_id is not None and node.attrib.get("resource-id") != resource_id:
            continue
        if text_value is not None and node.attrib.get("text") != text_value:
            continue
        if content_desc is not None and node.attrib.get("content-desc") != content_desc:
            continue
        return node
    return None


def find_search_button(root: ET.Element) -> Optional[ET.Element]:
    candidates = [
        {"resource_id": "index-bn"},
        {"text_value": "提交"},
        {"text_value": "百度一下"},
        {"content_desc": "搜索"},
    ]
    for candidate in candidates:
        node = find_node(root, **candidate)
        if node is not None:
            return node
    return None


def ensure_dirs() -> None:
    for path in (REPORT_DIR, SCREENSHOT_DIR, XML_DIR):
        path.mkdir(parents=True, exist_ok=True)


def write_html_report(report: TestReport) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / "via_baidu_adb_report.html"
    step_rows = []
    for step in report.steps:
        status = "PASS" if step.passed else "FAIL"
        color = "#1f7a1f" if step.passed else "#b42318"
        screenshot_link = (
            f'<a href="../screenshots/{step.screenshot.name}">{html.escape(step.screenshot.name)}</a>'
            if step.screenshot
            else "-"
        )
        xml_link = (
            f'<a href="../page_source/{step.xml_path.name}">{html.escape(step.xml_path.name)}</a>'
            if step.xml_path
            else "-"
        )
        step_rows.append(
            "<tr>"
            f"<td>{html.escape(step.name)}</td>"
            f"<td style='color:{color};font-weight:700'>{status}</td>"
            f"<td>{html.escape(step.detail)}</td>"
            f"<td>{screenshot_link}</td>"
            f"<td>{xml_link}</td>"
            "</tr>"
        )

    html_text = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>{html.escape(report.title)}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 32px; color: #111827; }}
    h1 {{ margin-bottom: 8px; }}
    .summary {{ margin-bottom: 24px; padding: 16px; background: #f3f4f6; border-radius: 12px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ border: 1px solid #d1d5db; padding: 10px; text-align: left; vertical-align: top; }}
    th {{ background: #e5e7eb; }}
  </style>
</head>
<body>
  <h1>{html.escape(report.title)}</h1>
  <div class="summary">
    <div>整体结果: {"PASS" if report.passed else "FAIL"}</div>
    <div>设备 ID: {html.escape(SERIAL)}</div>
    <div>应用: {html.escape(PACKAGE + "/" + ACTIVITY)}</div>
    <div>测试场景: Via 浏览器打开百度并搜索 chatgpt</div>
    <div>耗时: {report.duration_seconds:.2f} 秒</div>
  </div>
  <table>
    <thead>
      <tr>
        <th>步骤</th>
        <th>状态</th>
        <th>详情</th>
        <th>截图</th>
        <th>页面层级</th>
      </tr>
    </thead>
    <tbody>
      {''.join(step_rows)}
    </tbody>
  </table>
</body>
</html>
"""
    report_path.write_text(html_text, encoding="utf-8")
    return report_path


def main() -> int:
    ensure_dirs()
    report = TestReport(title="Via 打开百度并搜索 chatgpt")

    try:
        detail = start_via_with_baidu()
        time.sleep(2)
        report.add(
            StepResult(
                name="启动 Via 并打开百度",
                passed=True,
                detail=detail or "Activity started",
                screenshot=screenshot("01_open_baidu"),
            )
        )

        root, xml_path = dump_hierarchy("01_home")
        top_bar = find_node(root, text_value="百度一下")
        if top_bar is None:
            raise RuntimeError("未找到 Via 顶部地址栏文本“百度一下”")
        tap(*center_of(top_bar))
        time.sleep(1)
        report.add(
            StepResult(
                name="打开搜索面板",
                passed=True,
                detail="已点击 Via 顶部地址栏",
                screenshot=screenshot("02_open_search_panel"),
                xml_path=xml_path,
            )
        )

        root, xml_path = dump_hierarchy("02_search_panel")
        search_input_node = find_node(root, resource_id="index-kw")
        if search_input_node is None:
            raise RuntimeError("未找到百度搜索输入框 resource-id=index-kw")
        tap(*center_of(search_input_node))
        time.sleep(0.5)
        input_text(KEYWORD)
        time.sleep(1)
        report.add(
            StepResult(
                name="输入关键词",
                passed=True,
                detail=f"已输入关键词: {KEYWORD}",
                screenshot=screenshot("03_input_keyword"),
                xml_path=xml_path,
            )
        )

        root, xml_path = dump_hierarchy("03_after_input")
        search_button = find_search_button(root)
        if search_button is None:
            raise RuntimeError("未找到百度搜索按钮")
        tap(*center_of(search_button))
        time.sleep(3)
        report.add(
            StepResult(
                name="点击搜索按钮",
                passed=True,
                detail="已点击百度搜索按钮",
                screenshot=screenshot("04_click_search"),
                xml_path=xml_path,
            )
        )

        root, xml_path = dump_hierarchy("04_result_page")
        xml_text = xml_path.read_text(encoding="utf-8", errors="ignore").lower()
        matched = "chatgpt" in xml_text
        report.add(
            StepResult(
                name="校验搜索结果",
                passed=matched,
                detail="搜索结果页已包含 chatgpt" if matched else "搜索结果页中未检测到 chatgpt",
                screenshot=screenshot("05_result_validation"),
                xml_path=xml_path,
            )
        )
    except Exception as exc:
        fail_name = f"failure_{int(time.time())}"
        screenshot_path = screenshot(fail_name)
        root, xml_path = dump_hierarchy(fail_name)
        report.add(
            StepResult(
                name="执行异常",
                passed=False,
                detail=str(exc),
                screenshot=screenshot_path,
                xml_path=xml_path,
            )
        )

    report_path = write_html_report(report)
    print(f"Overall result: {'PASS' if report.passed else 'FAIL'}")
    print(f"HTML report: {report_path}")
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
