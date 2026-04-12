from __future__ import annotations

from textwrap import dedent, indent

from framework.generator.models import TextCaseSpec


def render_test_case(spec: TextCaseSpec) -> str:
    marker_lines = "\n".join(f"@pytest.mark.{marker}" for marker in spec.marker_list)
    if spec.has_executable_calls:
        body = spec.python_calls.rstrip()
    else:
        body = (
            'pytest.skip("Structured python_calls not provided. '
            'Use the generated AI prompt to finish this case.")'
        )

    docstring = dedent(f'''"""
用例标题: {spec.title}
前置条件: {spec.precondition or "-"}
测试步骤:
{spec.steps or "-"}
预期结果:
{spec.expected or "-"}
"""''').strip()

    return f"""from __future__ import annotations

import pytest


{marker_lines}
def {spec.test_name}({spec.fixture}):
{indent(docstring, "    ")}
{indent(body, "    ")}
"""


def render_ai_prompt(spec: TextCaseSpec) -> str:
    return f"""# AI 用例生成提示词

你是一个安卓 UI 自动化框架代码生成助手，请基于下面的测试文本，为当前框架生成可执行 pytest 用例。

## 生成约束
- 使用现有 fixture: `{spec.fixture}`
- 使用现有页面对象: `{spec.page_object}`
- 优先调用页面对象业务方法，不直接在测试里散落底层 driver 调用
- 测试函数命名必须为 `{spec.test_name}`
- 使用 `pytest.mark.device`，并按需保留 `smoke`
- 如果页面对象缺方法，可以同时补充页面对象方法实现建议
- 断言必须清晰，失败信息要可读

## 原始测试文本
- 用例标题: {spec.title}
- 前置条件: {spec.precondition or "-"}
- 测试步骤:
{spec.steps or "-"}
- 预期结果:
{spec.expected or "-"}
- AI 补充说明:
{spec.ai_notes or "-"}

## 输出要求
1. 先输出测试函数代码
2. 如果需要新增页面对象方法，再输出对应方法代码
3. 不要解释框架背景，只输出代码和必要注释
"""
