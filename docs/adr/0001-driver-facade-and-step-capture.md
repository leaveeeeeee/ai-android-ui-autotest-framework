# ADR 0001: 保持 DriverAdapter 外观稳定，内部拆分采集组件

## 状态

已采纳

## 背景

框架最早把大部分设备交互能力都集中在 `DriverAdapter`：

- 设备连接
- 元素查找、点击、输入
- 设备级截图、页面源导出
- 步骤记录
- 产物命名

这种写法对个人项目起步很快，但随着报告能力增强，`record_step()` 逐渐同时承担：

- 运行时命名
- 截图采集
- 页面层级采集
- 点击区域标注
- 前后截图差异图
- 焦点窗口上下文注入
- 最终步骤落库

结果是 `DriverAdapter` 成为稳定 facade 的同时，也变成了实现复杂度最高的类，单测需要 mock 很多副作用。

## 决策

### 1. 保留 `DriverAdapter` 作为对外 facade

当前页面对象、fixture、测试生成器都已经围绕 `DriverAdapter` 建立了稳定调用面。
本次不把它拆成多个公开组件，而是保持 facade 形态稳定，仅把步骤入参标准化为 `StepSpec`：

- `find()`
- `click()`
- `set_text()`
- `capture_state()`
- `record_step(spec: StepSpec)`
- `set_runtime_context()`
- `build_artifact_name()`

这样可以避免页面对象和测试用例同时面对“多公开对象 + 多套步骤参数”的双重改动。

### 2. 抽出 `ArtifactManager`

产物命名和状态采集下沉到 [framework/core/artifact_manager.py](../../framework/core/artifact_manager.py)：

- 管理 `run_id / case_name / sequence`
- 统一构建产物名
- 统一保存截图和页面层级

### 3. 抽出 `StepCaptureService`

步骤采集逻辑下沉到 [framework/core/step_capture.py](../../framework/core/step_capture.py)：

- 读取 `step_context_provider`
- 获取上一张截图路径
- 采集当前截图和 XML
- 生成点击高亮
- 生成 diff 图

`DriverAdapter.record_step()` 只负责：

- 检查 recorder 是否存在
- 调用 `StepCaptureService.collect()`
- 计算 `duration_ms`
- 调用 `step_recorder.add_step()`

页面对象层则统一使用 `BasePage.step()` 上下文管理器来编排 `StepSpec`，减少业务方法里的样板步骤代码。

### 4. 页面层优先通过装配注入 `ImageEngine`

页面对象 fixture 现在优先在 [framework/pytest_fixtures.py](../../framework/pytest_fixtures.py) 里组装 `ImageEngine` 并传入页面对象。
`BasePage` 仍保留默认构造能力，仅作为兼容性回退，不建议新代码依赖它直接从 `driver.framework_config` 取配置。

## 结果

正面结果：

- `record_step()` 的副作用链可以独立测试
- 页面对象步骤现在可以用显式 `StepSpec + StepContext` 表达，不再散落长参数列表
- `hooks.py` 可以直接断言结构化 store、附件和生命周期清理
- 页面对象不再需要知道图像引擎的具体配置拼装方式
- 外部 API 基本不变，升级成本低

负面结果：

- `DriverAdapter` 依然是框架 facade，类本身仍然偏大
- `BasePage` 仍保留兼容性回退路径，不是完全强制注入
- 采集组件增加后，阅读入口从单文件变成多文件，需要文档引导

## 备选方案

### 方案 A：把 `DriverAdapter` 拆成多个公开类

未采纳。原因：

- 会同时影响 fixture、页面对象、测试生成器、示例代码和文档
- 当前项目仍以中小团队、单设备执行为主，拆公开 API 的收益暂时小于升级成本

### 方案 B：直接引入完整断言层

未采纳。原因：

- 当前 `pytest` 原生 `assert` 已够用
- 当前更高优先级的问题是采集职责和 hook 测试缺口，而不是断言 DSL

## 后续工作

- 如果后续 `DriverAdapter` 再继续膨胀，优先继续抽内部组件，而不是立即拆公开 facade
- 如果页面对象装配方式增多，可以再引入显式 page factory
- 如果真机采集耗时成为瓶颈，再评估截图策略和 diff 生成策略的可配置化
