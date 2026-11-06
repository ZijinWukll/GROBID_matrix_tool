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
2. 不手工修改最终 xlsx；修正只进 `data/config/`、`data/state/` 或人工覆盖文件，然后运行 `build` 或离线 `export`。
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
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
# 编辑 .env 后，将 PDF 放入 data/seed_papers/，再运行：
python matrix_tool.py build
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

将 PDF 放入 `data/seed_papers/`，运行 `python matrix_tool.py build`。

- build 始终只扫描标准目录本层 PDF；有效 TEI 复用，无缓存、损坏或已知 PDF 变化时解析。没有哈希的旧缓存先复用，不因此强制联网。
- 移走 PDF 后旧论文退出矩阵，历史缓存不自动删除。build 不接受 --input-dir / --keep-existing。
- import 从外部复制 PDF，可带 --from-tei；只准备输入，不联网、不构建。已经手动放好 PDF 时不需要 import。
- export 只读最近 JSON 快照离线出表，不扫描 PDF、不抽取 TEI、不调用模型；可 --output 另存。
- status 只读当前输入与最近快照；cache 查看缓存，cache clean 默认预览，只有 --apply 才删除解析文件。
- cache clean --all --apply 包含当前解析文件；PDF、短名登记、译文池与人工覆盖始终保留，目标路径必须验证位于状态目录内。

```powershell
python matrix_tool.py import "下载目录/论文.pdf"
python matrix_tool.py import "论文.pdf" --from-tei "现成.tei.xml"
python matrix_tool.py build
python matrix_tool.py export
python matrix_tool.py cache clean
```

正常构建自动处理所有缺译，不再在 500 句截断；格式缺失/截断/标记丢失会有限补试，分类缩小批次。低置信候选自动检查一次，有分歧保留可选复核标记，不强行放行，不阻断出表。已检查过的残留不确定不每次反复请求。网络故障停止本轮连续请求、保存进度，服务恢复后 build 续跑。

build 支持 --no-llm、--no-translate、--relabel 和上下文窗口参数；--relabel 不能覆盖人工标签。人工标签与译文的导出/回填工具仅用于可选精修，导出只读快照，回填后仅离线刷新。

add 已兼容为 import，只导入；rebuild 已兼容为 export，仅离线出表；remove 退役，范围用 PDF 文件夹管理，清理用 cache。普通 init 创建空项目，旧三篇迁移用 init --migrate-legacy。

修改帮助系统时，同步维护 COMMANDS_HELP、COMMAND_GROUPS、HELP_QUICKSTART 和 tests/test_help.py。入口职责不得再次混合。

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

## 帮助与展示维护

README 保持快速上手；完整命令格式集中到 manual_files/commands.md，并与 COMMANDS_HELP 同步。构建输出五阶段，长任务约每十秒更新，错误即时显示。整理时仅删除生成的测试临时目录与 Python/pytest 缓存，保留测试源码、私有基线与研究缓存。
