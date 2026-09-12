# 关键决策

## D-001：数据统一放入 `data/`

配置、状态、种子 PDF 和导出物分别位于 `data/config/`、`data/state/`、`data/seed_papers/`、`data/exports/`。配置内路径保持项目根相对写法，便于定位和迁移。

## D-002：源码只移动、暂不拆模块

现有 `matrix_tool.py` 整体迁入 `src/`，根目录保留薄兼容入口。这样先稳定目录和路径，不把算法拆分与结构迁移混在一次改动里。

## D-003：运行日志与变更记录分开

`log/matrix_tool_YYYYMMDD.log` 是运行日志，按日追加并忽略入版本库；`log/CHANGELOG.md` 记录需要长期保留的版本变更。

## D-004：不再生成 PDF 预览

人工直接审查 `data/exports/` 中的 xlsx。`render_qa.py` 及 `pywin32` 依赖已移除，历史 PDF 文件可以保留但不参与流程。

## D-005：测试以逻辑结果为准

回归测试比较配置语义、译文池和整表逻辑行，不要求 xlsx 二进制完全一致。

## D-006：私有研究数据不进入 Git

真实配置、种子 PDF、TEI/抽取状态、译文池、导出物、回归基线和本机环境快照都只保存在本地。仓库提交目录占位、脱敏示例配置和可公开代码；缺少私有数据时，相关测试自动跳过而不是失败。

## D-007：自动翻译改走本地 vLLM

不再使用 MyMemory。翻译请求通过 OpenAI 兼容接口发送到学校本地模型，连接地址、密钥和模型 ID 由 `.env` 中的 `MATRIX_LLM_BASE_URL`、`MATRIX_LLM_API_KEY`、`MATRIX_LLM_MODEL` 提供；源码只读取环境变量。
