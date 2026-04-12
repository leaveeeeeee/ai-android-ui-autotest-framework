from __future__ import annotations

import pytest


@pytest.mark.smoke
@pytest.mark.device
def test_via_browser_search_chatgpt(via_baidu_page):
    via_baidu_page.search("chatgpt")
    assert via_baidu_page.is_result_loaded("chatgpt")
