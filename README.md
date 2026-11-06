# 科研矩阵表生长工具

把种子论文整理成可持续更新的引用矩阵：

`PDF → GROBID / TEI 缓存 → 引用上下文 → 自动关系标签 → 中文翻译 → xlsx`

## 日常只需一个命令

1. 将论文 PDF 放入 `data/seed_papers/`。
2. 在项目根目录运行：

```powershell
python matrix_tool.py build
```

3. 打开 `data/exports/科研矩阵表_AgentMemory.xlsx`。

以后添加、替换或移走论文，都修改这个 PDF 文件夹，再运行同一条命令。

`build` 始终只扫描 `data/seed_papers/` 本层的 PDF（扩展名不区分大小写）。目录外论文和历史缓存不会自动混进矩阵，取消了 `--input-dir` 和 `--keep-existing`。

有效 TEI 缓存直接复用；没有缓存、缓存损坏或已知 PDF 内容变化时重新解析。旧缓存缺少 PDF 哈希时先复用并补齐哈希。移走 PDF 只改变矩阵范围，不删除缓存。放回同一论文可继续复用。

## 首次准备

```powershell
conda create -n matrix python=3.13
conda activate matrix
python -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

编辑 `.env`，填写可用连接：

```dotenv
MATRIX_GROBID_URL=http://your-grobid-host:8070
MATRIX_LLM_BASE_URL=http://your-llm-host:8900/v1
MATRIX_LLM_API_KEY=EMPTY
MATRIX_LLM_MODEL=your-model-id
```

校园服务通常需要校园网络或 VPN。配置只保存在本机；`build` 会自动初始化项目，无需先 `init`。

## 不同命令各做什么

- `build`：日常完整自动构建。同步 PDF 范围，抽取、补标签、补译、生成 Excel。
- `import`：从下载目录复制 PDF 到标准目录，可带已有 TEI；只导入，不构建、不调用服务。已经手动放好 PDF 就不需要它。
- `export`：从最近一次构建的 JSON 快照离线生成 Excel，不扫描 PDF、不读 TEI、不调用模型。适合恢复丢失的 Excel、另存文件或更新标题/简写显示。
- `status`：只读查看当前输入和最近构建结果。
- `cache`：查看缓存，或由用户明确执行清理。

```powershell
python matrix_tool.py import "下载目录/论文.pdf"
python matrix_tool.py import "下载目录/论文文件夹"
python matrix_tool.py import "论文.pdf" --from-tei "现成.tei.xml"
python matrix_tool.py build
python matrix_tool.py export --output "data/exports/矩阵副本.xlsx"
python matrix_tool.py status
```

`add` 保留为 `import` 的兼容入口，已不再单篇构建；`rebuild` 保留为 `export` 的兼容入口。`remove` 退役：移走 PDF 再 `build` 即可退出矩阵。

## 自动处理与中断恢复

正常流程无需手动补译、分类或审核：

- 缺失/截断的分类输出会缩小批次并有限补试；使用短请求编号，减少长论文标识造成的格式问题。
- 低置信或缺少依据的标签自动检查一次；分歧仍保留不确定标记，不强行制造确定结论，不阻断出表。
- 翻译覆盖所有缺译句子，不再处理 500 句后要求手动重跑；空回复、输出截断或丢失引用标记会扩大预算后有限补试。
- 成功分类逐批保存，译文按检查点及结束/中断保存；再次 `build` 只补未完成部分。
- 连接失败时停止本轮后续模型请求，保留成功结果，以“待分类”和英文继续出表。服务恢复后再运行 `build`。

自动检查是模型辅助处理，不等于独立人工验证；保留的不确定标记仅供可选复核。不会用降低阈值或伪造译文的方式凑齐结果。

临时只需要表格时：

```powershell
python matrix_tool.py build --no-llm
```

该选项跳过分类与翻译，但新 PDF 仍需 GROBID。`export` 才是完全离线的快照导出。`--no-translate` 仅跳过翻译；`build --relabel` 强制重算非人工标签；上下文可用 `build --window 3`。

## 缓存只手动清理

```powershell
python matrix_tool.py cache
python matrix_tool.py cache clean
python matrix_tool.py cache clean --apply
python matrix_tool.py cache clean --all --apply
```

`clean` 默认仅预览不再使用、且 PDF 已移走的历史解析文件，`--apply` 才删除。`--all` 包含当前使用的解析文件，下次 `build` 会重建。PDF、论文短名登记、译文池和人工覆盖均保留。

## 可选精修工具

这些命令不是日常构建的必经步骤：

```powershell
python matrix_tool.py export-labels
python matrix_tool.py import-labels "标签复核表.xlsx"
python matrix_tool.py export-untranslated
python matrix_tool.py import-translations "译文.json"
```

导出只读最近快照；回填人工结果后仅离线刷新表格，不触发额外模型请求。人工标签与译文优先，自动过程不能覆盖。最终 Excel 是导出物，不能直接手改。

## 开发与文档

```powershell
python matrix_tool.py status
python -m pytest -q
```

核心在 `src/matrix_tool.py`，根目录 `matrix_tool.py` 是兼容入口。配置、状态、PDF 和导出物分别位于 `data/config/`、`data/state/`、`data/seed_papers/`、`data/exports/`。

真实配置、密钥、论文、TEI、译文池、人工覆盖、运行日志和私有回归基线不进入 Git。

- [日常操作](manual_files/operations.md)
- [配置说明](manual_files/configuration.md)
- [故障排查](manual_files/troubleshooting.md)
- [架构](project_memory/architecture.md)
- [本次设计](project_memory/design_20261106.md)
