# 变更记录

## 2026-09-12 - 引用关系标签

- 新增 B&E、S&S、C&A、Q&A、M/I 五类单元格关系标签。
- 标签按本地 vLLM 批量分类，先分类后翻译，结果按内容哈希缓存。
- Excel 单元格以局部粗体显示【中文名｜代码】。
- 新增 `export-labels` / `import-labels` 人工校对闭环和 `rebuild --relabel`。
- 复核阈值调整为 0.60，默认只导出待复核单元格；全量导出使用 `--all`。
- 重写 README、AGENTS 和专题手册，帮助首页增加快速开始与命令分组。

## 2026-09-12 - 本地 LLM 翻译

- 自动翻译后端由 MyMemory 切换为 OpenAI 兼容的学校本地 vLLM。
- 新增 `.env` 配置入口，连接地址、密钥和模型 ID 不再硬编码。
- 新增本地翻译参数、写回流程和非语言片段过滤测试。
- 使用 `Qwen2p5` 补全当前矩阵表缺译句。

## 2026-09-10 - 项目层级重构

- 源码迁入 `src/`，保留根目录 `matrix_tool.py` 兼容入口。
- 配置、状态、种子论文和导出物统一迁入 `data/`。
- 新增 pytest 冒烟测试与逻辑结果回归基线。
- 新增 `log/matrix_tool_YYYYMMDD.log` 按日 JSON Lines 运行日志。
- 移除 `render_qa.py` 与 PDF 预览流程，人工直接审查 xlsx。
