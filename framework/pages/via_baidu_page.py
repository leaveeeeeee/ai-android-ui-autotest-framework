from __future__ import annotations

from framework.core.base_page import BasePage
from framework.core.locator import Locator


class ViaBaiduPage(BasePage):
    """Via 浏览器中的百度搜索页面对象。"""

    top_address_bar = Locator(
        name="top_address_bar",
        strategy="xpath",
        value='//*[@class="android.widget.TextView" and @text="百度一下"]',
        fallback=[
            Locator(
                name="top_address_bar_desc",
                strategy="description",
                value="搜索",
            )
        ],
    )

    search_input = Locator(
        name="baidu_search_input",
        strategy="xpath",
        value='//*[@resource-id="index-kw"]',
        fallback=[
            Locator(
                name="baidu_search_input_hint",
                strategy="xpath",
                value='//*[@class="android.widget.EditText" and (@resource-id="index-kw" or @hint="搜索")]',
            )
        ],
    )

    search_button = Locator(
        name="baidu_search_button",
        strategy="xpath",
        value='//*[@resource-id="index-bn"]',
        fallback=[
            Locator(
                name="baidu_search_submit",
                strategy="xpath",
                value='//*[@text="提交"]',
            ),
            Locator(
                name="baidu_search_submit_alt",
                strategy="xpath",
                value='//*[@text="百度一下"]',
            ),
        ],
    )

    result_page_keyword = Locator(
        name="result_page_keyword",
        strategy="xpath",
        value='//*[@text="chatgpt"]',
        fallback=[
            Locator(
                name="result_page_keyword_contains",
                strategy="xpath",
                value='//*[contains(@text, "chatgpt")]',
            )
        ],
        timeout=15,
    )

    def open_search_panel(self) -> None:
        """打开 Via 顶部搜索面板。"""
        bounds = self.driver.get_bounds(self.top_address_bar)
        self.click(self.top_address_bar)
        self.record_step(
            name="打开搜索面板",
            detail="点击 Via 顶部地址栏，切换到搜索输入态。",
            expected="显示可输入的搜索面板。",
            actual="已点击顶部地址栏。",
            comparison="PASS",
            logs=f"action=click locator={self.top_address_bar.name}",
            highlight_rect=bounds,
        )

    def search(self, keyword: str) -> None:
        """执行搜索动作。

        标准流程：
        1. 检查首页搜索框是否直接可见
        2. 如不可见，则先打开搜索面板
        3. 点击搜索框并输入关键词
        4. 点击搜索按钮提交查询
        """
        if not self.is_visible(self.search_input):
            self.record_step(
                name="检查首页搜索框",
                detail="百度首页搜索框未直接可见，切换到 Via 搜索面板。",
                expected="可直接定位搜索输入框。",
                actual="首页搜索框未直接可见，改为打开搜索面板。",
                comparison="FALLBACK",
                logs=f"visibility=false locator={self.search_input.name}",
            )
            self.open_search_panel()
        else:
            self.record_step(
                name="检查首页搜索框",
                detail="百度首页搜索框已直接可见。",
                expected="可直接定位搜索输入框。",
                actual="已定位到首页搜索框。",
                comparison="PASS",
                logs=f"visibility=true locator={self.search_input.name}",
            )
        search_input_bounds = self.driver.get_bounds(self.search_input)
        self.click(self.search_input)
        self.record_step(
            name="点击搜索框",
            detail="聚焦百度搜索输入框。",
            expected="搜索框进入可输入状态。",
            actual="已点击搜索框。",
            comparison="PASS",
            logs=f"action=click locator={self.search_input.name}",
            highlight_rect=search_input_bounds,
        )
        self.input_text(self.search_input, keyword)
        self.record_step(
            name="输入搜索词",
            detail=f"在搜索框中覆盖输入关键词：{keyword}",
            expected=f"输入框内容应更新为 {keyword}",
            actual=f"已执行输入：{keyword}",
            comparison="PASS",
            logs=f'action=set_text locator={self.search_input.name} value="{keyword}"',
            highlight_rect=search_input_bounds,
        )
        search_button_bounds = self.driver.get_bounds(self.search_button)
        self.click(self.search_button)
        self.record_step(
            name="点击搜索按钮",
            detail="点击百度搜索按钮提交查询。",
            expected="页面跳转到搜索结果页。",
            actual="已点击搜索按钮。",
            comparison="PASS",
            logs=f"action=click locator={self.search_button.name}",
            highlight_rect=search_button_bounds,
        )

    def is_result_loaded(self, keyword: str) -> bool:
        """判断结果页是否已经出现指定关键词。"""
        dynamic_locator = Locator(
            name=f"result_keyword_{keyword}",
            strategy="xpath",
            value=f'//*[@text="{keyword}"]',
            fallback=[
                Locator(
                    name=f"result_keyword_contains_{keyword}",
                    strategy="xpath",
                    value=f'//*[contains(@text, "{keyword}")]',
                )
            ],
            timeout=15,
        )
        matched = self.is_visible(dynamic_locator)
        result_bounds = self.driver.get_bounds(dynamic_locator) if matched else None
        self.record_step(
            name="校验搜索结果",
            detail=f"检查结果页中是否出现关键词：{keyword}",
            expected=f"结果页包含 {keyword}",
            actual=f"检测结果：{'已出现' if matched else '未出现'} {keyword}",
            comparison="PASS" if matched else "FAIL",
            status="PASSED" if matched else "FAILED",
            logs=f"assert=contains_text keyword={keyword} matched={matched}",
            highlight_rect=result_bounds,
        )
        return matched
