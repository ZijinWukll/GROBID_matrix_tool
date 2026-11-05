# 配置说明

## 本地模型环境

真实连接信息放在 `.env`，不要写入源码：

```dotenv
MATRIX_GROBID_URL=http://your-grobid-host:8070
MATRIX_LLM_BASE_URL=http://your-llm-host:8900/v1
MATRIX_LLM_API_KEY=EMPTY
MATRIX_LLM_MODEL=your-model-id
```

可使用 `Copy-Item .env.example .env` 创建。`.env` 已被 Git 忽略。

## 项目配置

`data/config/project.json` 主要字段：

`build` / `add` 首次运行会自动创建可用的空配置，普通新项目无需手动复制带占位论文的示例文件。PDF 默认放入 `data/seed_papers/`；临时指定其他目录使用 `build --input-dir 文件夹`（不会更改后续默认扫描目录）。

| 字段 | 用途 |
| --- | --- |
| `paper_order` | 当前参与矩阵的论文及列顺序；build 默认同步为当前 PDF 集合 |
| `papers` | 论文 key、PDF、TEI、表头和加入日期，包含不再参与当前矩阵的历史缓存登记 |
| `papers.<KEY>.pdf_sha256` | PDF 内容哈希，用于 build 判断是否需要重新解析；无需手工填写 |
| `output_path` | 最终 xlsx 输出路径 |
| `translation` | 翻译开关、超时、批次和单次上限 |
| `relationship_labeling` | 关系标签批次、复核阈值和引用段长度 |
| `context_window` | 引用句前后句数 |

关系标签默认配置：

| 字段 | 默认值 | 含义 |
| --- | --- | --- |
| `enabled` | `true` | 是否自动分类 |
| `timeout` | `30` | 单次模型请求的读取超时秒数；连接超时固定为 5 秒，不自动重试 |
| `batch_size` | `8` | 每次 LLM 请求的单元格数 |
| `review_threshold` | `0.60` | 低于该值进入人工复核 |
| `max_excerpt_chars` | `2400` | 单个引用段送入模型的最大字符数 |

翻译的 `timeout` 默认 60 秒，`max_per_run` 默认 500 句。分类每批、翻译每 10 句及结束/中断时保存成功结果，模型请求失败后停止本轮连续调用；网络兜底标签在后续运行时可重试。需要先出表时用 `--no-llm`，无需改动持久配置。

## 修正入口

| 要改什么 | 改哪里 |
| --- | --- |
| 方法简写 | `data/config/abbrev_rules.json` |
| GROBID 漏标引用 | `data/config/alias_mentions.json` |
| 标题显示 | `data/config/display_title_fixes.json` |
| 人工关系标签 | `data/config/relation_label_overrides.json`，推荐通过 `import-labels` 修改 |

修改配置后运行 `python matrix_tool.py rebuild`。`abbrev_rules.json` 只改显示，`alias_mentions.json` 会改变次数和上下文。
