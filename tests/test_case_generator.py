from __future__ import annotations

import sys

from framework.generator.models import TextCaseSpec
from framework.generator.renderer import render_ai_prompt, render_test_case
from scripts import generate_cases_from_excel


def test_render_test_case_with_python_calls():
    spec = TextCaseSpec.from_mapping(
        {
            "case_id": "via_baidu_search_chatgpt",
            "module": "search",
            "title": "Via 搜索 chatgpt",
            "fixture": "via_baidu_page",
            "page_object": "ViaBaiduPage",
            "python_calls": 'via_baidu_page.search("chatgpt")\nassert via_baidu_page.is_result_loaded("chatgpt")',
            "markers": "smoke,device",
        }
    )

    code = render_test_case(spec)

    assert "def test_search_via_baidu_search_chatgpt" in code
    assert "@pytest.mark.smoke" in code
    assert 'via_baidu_page.search("chatgpt")' in code


def test_render_test_case_supports_feature_marker():
    spec = TextCaseSpec.from_mapping(
        {
            "case_id": "via_baidu_feature_search",
            "module": "search",
            "title": "Via 搜索 feature marker",
            "fixture": "via_baidu_page",
            "page_object": "ViaBaiduPage",
            "python_calls": 'assert via_baidu_page.is_result_loaded("chatgpt")',
            "markers": 'smoke,feature("search")',
        }
    )

    code = render_test_case(spec)

    assert '@pytest.mark.feature("search")' in code


def test_render_test_case_skips_unsafe_fixture_and_marker() -> None:
    spec = TextCaseSpec.from_mapping(
        {
            "case_id": "bad_case",
            "module": "search",
            "title": "bad",
            "fixture": "request):\n    assert False\n#",
            "python_calls": "assert True",
            "markers": 'smoke,evil("x")',
        }
    )

    code = render_test_case(spec)

    assert "@pytest.mark.smoke" in code
    assert "evil" not in code.split("def ", maxsplit=1)[0]
    assert "def test_search_bad_case(via_baidu_page):" in code
    assert "Unsafe generated case" in code
    assert "fixture is not allowed" in code


def test_render_test_case_skips_invalid_python_calls() -> None:
    spec = TextCaseSpec.from_mapping(
        {
            "case_id": "bad_python",
            "module": "search",
            "title": "bad python",
            "fixture": "via_baidu_page",
            "python_calls": "via_baidu_page.search(",
            "markers": "smoke,device",
        }
    )

    code = render_test_case(spec)

    assert "Invalid generated python_calls" in code
    assert "via_baidu_page.search(" not in code.split("pytest.skip", maxsplit=1)[-1]


def test_render_ai_prompt_for_incomplete_case():
    spec = TextCaseSpec.from_mapping(
        {
            "case_id": "missing_calls",
            "title": "缺少结构化调用",
            "fixture": "via_baidu_page",
            "page_object": "ViaBaiduPage",
            "steps": "1. 输入 chatgpt 2. 点击搜索",
            "expected": "结果页中包含 chatgpt",
        }
    )

    prompt = render_ai_prompt(spec)

    assert "ViaBaiduPage" in prompt
    assert "结果页中包含 chatgpt" in prompt


def test_text_case_spec_from_mapping_restores_defaults_and_newlines() -> None:
    spec = TextCaseSpec.from_mapping(
        {
            "title": "搜索 / 特殊? Case",
            "module": "搜索模块",
            "steps": "1. 打开首页\\n2. 搜索 chatgpt",
            "expected": "出现结果\\n且可点击",
            "fixture": "",
            "page_object": "",
        }
    )

    assert spec.case_id == "case"
    assert spec.module == "generated"
    assert spec.fixture == "via_baidu_page"
    assert spec.page_object == "ViaBaiduPage"
    assert spec.steps == "1. 打开首页\n2. 搜索 chatgpt"
    assert spec.expected == "出现结果\n且可点击"
    assert spec.markers == "smoke,device"


def test_render_test_case_without_calls_emits_skip_and_docstring() -> None:
    spec = TextCaseSpec.from_mapping(
        {
            "case_id": "missing_calls",
            "module": "search",
            "title": "缺少结构化调用",
            "fixture": "via_baidu_page",
            "precondition": "已打开百度首页",
            "steps": "1. 输入 chatgpt",
            "expected": "出现结果页",
        }
    )

    code = render_test_case(spec)

    assert 'pytest.skip("Structured python_calls not provided.' in code
    assert "用例标题: 缺少结构化调用" in code
    assert "前置条件: 已打开百度首页" in code
    assert "def test_search_missing_calls" in code


def test_render_ai_prompt_locks_output_constraints() -> None:
    spec = TextCaseSpec.from_mapping(
        {
            "case_id": "ai_case",
            "module": "search",
            "title": "AI 生成 case",
            "fixture": "via_baidu_page",
            "page_object": "ViaBaiduPage",
            "ai_notes": "优先复用已有页面对象方法",
        }
    )

    prompt = render_ai_prompt(spec)

    assert "测试函数命名必须为 `test_search_ai_case`" in prompt
    assert "使用现有 fixture: `via_baidu_page`" in prompt
    assert "优先复用已有页面对象方法" in prompt
    assert "1. 先输出测试函数代码" in prompt


def test_generate_cases_script_cleans_stale_outputs(tmp_path, monkeypatch):
    input_file = tmp_path / "cases.csv"
    output_dir = tmp_path / "generated"
    prompt_dir = tmp_path / "prompts"

    input_file.write_text(
        "\n".join(
            [
                "case_id,module,title,fixture,page_object,python_calls,expected",
                'keep_case,search,保留用例,via_baidu_page,ViaBaiduPage,"via_baidu_page.search(""chatgpt"")",搜索成功',
                "remove_case,search,待删除用例,via_baidu_page,ViaBaiduPage,,需要 AI 补全",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "generate_cases_from_excel.py",
            str(input_file),
            "--output-dir",
            str(output_dir),
            "--prompt-dir",
            str(prompt_dir),
        ],
    )
    assert generate_cases_from_excel.main() == 0

    removed_case = output_dir / "test_search_remove_case.py"
    removed_prompt = prompt_dir / "remove_case.md"
    assert removed_case.exists()
    assert removed_prompt.exists()

    input_file.write_text(
        "\n".join(
            [
                "case_id,module,title,fixture,page_object,python_calls,expected",
                'keep_case,search,保留用例,via_baidu_page,ViaBaiduPage,"via_baidu_page.search(""chatgpt"")",搜索成功',
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "generate_cases_from_excel.py",
            str(input_file),
            "--output-dir",
            str(output_dir),
            "--prompt-dir",
            str(prompt_dir),
        ],
    )
    assert generate_cases_from_excel.main() == 0

    assert not removed_case.exists()
    assert not removed_prompt.exists()
    assert len(list((output_dir / ".manifest").glob("*.json"))) == 1
