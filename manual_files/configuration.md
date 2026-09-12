# 配置与修正

配置文件集中在 `data/config/`：

| 文件 | 用途 |
| --- | --- |
| `project.json` | 论文顺序、PDF/TEI 路径、表头、GROBID、翻译配置、上下文窗口 |
| `abbrev_rules.json` | 方法简写显示规则，靠前规则优先 |
| `alias_mentions.json` | 补 GROBID 漏标的正文提及，影响次数和上下文 |
| `display_title_fixes.json` | 标题连字符等显示修复 |

修改任何配置文件后运行 `matrix_tool.py rebuild`。`abbrev_rules.json` 只影响显示层；`alias_mentions.json` 会改变数据结果，两者不要混淆。

上下文窗口默认前后各 2 句，可通过 `project.json` 的 `context_window` 或命令行的 `--window`、`--window-before`、`--window-after` 覆盖。

自动翻译由 `project.json` 的 `translation` 段控制，但模型连接信息不在 JSON 中硬编码，统一从 `.env` 读取：

| 环境变量 | 用途 |
| --- | --- |
| `MATRIX_LLM_BASE_URL` | OpenAI 兼容接口地址，通常以 `/v1` 结尾 |
| `MATRIX_LLM_API_KEY` | 本地 vLLM 可填 `EMPTY`，真实密钥不得提交 |
| `MATRIX_LLM_MODEL` | 服务端模型 ID，例如 `Qwen2p5` |

关闭自动翻译后将保留英文原文并计入缺译统计；临时跳过使用 `--no-translate`。
