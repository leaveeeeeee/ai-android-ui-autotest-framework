# 升级指南

这份文档用于说明从“早期一体化版本”升级到当前版本时，需要注意哪些接口和行为变化。

## 升级原则

- 测试用例和页面对象对外 API 尽量保持稳定
- 优先升级 pytest 插件入口和 fixture 装配方式
- 真机用例继续按单设备、单 worker 执行

## 主要变化

### 0. 步骤 API 现在统一切到 `StepSpec + BasePage.step()`

旧版本里，页面对象和测试辅助代码可以直接写：

- `driver.record_step(name="...", detail="...", capture=False)`
- `page.record_step(name="...", expected="...", actual="...")`

当前版本已经改成显式步骤模型：

- `driver.record_step(StepSpec(...))`
- `page.record_step(StepSpec(...))`
- 页面对象主推荐入口：`with page.step("步骤名", expected="...") as step: ...`

影响：

- 旧的 `record_step(**kwargs)` 调用方式不再兼容
- 页面对象里推荐把动态字段通过 `step.update(...)` 补进去，而不是把一长串关键字参数塞给 `record_step()`

### 1. pytest 入口变薄了

旧版本里，大部分逻辑都在 `tests/conftest.py`。
当前版本已经拆成：

- [tests/conftest.py](../tests/conftest.py)：只做插件注册
- [framework/pytest_plugin.py](../framework/pytest_plugin.py)：参数注册与并行边界检查
- [framework/pytest_fixtures.py](../framework/pytest_fixtures.py)：fixture 装配
- [framework/reporting/hooks.py](../framework/reporting/hooks.py)：前后置和失败采集

影响：

- 如果之前在 `tests/conftest.py` 里直接加逻辑，现在应该按职责放到 plugin、fixtures 或 hooks

### 2. `DriverAdapter` 内部拆分了采集能力

对外接口未变，但内部新增：

- [framework/core/artifact_manager.py](../framework/core/artifact_manager.py)
- [framework/core/step_capture.py](../framework/core/step_capture.py)

影响：

- 如果你在测试里直接 monkeypatch `DriverAdapter.record_step()` 内部的截图逻辑，需要改成 patch `StepCaptureService` 或 `ArtifactManager`
- 如果你直接断言 `record_step()` 的入参字典，需要改成断言 `StepSpec`

### 3. 页面对象优先由 fixture 注入 `ImageEngine`

当前 fixture 会显式调用 [framework/vision/factory.py](../framework/vision/factory.py) 构建 `ImageEngine`。
`BasePage(driver)` 仍然可用，但只是兼容性回退。

建议：

- 新页面对象 fixture 一律显式注入 `image_engine`
- 新测试不要自行拼装图片阈值和模板目录

### 4. 报告结构化数据口径更明确

当前的报告链路是：

- `runtime_store`：服务结构化 HTML
- `pytest-html`：通过 hook 挂 extras
- Allure：通过 hook 挂附件

影响：

- 不要再假设三套报告完全共用同一份原始对象
- 如果你要给 HTML 报告加字段，优先改 `runtime_store` 和 `simple_html`

### 5. 并行边界更严格

只要收集到 `@pytest.mark.device` 用例，框架会阻止 `pytest-xdist` 并行执行。

影响：

- CI 中需要把纯单测和真机用例分开跑
- `device` 用例继续保持单 worker

### 6. CI 现在输出 coverage 可见性

`PR Check` 中的 `unit-tests` job 现在会输出：

- 终端 coverage 摘要
- `coverage.xml`
- HTML/JUnit/Coverage 工件

影响：

- 这轮还没有 coverage 阈值，不会因为覆盖率低直接拦 PR
- 但后续如果要加阈值，可以直接基于现有 artifact 和基线推进

## 推荐升级步骤

1. 先同步配置文件和依赖。
2. 确认自定义 fixture 是否仍然在正确模块里。
3. 确认页面对象 fixture 改成显式注入 `ImageEngine`。
4. 跑 `tests -m "not device"`。
5. 跑真机基线脚本 `run_via_baidu_report.sh`。
6. 最后检查 `artifacts/reports/index.html` 和 Allure 结果目录。

## 常见兼容性提醒

- 旧测试如果直接依赖 `tests/conftest.py` 里的私有函数，需要改成依赖公开 fixture 或插件 hook
- 旧 monkeypatch 如果打在 `DriverAdapter.record_step()` 的内部实现上，升级后需要改 patch 点
- 旧页面对象里如果还在手写 `record_step(name=..., ...)`，需要统一迁移到 `StepSpec` 或 `BasePage.step()`
- 如果历史文档还写着“全部逻辑都在 `conftest.py`”，需要一起更新，避免新同事走错入口
