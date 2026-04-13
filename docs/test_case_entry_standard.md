# 文本用例录入规范

## 目标

为了让“文本转测试代码”尽量稳定，录入人需要按统一格式提供测试文本。越结构化，生成的代码越规范、越可执行。

## 推荐字段

一行代表一个测试用例，推荐字段如下：

- `case_id`: 唯一标识，例如 `via_baidu_search_chatgpt`
- `module`: 业务模块，例如 `search`
- `title`: 用例标题
- `fixture`: 用哪个 fixture，例如 `via_baidu_page`
- `page_object`: 对应页面对象，例如 `ViaBaiduPage`
- `precondition`: 前置条件
- `steps`: 测试步骤
- `expected`: 预期结果
- `python_calls`: 如果已经知道框架方法调用，可以直接写 Python 语句
- `markers`: 例如 `smoke,device` 或 `smoke,feature("search")`
- `ai_notes`: 给 AI 的补充说明

## 录入要求

### 1. 步骤要可执行

不要写：

- “正常搜索”
- “看一下结果对不对”

要写：

- “在百度首页搜索框输入 chatgpt”
- “点击提交按钮”
- “校验结果页中出现 chatgpt 文本”

### 2. 预期要可验证

不要写：

- “页面正确”
- “结果正常”

要写：

- “结果页出现 chatgpt 关键字”
- “页面标题包含 chatgpt”

### 3. 页面对象要明确

如果用例属于已有页面对象，请明确写：

- `fixture=via_baidu_page`
- `page_object=ViaBaiduPage`

### 4. 尽量提供稳定锚点

如果你知道页面上稳定的元素文本、resource-id、按钮名称，建议写进 `ai_notes`：

- “搜索框 resource-id 是 index-kw”
- “搜索按钮可能显示为 提交”

### 5. 如果能给出 `python_calls`，优先给

例如：

```python
via_baidu_page.search("chatgpt")
assert via_baidu_page.is_result_loaded("chatgpt")
```

这会让生成结果直接可执行，不需要再让 AI 二次补全。

### 6. `case_id` 要稳定，不要频繁改名

生成脚本现在会按“输入文件 + `case_id`”维护 manifest，并自动清理该输入源过期的生成文件。

所以推荐：

- 同一条用例长期保持同一个 `case_id`
- 真的要废弃一条用例时，直接从表里删掉这行
- 不要把不同业务场景反复复用同一个 `case_id`

### 7. `markers` 支持参数化 marker

当前生成器会原样渲染 marker，所以除了 `smoke`、`device` 之外，也可以写：

- `slow`
- `flaky`
- `feature("search")`

推荐业务标签优先使用 `feature("模块名")` 这种形式，便于后续按功能维度筛选执行。
