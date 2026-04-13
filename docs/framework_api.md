# 框架接口文档

## 目标

这份文档用于定义框架的公共接口，让新同事可以快速知道：

- 用例应该调用哪些 fixture
- pytest 插件入口和 fixture/hook 分别放在哪里
- 页面对象应该暴露哪些业务方法
- 底层驱动和设备管理各负责什么
- 文本生成用例时应该参考哪些接口

补充阅读：

- 流程图说明：[docs/framework_flow.md](/Volumes/SD%20Card/从入门到%20recode/uiauto/docs/framework_flow.md)

当前验证通过的关键版本：

- `uiautomator2==3.4.1`

## Fixture

pytest 的注册入口仍然是 [tests/conftest.py](/Volumes/SD%20Card/从入门到%20recode/uiauto/tests/conftest.py)，
但真正的实现已经拆分到：

- [framework/pytest_plugin.py](/Volumes/SD%20Card/从入门到%20recode/uiauto/framework/pytest_plugin.py)：插件总入口、参数注册、并行边界检查
- [framework/pytest_fixtures.py](/Volumes/SD%20Card/从入门到%20recode/uiauto/framework/pytest_fixtures.py)：fixture 定义
- [framework/reporting/hooks.py](/Volumes/SD%20Card/从入门到%20recode/uiauto/framework/reporting/hooks.py)：真机前后置、失败采集、报告落库

常用 fixture 如下：

### `config`

- 类型：`ConfigManager`
- 作用：读取 `config/config.yaml`
- 场景：在 fixture、生成脚本、设备管理中读取环境配置

### `driver`

- 类型：`DriverAdapter`
- 作用：连接真实设备并提供统一 UI 操作能力
- 场景：页面对象内部调用，不建议直接在测试里大量使用
- 特点：统一走 `Waiter` 轮询等待，`click()` 支持可配置重试，并自动注入步骤耗时与运行时上下文

### `adb`

- 类型：`AdbClient`
- 作用：执行设备级操作，比如启动 Activity、回首页、强杀应用

### `via_baidu_page`

- 类型：`ViaBaiduPage`
- 作用：Via + 百度业务页对象

### `device_manager`

- 类型：`DeviceManager`
- 作用：管理设备级前后置、恢复基线页、构建 `DriverAdapter`
- 场景：通常由框架 hook 使用，业务测试很少直接依赖

## `DriverAdapter`

文件：[framework/core/driver.py](/Volumes/SD%20Card/从入门到%20recode/uiauto/framework/core/driver.py)

公共方法：

- `connect()`: 连接设备
- `find(locator)`: 按统一 `Locator` 查找元素
- `click(locator)`: 点击元素
- `click_point(x, y)`: 点击坐标
- `set_text(locator, value)`: 输入文本
- `send_keys(value, clear=False)`: 直接调用设备级输入，常用于图片兜底后的输入场景
- `clear_text(locator)`: 清空文本
- `exists(locator)`: 判断元素是否存在
- `screenshot(path)`: 保存截图
- `page_source()`: 获取页面层级
- `app_start(package, activity=None)`: 启动应用
- `app_stop(package)`: 停止应用
- `press(key)`: 发送按键
- `set_runtime_context(run_id=..., case_name=...)`: 设置运行时上下文，用于生成唯一产物名
- `build_artifact_name(base_name, category="artifact")`: 统一生成截图、XML、调试图命名
- `record_step(...)`: 写入结构化步骤、前后截图、差异图和 `duration_ms`

当前行为约束：

- 元素等待统一走 `Waiter`，与 `DeviceManager` 使用相同的超时/轮询语义
- `click()` 支持 `framework.click_retry_count` 和 `framework.click_retry_interval`
- 查找、点击、输入失败时会附带 `locator.describe()`、有效超时、重试次数等上下文

## `BasePage`

文件：[framework/core/base_page.py](/Volumes/SD%20Card/从入门到%20recode/uiauto/framework/core/base_page.py)

建议所有页面对象继承 `BasePage`，并只暴露业务语义方法。

公共方法：

- `click(locator)`
- `input_text(locator, value)`
- `clear_text(locator)`
- `is_visible(locator)`
- `save_failure_artifacts(case_name)`

当前设计重点：

- 默认路径、图片阈值、图像缩放列表都从统一默认值模块回退
- 页面对象里的图片兜底走 `ImageEngine` 多尺度模板匹配

### `Locator`

文件：[framework/core/locator.py](/Volumes/SD%20Card/从入门到%20recode/uiauto/framework/core/locator.py)

关键字段：

- `strategy / value`: 普通定位方式
- `fallback`: 普通定位兜底链
- `allow_image_fallback`: 是否允许图片兜底，保留兼容旧逻辑
- `image_template`: 显式模板名，推荐优先填写
- `image_region`: 可选图片搜索区域
- `image_threshold`: 可选图片匹配阈值

推荐写法：

```python
Locator(
    name="login_button",
    strategy="resource_id",
    value="demo:id/login",
    allow_image_fallback=True,
    image_template="login_button",
    image_region=(100, 300, 900, 1200),
    image_threshold=0.9,
)
```

## `DeviceManager`

文件：[framework/device/manager.py](/Volumes/SD%20Card/从入门到%20recode/uiauto/framework/device/manager.py)

公共方法：

- `build_driver()`: 构建 `DriverAdapter`
- `adb()`: 构建 `AdbClient`
- `prepare_test_environment()`: 用例前环境检查并准备基线页面
- `reset_to_baseline()`: 用例后恢复到统一初始页面
- `baseline_description()`: 返回当前基线页面定义

当前设计重点：

- 前后置基于 `focus/package/activity/输入法/屏幕状态` 判定恢复策略
- `Waiter` 负责轮询等待，不再单独维护一套时间循环
- `device.home_packages` 和 `device.transient_packages` 可在配置里扩展
- 报告会记录恢复前后状态明细，方便排查“为什么没有回到预期基线页”

## `AdbClient`

文件：[framework/device/adb.py](/Volumes/SD%20Card/从入门到%20recode/uiauto/framework/device/adb.py)

公共方法：

- `shell(command)`
- `devices()`
- `wait_for_device()`
- `get_state()`
- `start_activity(package, activity, data_uri=None)`
- `start_home()`
- `close_system_dialogs()`
- `force_stop(package)`
- `press_keyevent(keycode)`
- `go_home()`
- `wake_up()`
- `unlock_screen()`
- `current_focus()`
- `current_focus_state()`
- `screen_is_on()`
- `is_keyboard_visible()`
- `is_package_installed(package)`

补充说明：

- `dumpsys` 解析逻辑已抽成纯函数，便于单测覆盖和后续扩展
- `DeviceSnapshot` 仍是设备状态快照的统一数据结构

## 页面对象约束

页面对象方法应尽量是业务表达，而不是技术表达。

推荐：

```python
via_baidu_page.search("chatgpt")
assert via_baidu_page.is_result_loaded("chatgpt")
```

不推荐：

```python
driver.click(locator)
driver.set_text(locator, "chatgpt")
```

## 用例生成接口约束

文本生成用例时，默认只允许直接使用：

- fixture：`via_baidu_page`、`driver`、`config`
- 页面对象公共业务方法
- marker：`pytest.mark.device`、`pytest.mark.smoke`、`pytest.mark.slow`、`pytest.mark.flaky`、`pytest.mark.feature("name")`

如果必须新增页面对象方法，应优先补到页面对象，而不是把底层 locator 直接写进测试函数。

注意：

- `device` 用例必须单 worker 执行，不支持 `pytest-xdist`
- 生成器会原样渲染 marker，所以 `feature("search")` 这类参数化 marker 可以直接出现在 `markers` 字段里

## 报告数据约束

HTML 报告现在直接消费 pytest 生命周期里的结构化数据，不再从 `report.sections` 反解析文本。

这意味着：

- 失败原因、失败截图、页面层级、前后置明细、步骤列表都走统一数据通道
- `runtime_store` 主要服务结构化 HTML 报告
- `pytest-html` 和 Allure 仍通过 pytest hook 直接挂附件，不与 `runtime_store` 完全共用同一份原始对象
- 升级 pytest 或更换插件时，结构化 HTML 报告的稳定性更高
