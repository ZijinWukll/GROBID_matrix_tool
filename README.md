# 科研矩阵表生长工具

把种子论文持续整理成一张可重建的引用矩阵表：

`种子论文 → GROBID 解析 → 引用上下文抽取 → 关系标签 → 中文翻译 → xlsx`

将论文 PDF 放进 `data/seed_papers/`，运行 `python matrix_tool.py build`，即可批量解析并生成整张表。以后继续放入新论文，再运行同一个命令。

## 快速开始

### 1. 准备环境

```powershell
conda create -n matrix python=3.13  # 第一次新建
conda activate matrix
python -m pip install -r requirements.txt
```

第一次使用时复制并填写本地模型配置：

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

`.env` 示例：

```dotenv
MATRIX_GROBID_URL=http://your-grobid-host:8070
MATRIX_LLM_BASE_URL=http://your-llm-host:8900/v1
MATRIX_LLM_API_KEY=EMPTY
MATRIX_LLM_MODEL=your-model-id
```

`.env` 只保存在本机，不会进入 Git。

### 2. 放入 PDF，一条命令生成

将所有种子论文 PDF 放入 `data/seed_papers/`，然后运行：

```powershell
python matrix_tool.py build
```

首次会自动创建项目配置，无需先运行 `init`。需要解析 PDF 时，确保 `.env` 中的 GROBID 可达；学校服务通常需要校园网络或 VPN。关系标签与中文翻译使用 `.env` 中配置的模型。

程序只扫描文件夹本层的 `.pdf` / `.PDF`，按文件名顺序登记新增论文，保留已有列顺序。默认目录中的 PDF 保持原位；使用其他文件夹时，PDF 会复制到 `data/seed_papers/`。

习惯使用项目根目录的 `input/` 时，创建该文件夹、放入 PDF 后运行：

```powershell
python matrix_tool.py build --input-dir input
```

每次批量处理后只统一导出一次。PDF 内容未变且 TEI 缓存存在时跳过解析；旧记录没有 PDF 哈希时会重新解析一次。中文文件名可直接使用。移走 PDF 不会自动注销已登记论文。

解析失败会显示具体文件，保存成功论文，并在有已登记论文时导出可用结果，同时以失败状态结束；修复问题后重跑同一命令即可续跑。空目录且没有已登记论文时只提示放入 PDF，不生成空表。

完成后打开 `data/exports/科研矩阵表_AgentMemory.xlsx`。查看状态：

```powershell
python matrix_tool.py status
```

### 3. 按需使用单篇或离线入口

需要校园 VPN 连接 GROBID：

```powershell
python matrix_tool.py add data/seed_papers/新论文.pdf
```

无 VPN 时使用现成 TEI（首次同样会自动创建配置）：

```powershell
python matrix_tool.py add data/seed_papers/新论文.pdf --from-tei 现成.tei.xml
```

### 4. 修改配置后重建

```powershell
python matrix_tool.py rebuild
```

`rebuild` 只处理已登记论文的 TEI，不扫描新 PDF、不调用 GROBID。重建流程：抽取 → 关系标签 → 翻译 → 写出 xlsx。只处理新增或缓存失效的标签和译文。

只想提前创建空项目时可运行 `python matrix_tool.py init`，无需旧论文或网络。已有项目补齐缺失配置使用 `init --force`，保留已有配置、人工规则和论文；早期三篇种子的数据迁移仍可通过 `init --migrate-legacy` 使用，详见[日常操作](manual_files/operations.md)。

## 关系标签复核

关系标签用于快速判断“列对应论文”如何使用“行对应被引论文”：

| 标签                 | 含义                                     |
| -------------------- | ---------------------------------------- |
| `B&E` 基于与拓展     | 基于、扩展、应用、受启发于或推广被引论文 |
| `S&S` 支持与补充     | 引用、复用、补充或间接支持               |
| `C&A` 对比与替代     | 比较、替代或从不同角度总结               |
| `Q&A` 质疑与反驳     | 质疑、纠正或反驳                         |
| `M/I` 简单提及或无关 | 仅提及或几乎无直接关系                   |

默认复核流程：

```powershell
python matrix_tool.py export-labels
python matrix_tool.py import-labels data/exports/relation_labels_时间戳.xlsx
```

打开复核表后，只修改“人工标签”列：

- 标签正确：留空，不需要操作。
- 标签错误：从下拉框选择正确标签。
- 清除已有覆盖：选择“自动”。

默认只导出 `needs_review=true` 的单元格。需要查看全部标签时使用：

```powershell
python matrix_tool.py export-labels --all
```

最终矩阵表位于 `data/exports/科研矩阵表_AgentMemory.xlsx`。不要直接编辑最终 xlsx，所有修正都应进入配置、标签覆盖或译文池后重新 rebuild。

## 常用命令

| 命令                                                  | 作用                                       |
| ----------------------------------------------------- | ------------------------------------------ |
| `python matrix_tool.py build`                         | 扫描默认 PDF 文件夹并一键生成；首次自动初始化 |
| `python matrix_tool.py build --input-dir input`        | 从指定文件夹批量导入并生成 |
| `python matrix_tool.py status`                        | 查看论文、行数、缺译、缺简写和标签复核状态 |
| `python matrix_tool.py add data/seed_papers/文件.pdf` | 添加种子论文并重建                         |
| `python matrix_tool.py rebuild`                       | 重新分类、翻译并生成 xlsx                  |
| `python matrix_tool.py rebuild --relabel`             | 强制重新分类全部非人工标签                 |
| `python matrix_tool.py init [--force]`                | 创建空项目；已有项目仅补齐缺失配置 |
| `python matrix_tool.py export-labels [--all]`         | 导出关系标签复核表                         |
| `python matrix_tool.py import-labels 文件.xlsx`       | 回填人工标签并重建                         |
| `python matrix_tool.py export-untranslated`           | 导出缺译句子                               |
| `python matrix_tool.py import-translations 文件.json` | 回填人工译文并重建                         |
| `python matrix_tool.py help [命令名]`                 | 查看中文帮助                               |

`build`、`add` 和 `rebuild` 均支持 `--no-translate`，只跳过本轮自动翻译，关系标签仍按配置执行。

## 目录结构

```text
Grobid_Demo_Codes/
├── matrix_tool.py            # 兼容 CLI 入口
├── src/                      # Python 实现
├── tests/                    # 冒烟、回归和标签测试
├── scripts/                  # PowerShell / Bash 封装
├── data/
│   ├── config/               # 本地配置、规则和人工覆盖
│   ├── state/                # TEI、抽取 JSON、译文池和标签缓存
│   ├── seed_papers/          # 种子论文 PDF
│   └── exports/              # xlsx、复核表和缺译清单
├── project_memory/           # 架构、决策、迁移记录
├── road_map/                 # 路线图、时间线和待办
├── manual_files/             # 操作、配置、排障和开发手册
├── log/                      # CHANGELOG 与按日运行日志
└── README.md
```

## 核心约定

1. `data/state/papers/<KEY>.json` 是矩阵数据的唯一事实源。
2. `data/exports/` 下的 xlsx 是导出物，可以随时重新生成。
3. 译文按英文句子的 md5 前 8 位缓存，原文不变则译文不会丢。
4. 关系标签按 `<row_id>|<paper_key>` 和引用段内容哈希缓存。
5. 人工标签和人工译文优先于自动结果。
6. GROBID 和本地 LLM 地址统一放在 `.env`，脚本和示例配置不保存学校真实地址。
7. `data/config/`、`data/state/`、`data/seed_papers/`、`data/exports/`、`.env` 和运行日志默认不提交 Git。

## 文档导航

- [日常操作](manual_files/operations.md)
- [配置说明](manual_files/configuration.md)
- [故障排查](manual_files/troubleshooting.md)
- [开发与测试](manual_files/development.md)
- [项目架构](project_memory/architecture.md)
- [关键决策](project_memory/decisions.md)
