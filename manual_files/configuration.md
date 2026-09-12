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

| 字段 | 用途 |
| --- | --- |
| `paper_order` | 表格列顺序 |
| `papers` | 论文 key、PDF、TEI、表头和加入日期 |
| `output_path` | 最终 xlsx 输出路径 |
| `translation` | 翻译开关、超时、批次和单次上限 |
| `relationship_labeling` | 关系标签批次、复核阈值和引用段长度 |
| `context_window` | 引用句前后句数 |

关系标签默认配置：

| 字段 | 默认值 | 含义 |
| --- | --- | --- |
| `enabled` | `true` | 是否自动分类 |
| `batch_size` | `8` | 每次 LLM 请求的单元格数 |
| `review_threshold` | `0.60` | 低于该值进入人工复核 |
| `max_excerpt_chars` | `2400` | 单个引用段送入模型的最大字符数 |

## 修正入口

| 要改什么 | 改哪里 |
| --- | --- |
| 方法简写 | `data/config/abbrev_rules.json` |
| GROBID 漏标引用 | `data/config/alias_mentions.json` |
| 标题显示 | `data/config/display_title_fixes.json` |
| 人工关系标签 | `data/config/relation_label_overrides.json`，推荐通过 `import-labels` 修改 |

修改配置后运行 `python matrix_tool.py rebuild`。`abbrev_rules.json` 只改显示，`alias_mentions.json` 会改变次数和上下文。
