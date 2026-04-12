from __future__ import annotations

from framework.core.base_page import BasePage
from framework.core.locator import Locator


class DemoPage(BasePage):
    """示例页面对象。

    这个类主要用于演示页面对象应该怎么写：
    - 先定义定位器
    - 再暴露业务方法
    - 测试用例只调用业务方法，不直接写底层定位逻辑
    """

    login_button = Locator(
        name="login_button",
        strategy="resource_id",
        value="com.demo.android:id/btn_login",
        fallback=[Locator(name="login_button_text", strategy="text", value="登录")],
        allow_image_fallback=True,
    )

    username_input = Locator(
        name="username_input",
        strategy="resource_id",
        value="com.demo.android:id/et_username",
    )

    def tap_login(self) -> None:
        """点击登录按钮。"""
        self.click(self.login_button)

    def enter_username(self, username: str) -> None:
        """输入用户名。"""
        self.input_text(self.username_input, username)
