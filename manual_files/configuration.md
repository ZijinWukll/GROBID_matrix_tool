# 配置说明

服务连接只写本机 `.env`：`MATRIX_GROBID_URL`、`MATRIX_LLM_BASE_URL`、`MATRIX_LLM_API_KEY`、`MATRIX_LLM_MODEL`。旧 project.grobid_url 仅保留兼容回落。build/import 自动初始化，不必复制占位论文配置。

## 项目与缓存

`data/config/project.json` 的 paper_order 表示最近一次构建的论文范围，build 始终将其同步为 seed_papers 中的可用 PDF；papers 保留历史元数据及短名，不代表所有历史论文都进入矩阵。output_path 指定默认导出文件。

papers.<KEY>.pdf_sha256 用于识别已知 PDF 变化。没有哈希但存在 TEI 的旧缓存先复用并补哈希；没有元数据的标准命名 TEI 也可被发现复用。context_window.before/after 控制上下文，改变后运行 build 重新抽取。

## 自动分类

relationship_labeling 默认 enabled=true、timeout=60、batch_size=4、max_tokens=4096、max_excerpt_chars=2400、review_threshold=0.60。

repair_attempts 默认 2：格式缺失/截断时缩小批次、扩大输出预算，有限次数恢复；网络异常不会逐条无限重试。auto_check 默认 true：低置信、缺少依据的候选自动检查一次，有分歧则保留不确定标记，不强行放行。缓存记录 auto_checked，已检查过的残留分歧不会每次构建反复请求；需要明确重算用 build --relabel。

## 自动翻译

translation 默认 enabled=true、timeout=60、max_tokens=4096、repair_attempts=2。兼容字段 max_per_run 现在用于批次检查点，不再截断整个构建；0 表示不分批限制。所有缺译都会继续处理到完成、无有效进展或服务异常。

空回复、输出截断、引用标记丢失会扩大预算后有限补试。成功结果定期及结束/中断时保存。已有译文不会由自动处理重写，人工优先。

连接超时为 5 秒，SDK 隐式重试关闭；读取超时由对应阶段 timeout 控制。临时跳过模型用 --no-llm，不必修改持久配置。

## 显示与人工覆盖

abbrev_rules.json 只改变简写显示，display_title_fixes.json 改标题显示，修改后 export 即可；alias_mentions.json 改提及次数与上下文，修改后 build。

人工关系标签在 relation_label_overrides.json，建议通过可选 import-labels 写入。自动分类、自动检查与缓存清理不能覆盖或删除人工结果。译文按英文句子 md5 前 8 位复用，标签按 row_id|paper_key 与内容哈希复用。
