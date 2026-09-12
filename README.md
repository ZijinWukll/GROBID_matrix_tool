# 科研矩阵表生长工具

把种子论文持续整理成一张可重建的引用矩阵表：

`种子论文 → GROBID 解析 → 引用上下文抽取 → 关系标签 → 中文翻译 → xlsx`

每加入一篇种子论文，工具会重新抽取、合并、去重、分类和翻译，并按总内部引用次数降序重建整张表。

## 快速开始

### 1. 准备环境

```powershell
conda create -n matrix python=3.13 （第一次新建）
conda activate matrix
python -m pip install -r requirements.txt
```

第一次使用时复制并填写本地模型配置：

```powershell
Copy-Item .env.example .env
```

`.env` 示例：

```dotenv
MATRIX_LLM_BASE_URL=http://your-llm-host:8900/v1
MATRIX_LLM_API_KEY=EMPTY
MATRIX_LLM_MODEL=your-model-id
```

`.env` 只保存在本机，不会进入 Git。

### 2. 查看当前状态

```powershell
python matrix_tool.py status
```

### 3. 加入一篇论文

需要校园 VPN 连接 GROBID：

```powershell
python matrix_tool.py add data/seed_papers/新论文.pdf
```

无 VPN 时使用现成 TEI：

```powershell
python matrix_tool.py add data/seed_papers/新论文.pdf --from-tei 现成.tei.xml
```

### 4. 修改配置后重建

```powershell
python matrix_tool.py rebuild
```

重建流程：抽取 → 关系标签 → 翻译 → 写出 xlsx。只处理新增或缓存失效的标签和译文。

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
| `python matrix_tool.py status`                        | 查看论文、行数、缺译、缺简写和标签复核状态 |
| `python matrix_tool.py add data/seed_papers/文件.pdf` | 添加种子论文并重建                         |
| `python matrix_tool.py rebuild`                       | 重新分类、翻译并生成 xlsx                  |
| `python matrix_tool.py rebuild --relabel`             | 强制重新分类全部非人工标签                 |
| `python matrix_tool.py export-labels [--all]`         | 导出关系标签复核表                         |
| `python matrix_tool.py import-labels 文件.xlsx`       | 回填人工标签并重建                         |
| `python matrix_tool.py export-untranslated`           | 导出缺译句子                               |
| `python matrix_tool.py import-translations 文件.json` | 回填人工译文并重建                         |
| `python matrix_tool.py help [命令名]`                 | 查看中文帮助                               |

`--no-translate` 可跳过本轮自动翻译。

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
6. `data/config/`、`data/state/`、`data/seed_papers/`、`data/exports/`、`.env` 和运行日志默认不提交 Git。

## 文档导航

- [日常操作](manual_files/operations.md)
- [配置说明](manual_files/configuration.md)
- [故障排查](manual_files/troubleshooting.md)
- [开发与测试](manual_files/development.md)
- [项目架构](project_memory/architecture.md)
- [关键决策](project_memory/decisions.md)
