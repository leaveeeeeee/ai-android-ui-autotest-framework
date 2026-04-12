# 框架接口文档

## 目标

这份文档用于定义框架的公共接口，让新同事可以快速知道：

- 用例应该调用哪些 fixture
- 页面对象应该暴露哪些业务方法
- 底层驱动和设备管理各负责什么
- 文本生成用例时应该参考哪些接口

补充阅读：

- 流程图说明：[docs/framework_flow.md](/Volumes/SD%20Card/从入门到%20recode/uiauto/docs/framework_flow.md)

当前验证通过的关键版本：

- `uiautomator2==3.4.1`

## Fixture

### `config`

- 类型：`ConfigManager`
- 作用：读取 `config/config.yaml`
- 场景：在 fixture、生成脚本、设备管理中读取环境配置

### `driver`

- 类型：`DriverAdapter`
- 作用：连接真实设备并提供统一 UI 操作能力
- 场景：页面对象内部调用，不建议直接在测试里大量使用

### `adb`

- 类型：`AdbClient`
- 作用：执行设备级操作，比如启动 Activity、回首页、强杀应用

### `via_baidu_page`

- 类型：`ViaBaiduPage`
- 作用：Via + 百度业务页对象

## `DriverAdapter`

文件：[framework/core/driver.py](/Volumes/SD%20Card/从入门到%20recode/uiauto/framework/core/driver.py)

公共方法：

- `connect()`: 连接设备
- `find(locator)`: 按统一 `Locator` 查找元素
- `click(locator)`: 点击元素
- `click_point(x, y)`: 点击坐标
- `set_text(locator, value)`: 输入文本
- `clear_text(locator)`: 清空文本
- `exists(locator)`: 判断元素是否存在
- `screenshot(path)`: 保存截图
- `page_source()`: 获取页面层级
- `app_start(package, activity=None)`: 启动应用
- `app_stop(package)`: 停止应用
- `press(key)`: 发送按键

## `BasePage`

文件：[framework/core/base_page.py](/Volumes/SD%20Card/从入门到%20recode/uiauto/framework/core/base_page.py)

建议所有页面对象继承 `BasePage`，并只暴露业务语义方法。

公共方法：

- `click(locator)`
- `input_text(locator, value)`
- `clear_text(locator)`
- `is_visible(locator)`
- `save_failure_artifacts(case_name)`

## `DeviceManager`

文件：[framework/device/manager.py](/Volumes/SD%20Card/从入门到%20recode/uiauto/framework/device/manager.py)

公共方法：

- `build_driver()`: 构建 `DriverAdapter`
- `adb()`: 构建 `AdbClient`
- `prepare_test_environment()`: 用例前环境检查并准备基线页面
- `reset_to_baseline()`: 用例后恢复到统一初始页面
- `baseline_description()`: 返回当前基线页面定义

## `AdbClient`

文件：[framework/device/adb.py](/Volumes/SD%20Card/从入门到%20recode/uiauto/framework/device/adb.py)

公共方法：

- `shell(command)`
- `devices()`
- `wait_for_device()`
- `get_state()`
- `start_activity(package, activity, data_uri=None)`
- `force_stop(package)`
- `press_keyevent(keycode)`
- `go_home()`
- `wake_up()`
- `unlock_screen()`
- `current_focus()`
- `is_package_installed(package)`

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
- `pytest.mark.device`、`pytest.mark.smoke`

如果必须新增页面对象方法，应优先补到页面对象，而不是把底层 locator 直接写进测试函数。
