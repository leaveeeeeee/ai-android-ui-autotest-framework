# 框架使用与执行流程图

这份文档面向第一次接触仓库的同事，重点回答两个问题：

- 这个框架平时该怎么用
- 一条真机用例从启动到产出报告，中间到底发生了什么

## 日常使用流程

```mermaid
flowchart TD
    A[准备配置文件 config/config.yaml] --> B[编写或生成测试用例]
    B --> C[执行脚本 scripts/run_via_baidu_report.sh]
    C --> D[pytest 加载 tests/conftest.py]
    D --> E[framework.pytest_plugin 注册 fixtures 和 hooks]
    E --> F[创建 config / device_manager / driver fixture]
    F --> G[真机前置检查]
    G --> H[启动页面对象 fixture 并登记到 stash]
    H --> I[用例调用页面对象业务方法]
    I --> J[DriverAdapter 统一等待/点击重试]
    J --> K{普通定位是否成功}
    K -- 是 --> L[uiautomator2 与设备交互]
    K -- 否且声明了图片兜底契约 --> M[ImageEngine 多尺度模板匹配]
    L --> N[record_step 记录步骤与 duration_ms]
    M --> N
    N --> O[hook 挂附件 + runtime_store 聚合]
    O --> P[生成 HTML 报告和 Allure 结果]
```

## 真机用例执行链路

```mermaid
sequenceDiagram
    participant U as 用户
    participant S as 运行脚本
    participant P as pytest
    participant Plugin as pytest_plugin
    participant Hooks as reporting_hooks
    participant D as DeviceManager
    participant G as DriverAdapter
    participant Page as PageObject
    participant A as Android 设备
    participant R as Reporting

    U->>S: 执行 run_via_baidu_report.sh
    S->>P: 启动 pytest
    P->>Plugin: 加载 tests/conftest.py 并注册插件
    Plugin->>Hooks: 挂接 fixture 和报告 hook
    Hooks->>D: prepare_test_environment()
    D->>A: ADB 检查、读取 focus/package/activity/输入法/屏幕状态
    D->>A: 按状态驱动解锁、收敛临时层、回基线页
    Plugin->>Page: 构建页面对象 fixture 并登记 stash
    Page->>G: 调用 click/input_text/is_visible
    G->>A: 通过 uiautomator2 或图像兜底操作设备
    G->>R: record_step() 保存步骤信息和耗时
    P->>Hooks: 失败时触发 makereport
    Hooks->>R: 结构化数据写入失败原因、截图、page source、前后置信息
    P->>R: sessionfinish 生成报告入口
    R-->>U: artifacts/reports/index.html
```

## 并行执行边界

- 纯单测可以使用 `pytest-xdist`
- 只要收集到 `@pytest.mark.device` 用例，框架会在 pytest 启动阶段直接拒绝 `-n/--numprocesses`
- 原因不是线程安全的小问题，而是当前框架以“单 serial、单设备”作为执行语义，多 worker 会争抢同一台真机

## 报告目录结构

```mermaid
flowchart TD
    A[artifacts] --> B[reports]
    A --> C[report_data]
    B --> B1[index.html 总览入口]
    B --> B2[latest 最新结果]
    B --> B3[runs 历史运行]
    C --> C1[screenshots 截图]
    C --> C2[page_source 页面层级]
    C --> C3[logs 日志]
    C --> C4[allure-results Allure 原始结果]
    C --> C5[image_debug 图像匹配调试图]
    C --> C6[ai-prompts AI 提示词]
    C --> C7[tests/generated/.manifest 生成清单]
```

## 推荐阅读顺序

1. 先看 [README.md](/Volumes/SD%20Card/从入门到%20recode/uiauto/README.md)
2. 再看 [docs/framework_api.md](/Volumes/SD%20Card/从入门到%20recode/uiauto/docs/framework_api.md)
3. 然后看 [framework/pytest_plugin.py](/Volumes/SD%20Card/从入门到%20recode/uiauto/framework/pytest_plugin.py) 和 [framework/reporting/hooks.py](/Volumes/SD%20Card/从入门到%20recode/uiauto/framework/reporting/hooks.py)
4. 最后结合实际页面对象查看 [framework/pages/via_baidu_page.py](/Volumes/SD%20Card/从入门到%20recode/uiauto/framework/pages/via_baidu_page.py)
