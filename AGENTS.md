# AGENTS.md

请使用中文回答所有问题和交流，包括代码解释、错误提示、操作建议和提交说明。

---

# 项目维护说明

## 项目定位

科研矩阵表生长工具把种子论文持续整理成可重建的引用矩阵表：

`PDF/TEI → GROBID → 引用上下文 → 关系标签 → 中文翻译 → xlsx`

根目录 `matrix_tool.py` 是兼容 CLI 入口，核心实现在 `src/matrix_tool.py`。抽取、合并、排序和渲染核心尽量保持纯函数；CLI 层负责参数、网络、文件 I/O 和日志。

## 必须遵守

1. `data/state/papers/<KEY>.json` 是矩阵数据的事实源，`data/exports/` 中的 xlsx 只是导出物。
2. 不手工修改最终 xlsx；修正只进 `data/config/`、`data/state/` 或人工覆盖文件，然后运行 `rebuild`。
3. 译文按英文句子 md5 前 8 位缓存；关系标签按 `row_id|paper_key` 和引用段内容哈希缓存。
4. 人工标签、人工译文优先级最高，不能被自动结果覆盖。
5. `.env`、密钥、证书、真实研究数据、标签缓存、回归基线和运行日志不进入 Git。
6. 修改代码、配置、状态或文档后，至少运行 `python matrix_tool.py status` 和 `python -m pytest -q`。

## 目录结构

```text
Grobid_Demo_Codes/
├── matrix_tool.py                  # 兼容入口
├── src/
│   ├── matrix_tool.py              # 核心实现
│   └── util_get_current_time.py
├── tests/
│   ├── test_smoke.py
│   ├── test_regression.py
│   ├── test_translation_llm.py
│   ├── test_relation_labels.py
│   └── test_help.py
├── scripts/                        # PS1 / Bash 薄封装
├── data/
│   ├── config/                     # 本地配置、规则、人工标签覆盖
│   ├── state/                      # TEI、抽取 JSON、译文池、标签缓存
│   ├── seed_papers/                # 种子 PDF
│   └── exports/                    # xlsx、标签复核表、缺译清单
├── manual_files/                   # 操作、配置、排障、开发手册
├── project_memory/                 # 架构、决策、迁移记录
├── road_map/                       # 路线图、时间线、待办
├── log/                            # CHANGELOG + 按日日志
└── README.md
```

## 首次配置

```powershell
conda activate matrix
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python matrix_tool.py status
```

`.env` 使用以下变量，源码中不得硬编码真实值：

```dotenv
MATRIX_GROBID_URL=http://your-grobid-host:8070
MATRIX_LLM_BASE_URL=http://your-llm-host:8900/v1
MATRIX_LLM_API_KEY=EMPTY
MATRIX_LLM_MODEL=your-model-id
```

GROBID 地址只从 `MATRIX_GROBID_URL` 读取；旧配置中的 `grobid_url` 仅作为兼容回落，不再是标准入口。

## 标准工作流

### 加论文

```powershell
python matrix_tool.py add data/seed_papers/新论文.pdf
python matrix_tool.py add data/seed_papers/新论文.pdf --from-tei 现成.tei.xml
```

### 重建

```powershell
python matrix_tool.py rebuild
python matrix_tool.py rebuild --no-translate
python matrix_tool.py rebuild --relabel
```

重建顺序固定为：抽取 → 合并排序 → 关系标签 → 自动翻译 → 写 xlsx。`--relabel` 只强制重算非人工标签，人工覆盖保留。

### 标签复核

```powershell
python matrix_tool.py export-labels
python matrix_tool.py import-labels data/exports/relation_labels_时间戳.xlsx
```

默认只导出待复核项；全部导出使用 `export-labels --all`。人工只需编辑“人工标签”列：留空不修改，选择“自动”清除覆盖，其他值覆盖自动标签。

### 译文维护

```powershell
python matrix_tool.py export-untranslated
python matrix_tool.py import-translations data/exports/untranslated_时间戳.json
```

## 命令速查

| 命令 | 作用 |
| --- | --- |
| `status` | 查看论文、行数、缺译、缺简写、标签复核状态 |
| `add` | 加论文并自动完成标签、翻译、重建 |
| `rebuild` | 全量增量重建；支持 `--relabel`、`--no-translate` |
| `export-labels [--all]` | 导出标签复核表 |
| `import-labels 文件.xlsx` | 导入人工标签并重建 |
| `export-untranslated` | 导出缺译句子 |
| `import-translations 文件.json` | 回填人工译文并重建 |
| `remove KEY` | 注销种子论文并重建 |
| `init [--force]` | 首次迁移或重置 |
| `help [命令名]` | 查看快速上手、命令分组或单命令详情 |

修改帮助系统时，同步维护 `COMMANDS_HELP`、`COMMAND_GROUPS`、`HELP_QUICKSTART` 和 `tests/test_help.py`。

## 配置修正入口

| 目标 | 文件 |
| --- | --- |
| 论文顺序、表头、路径、模型参数 | `data/config/project.json` |
| 方法简写 | `data/config/abbrev_rules.json` |
| 漏标引用提及 | `data/config/alias_mentions.json` |
| 标题显示修复 | `data/config/display_title_fixes.json` |
| 人工关系标签 | `data/config/relation_label_overrides.json`，优先通过 `import-labels` 修改 |

`alias_mentions.json` 改变次数和上下文；`abbrev_rules.json` 只改变方法简写显示，二者不要混淆。

## 测试与日志

```powershell
python -m pytest -q
```

- 回归基线为 `tests/baselines/logical_rows.json`，由本机数据生成，不提交 Git。
- 缺少私有基线时，相关测试自动跳过。
- 运行日志写入 `log/matrix_tool_YYYYMMDD.log`，使用 JSON Lines，不记录论文正文、引用段或译文。
- `log/CHANGELOG.md` 记录需要提交的版本变化。

## 发布与隐私

- 提交前运行 `git status --short` 和 `git diff --cached --stat`。
- 不要使用 `git add -f` 添加被忽略的本地数据。
- 公开仓库只应包含源码、测试、文档、目录占位、脱敏示例配置和 `requirements*.txt`。
- 真实 `.env`、PDF、TEI、抽取状态、译文池、标签缓存、人工覆盖、导出物、日志和本机归档均不提交。
