# 变更记录

## 2026-09-10 - 项目层级重构

- 源码迁入 `src/`，保留根目录 `matrix_tool.py` 兼容入口。
- 配置、状态、种子论文和导出物统一迁入 `data/`。
- 新增 pytest 冒烟测试与逻辑结果回归基线。
- 新增 `log/matrix_tool_YYYYMMDD.log` 按日 JSON Lines 运行日志。
- 移除 `render_qa.py` 与 PDF 预览流程，人工直接审查 xlsx。
