# 架构与数据流

科研矩阵表工具把种子论文转换成可持续重建的引用矩阵，核心流程如下：

`build` 扫描 `data/seed_papers/*.pdf`（或 `--input-dir`）→ 增量 GROBID 解析 → `data/state/papers/<KEY>.tei.xml` → `data/state/papers/<KEY>.json` → 跨论文合并、去重、排序 → 关系标签 → 本地 vLLM 翻译 → `data/exports/科研矩阵表_AgentMemory.xlsx`。单篇 `add` / `--from-tei` 入口保留。

## 事实源与导出物

- `data/state/papers/<KEY>.json` 是单篇抽取结果的持久状态。实际 `rebuild` 先从已登记 TEI 重新抽取并更新这些 JSON，再重算整表；不会扫描或解析 PDF。
- `data/state/papers/<KEY>.tei.xml` 是离线重建所依赖的原始解析缓存。
- `data/exports/` 中的 xlsx 和未翻译清单都是导出物，可以重新生成，不直接手改。
- 译文池位于 `data/state/translations_by_hash.json`，键为英文句子 md5 的前 8 位；原文不变则译文不会丢。

## 代码边界

- 根目录 `matrix_tool.py` 只是兼容入口，实际实现位于 `src/matrix_tool.py`。
- 抽取、清洗、排序、简写选择和渲染核心保持为纯函数；CLI 层负责参数、文件 I/O、网络调用和日志。
- 路径统一以项目根为基准解析，配置中的 PDF、TEI 和输出路径使用 `data/...` 相对路径。
- CLI 日志只写结构化事件，不记录论文正文、引用上下文或整段译文。
- `ensure_project` 为 `build`、`add` 和普通 `init` 创建缺失配置，保留已有配置与人工数据。普通 `init` 不再依赖旧论文；旧迁移由 `init --migrate-legacy` 显式调用。
- `build` 根据已登记的 PDF 路径匹配已有短名，再用 `pdf_sha256` 与 TEI 是否存在判断是否解析。新论文按文件名排序追加，不删除扫描目录外的登记。逐篇保存成功状态，整批只重建一次；单篇解析失败不影响其他论文，最终返回失败状态以支持重试。
- 自动翻译通过 OpenAI 兼容客户端访问本地 vLLM；地址、密钥和模型 ID 只从 `.env` / 环境变量读取。
- GROBID 地址只从 `.env` 的 `MATRIX_GROBID_URL` 读取；学校真实地址不写入源码、示例配置或文档。
- 关系标签在翻译前按单元格批量分类，缓存于 `data/state/relation_labels.json`；人工覆盖保存在 `data/config/relation_label_overrides.json`，优先级高于模型结果。
