# AGENTS.md

请使用中文回答所有问题和交流。与用户的互动、代码解释、错漏消息和建议都使用中文。

---

# 项目引导（Agents / 接管说明）

## 项目是什么

**科研矩阵表生长工具**：把“种子论文 → GROBID 解析 → 引用上下文抽取 → 矩阵表”流水线改造成可重复生长的工具。每加一篇种子论文，工具会解析、抽取、跨论文去重合并，并按总内部引用次数降序重建整张 xlsx。

根目录 `matrix_tool.py` 是兼容 CLI 入口，核心实现位于 `src/matrix_tool.py`。抽取、合并、排序和渲染核心保持为纯函数；CLI 层负责参数、网络、文件 I/O 和日志。

## 铁则

1. **xlsx 只是导出物**，手改会在下一次 `rebuild` 被覆盖。
2. **`data/state/papers/<KEY>.json` 是唯一事实源**，整张表每次 `rebuild` 都从它重新计算。
3. **译文按内容哈希键**，键为 `md5(英文句)[:8]`；原文不变则译文不会丢。
4. **配置和数据保持 git 友好**：UTF-8 无 BOM、项目根相对路径、无易变时间戳、原子写入。
5. 行 ID 使用归一化标题；批注、人工覆盖和行合并将来都应按 ID 定位。
6. 不手工生成或修改 `data/exports/` 中的成品来修正数据；修正只进 `data/config/`、`data/state/` 和译文池。

## 目录结构

```text
Grobid_Demo_Codes/
├── matrix_tool.py                  # 兼容入口：python matrix_tool.py ...
├── src/
│   ├── matrix_tool.py              # 核心实现
│   └── util_get_current_time.py
├── tests/
│   ├── test_smoke.py               # 冒烟测试
│   ├── test_regression.py          # 逻辑结果回归
│   └── baselines/logical_rows.json # 重构前冻结基线
├── scripts/                        # PowerShell / Bash 命令封装
├── data/
│   ├── config/                     # project.json、规则和修正表
│   ├── state/papers/               # TEI 缓存 + 抽取 JSON
│   ├── seed_papers/                # PDF 投放区
│   └── exports/                    # xlsx、未翻译清单等导出物
├── project_memory/                 # 架构、决策、迁移记录
├── road_map/                       # 路线图、时间线、待办
├── manual_files/                   # 专题操作手册
├── log/                            # CHANGELOG + 按日运行日志
├── README.md                       # 项目入口
└── requirements*.txt
```

## 运行环境

- 运行前激活本机 conda/miniconda 环境；脚本可用环境变量 `MATRIX_PYTHON` 指定解释器，不把本机绝对路径写入仓库。
- 运行依赖见 `requirements.txt`；测试依赖见 `requirements-dev.txt`。
- 自动翻译通过 OpenAI 兼容接口调用本地 vLLM，连接参数只从 `.env` 读取：`MATRIX_LLM_BASE_URL`、`MATRIX_LLM_API_KEY`、`MATRIX_LLM_MODEL`；不得写进源码或提交 `.env`。
- GROBID 地址在本地 `data/config/project.json` 中配置；代码示例默认 `http://localhost:8070`，联网调用前需确保 VPN 或内网可达。
- `add X.pdf --from-tei 现成.tei.xml` 是离线入口，无 VPN 也能加论文或做冒烟测试。
- `add` / `rebuild` 默认自动翻译缺译句；`--no-translate` 跳过；`init` / `import-translations` / `remove` 不触发自动翻译。

## 命令速查

| 命令 | 作用 |
| --- | --- |
| `status` | 查看种子、行数、缺译句和缺简写行 |
| `add data/seed_papers/新论文.pdf` | GROBID 解析、注册、抽取、重建、自动补译 |
| `add ... --from-tei 文件.tei.xml` | 离线加入论文 |
| `rebuild [--no-translate] [--window N]` | 全量重建；默认自动补译 |
| `export-untranslated` | 导出缺译清单到 `data/exports/` |
| `import-translations 文件.json` | 回填译文并自动重建 |
| `remove KEY` | 注销种子论文并重建 |
| `help [命令名]` | 查看项目专属中文帮助 |

PowerShell 示例：

```powershell
conda activate matrix
python matrix_tool.py status
```

## 修正指南（改文件后跑 rebuild）

| 想改什么 | 改哪里 |
| --- | --- |
| 方法简写不对或缺失 | `data/config/abbrev_rules.json` 增加规则，靠前优先 |
| 正文提到但次数为 0 | `data/config/alias_mentions.json` 补别名 |
| 标题连字符等显示错误 | `data/config/display_title_fixes.json` |
| 列顺序、表头、输出文件名、GROBID 地址 | `data/config/project.json` |
| 自动翻译配置 | `data/config/project.json` 的 `translation` 段 |
| 上下文窗口 | `data/config/project.json` 的 `context_window` 或 `rebuild --window N` |

## 两个“别名”的区别

- `data/config/alias_mentions.json`：数据层补救，补 GROBID 漏打的引用提及，会改变次数和上下文。
- `data/config/abbrev_rules.json`：显示层标签，只决定方法简写列，不改次数和上下文。

## 测试与日志

- 改动任何 `.py`、配置或状态后运行 `python matrix_tool.py status` 和 `python -m pytest -q`。
- 回归基线位于 `tests/baselines/logical_rows.json`；修改核心算法前先确认基线语义，不要为了通过测试随意改基线。
- 运行日志位于 `log/matrix_tool_YYYYMMDD.log`，为 JSON Lines；不得记录论文全文、引用上下文或整段译文。
- `log/CHANGELOG.md` 是版本变更记录，运行日志本身不纳入版本管理。
- 真实 `data/config/*.json`、`data/state/`、种子 PDF、导出物、回归基线和本机归档默认由 `.gitignore` 排除；提交前必须检查暂存区。
- `.env`、密钥、证书和本机模型地址不得提交；仓库只维护 `.env.example`。

## 维护注意

- 修改路径或目录结构时同步更新 README、AGENTS、manual_files 和测试。
- 编辑器包导出告警不等同于运行错误；以终端命令和 pytest 结果为准。
- 自动翻译失败时缺译句保留英文原文，出表不受影响；网络恢复后再次 `rebuild` 自动补齐。
- 历史资料和旧环境快照放在 `project_memory/archive/`，不与当前运行数据混放。
