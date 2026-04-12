# 文本转用例工作流

## 方案一：结构化直接生成

适合已经知道框架页面对象和方法名的情况。

执行命令：

```bash
python scripts/generate_cases_from_excel.py examples/case_inputs/test_cases_template.csv
```

生成结果：

- `tests/generated/` 下输出 pytest 用例文件
- 如果某条用例缺少 `python_calls`，会同时在 `artifacts/report_data/ai-prompts/` 输出 AI 提示词
- `tests/generated/.manifest/` 下会记录当前输入源生成过哪些文件，便于下次自动清理旧文件

## 方案二：AI 辅助生成

适合只有自然语言测试文本、但还不能直接映射到框架方法的情况。

流程：

1. 按录入规范填写测试文本
2. 运行生成脚本
3. 取生成的 AI prompt
4. 将 prompt 喂给 AI
5. 把 AI 生成的代码补回项目

## 推荐原则

- 能结构化生成，就不要完全依赖 AI
- AI 更适合补充页面对象方法和补齐断言
- 生成后的代码仍然需要做一次人工 review
- 同一个输入文件请保持 `case_id` 稳定且唯一，这样 manifest 才能准确清理陈旧文件
