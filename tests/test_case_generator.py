from __future__ import annotations

from framework.generator.models import TextCaseSpec
from framework.generator.renderer import render_ai_prompt, render_test_case


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
