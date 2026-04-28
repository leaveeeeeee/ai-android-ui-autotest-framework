from __future__ import annotations

from framework.core.xpath import xpath_literal


def test_xpath_literal_uses_double_quotes_for_simple_text() -> None:
    assert xpath_literal("chatgpt") == '"chatgpt"'


def test_xpath_literal_uses_single_quotes_when_text_contains_double_quote() -> None:
    assert xpath_literal('chat"gpt') == "'chat\"gpt'"


def test_xpath_literal_uses_concat_when_text_contains_both_quote_types() -> None:
    assert xpath_literal("chat\"gpt's") == 'concat("chat", \'"\', "gpt\'s")'
