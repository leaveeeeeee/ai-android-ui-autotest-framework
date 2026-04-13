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
