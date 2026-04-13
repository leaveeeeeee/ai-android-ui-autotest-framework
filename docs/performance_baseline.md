# 性能基线

这份文档记录当前框架的最低限度性能基线，目标不是做极限优化，而是让后续重构能有可比较的参考点。

## 采集范围

当前只记录三类基线：

- 主机侧步骤采集开销
- 主机侧图像匹配开销
- 真机基线业务流耗时

## 测量方法

### 1. 步骤采集

通过 `DriverAdapter.record_step()` 走完整的：

- 运行时产物命名
- 截图采集
- 页面源采集
- recorder 落库

使用 fake device，避免把 ADB 和真机波动混进主机基线。

### 2. 图像匹配

通过 `ImageEngine.match()` 走当前默认多尺度模板匹配列表：

- `0.67`
- `0.75`
- `0.875`
- `1.0`
- `1.125`
- `1.25`
- `1.33`

使用本地生成的固定截图和模板，避免真机渲染差异干扰。

### 3. 真机基线流

使用：

- [scripts/run_via_baidu_report.sh](/Volumes/SD%20Card/从入门到%20recode/uiauto/scripts/run_via_baidu_report.sh)

观察：

- `tests/test_via_baidu_search.py`
- HTML 报告生成
- Allure results 生成

## 当前基线

采集日期：

- `2026-04-13`

采集环境：

- Python: `'/Volumes/SD Card/从入门到 recode/解释器/bin/python'`
- 分支：`codex-driver-step-capture-cleanup`

### 主机侧

| 项目 | 结果 | 说明 |
| --- | --- | --- |
| `record_step()` 单次采集 | 平均 `0.21ms`，P95 `0.39ms` | 基于 fake device 的完整截图 + XML + recorder 落库，不含 diff 图 |
| `ImageEngine.match()` 单次匹配 | 平均 `7.12ms`，P95 `50.92ms` | 基于本地固定截图和 7 个尺度候选，包含截图文件写入和调试图输出 |

### 真机侧

| 项目 | 结果 | 说明 |
| --- | --- | --- |
| `tests/test_via_baidu_search.py` | `1 passed in 17.98s` | 命令为 `./scripts/run_via_baidu_report.sh`，同时生成 HTML 报告与 Allure 结果 |

## 使用方式

当后续重构下列模块时，建议同步更新这份文档：

- [framework/core/driver.py](/Volumes/SD%20Card/从入门到%20recode/uiauto/framework/core/driver.py)
- [framework/core/step_capture.py](/Volumes/SD%20Card/从入门到%20recode/uiauto/framework/core/step_capture.py)
- [framework/vision/image_engine.py](/Volumes/SD%20Card/从入门到%20recode/uiauto/framework/vision/image_engine.py)
- [framework/reporting/simple_html.py](/Volumes/SD%20Card/从入门到%20recode/uiauto/framework/reporting/simple_html.py)

## 解读原则

- 真机耗时优先看趋势，不要把单次结果当作绝对 SLA
- 主机侧基线更适合判断“这次重构是否显著增加了纯框架开销”
- 如果差异超过 `20%`，建议补充原因说明
- `ImageEngine.match()` 的 P95 受文件写入和 OpenCV 首次调用影响较大，后续如果要精细分析，可拆成“纯匹配”和“带调试图输出”两组基线
