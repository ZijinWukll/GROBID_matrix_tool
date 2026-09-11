# 科研矩阵表生长工具

把“种子论文 → GROBID 解析 → 引用上下文抽取 → 矩阵表”的流水线做成可重复重建的工具。每加入一篇种子论文，工具会重新抽取全部论文、合并去重、按总内部引用次数降序排序，并生成新的 xlsx。

## 快速开始

先激活本机的 conda/miniconda 环境，并在项目根目录执行：

```powershell
conda activate matrix
python matrix_tool.py status
python matrix_tool.py rebuild
```

根目录的 `matrix_tool.py` 是兼容入口，实际实现位于 `src/matrix_tool.py`。也可以使用脚本封装：

```powershell
.\scripts\matrix.ps1 status
.\scripts\matrix.ps1 rebuild
```

## 目录结构

```text
Grobid_Demo_Codes/
├── src/                  # Python 源码
├── tests/                # 冒烟测试、回归测试和冻结基线
├── scripts/              # PowerShell / Bash 命令封装
├── data/
│   ├── config/           # project.json 等配置
│   ├── state/            # TEI 缓存、论文 JSON 和译文池
│   ├── seed_papers/      # 种子论文 PDF 投放区
│   └── exports/          # xlsx 和未翻译清单等导出物
├── project_memory/       # 架构、决策、迁移记录
├── road_map/             # 路线图、时间线、待办池
├── manual_files/         # 操作、配置、排障和开发手册
├── log/                  # CHANGELOG 与按日运行日志
├── matrix_tool.py        # 兼容 CLI 入口
└── requirements*.txt     # 运行与开发依赖
```

## 核心约定

1. `data/state/papers/<KEY>.json` 是矩阵数据的唯一事实源；xlsx 只是导出物，永远不要手改。
2. `rebuild` 每次从 TEI 和状态文件重算整表；配置或译文改完统一运行 `rebuild`。
3. 译文按英文句子的 md5 前 8 位保存，英文原句不变则译文不会丢。
4. 配置中的文件路径按项目根目录解析，均使用 `data/...` 相对路径。
5. `data/config/` 与 `data/state/` 保持 UTF-8、相对路径和原子写入，方便未来纳入版本库。

## 本地数据与 Git

真实的 `data/config/*.json`、`data/state/`、`data/seed_papers/`、`data/exports/`、每日运行日志和 `tests/baselines/logical_rows.json` 都只保存在本机，默认不会提交到 Git。仓库只保留目录占位、`data/config/*.example.json` 示例和公开测试逻辑。

新环境可从示例配置开始：

```powershell
Copy-Item data/config/project.example.json data/config/project.json
Copy-Item data/config/abbrev_rules.example.json data/config/abbrev_rules.json
Copy-Item data/config/alias_mentions.example.json data/config/alias_mentions.json
Copy-Item data/config/display_title_fixes.example.json data/config/display_title_fixes.json
```

然后把本机文件按 `data/...` 相对路径放入对应目录。不要在配置、日志或文档中写入个人绝对路径。

## 常用命令

| 命令 | 作用 |
| --- | --- |
| `matrix_tool.py status` | 查看种子论文、行数、缺译与缺简写情况 |
| `matrix_tool.py add data/seed_papers/新论文.pdf` | 调用 GROBID 解析并加入新种子 |
| `matrix_tool.py add 新论文.pdf --from-tei 现成.tei.xml` | 离线加入论文 |
| `matrix_tool.py rebuild [--no-translate] [--window N]` | 全量重建及自动补译 |
| `matrix_tool.py export-untranslated` | 导出缺译清单 |
| `matrix_tool.py import-translations 文件.json` | 回填人工译文并重建 |
| `matrix_tool.py help [命令名]` | 查看项目专属中文帮助 |

详细说明见 [manual_files](manual_files/README.md)。架构和关键决策见 [project_memory](project_memory/README.md)，后续安排见 [road_map/roadmap.md](road_map/roadmap.md)。

## 测试

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

运行日志写入 `log/matrix_tool_YYYYMMDD.log`。日志为 JSON Lines，只记录命令、耗时、状态和异常摘要，不记录论文正文或整段译文。
