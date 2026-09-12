# 架构与数据流

科研矩阵表工具把种子论文转换成可持续重建的引用矩阵，核心流程如下：

`data/seed_papers/*.pdf` → GROBID / `--from-tei` → `data/state/papers/<KEY>.tei.xml` → `data/state/papers/<KEY>.json` → 跨论文合并、去重、排序 → 本地 vLLM 翻译 → `data/exports/科研矩阵表_AgentMemory.xlsx`。

## 事实源与导出物

- `data/state/papers/<KEY>.json` 是矩阵数据的唯一事实源，每次 `rebuild` 都从这些文件重算整表。
- `data/state/papers/<KEY>.tei.xml` 是离线重建所依赖的原始解析缓存。
- `data/exports/` 中的 xlsx 和未翻译清单都是导出物，可以重新生成，不直接手改。
- 译文池位于 `data/state/translations_by_hash.json`，键为英文句子 md5 的前 8 位；原文不变则译文不会丢。

## 代码边界

- 根目录 `matrix_tool.py` 只是兼容入口，实际实现位于 `src/matrix_tool.py`。
- 抽取、清洗、排序、简写选择和渲染核心保持为纯函数；CLI 层负责参数、文件 I/O、网络调用和日志。
- 路径统一以项目根为基准解析，配置中的 PDF、TEI 和输出路径使用 `data/...` 相对路径。
- CLI 日志只写结构化事件，不记录论文正文、引用上下文或整段译文。
- 自动翻译通过 OpenAI 兼容客户端访问本地 vLLM；地址、密钥和模型 ID 只从 `.env` / 环境变量读取。
